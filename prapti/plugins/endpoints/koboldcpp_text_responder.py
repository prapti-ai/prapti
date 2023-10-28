"""
    Koboldcpp text completions responder plugin.

    Targetting the text generation subset of the kobold API supported by koboldcpp

    Kobold API reference: https://petstore.swagger.io/?url=https://lite.koboldai.net/kobold_api.json#/generate/post_generate

    Koboldcpp:  https://github.com/LostRuins/koboldcpp
                https://github.com/LostRuins/koboldcpp/blob/concedo/koboldcpp.py
"""
import datetime
from typing import Literal, AsyncGenerator, Any
import json
import asyncio
from contextlib import suppress

import aiohttp
from pydantic import BaseModel, ConfigDict, Field
from cancel_token import CancellationToken

from ...core.plugin import Plugin, PluginCapabilities, PluginContext
from ...core.command_message import Message
from ...core.configuration import VarRef, resolve_var_refs
from ...core.responder import Responder, ResponderContext
from ...core.logger import DiagnosticsLogger

class KoboldcppResponderConfiguration(BaseModel):
    """Configuration parameters for koboldcpp responder."""
    model_config = ConfigDict(
        validate_assignment=True)

    api_base: str = "http://localhost:5001/api/v1"  # "api_format 2" in koboldcpp

    max_context_length: int|None = None
    max_length: int = 50
    temperature: float = 0.8
    top_k: int = 120
    top_a: float = 0.0
    top_p: float = 0.85
    typical_p: float = 1.0 # `typical` in the koboldcpp API
    tfs: float = 1.0
    rep_pen: float = 1.1
    rep_pen_range: int = 128
    mirostat: Literal[0, 1, 2] = 0
    mirostat_tau: float = 5.0
    mirostat_eta: float = 0.1
    sampler_order: list[int] = Field(default_factory=lambda: list([6,0,1,3,4,2,5])) # max len sampler_order_max
    seed: int = -1
    stop_sequence: list[str] = Field(default_factory=list) # max len stop_token_max
    stream: bool = True

    # TODO:
    # n -- number of generated responses

def convert_message_sequence_to_text_prompt(message_sequence: list[Message], log: DiagnosticsLogger) -> str:
    result = ""
    for message in message_sequence:
        if not message.is_enabled or message.is_hidden:
            continue # skip disabled and hidden messages

        if message.role == "prompt":
            assert len(message.content) == 1 and isinstance(message.content[0], str), "internal error. expected flattened message content"
            result += message.content[0]
        elif message.role in ("user", "assistant"):
            log.warning("unsupported-chat-role", f"message will not be included in LLM prompt. role '{message.role}' is not supported. use '### @prompt:'.", message.source_loc)
        else:
            log.warning("unrecognised-public-role", f"message will not be included in LLM prompt. public role '{message.role}' is not recognised.", message.source_loc)
            continue

    return result


def _rstrip_eol(line: str) -> str:
    # as per the server-sent-events spec: "Lines must be separated by either a U+000D CARRIAGE RETURN U+000A LINE FEED (CRLF)
    # character pair, a single U+000A LINE FEED (LF) character, or a single U+000D CARRIAGE RETURN (CR) character."
    # we strip any valid line ending from the end of /line/
    if line.endswith("\r\n"):
        return line[:-2]
    elif line.endswith("\n") or line.endswith("\r"):
        return line[:-1]
    return line

async def _generate_async_content(session: aiohttp.ClientSession, response: aiohttp.ClientResponse, cancellation_token: CancellationToken) -> AsyncGenerator[str, None]:
    """process server sent events as they are received, yielding the string data contained in the json payloads, e.g.:

        b'event: message\n'
        b'data: {"token": " last"}\n'
        b'\n'
        b'event: message\n'
        b'data: {"token": " few"}\n'
        b'\n'
        b'event: message\n'
        b'data: {"token": " months"}\n'
        b'\n'
    """
    # https://blog.axway.com/learning-center/apis/api-streaming/server-sent-events
    # https://www.w3.org/TR/2012/WD-eventsource-20120426/
    # REVIEW: consider using https://pypi.org/project/aiohttp-sse-client2/ instead of rolling our own
    # note that koboldcpp returns the full json completion response after the server sent events,
    # not sure that is conformant, not sure whether that will play nice with aiohttp-sse-client2

    try:
        event_name, data = "message", "" # default init/reset

        async for bline in response.content:
            line = _rstrip_eol(bline.decode(encoding="utf-8"))
            if not line:
                # dispatch the message
                if event_name == "message" and data:
                    try:
                        json_data = json.loads(data)
                        if "token" in json_data:
                            yield json_data["token"]
                    except ValueError:
                        pass
                event_name, data = "message", "" # default init/reset
                continue
            elif line.startswith(":"):
                continue # ignore comment lines
            elif ":" in line:
                field,value = line.split(":", maxsplit=1)
                if value.startswith(" "):
                    value = value[1:]
            else:
                field = line
                value = ""

            match field:
                case "event":
                    event_name = value
                case "data":
                    data += value
                    data += "\n"
                case "id":
                    pass # not needed, not implemented
                case "retry":
                    pass # not needed, not implemented
                case _:
                    pass # ignore unknown fields as specified
    except aiohttp.ClientConnectionError:
        # eat connection error if the stream has been cancelled, it's probably a result of our
        # closing the connection and even if it isn't we can reasonably treat the error as-if cancelled.
        if not cancellation_token.cancelled:
            raise
    finally:
        await session.close()

