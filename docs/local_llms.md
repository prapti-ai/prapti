# Using Local LLMs With Prapti

Prapti supports a number of different methods for talking to locally running large language models. Each method is described below.

## OpenAI API-compatible Local LLMs

Prapti supports local LLM software that provides an OpenAI-compatible chat completions API server. This includes GPT4All, vLLM, LocalAI, and others. To do this,
Prapti provides the `local.openai.chat` responder, which is tailored for use with local LLMs.

Unlike the `openai.chat` responder, `local.openai.chat` does not use, expose or send the
`OPENAI_API_KEY` environment variable, and does not perform any operations specific
to OpenAI models, such as using OpenAI token counters. It also provides an easy way to set the API endpoint base address (`api_base`) from within your prapti configuration.

Use the Prapti configuration in the following markdown file as a starting point.

```
prapti/plugins/endpoints/local_openai_chat_responder.md
```

[Or just click here](../prapti/plugins/endpoints/local_openai_chat_responder.md)

The Python code that implements support for OpenAI-compatible API servers in Prapti can be found at:

```
prapti/plugins/endpoints/local_openai_chat_responder.py
```

## Koboldcpp

Prapti supports Koboldcpp, a CPU-based LLM inference engine based on `llama.cpp`.

The first step is to ensure Koboldcpp is operational using its "lite" UI. Do this by
following the Koboldcpp documentation. Once this is achieved, Prapti can then
query the running Koboldcpp API server.

Koboldcpp is designed to provide raw text completions, not structured chat-format
completions. As a result, prompts should be written to elicit a natural text
continuation from the LLM. Instead of initiating your prompt with `### @user:`,
use `### @prompt:`. Prapti will then append the LLM's completion directly after
the prompt. Please note that this workflow necessitates a more nuanced understanding
of prompting LLMs than simply engaging with a "chat" fine-tuned model.

Use the Prapti configuration in the following markdown file as a starting point.

```
prapti/plugins/endpoints/koboldcpp_text_responder.md
```

[Or just click here](../prapti/plugins/endpoints/koboldcpp_text_responder.md)

The Python code that implements support for Koboldcpp in Prapti can be found at:

```
prapti/plugins/endpoints/koboldcpp_text_responder.py
```

## GPT4All (Experimental)

Prapti has experimental support for GPT4All, a CPU-based LLM inference engine.

You can use the Prapti configuration in the following markdown file as a starting point.

```
prapti/plugins/endpoints/gpt4all_test_1.md
```

[Or just click here](../prapti/plugins/endpoints/gpt4all_test_1.md)

The Python code that implements support for GPT4All in Prapti can be found at:

```
prapti/plugins/endpoints/gpt4all_chat_responder.py
```

## Others

We plan to add support for other local LLM engines. Watch this space, or contribute your own.
