# Using Local LLMs With Prapti

## GPT4All (Experimental)

Prapti has experimental support for GPT4All, a CPU-based LLM inference engine.

You can use the Prapti configuration in the following markdown file as a starting point.

```
prapti/plugins/gpt4all_test_1.md
```

[Or just click here](../prapti/plugins/gpt4all_test_1.md)

The Python code that implements support for GPT4All in Prapti can be found at:

```
prapti/plugins/gpt4all_chat_responder.py
```

## Others

We plan to add support for other local LLM libraries. Watch this space, or contribute your own.

## Koboldcpp

Prapti supports Koboldcpp, a CPU-based LLM inference engine based on llama.cpp.

Start by getting Koboldcpp working using its own "lite" UI. After that,
Prapti will also be able to query the running Koboldcpp API server.

Koboldcpp provides raw text completions, not structured chat-format completions,
so you will need to use the `### @prompt:` message heading with Prapti. Be warned
that this requires a more nuanced understanding of prompting LLMs than simply
conversing with a "chat" fine-tuned model.

Use the Prapti configuration in the following markdown file as a starting point.

```
prapti/plugins/koboldcpp_text_responder.md
```

[Or just click here](../prapti/plugins/koboldcpp_text_responder.md)

The Python code that implements support for Koboldcpp in Prapti can be found at:

```
prapti/plugins/koboldcpp_text_responder.py
```
