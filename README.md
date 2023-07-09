# Prapti: converse with LLMs directly in markdown files

> Hello! Welcome to Prapti. We're just getting started and we'd love for you to join the conversation. Please use GitHub *Discussions* general queries and suggestions, *Issues* for bug reports. Our *Pull Requests* are open.

Prapti is a tool for prompting Large Language Models (LLMs) with an editable history. You work within a [markdown](https://www.markdownguide.org/) file where you can edit your prompts and the LLM's responses. Press a hot-key to get the next response from the LLM. Once received, the response is automatically appended to the file.

### Features

- Work in your favourite editor
- Markdown files are the native conversation format (headings with special text delimit message boundaries)
- Easily edit the whole conversation history/context window, including previous LLM outputs
- Inline configuration syntax: easily change LLM parameters and switch language models ("responders") with each round of the conversation
- Extensible with plugins (responders, commands and processing hooks)
- Support for OpenAI, GPT4All (experimental), or add your favourite LLM back-end by implementing a Responder plugin.

## Installation and Setup

Prapti requires Python 3.10 or newer.

Installation involves the following required steps:

1. Install the `prapti` command line tool
2. Set up your OpenAI API key (or configure a local LLM: see docs)
3. Check that the `prapti` tool runs manually in your terminal
4. Set up a keybinding to run `prapti` in your editor

### 1. Install the `prapti` command line tool

In your terminal, run:

```
pip install git+https://github.com/prapti-ai/prapti
```

(or `pip3` or `py -3 -m pip` depending on your system).

We recommend running prapti in a Python virtual environment such as
[venv](https://docs.python.org/3/tutorial/venv.html).

### 2. Set up your OpenAI API key (or configure a local LLM)

```
export OPENAI_API_KEY=your-key-goes-here
```

(or `setx`, depending on your system. There are other ways to manage your environment variables. For details see OpenAI's [Best Practices for API Key Safety](https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety) ).

To select a non-default organisation, use the `OPENAI_ORGANIZATION` environment variable.

To use a alternate OpenAI API key and/or organization specifically with prapti you can set `PRAPTI_OPENAI_API_KEY` and/or `PRAPTI_OPENAI_ORGANIZATION`. If set, prapti will use these environment variables in preference to `OPENAI_API_KEY` and `OPENAI_ORGANIZATION`.

[Click here for local LLM configuration](docs/local_llms.md)

### 3. Check that the `prapti` tool runs manually in your terminal

First, create a test markdown file with `.md` extension or work with an existing markdown file such as `chat-example.md`

Edit the file with a trailing user prompt like this:

```markdown:chat-example.md
### @user:

Write your prompt here.
```

Then run the script to generate a new assistant response:

```
prapti chat-example.md
```

### 4. Set up a keybinding to run `prapti` in your editor

Bind the key combination `Ctrl-Enter` to save the file and then run prapti (only when editing markdown files).

Below are the instructions for VSCode. If you use another editor please contribute instructions.

#### VSCode instructions

> NOTE: This key binding runs `prapti` in the active VSCode terminal window. So make sure you have the terminal open with the `prapti` command available.

First use the *Quick Open* menu (*Cmd-Shift-P* on Mac, *Ctrl-Shift-P* on Windows) to run:

> Preferences: Open Keyboard Shortcuts (JSON)

then add the following binding to the opened `keybindings.json` file.

```json
{
    "key": "ctrl+enter",
    "command": "runCommands",
    "args":{
        "commands":[
            "workbench.action.files.save",
            "cursorBottom",
            {
                "command": "workbench.action.terminal.sendSequence",
                "args": { "text": "prapti ${file}\u000D" }
            },
            "cursorBottom",
        ]
    },
    "when": "editorLangId == markdown"
},
```

Now, when editing your markdown file you should be able to hit `Ctrl-Enter` to get a response from the LLM. You can watch the terminal window for progress. Be patient, GPT4 can take 30 seconds to generate a full response.

See [our documentation](docs/editor_tweaks.md) for setting up syntax highlighting and chat-aware markdown display.

## License

This project is [MIT](LICENSE) licensed.
