## 6. Highlight chat/assistant headings in .md file

To provide some visual cues in the markdown .md file you can get whole-line highlighting for the "system", "user" and "assistant" headings by installing the following extension:

[Highlight extension by Fabio Spampinato](vscode:extension/fabiospampinato.vscode-highlight)

After installing, go to the extension settings and under **Highlight: Regexes** choose **Edit in settings.json** and add the following:

```json
    "highlight.regexes": {
        "(^###\\s@assistant:)": {
            "regexFlags": "gm",
            "filterLanguageRegex": "markdown",
            "decorations": [ {
                "isWholeLine": "true",
                "backgroundColor": "rgba(255, 255, 255, 0.05)" }
            ]
        },
        "(^###\\s@user:)": {
            "regexFlags": "gm",
            "filterLanguageRegex": "markdown",
            "decorations": [ {
                "isWholeLine": "true",
                "backgroundColor": "rgba(0, 0, 0, 0.2)" }
            ]
        },
        "(^###\\s@system:)": {
            "regexFlags": "gm",
            "filterLanguageRegex": "markdown",
            "decorations": [ {
                "isWholeLine": "true",
                "backgroundColor": "rgba(0, 0, 0, 0.2)" }
            ]
        }
    },
```

### 7. Enable markdown preview formatting tweaks

If your chat script includes the `script_test_script.js` and `script_test_stylesheet.css` tags as in `chat-example.md` then you can enable extra colorisation in the markdown preview by enabling the following VSCode setting:

- Display markdown preview for `chat-example.md`
- Click "Some content as been disabled in this document" at top of preview
- Select "Disable"

That will apply to all content in the current workspace including new chat logs. See the following link for more info:
https://code.visualstudio.com/docs/languages/markdown#_markdown-preview-security