async def _get_streaming_response(api_base: str, prompt: str, generate_args: dict[str, Any], timeout: float, cancellation_token: CancellationToken) -> Message:
    route = api_base.replace("/api/v1", "/api/extra") + "/generate/stream"
    # NOTE: we can not use context managers (`async with`) here, because we need the session to
    # remain active until async content streaming completes in _generate_async_content() completes
    session = aiohttp.ClientSession()
    try:
        cancellation_token.on_cancel(lambda: _discard_arg(asyncio.create_task(session.close())))
        response = await session.post(route, json={"prompt": prompt, **generate_args}, timeout=timeout)
        return Message(role="completion", name=None, content=[], async_content=_generate_async_content(session, response, cancellation_token))
        # ^^^ NOTE: _generate_async_content consumes `session` and is responsible for closing `session`.
    except (Exception, asyncio.CancelledError):
        await session.close()
        raise

async def _get_non_streaming_response(api_base: str, prompt: str, generate_args: dict[str, Any], timeout: float) -> Message:
    route = f"{api_base}/generate"
    async with aiohttp.ClientSession() as session:
        async with session.post(route, json={"prompt": prompt, **generate_args}, timeout=timeout) as response:
            response_json = await response.json()
            response_text = response_json["results"][0]["text"]
            return Message(role="completion", name=None, content=[response_text], async_content=None)

def _discard_arg(arg: Any) -> None:
    return None

class KoboldcppResponder(Responder):
    def construct_configuration(self, context: ResponderContext) -> BaseModel|tuple[BaseModel, list[tuple[str,VarRef]]]|None:
        return KoboldcppResponderConfiguration(), [
            ("temperature", VarRef("temperature")),
            ("stream", VarRef("stream"))]

    async def _async_response_generator(self, input_: list[Message], cancellation_token: CancellationToken, context: ResponderContext) -> AsyncGenerator[Message, None]:
        config: KoboldcppResponderConfiguration = context.responder_config
        context.log.debug(f"input: {config = }", context.state.input_file_path)
        config = resolve_var_refs(config, context.root_config, context.log)
        context.log.debug(f"resolved: {config = }", context.state.input_file_path)

        prompt = convert_message_sequence_to_text_prompt(input_, context.log)
        if not prompt:
            context.log.error("can't generate completion. prompt is empty.")
            return

        if context.root_config.prapti.dry_run:
            context.log.info("koboldcpp-text-dry-run", "dry run: halting before calling the Kobold API", context.state.input_file_path)
            current_time = str(datetime.datetime.now())
            yield Message(role="assistant", name=None, content=[f"dry run mode. {current_time}\nconfig = {json.dumps(config.model_dump())}"])
            return

        generate_args = config.model_dump(exclude_none=True, exclude_defaults=True)
        context.log.debug(f"{generate_args = }")

        if cancellation_token.cancelled:
            return
        try:
            timeout = 1000 # TODO: expose timeout in config

            if config.stream:
                task = asyncio.create_task(_get_streaming_response(config.api_base, prompt, generate_args, timeout, cancellation_token))
                cancellation_token.on_cancel(lambda: _discard_arg(task.cancel()))
                with suppress(asyncio.CancelledError):
                    yield await task
                    # NOTE: fall through and return here even though the async content may still be streaming
                    # this is not required behavior, it is one allowed behavior
            else:
                task = asyncio.create_task(_get_non_streaming_response(config.api_base, prompt, generate_args, timeout))
                cancellation_token.on_cancel(lambda: _discard_arg(task.cancel()))
                with suppress(asyncio.CancelledError):
                    yield await task

        except Exception as ex:
            context.log.error("koboldcpp-text-api-exception", f"exception while requesting a response from koboldcpp: {repr(ex)}", context.state.input_file_path)
            context.log.debug_exception(ex)

    def generate_responses(self, input_: list[Message], cancellation_token: CancellationToken, context: ResponderContext) -> AsyncGenerator[Message, None]:
        return self._async_response_generator(input_, cancellation_token, context)

class KoboldcppResponderPlugin(Plugin):
    def __init__(self):
        super().__init__(
            api_version = "1.0.0",
            name = "koboldcpp.text",
            version = "0.0.2",
            description = "Responder using the Koboldcpp text completions API",
            capabilities = PluginCapabilities.RESPONDER
        )

    def construct_responder(self, context: PluginContext) -> Responder|None:
        return KoboldcppResponder()

prapti_plugin = KoboldcppResponderPlugin()
