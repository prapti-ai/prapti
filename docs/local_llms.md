# Using Local LLMs With Prapti

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

## Koboldcpp

Prapti supports Koboldcpp, a CPU-based LLM inference engine based on llama.cpp.

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

## Others

We plan to add support for other local LLM engines. Watch this space, or contribute your own.
