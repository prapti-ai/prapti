"""
    Generate responses using the OpenAI chat API
"""
import os
from dataclasses import dataclass, asdict
import datetime
import typing

import openai
import tiktoken

from ..core.plugin import Plugin
from ..core.command_message import Message
from ..core.responder import Responder, ResponderContext
from ..core.logger import DiagnosticsLogger

# openai chat API docs:
# https://platform.openai.com/docs/guides/chat/introduction
# basic example:
# https://gist.github.com/pszemraj/c643cfe422d3769fd13b97729cf517c5

# command line arguments, api key --------------------------------------------

# NOTE: we do not want to allow the user to store secrets in files that could easily be leaked.
# therefore we do not support specifying the API key in the configuration space
# i.e. we do not allow secrets to be set in input markdown or in our config files.

def setup_api_key_and_organization() -> None:
    """setup OpenAI API key and organization from environment variables"""

    # first check Prapti-specific environment variables,
    # then fall-back to OpenAI standard varaiables.
    # put your API key in the OPENAI_API_KEY environment variable, see:
    # https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety

    openai_api_key = os.environ.get("PRAPTI_OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", None))
    openai_organization = os.environ.get("PRAPTI_OPENAI_ORGANIZATION", os.environ.get("OPENAI_ORGANIZATION", None))

    if openai_api_key is None:
        raise ValueError("OpenAI API key not set in environment variable.")

    openai.api_key = openai_api_key
    openai.organization = openai_organization

# chat API parameters --------------------------------------------------------

@dataclass
class OpenAIChatParameters:
    model: str = "gpt-3.5-turbo"
    messages: list|None = None
    temperature: float = 1
    top_p: float = 1
    max_tokens: int = 2000 # GPT 3.5 Turbo max content: 4096
    n: int = 1 # how many completions to generate
    #stop: Optional[Union[str, list]] = None
    stop = None
    presence_penalty: float = 0
    frequency_penalty: float = 0
    # logit_bias = # NOTE can't pass None for logit_bias
    # user = # used for abuse monitoring only NOTE can't pass NONE

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

def convert_message_sequence_to_openai_messages(message_sequence: list[Message]) -> list[dict]:
    result = []
    for message in message_sequence:
        if not message.is_enabled or message.is_private:
            continue # skip disabled and private messages

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

class OpenAIChatResponder(Responder):
    def __init__(self):
        setup_api_key_and_organization()

    def construct_configuration(self, context: ResponderContext) -> typing.Any|None:
        return OpenAIChatParameters()

    def generate_responses(self, input_: list[Message], context: ResponderContext) -> list[Message]:
        chat_parameters: OpenAIChatParameters = context.responder_config
        context.log.debug(f"openai.chat: {chat_parameters = }", context.state.input_file_path)
        # REVIEW: we should be treating the parameters as read-only here

        # propagate top-level parameter aliases:
        for name in ("model", "temperature", "n"):
            if (value := getattr(context.root_config, name, None)) is not None:
                context.log.debug(f"openai.chat: {name}, {value}", context.state.input_file_path)
                setattr(chat_parameters, name, value)

        chat_parameters.messages = convert_message_sequence_to_openai_messages(input_)

        # clamp requested completion token count to avoid API error if we ask for more than can be provided
        prompt_token_count = num_tokens_from_messages(chat_parameters.messages, model=chat_parameters.model, log=context.log)
        context.log.debug(f"openai.chat: {prompt_token_count = }", context.state.input_file_path)
        model_token_limit = get_model_token_limit(chat_parameters.model)
        # NB: chat_parameters.max_tokens is the maximum response tokens
        if prompt_token_count + chat_parameters.max_tokens > model_token_limit:
            chat_parameters.max_tokens = model_token_limit - prompt_token_count
            if chat_parameters.max_tokens > 0:
                context.log.info("openai.chat-clamping-max-tokens", f"openai.chat: clamping requested completion to {chat_parameters.max_tokens} max tokens", context.state.input_file_path)
            else:
                context.log.info("openai.chat-at-token-limit", "openai.chat: token limit reached. exiting", context.state.input_file_path)
                return []

        context.log.debug(f"openai.chat: {chat_parameters = }")
        if context.root_config.dry_run:
            context.log.info("openai.chat-dry-run", "openai.chat: dry run: bailing before hitting the OpenAI API", context.state.input_file_path)
            current_time = str(datetime.datetime.now())
            d = asdict(chat_parameters)
            d["messages"] = ["..."] # avoid overly long output
            return [Message(role="assistant", name=None, content=[f"dry run mode. {current_time}\nchat_parameters = {d}"])]

        # docs: https://platform.openai.com/docs/api-reference/chat/create
        response = openai.ChatCompletion.create(**asdict(chat_parameters))
        context.log.debug(f"openai.chat: {response = }", context.state.input_file_path)

        if len(response["choices"]) == 1:
            choice = response["choices"][0]
            result = [Message(role="assistant", name=None, content=[choice.message["content"].strip()])]
        else:
            result = []
            for i, choice in enumerate(response["choices"], start=1):
                result.append(Message(role="assistant", name=str(i), content=[choice.message["content"].strip()]))
        return result

class OpenAIChatResponderPlugin(Plugin):
    def __init__(self):
        super().__init__(
            api_version = "0.1.0",
            name = "openai.chat",
            version = "0.0.1",
            description = "Responder using the OpenAI Chat Completion API"
        )

    def construct_responder(self) -> Responder|None:
        return OpenAIChatResponder()

prapti_plugin = OpenAIChatResponderPlugin()
