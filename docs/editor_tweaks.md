# Editor Tweaks

This file documents optional editor setup that may improve your Prapti experience.

## VSCode

Here are two ways to streamline creation of markdown files.

To add keyboard shortcuts use the *Quick Open* menu to run:

> Preferences: Open Keyboard Shortcuts (JSON)

### Keyboard shortcut to create an untitled markdown file and immediately show the save-as dialog box

```json
{
    "key": "ctrl+shift+alt+enter",
    "command": "runCommands",
    "args": {
        "commands": [
            {
                "command": "workbench.action.files.newUntitledFile",
                "args": {
                    "languageId": "markdown"
                }
            },
            "workbench.action.files.save",
        ]
    }
},
```

### Keyboard shortcut to create a new file, in a selected folder

To use this shortcut first click on a directory in the VSCode File Explorer. Now type `Ctrl+n`. Now type the name of the file to create and press `Enter`. The file should open for editing and you can start using prapti. (For use with prapti the file name should end in `.md`.)

```json
{
    "key": "ctrl+n",
    "command": "workbench.files.action.createFileFromExplorer",
    "when": "explorerViewletFocus && explorerViewletVisible && !inputFocus"
},
```

The tweaks below provide additional visual cues in the text editor when editing markdown that contains Prapti message headings.

### Highlight Message Headings in Markdown Files

To get whole-line highlighting for the `system`, `user` and `assistant` message headings install the following extension:

[Highlight extension by Fabio Spampinato](vscode:extension/fabiospampinato.vscode-highlight)

After installing, go to the extension settings and under **Highlight: Regexes** choose **Edit in settings.json** and add the following:

```json
    "highlight.regexes": {
        "(^[ ]{0,3}###\\s+@assistant(/\\w*)?:)": {
            "regexFlags": "gm",
            "filterLanguageRegex": "markdown",
            "decorations": [ {
                "isWholeLine": "true",
                "backgroundColor": "rgba(255, 255, 255, 0.05)" }
            ]
        },
        "(^[ ]{0,3}###\\s+@user(/\\w*)?:)": {
            "regexFlags": "gm",
            "filterLanguageRegex": "markdown",
            "decorations": [ {
                "isWholeLine": "true",
                "backgroundColor": "rgba(0, 0, 0, 0.2)" }
            ]
        },
        "(^[ ]{0,3}###\\s+@system(/\\w*)?:)": {
            "regexFlags": "gm",
            "filterLanguageRegex": "markdown",
            "decorations": [ {
                "isWholeLine": "true",
                "backgroundColor": "rgba(0, 0, 0, 0.2)" }
            ]
        }
    },
```

### Enable Markdown Preview Message Colorisation [Experimental]

The idea here is to try to make the markdown preview in VSCode alternate background colours with each message (somewhat like the ChatGPT web interface -- with the colour bleeding out to the edges of the window). This makes it easy to differentiate between your input and the assistant output.

Protect your eyes. This is a total hack, but it's in the direction of what we'd like to achieve. Also note that it's a VSCode security violation to load javascript into the markdown preview so maybe just walk away quietly.

- Download `script_test_script.js` and `script_test_stylesheet.css` from [this gist](https://gist.github.com/RossBencina/c922ecc9b7f798a403dca444d76809ee) and put them in the same directory as your markdown file.
- Add the following two lines to the top of your markdown file
```
<script src="script_test_script.js"></script>
<link rel="stylesheet" type="text/css" href="script_test_stylesheet.css">
```
- Change the following VSCode setting to enable javascript execution in markdown preview:
    - Save, close and reopen `your-markdown-file.md`
    - Display markdown preview for `your-markdown-file.md`
    - Click "Some content as been disabled in this document" at top of preview
    - Select "Disable"
This setting will apply to all content in the current workspace including new markdown documents. See the following link for more info:
https://code.visualstudio.com/docs/languages/markdown#_markdown-preview-security

> I think the correct way to do this is to implement a markdown-it plugin and put it in a [VSCode Markdown Extension](https://code.visualstudio.com/api/extension-guides/markdown-extension). But first we need to work out a minimum transformation on the DOM to support the styling that we want. -- Ross