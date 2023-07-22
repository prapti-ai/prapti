# Prapti: converse with LLMs directly in markdown files

> Hello! Welcome to Prapti. It's early, and we're just getting started. Please use GitHub *Discussions* for general queries and suggestions, and *Issues* for bug reports. See [CONTRIBUTING.md](CONTRIBUTING.md) for code contributions.

Prapti is a tool for prompting Large Language Models (LLMs) with an editable history. You work within a [markdown](https://www.markdownguide.org/) file where you can edit your prompts and the LLM's responses. Press a hot-key to get the next response from the LLM. Once received, the response is automatically appended to the file.

### Features

- Work in your favourite editor
- Markdown files are the native conversation format (headings with special text delimit message boundaries)
- Easily edit the whole conversation history/context window, including previous LLM outputs
- Inline configuration syntax: easily change LLM parameters and switch language models ("responders") with each round of the conversation
- Designed to be extensible with plugins (responders, commands and processing hooks)
- Supports OpenAI, GPT4All (experimental), or add your favourite LLM back-end by implementing a Responder plugin

Using prapti is an interactive experience, but you can get an idea of what it might be like by reading [your first prapti conversation](start_here.md).

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

To use an alternate OpenAI API key and/or organization specifically with prapti you can set `PRAPTI_OPENAI_API_KEY` and/or `PRAPTI_OPENAI_ORGANIZATION`. If set, prapti will use these environment variables in preference to `OPENAI_API_KEY` and `OPENAI_ORGANIZATION`.

[Click here for local LLM configuration](docs/local_llms.md)

### 3. Check that the `prapti` tool runs manually in your terminal

First, create a new markdown file with `.md` extension. You can name it anything you like, for example `test-chat.md`.

Edit the file so that the final lines consist of a user prompt. A user prompt is a message that you, as the user, write to the LLM. It should look like this:

```markdown:test-chat.md
### @user:

Write your prompt here.
```

Then run `prapti` in the terminal to generate a new assistant response:

```
prapti test-chat.md
```

After running `prapti`, refresh or reload the `test-chat.md` file. You should see that prapti has appended an assistant response to the file. With this test, you've confirmed that prapti works correctly in your terminal. The next step is to set up a convenient way to run prapti, such as a hot-key, for a smoother conversation flow with the LLM.

### 4. Set up a keybinding to run `prapti` in your text editor

Choose a key combination (e.g. `Ctrl-Enter`) in your preferred text editor, and configure it to save the current file and run `prapti`. This keybinding should be set to function only when you're editing markdown files.

Below are the instructions for VSCode. If you use another editor please contribute instructions.

#### VSCode

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

See [our documentation](docs/editor_tweaks.md) for optional text editor setup to streamline your experience.

## License

This project is [MIT](LICENSE) licensed.
