# Prapti Markdown Specification

DRAFT. Last updated July 10, 2023.

> This document provides a technical specification of Prapti's interpretation of markdown files. If you're a new user, do not start here, check the [User Guide](user_guide.md) instead.

Prapti aims to be 100% compatible with standard [CommonMark](https://commonmark.org/) markdown files. In addition to the standard CommonMark specifications, Prapti gives additional meaning to certain text elements as described below.

## Document Structure and Interpretation

Prapti treats a markdown document as a sequence of "messages". Messages are the fundamental units of interaction in Prapti and are used to represent an exchange of information in a conversation.

Each message is a sequence of text spans interspersed with configuration lines. The text spans form the content of the message, while the configuration lines provide instructions for processing the message.

Messages are delimited by special level-3 headings, referred to as "message headings". Each message starts with a message heading and continues until the next message heading, or until the end of the document if there is no subsequent message heading.

The first part of the document, preceding the first message heading, is treated as a hidden message with the role `_head`. This allows configuration lines at the start of the document to be processed. Since `_head` is a hidden message, it is not passed to the Large Language Model (LLM), but it can be used by plugins and for setting configuration parameters.


## Message Headings

Prapti uses level-3 headings (`###`) to delimit messages within the markdown file. However, not all level-3 headings are treated as message delimiters. Only headings that follow a specific syntax are recognized as Prapti messages. The basic structure of a Prapti message heading is `### @role/name:`, where `/name` is optional. All other headings are treated as part of the text stream.

### Role

The `role` typically represents the sender of the message and can be `user`, `assistant`, or `system`. However, the interpretation of roles depends on the responder that processes the messages.

A role can also start with an underscore (`_`), indicating a "hidden" role. Messages with hidden roles are not sent directly to the Large Language Model (LLM), but their inline configuration is processed. Some plugins may define hidden roles for specific purposes.

### Name

The `name` is an optional suffix to the `role`, separated by a forward slash (`/`). For example, `@user/Ross`. The usage of the `name` varies depending on the configuration. In the context of OpenAI chat completions, names attached to `user` and `system` messages are passed to the LLM.

### Disabled Messages

A message can be disabled by adding a double forward slash (`//`) before the `@` symbol in the heading. For example, `### //@user:`. Disabled messages behave as if they are "commented out". They are not passed to the LLM and are ignored during processing.

### Example

Here is an example of how these elements can be used in a markdown file:

```markdown
### @user/Ross:
Hello, how are you?

### @_aside:
This message will not be sent to the LLM.

Configuration lines in hidden messages will be processed. The following line will change the model.
% model = "gpt-4"

### //@user:
This message is disabled and will be ignored, including any inline configuration.
```

In this example, the first message is from a `user` named `Ross`, the second message is a hidden message with role `_aside`, and the third message is a disabled `user` message.


## Single-Line Configuration Lines

Configuration lines are a special type of line in Prapti markdown files that start with a percent symbol (`%`). These lines are used to configure the behavior of the tool. Configuration lines may cause an action to be executed (command/action lines), or may assign a value to a configuration parameter.

When commands are interpreted, their corresponding line in the message text will be removed and replaced with the output of the command, which may be empty. For instance, an `%include` command may return text read from a file, and this text would be inserted at the location where the command appears. Commands can have other side effects, but it is important to note that the raw command line, as written by the user, is never passed to the LLM.

### Basic Syntax

The basic syntax of a configuration line is `% <command-string>`. The text following the `%` symbol is interpreted by Prapti (including loaded plugins) prior to querying the LMM.

### Disabled Configuration Lines

Configuration lines can be disabled by adding a double forward slash (`//`) before the `%` symbol. For example, `//% command`. Disabled configuration lines are ignored during processing, behaving as if they are "commented out". As for normal configuration lines, disabled configuration lines are never passed to the LLM.

### Configuration Lines in Block Quotes

Configuration lines can also appear inside a markdown block quote. In this case, the configuration line is preceded by a `>` symbol. For example, `> % command`. The command is processed in the same way as it would be outside of a block quote.

### Example

Here is an example of how these elements can be used in a markdown file:

```markdown
% temperature = 0.8

//% temperature = 0.6

> % temperature = 0.7

% plugins.load prapti.include
```

In this example, the first line sets the temperature to 0.8. The second line is a disabled configuration line and is ignored during processing. The third line sets the temperature to 0.7 and is formatted inside a block quote. The fourth line runs the `plugins.load` action to load the `prapti.include` plugin.

> NOTE: the precise details of parameter assignment and command/action invocation are in flux but the general idea is that `%identifier = literal` is interpreted as an assignment to a field in the configuration parameters tree, and `%identifier ...` is interpreted as a command that executes an action in the namespace of registered actions.


## Future Directions

In future, Prapti might...

- Ignore configuration lines inside fenced blocks (and pass them to the LLM uninterpreted)
- Treat HTML comments `<!-- -->` as disabled spans (1) ignore configuration lines inside them, and (2) don't pass the commented-out text to the LLM.
- Support multi-line configuration lines. These would begin with `%%` and capture subsequent lines for processing by the command/action (not sure what "subsequent lines" means yet, but could be to end-of-block-element or end-of-message.)
- Treat roles as case insensitive to support @User: @user: and @USER: as equivalent.
- Clarify whether `user`, `assitant` and `system` have globally well-specified semantics or whether they are just an artefact of the implementation
