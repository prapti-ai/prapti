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

from dataclasses import dataclass, field, asdict
import datetime
import typing
import sys

import gpt4all

from ..core.plugin import Plugin
from ..core.command_message import Message
from ..core.responder import Responder, ResponderContext
from ..core.logger import DiagnosticsLogger

def convert_message_sequence_to_text_prompt(message_sequence: list[Message], log: DiagnosticsLogger) -> str:
    # a hack, based on: https://github.com/nomic-ai/gpt4all/pull/652
    # note we are currently ignoring message.name

    result = ""
    for message in message_sequence:
        if not message.is_enabled or message.is_private:
            continue # skip disabled and private messages

        if message.role not in ["system", "user", "assistant"]:
            log.warning("unrecognised-public-role", f"message will not be included in LLM prompt. public role '{message.role}' is not recognised.", message.source_loc)
            continue

        assert len(message.content) == 1 and isinstance(message.content[0], str), "gpt4all.chat: expected flattened message content"
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

@dataclass
class GPT4AllResponderConfiguration:
    model_name: str = "ggml-mpt-7b-chat.bin"
    model_path: str = field(default_factory=str) # TODO: look up model path in registry or similar
    n_threads: int = 0 #int|None = None # None==use default thread allocation

    max_tokens: int = 500
    temp: float = 0.7
    top_k: int = 40
    top_p: float = 0.1
    repeat_penalty: float = 1.18
    repeat_last_n: int = 64
    n_batch: int = 8
    n_predict: int|None = None
    streaming: bool = True

_generate_arg_names = { "prompt", "max_tokens", "temp", "top_k", "top_p", "repeat_penalty", "repeat_last_n", "n_batch", "n_predict", "streaming" }

def generate_args_from(config: GPT4AllResponderConfiguration) -> dict:
    return {k:v for k,v in asdict(config).items() if k in _generate_arg_names}

class GPT4AllChatResponder(Responder):
    def __init__(self):
        pass

    def construct_configuration(self, context: ResponderContext) -> typing.Any|None:
        return GPT4AllResponderConfiguration()

    def generate_responses(self, input_: list[Message], context: ResponderContext) -> list[Message]:
        config: GPT4AllResponderConfiguration = context.responder_config
        context.log.debug(f"gpt4all.chat: {config = }", context.state.input_file_path)

        #TODO: support global model and n
        if (value := getattr(context.root_config, "temperature", None)) is not None:
            config.temp = value

        if context.root_config.dry_run:
            context.log.info("gpt4all.chat-dry-run", "gpt4all.chat: dry run: bailing before hitting the GPT4All API", context.state.input_file_path)
            current_time = str(datetime.datetime.now())
            d = asdict(config)
            return [Message(role="assistant", name=None, content=[f"dry run mode. {current_time}\nconfig = {d}"])]

        prompt = convert_message_sequence_to_text_prompt(input_, context.log)

        model = gpt4all.GPT4All(model_name = config.model_name,
                                model_path = config.model_path,
                                model_type = None, # currently unused
                                allow_download = False,
                                n_threads = config.n_threads if config.n_threads > 0 else None)

        generate_args = generate_args_from(config)
        context.log.debug(f"gpt4all.chat: {generate_args = }", context.state.input_file_path)
        if config.streaming:
            response = ""
            sys.stdout.flush()
            response_generator = model.generate(prompt=prompt, **generate_args)
            for s in response_generator:
                response += s
                sys.stdout.write(s)
                sys.stdout.flush()
            sys.stdout.write("\n")
            sys.stdout.flush()
        else:
            response = model.generate(prompt=prompt, **generate_args)

        return [Message(role="assistant", name=None, content=[response])]

# ^^^ END UNDER CONSTRUCTION /////////////////////////////////////////////////
# ----------------------------------------------------------------------------

class GPT4AllChatResponderPlugin(Plugin):
    def __init__(self):
        super().__init__(
            api_version = "0.1.0",
            name = "experimental.gpt4all.chat",
            version = "0.0.1",
            description = "Responder using the GPT4All Chat Completion API"
        )

    def construct_responder(self) -> Responder|None:
        return GPT4AllChatResponder()

prapti_plugin = GPT4AllChatResponderPlugin()
