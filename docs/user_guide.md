### @system:

The user is developing end-user documentation for "Prapti" a tool that lets you conduct AI conversations in markdown files. Please assist. The latest revision of the markdown file is given in the_markdown_file system message. Note that the conversation with the user is ongoing and may include references to older revisions of the document.

### @system/the_markdown_file:

# Prapti User Guide

... content goes here ... nothing yet (see below)

### @user:

Hi, we're working on providing user documentation for Prapti. This document we're working on is called `user_guide.md`. I think our first order of business should be to determine what should go in this file.
The target audience is broad. I expect it will be looked at by people who are getting started, but it's probably not their first point of contact.

In order of user contact we already have the following other files:

[README](../README.md) that the user will see when they visit our project page on GitHub.

%include.code "../README.md"

[An introductory usage example](../start_here.md), that the user might look at after the README:

%include.code "../start_here.md"

Then I'd expect that they'd look at the [user guide](user_guide.md) that we're working on right now.

Then we have more specific or more technical content:

%include.code "local_llms.md"

%include.code "editor_tweaks.md"

%include.code "config_files.md"

Finally, our formal markdown specification (for technical readers):

%include.code "prapti_spec.md"

Can you start by suggesting what content we should put in the User Guide, if any?

### @assistant:

Given the existing documentation, the User Guide can serve as a comprehensive manual that combines the essential information from the README and the introductory usage example, while also providing additional context, tips, and best practices. Here's a proposed structure:

# Prapti User Guide

## Table of Contents
1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Prapti Conversations](#prapti-conversations)
4. [Inline Configuration](#inline-configuration)
5. [Advanced Usage](#advanced-usage)
6. [Troubleshooting](#troubleshooting)
7. [Additional Resources](#additional-resources)

## Introduction
- Brief overview of Prapti
- Explanation of the benefits of using Prapti
- Who this guide is for

## Getting Started
- Prerequisites (Python 3.10 or newer)
- Installation instructions
- Setting up OpenAI API key
- Checking that the `prapti` tool runs manually in the terminal
- Setting up a keybinding to run `prapti` in your editor

## Prapti Conversations
- Explanation of how Prapti treats a markdown document as a sequence of "messages"
- How to structure a conversation (use of `@user`, `@assistant`, `@system`, and `@user/name`)
- How to disable messages
- How to use hidden messages

## Inline Configuration
- Explanation of configuration lines and how they provide instructions for processing the message
- How to use configuration lines to trigger actions and set configuration variables
- How to disable configuration lines
- How to use configuration lines in block quotes

## Advanced Usage
- [Explanation of how to use local LLMs with Prapti](local_llms.md)
- [How to make editor tweaks for a better Prapti experience](editor_tweaks.md)
- [How to use Prapti configuration files](config_files.md)

## Troubleshooting
- Common issues and their solutions (ask us on [GitHub Discussions](https://github.com/prapti-ai/prapti/discussions))
- How to report bugs (use [GitHub Issues](https://github.com/prapti-ai/prapti/issues))

## Additional Resources
- [Link to the formal syntax spec for technical readers](prapti_spec.md)
- [Link to the Prapti GitHub repository for updates and discussions](https://github.com/prapti-ai/prapti)
- Contact information for support (use [GitHub Discussions](https://github.com/prapti-ai/prapti/discussions))

This structure provides a comprehensive guide for users, starting from the basics and gradually introducing more advanced topics. It also provides resources for troubleshooting and further learning.

### @user:

Ok that sounds good. But I'd like to minimise repetition because it makes it difficult to maintain the documentation. The user can refer to the [README](../README.md) and [your first prapti conversation](../start_here.md) for an introduction and setup instructions.

For now, let's focus on the two sections "Prapti Conversations" and "Inline Configuration". I think these are the most important to cover in this User Guide. I've added links for the later sections.

Could you write the "Prapti Conversations" section for me please?

### @assistant:

Sure, here's a draft for the "Prapti Conversations" section:

## Prapti Conversations

Prapti treats a markdown document as a sequence of "messages". These messages form the basis of a conversation with the Large Language Model (LLM). In this section, we'll explain how to structure a conversation and use different types of messages.

### Structuring a Conversation

In Prapti, a conversation is structured using level-3 headings (`###`) to delimit messages within the markdown file. Each message starts with a message heading and continues until the next message heading, or until the end of the document if there is no subsequent message heading.

The basic structure of a Prapti message heading is `### @role/name:`, where `/name` is optional. The `role` typically represents the sender of the message and can be `user`, `assistant`, or `system`. However, the interpretation of roles depends on the responder that processes the messages.

Here's an example of a simple conversation:

```markdown
### @user:
Hello, how are you?

### @assistant:
I'm an AI, so I don't have feelings, but I'm here to help you. How can I assist you today?
```

### Using Names

The `name` is an optional suffix to the `role`, separated by a forward slash (`/`). For example, `@user/Ross`. The usage of the `name` varies depending on the configuration. In the context of OpenAI chat completions, names attached to `user` and `system` messages are passed to the LLM. This can be useful for personalizing the conversation or distinguishing between different users.

```markdown
### @user/Ross:
Can you tell me the weather?

### @assistant:
Sure, Ross. I can do that, but I'll need to know your location first.
```

### Disabling Messages

A message can be disabled by adding a double forward slash (`//`) before the `@` symbol in the heading. For example, `### //@user:`. Disabled messages behave as if they are "commented out". They are not passed to the LLM and are ignored during processing.

```markdown
### @user:
What's the capital of France?

### //@assistant:
The capital of France is Paris.
```

In this example, the assistant's message is disabled and will not be processed.

### Hidden Messages

A role can also start with an underscore (`_`), indicating a "hidden" role. Messages with hidden roles are not sent directly to the Large Language Model (LLM), but their inline configuration is processed. Some plugins may define hidden roles for specific purposes.

```markdown
### @_aside:
This message will not be sent to the LLM.
```

In this example, the message with the `_aside` role is hidden and will not be processed by the LLM.

Remember, you can always refer back to the [your first prapti conversation](../start_here.md) for a practical example of how to structure a conversation.

### @user:

That looks great. [I should warn you that those examples in fenced code blocks look fine here, but you're probably going to get scrambled input from them since we're not properly escaping them yet.]

Could you write the "Inline Configuration" section please. Keep it short since the details are in flux.

% responders.default.max_tokens = 900

### @assistant:

Absolutely, here's a draft for the "Inline Configuration" section:

## Inline Configuration

Prapti allows you to control the behavior of the tool and the LLM directly within your markdown file using inline configuration lines. These lines start with a percent symbol (`%`) and can be used to trigger actions or set configuration variables.

### Basic Syntax

The basic syntax of a configuration line is `% <command-string>`. The text following the `%` symbol is interpreted by Prapti (including loaded plugins) prior to querying the LLM. For example, you can change the temperature setting of the LLM as follows:

```markdown
% temperature = 0.8
```

Another common use of configuration lines is to change the model:

```markdown
% model = "gpt-4"
```

### Disabling Configuration Lines

Configuration lines can be disabled by adding a double forward slash (`//`) before the `%` symbol. For example, `//% temperature = 0.6`. Disabled configuration lines are ignored during processing, behaving as if they are "commented out".

### Configuration Lines in Block Quotes

Configuration lines can also appear inside a markdown block quote. In this case, the configuration line is preceded by a `>` symbol. For example, `> % temperature = 0.7`. The command is processed in the same way as it would be outside of a block quote.

Please note that the precise details of parameter assignment and command/action invocation are in flux. For the most up-to-date information, please refer to the [Prapti Markdown Specification](prapti_spec.md).

### @user:

