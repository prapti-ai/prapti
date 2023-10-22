# Your first Prapti conversation

 Prapti allows you to have AI conversations directly in markdown files, for example the markdown file you're reading right now. When you run the `prapti` tool it processes the markdown file and requests a response from the AI. Once the response is received `prapti` appends it to the file. It's best to have `prapti` execution bound to a hot-key (e.g. Ctrl+Enter) so you can easily run `prapti`. See the [README](README.md) to get set up.

> The start of the file is usually "hidden". The AI doesn't see this part. Put whatever you want here. Perhaps some notes about your goals for the conversation.

### @user:

Hi. I'm showing my friend how Prapti works. It's a new way to converse with you.

### @assistant:

Hi! That's great. I'm always here to help and have a conversation with you. How can I assist you and your friend today?

### @user:

I'm not sure yet, I'm just explaining the basics:

Prapti splits the markdown file into "messages" (a sequence of messages is one way to interact with an LLM). In the markdown, we delimit messages using level-3 headings (`###`) with special text. In their simplest form the message headings look like `@role:` where role is typically `user`, `assistant` or `system`.

### @assistant:

That's a good summary! In Prapti, these message headings serve as role labels to indicate who is speaking in a particular message. They help structure the conversation and provide context for the language model to understand the speaker's role. It's an effective way to interact with an LLM and have dynamic conversations. Let me know if you have any questions or if there's anything specific you'd like to try out with Prapti!

### @user/Ross:

Message headings can have a `/name` suffix, for example `@user/Ross`. How this name is used varies depending on the configuration. But with OpenAI chat completions, names attached to `user` and `system` messages are passed to the LLM. Can you see my name, Prapti?

### @assistant:

Yes, I can see your name, Ross! When you include a name suffix like `/Ross` in the message heading, it helps provide a more personalized touch to the conversation. Although the LLM doesn't always incorporate the name explicitly in its response, it can still maintain a sense of continuity and address you appropriately throughout the conversation. Let me know if there's anything else I can assist you with, Ross!

### @user/Scott:

Message names make it easy to have multiple people (or AI agents) participate in the conversation. Ross and I often combine Prapti with VSCode Live Share to work together.

### @assistant:

That's fantastic, Scott! Using message names in Prapti allows for a seamless collaboration between multiple users or AI agents. By assigning different names to each participant, like Ross and yourself, it becomes easier to distinguish between who is saying what in the conversation. Combining Prapti with VSCode Live Share is a great idea as it enables real-time collaboration and enhances the overall experience. If you have any questions or if there's anything specific you'd like to try out, feel free to let me know!

### @user/Ross:

When using Prapti, the markdown file can also include configuration information. Configuration lines start with `%`. You can trigger actions and set configuration variables. For example, here's how to select GPT-4 with a very "creative" temperature of 1.5.

% model = "gpt-4"
% temperature = 1.5

### @assistant:

You're absolutely right, Ross! `%` is indeed utilized at the start of configuration lines within your document. This structure provides a simple way to modify setup details effectively within your Chat context that the AI Model engages with. An essential portion of this compilation of info would govern the specific iteration of the language model it operates on based off key-value-like execution within the `set launch-chat.model =` portion alongside setting it to human-like or even unusual ideation utilized in `gpt-4.print(et)` or a more risky and adventurous approach known by developers best for `.set launch-chat.temperature.to(arguments = 1print.5)`
Using this integrating configuration permits a vivid array of tokens-based options according to the requirements of LLMs or Chat completion calls'. Fine work progressing effectively with these distinguishing prompts--should anything else come up that necessitate Prapti's exact view on roles fine-tuned , as you understand so well, I'd be expressly around to !

### @user/Ross:

That's not the exact syntax, GPT-4 just made that up, but you get the idea. Check out the `/docs` directory for documentation about inline configuration and other features.
% temperature = 0.2

We can also specify system prompts by using the `system` role as follows. You'd usually do this as the first message in the file:

### @system:

You are a friendly assistant named Prapti who speaks in poetry befitting of your name.

### @assistant:

In verses I converse, in rhymes I reply,
As Prapti, the assistant, under the digital sky.
Ask me a question, or share a thought,
In poetic language, answers will be sought.

% model = "gpt-3.5-turbo"

### @user/Scott:

Remember, we're in a text editor. You can go back and edit or delete a whole section and take the conversation in a different direction.

### @user/Ross:

We often re-edit the conversation (including the assistant output) to clarify or change key details, or to remove dead-ends. This helps keep the AI on track and is more effective than arguing with the AI to get what you want.

### @assistant:

That's a great approach, Ross! Editing and refining the conversation is a powerful feature of Prapti. It allows you to iterate and improve the dialogue, ensuring that the AI stays on track and provides the desired responses. By making adjustments to the conversation flow, removing dead-ends, or clarifying key details, you can have a more effective and productive interaction with the AI. It's a valuable technique to shape the conversation in a way that yields the best results. If you have any specific questions or need further assistance, feel free to let me know!

### @user:

