%plugins.load local.openai.chat
%responder.new default local.openai.chat

Set the API base address according to the settings of your local LLM server. Some common default values are listed below:

- GPT4ALL: http://localhost:4891/v1
- vLLM: http://localhost:8000/v1
- LocalAI: http://localhost:8080/v1

Here we'll use GPT4ALL:

%local_openai_api_base = "http://localhost:4891/v1"

Depending on the server, you will need to specify the model file either here, or in the server settings:

%model = "ggml-mpt-7b-chat.bin"

%responders.default.max_tokens = 500

Make sure the server is running so that Prapti can use it. For GPT4All, check the "Enable API server" box in Application General Settings.

### @system:

You are a friendly helpful assistant.

### @user:

Hello. Could you help me develop some python code?

### @assistant:

Sure! What is the specific task that you want to accomplish with Python? Can you provide more details about what your project involves, so I can better understand how we might work together on it?

### @user:

Let's start simple. How do I write a program that prints out the numbers from 1 to 5?
