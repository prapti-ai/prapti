"""
    Generate responses using the OpenAI chat API
"""
import os
import datetime
import inspect
import json
import copy
from enum import Enum
from typing import AsyncGenerator, Any
import asyncio
from contextlib import suppress

from pydantic import BaseModel, Field, ConfigDict
from cancel_token import CancellationToken
import openai
import tiktoken

from . import openai_globals # ensure openai globals are saved, no matter which module is loaded first
from ...core.plugin import Plugin, PluginCapabilities, PluginContext
from ...core.command_message import Message
from ...core.configuration import VarRef, resolve_var_refs
from ...core.responder import Responder, ResponderContext
from ...core.logger import DiagnosticsLogger

# openai chat API docs:
# https://platform.openai.com/docs/guides/chat/introduction
# basic example:
# https://gist.github.com/pszemraj/c643cfe422d3769fd13b97729cf517c5

# api key --------------------------------------------------------------------

# NOTE: we do not want to allow the user to store secrets in files that could easily be leaked.
# therefore we do not support specifying the API key in the configuration space
# i.e. we do not allow secrets to be set in input markdown or in our config files.

def load_api_key_and_organization() -> openai_globals.OpenAIGlobals:
    """Load OpenAI API key and organization from environment variables"""

    result = copy.copy(openai_globals.saved_openai_globals)

    # first check Prapti-specific environment variables,
    # then fall-back to OpenAI standard varaiables.
    # put your API key in the OPENAI_API_KEY environment variable, see:
    # https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety

    result.api_key = os.environ.get("PRAPTI_OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", None))
    result.organization = os.environ.get("PRAPTI_OPENAI_ORGANIZATION", os.environ.get("OPENAI_ORGANIZATION", None))

    if result.api_key is None:
        raise ValueError("OpenAI API key not set in environment variable.")

    return result

# chat API parameters --------------------------------------------------------

class OpenAIChatResponderConfiguration(BaseModel):
    """Configuration parameters for the OpenAI chat responder.
    See the [OpenAI chat completions documentation](https://platform.openai.com/docs/api-reference/chat/create) for more information."""
    model_config = ConfigDict(
        validate_assignment=True,
        protected_namespaces=()) # pydantic config: suppress warnings about `model` prefixed names

    model: str = Field(default="gpt-3.5-turbo", description=inspect.cleandoc("""\
        ID of the model to use. See the [model endpoint compatibility](https://platform.openai.com/docs/models/model-endpoint-compatibility)
        table for details on which models work with the Chat API."""))

    # messages: list|None = None (not available in configuration, injected by the responder)

    temperature: float = Field(default=1.0, description=inspect.cleandoc("""\
        What sampling temperature to use, between 0 and 2. Higher values like 0.8 will
        make the output more random, while lower values like 0.2 will make it more focused and deterministic.

        We generally recommend altering this or `top_p` but not both."""))

    top_p: float = Field(default=1.0, description=inspect.cleandoc("""\
        An alternative to sampling with temperature, called nucleus sampling,
        where the model considers the results of the tokens with top_p probability mass.
        So 0.1 means only the tokens comprising the top 10% probability mass are considered.

        We generally recommend altering this or `temperature` but not both."""))

    n: int = Field(default=1, description=inspect.cleandoc("""\
        How many chat completion choices to generate for each input message."""))

    stream: bool = Field(default=False, description=inspect.cleandoc("""\
        If set, partial message fragments will be returned progressively as they are generated."""))

    stop: str|list[str]|None = Field(default=None, description=inspect.cleandoc("""\
        Up to 4 sequences where the API will stop generating further tokens."""))

    max_tokens: int|None = Field(default=None, description=inspect.cleandoc("""\
        The maximum number of tokens to generate in the chat completion.

        The total length of input tokens and generated tokens is limited by the model's context length.
        (GPT 3.5 Turbo max context: 4096 tokens)

        When `max_tokens` is set to `null` no limit will be placed on the number of generated tokens,
        except for that imposed by the model's context length."""))

    presence_penalty: float = Field(default=0.0, description=inspect.cleandoc("""\
        Number between -2.0 and 2.0. Positive values penalize new tokens based on whether they appear in the text so far,
        increasing the model's likelihood to talk about new topics."""))

    frequency_penalty: float = Field(default=0.0, description=inspect.cleandoc("""\
        Number between -2.0 and 2.0. Positive values penalize new tokens based on their existing frequency in the text so far,
        decreasing the model's likelihood to repeat the same line verbatim."""))

    # logit_bias (not currently supported)
    # probably want to allow a dict[str,float] with the str causing a lookup to the token id, which is what the api expects

    user: str|None = Field(default=None, description=inspect.cleandoc("""\
        A unique identifier representing your end-user, which can help OpenAI to monitor and detect abuse."""))

# count tokens ---------------------------------------------------------------

# num_tokens_from_messages taken verbatim from:
# https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
# NOTE: does not estimate correctly if the functions API is being used.
def num_tokens_from_messages(messages, model: str, log: DiagnosticsLogger) -> int:
    """Return the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        log.warning("openai.chat-tiktoken-module-not-found", f"openal.chat.responder: num_tokens_from_messages: model '{model}' not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    if model in {
        "gpt-3.5-turbo-0613",
        "gpt-3.5-turbo-16k-0613",
        "gpt-4-0314",
        "gpt-4-32k-0314",
        "gpt-4-0613",
        "gpt-4-32k-0613",
        }:
        tokens_per_message = 3
        tokens_per_name = 1
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif "gpt-3.5-turbo" in model:
        log.warning("openai.chat-tiktoken-gpt-3.5-turbo-guess", "openal.chat: num_tokens_from_messages: gpt-3.5-turbo may update over time. Returning num tokens assuming gpt-3.5-turbo-0613.")
        return num_tokens_from_messages(messages, model="gpt-3.5-turbo-0613", log=log)
    elif "gpt-4" in model:
        log.warning("openai.chat-tiktoken-gpt-4-guess", "openal.chat: num_tokens_from_messages: gpt-4 may update over time. Returning num tokens assuming gpt-4-0613.")
        return num_tokens_from_messages(messages, model="gpt-4-0613", log=log)
    else:
        raise NotImplementedError(
            f"""num_tokens_from_messages() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens."""
        )
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens

def get_model_token_limit(model: str) -> int:
    # see: https://platform.openai.com/docs/models/overview
    result = 0
    if model.startswith("gpt-3.5"):
        result = 4096
    elif model.startswith("gpt-4"):
        result = 8192

    if "-8k" in model:
        result = 8192
    elif "-16k" in model:
        result = 16384
    elif "-32k" in model:
        result = 32768

    if result == 0:
        raise ValueError(f"Could not determine token limit for model '{model}'")
    return result

# ----------------------------------------------------------------------------

def convert_message_sequence_to_openai_messages(message_sequence: list[Message], log: DiagnosticsLogger) -> list[dict]:
    result = []
    for message in message_sequence:
        if not message.is_enabled or message.is_hidden:
            continue # skip disabled and hidden messages

        if message.role not in ["system", "user", "assistant"]:
            log.warning("unrecognised-public-role", f"message will not be included in LLM prompt. public role '{message.role}' is not recognised.", message.source_loc)
            continue

        assert len(message.content) == 1 and isinstance(message.content[0], str), "openai.chat: expected flattened message content"
        m = {
            "role": message.role,
            "content": message.content[0]
        }

        if message.name: # only include name field if a name was specified
            # NOTE: as of July 1 2023, this seems to only get passed to the LLM for system and user messages
            m["name"] = message.name

        result.append(m)
    return result

class QueueSentinel(Enum):
    END_OF_RESPONSE = 0

async def _cancel_async_generator(agen: AsyncGenerator) -> None:
    # https://stackoverflow.com/questions/60226557/how-to-forcefully-close-an-async-generator
    task = asyncio.create_task(agen.__anext__())
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task

async def _stream_chunks_task(chunks: AsyncGenerator[dict, None], queues: list[asyncio.Queue[str|QueueSentinel]]) -> None:
    """receive chunks from the async generator returned by openai.ChatCompletion.acreate
    and route each chunk into the appropriate queue. this part of the receive process is cancelable.
    """
    async for chunk in chunks:
        if chunk["choices"]:
            choices = chunk["choices"]
            for choice in choices:
                index = choice["index"]
                delta = choice["delta"]
                if "content" in delta:
                    if bool(delta_content := delta["content"]):
                        queues[index].put_nowait(delta_content)

async def _streaming_receive_task(chunks: AsyncGenerator[dict, None], queues: list[asyncio.Queue[str|QueueSentinel]], cancellation_token: CancellationToken) -> None:
    """stream chunks from the async generator returned by openai.ChatCompletion.acreate
    and route to queues using _stream_chunks_task.
    handle cancellation and ensure that all queues are terminated with a END_OF_RESPONSE item
    both at the end of processing and if cancelled."""
    try:
        receive_chunks_task = asyncio.create_task(_stream_chunks_task(chunks, queues))
        cancellation_token.on_cancel(lambda: _discard_arg(receive_chunks_task.cancel()))

        with suppress(asyncio.CancelledError):
            await receive_chunks_task

        if cancellation_token.cancelled:
            # cancel the source, i.e. the AsyncGenerator that openai.ChatCompletion.acreate gave us
            with suppress(asyncio.CancelledError):
                await _cancel_async_generator(chunks)
    finally:
        # terminate the queues. note that this needs to happen under all cancellation and error scenarios
        for queue in queues:
            queue.put_nowait(QueueSentinel.END_OF_RESPONSE)

async def _dequeue_async_content(queue) -> AsyncGenerator[str, None]:
    while True:
        s = await queue.get()
        if s == QueueSentinel.END_OF_RESPONSE:
            return
        yield s

def _discard_arg(arg: Any) -> None:
    return None

class OpenAIChatResponder(Responder):
    def __init__(self):
        # save OpenAI global variables because local.openai.chat may alter them
        self._openai_globals = load_api_key_and_organization()

    def construct_configuration(self, context: ResponderContext) -> BaseModel|tuple[BaseModel, list[tuple[str,VarRef]]]|None:
        return OpenAIChatResponderConfiguration(), [
            ("model", VarRef("model")),
            ("temperature", VarRef("temperature")),
            ("n", VarRef("n")),
            ("stream", VarRef("stream"))]

    async def _async_response_generator(self, input_: list[Message], cancellation_token: CancellationToken, context: ResponderContext) -> AsyncGenerator[Message, None]:
        config: OpenAIChatResponderConfiguration = context.responder_config
        context.log.debug(f"openai.chat: input: {config = }", context.state.input_file_path)
        config = resolve_var_refs(config, context.root_config, context.log)
        context.log.debug(f"openai.chat: resolved: {config = }", context.state.input_file_path)

        openai_globals.restore_openai_globals(self._openai_globals)

        messages = convert_message_sequence_to_openai_messages(input_, context.log)

        if config.max_tokens is not None: # i.e. if we're not using the default
            # clamp requested completion token count to avoid API error if we ask for more than can be provided
            prompt_token_count = num_tokens_from_messages(messages, model=config.model, log=context.log)
            context.log.debug(f"openai.chat: {prompt_token_count = }", context.state.input_file_path)
            model_token_limit = get_model_token_limit(config.model)
            # NB: config.max_tokens is the maximum response tokens
            if prompt_token_count + config.max_tokens > model_token_limit:
                config.max_tokens = model_token_limit - prompt_token_count
                if config.max_tokens > 0:
                    context.log.info("openai.chat-clamping-max-tokens", f"openai.chat: clamping requested completion to {config.max_tokens} max tokens", context.state.input_file_path)
                else:
                    context.log.info("openai.chat-at-token-limit", "openai.chat: token limit reached. exiting", context.state.input_file_path)
                    return

        context.log.debug(f"openai.chat: final: {config = }")
        chat_args = config.model_dump(exclude_none=True, exclude_defaults=True)
        chat_args["model"] = config.model # include model, even if it was left at default
        context.log.debug(f"openai.chat: {chat_args = }")
        chat_args["messages"] = messages

        if context.root_config.prapti.dry_run:
            context.log.info("openai.chat-dry-run", "openai.chat: dry run: halting before calling the OpenAI API", context.state.input_file_path)
            current_time = str(datetime.datetime.now())
            chat_args["messages"] = ["..."] # avoid overly long output
            yield Message(role="assistant", name=None, content=[f"dry run mode. {current_time}\nchat_args = {json.dumps(chat_args)}"])
            return

        if cancellation_token.cancelled:
            return
        try:
            # docs: https://platform.openai.com/docs/api-reference/chat/create
            if config.stream:
                # https://github.com/openai/openai-cookbook/blob/main/examples/How_to_stream_completions.ipynb
                task = asyncio.create_task(openai.ChatCompletion.acreate(**chat_args))
                cancellation_token.on_cancel(lambda: _discard_arg(task.cancel()))
                chunks = None
                with suppress(asyncio.CancelledError):
                    chunks = await task
                if cancellation_token.cancelled or chunks is None:
                    return

                queues: list[asyncio.Queue[str|QueueSentinel]] = [asyncio.Queue(maxsize=0) for _ in range(config.n)]
                # ^^^ unbounded queues -- to avoid constraining caller's response iteration strategy
                receive_task = asyncio.create_task(_streaming_receive_task(chunks, queues, cancellation_token))

                if config.n == 1:
                    yield Message(role="assistant", name=None, content=[], async_content=_dequeue_async_content(queues[0]))
                else:
                    for i, queue in enumerate(queues, start=1):
                        yield Message(role="assistant", name=str(i), content=[], async_content=_dequeue_async_content(queue))

                await receive_task
            else:
                task = asyncio.create_task(openai.ChatCompletion.acreate(**chat_args))
                cancellation_token.on_cancel(lambda: _discard_arg(task.cancel()))
                response = None
                with suppress(asyncio.CancelledError):
                    response = await task
                if cancellation_token.cancelled or response is None:
                    return
                assert isinstance(response, dict)

                context.log.debug(f"openai.chat: {response = }", context.state.input_file_path)

                if len(response["choices"]) == 1:
                    choice = response["choices"][0]
                    yield Message(role="assistant", name=None, content=[choice.message["content"]], async_content=None)
                else:
                    for i, choice in enumerate(response["choices"], start=1):
                        yield Message(role="assistant", name=str(i), content=[choice.message["content"]], async_content=None)
        except Exception as ex:
            context.state.log.error("openai-chat-api-exception", f"exception while requesting a response from the API server: {repr(ex)}", context.state.input_file_path)
            context.state.log.logger.debug(ex, exc_info=True)

    def generate_responses(self, input_: list[Message], cancellation_token: CancellationToken, context: ResponderContext) -> AsyncGenerator[Message, None]:
        return self._async_response_generator(input_, cancellation_token, context)

class OpenAIChatResponderPlugin(Plugin):
    def __init__(self):
        super().__init__(
            api_version = "1.0.0",
            name = "openai.chat",
            version = "0.0.2",
            description = "Responder using the OpenAI Chat Completion API",
            capabilities = PluginCapabilities.RESPONDER
        )

    def construct_responder(self, context: PluginContext) -> Responder|None:
        return OpenAIChatResponder()

prapti_plugin = OpenAIChatResponderPlugin()
