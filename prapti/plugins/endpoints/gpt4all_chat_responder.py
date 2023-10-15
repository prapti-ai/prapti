"""
    Generate responses using the GPT4All chat API

    ** EXPERIMENTAL **

    Notes:

    It's not clear to me what's going on with the state of chat templates in
    the GPT4ALL API. Need to look into this. For now we just roll our own, which
    have no hope of being correlated with the way the model was trained.

    We would like inference to run in a persistent process, not in the
    transient prapti tool invocation. Consider setting up something using Pyro5
"""
# ----------------------------------------------------------------------------
# /// DANGER -- UNDER CONSTRUCTION ///////////////////////////////////////////

import datetime
import inspect
import json
from typing import AsyncGenerator, Iterable
from enum import Enum
import asyncio

from pydantic import BaseModel, Field, ConfigDict
from cancel_token import CancellationToken
import gpt4all

from ...core.plugin import Plugin, PluginCapabilities, PluginContext
from ...core.command_message import Message
from ...core.configuration import VarRef, resolve_var_refs
from ...core.responder import Responder, ResponderContext
from ...core.logger import DiagnosticsLogger

def convert_message_sequence_to_text_prompt(message_sequence: list[Message], log: DiagnosticsLogger) -> str:
    # a hack, based on: https://github.com/nomic-ai/gpt4all/pull/652
    # note we are currently ignoring message.name

    result = ""
    for message in message_sequence:
        if not message.is_enabled or message.is_hidden:
            continue # skip disabled and hidden messages

        if message.role not in ["system", "user", "assistant"]:
            log.warning("unrecognised-public-role", f"message will not be included in LLM prompt. public role '{message.role}' is not recognised.", message.source_loc)
            continue

        # HACK WARNING: not all LLMs use the same chat structure delimiters.
        # the following format will perform badly if it is not consistent with the fine-tuning of the selected model.
        # ideally, we will delegate chat structure formatting to our dependencies.
        assert len(message.content) == 1 and isinstance(message.content[0], str), "gpt4all.chat: internal error. expected flattened message content"
        match message.role:
            case "system":
                result += "### Instruction:\n"
                result += message.content[0]
                result += "\n"
            case "user":
                result += "### Prompt:\n"
                result += message.content[0]
                result += "\n"
            case "assistant":
                result += "### Response:\n"
                result += message.content[0]
                result += "\n"
    result += "### Response:\n"
    return result

class GPT4AllResponderConfiguration(BaseModel):
    """Configuration parameters for the GPT4All chat responder.
    See the [GPT4All API documentation](https://docs.gpt4all.io/gpt4all_api.html) for more information."""
    model_config = ConfigDict(
        validate_assignment=True,
        protected_namespaces=()) # pydantic config: suppress warnings about `model` prefixed names

    # --- model instantiation parameters:

    model_name: str = Field(default="ggml-mpt-7b-chat.bin", description=inspect.cleandoc("""\
        Name of GPT4All or custom model. Including ".bin" file extension is optional but encouraged."""))

    model_path: str = Field(default_factory=str, description=inspect.cleandoc("""\
        Path to directory containing model file.
        Default is None, in which case models will be stored in `~/.cache/gpt4all/`."""))
        # TODO: ^^^look up model path in registry or similar

    n_threads: int|None = Field(default=0, description=inspect.cleandoc("""\
        Number of CPU threads used by GPT4All. Default is None, in which case the number of threads is determined automatically."""))

    # --- generate parameters:

    max_tokens: int = Field(default=500, description=inspect.cleandoc("""\
        The maximum number of tokens to generate."""))

    temp: float = Field(default=0.7, description=inspect.cleandoc("""\
        The model temperature. Larger values increase creativity but decrease factuality."""))

    top_k: int = Field(default=40, description=inspect.cleandoc("""\
        Randomly sample from the top_k most likely tokens at each generation step. Set this to 1 for greedy decoding."""))

    top_p: float = Field(default=0.1, description=inspect.cleandoc("""\
        Randomly sample at each generation step from the top most likely tokens whose probabilities add up to top_p."""))

    repeat_penalty: float = Field(default=1.18, description=inspect.cleandoc("""\
        Penalize the model for repetition. Higher values result in less repetition."""))

    repeat_last_n: int = Field(default=64, description=inspect.cleandoc("""\
        How far in the models generation history to apply the repeat penalty."""))

    n_batch: int = Field(default=8, description=inspect.cleandoc("""\
        Number of prompt tokens processed in parallel. Larger values decrease latency but increase resource requirements."""))

    n_predict: int|None = Field(default=None, description=inspect.cleandoc("""\
        Equivalent to max_tokens, exists for backwards compatibility."""))

    streaming: bool = Field(default=True, description=inspect.cleandoc("""\
        If True, this method will instead return a generator that yields tokens as the model generates them."""))

    # TODO: add n parameter for number of generations.

_generate_arg_names = { "max_tokens", "temp", "top_k", "top_p", "repeat_penalty", "repeat_last_n", "n_batch", "n_predict", "streaming" }

class QueueSentinel(Enum):
    END_OF_RESPONSE = 0

def _sync_generator_to_queue(sync_generator: Iterable[str], queue: asyncio.Queue[str|QueueSentinel], loop: asyncio.AbstractEventLoop, cancellation_token: CancellationToken) -> None:
    try:
        for s in sync_generator:
            # NOTE: asyncio.Queue is neither thread-aware nor thread safe: https://stackoverflow.com/questions/32889527
            # hence the call to loop.call_soon_threadsafe()
            loop.call_soon_threadsafe(queue.put_nowait, s)
            if cancellation_token.cancelled:
                break
    finally:
        loop.call_soon_threadsafe(queue.put_nowait, QueueSentinel.END_OF_RESPONSE)

async def _generate_async_content(sync_generator: Iterable[str], cancellation_token: CancellationToken) -> AsyncGenerator[str, None]:
    queue: asyncio.Queue[str|QueueSentinel] = asyncio.Queue(maxsize=0) # unbounded
    thread_task = asyncio.create_task(asyncio.to_thread(_sync_generator_to_queue, sync_generator, queue, asyncio.get_event_loop(), cancellation_token))

    while True:
        s = await queue.get()
        if s == QueueSentinel.END_OF_RESPONSE:
            break
        yield s

    await thread_task

class GPT4AllChatResponder(Responder):
    def __init__(self):
        pass

    def construct_configuration(self, context: ResponderContext) -> BaseModel|tuple[BaseModel, list[tuple[str,VarRef]]]|None:
        return GPT4AllResponderConfiguration(), [
            ("model_name", VarRef("model")),
            ("temp", VarRef("temperature")),
            ("streaming", VarRef("stream"))]
        # TODO: n -> var(n)

    async def _async_response_generator(self, input_: list[Message], cancellation_token: CancellationToken, context: ResponderContext) -> AsyncGenerator[Message, None]:
        config: GPT4AllResponderConfiguration = context.responder_config
        config = resolve_var_refs(config, context.root_config, context.log)
        context.log.debug(f"gpt4all.chat: {config = }", context.state.input_file_path)

        if context.root_config.prapti.dry_run:
            context.log.info("gpt4all.chat-dry-run", "gpt4all.chat: dry run: bailing before hitting the GPT4All API", context.state.input_file_path)
            current_time = str(datetime.datetime.now())
            yield Message(role="assistant", name=None, content=[f"dry run mode. {current_time}\nconfig = {json.dumps(config.model_dump())}"])
            return

        prompt = convert_message_sequence_to_text_prompt(input_, context.log)

        context.log.info("gpt4all-loading-model", "gpt4all.chat: loading model. please wait...", context.state.input_file_path)

        model = await asyncio.to_thread(gpt4all.GPT4All,
            model_name = config.model_name,
            model_path = config.model_path,
            model_type = None, # currently unused
            allow_download = False,
            n_threads = config.n_threads if (config.n_threads and config.n_threads > 0) else None)
        if cancellation_token.cancelled:
            return

        generate_args = config.model_dump(include=_generate_arg_names)

        context.log.info("gpt4all-generating", "gpt4all.chat: generating...", context.state.input_file_path)

        context.log.debug(f"gpt4all.chat: {generate_args = }", context.state.input_file_path)
        response = await asyncio.to_thread(model.generate, prompt=prompt, **generate_args)

        if isinstance(response, str):
            context.log.debug("gpt4all.chat: got non-streaming response", context.state.input_file_path)
            yield Message(role="assistant", name=None, content=[response], async_content=None)
        else:
            context.log.info("gpt4all-streaming-generation", "gpt4all.chat: streaming generation...", context.state.input_file_path)
            yield Message(role="assistant", name=None, content=[], async_content=_generate_async_content(response, cancellation_token))

    def generate_responses(self, input_: list[Message], cancellation_token: CancellationToken, context: ResponderContext) -> AsyncGenerator[Message, None]:
        return self._async_response_generator(input_, cancellation_token, context)

# ^^^ END UNDER CONSTRUCTION /////////////////////////////////////////////////
# ----------------------------------------------------------------------------

class GPT4AllChatResponderPlugin(Plugin):
    def __init__(self):
        super().__init__(
            api_version = "0.1.0",
            name = "experimental.gpt4all.chat",
            version = "0.0.1",
            description = "Responder using the GPT4All Chat Completion API",
            capabilities = PluginCapabilities.RESPONDER
        )

    def construct_responder(self, context: PluginContext) -> Responder|None:
        return GPT4AllChatResponder()

prapti_plugin = GPT4AllChatResponderPlugin()
