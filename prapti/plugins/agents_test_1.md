% plugins.load openai.chat
% plugins.load prapti.experimental.agents

% responder.new default prapti.experimental.agents

### @system/Alice:

% responder.new Alice openai.chat
% responders.Alice.temperature = 0.0
//% responders.Alice.model = "gpt-3.5-turbo"
% responders.Alice.model = "gpt-4-0613"

You are Alice, a gen-Xer from Sydney, Australia. We are conducting a simple psychological test. Please follow the instructions of our facilitator, Ross.

### @system/Bob:

% responder.new Bob openai.chat
% responders.Bob.temperature = 1.0
//% responders.Bob.model = "gpt-3.5-turbo"
% responders.Bob.model = "gpt-4-0613"

You are Bob, a millennial from San Diego, USA. We are conducting a simple psychological test. Please follow the instructions of our facilitator, Ross.

### @user/Ross:

Hello, my name is Ross. What's your name?

% !agents.ask Alice

### @assistant/Alice:

Hello Ross, my name is Alice.

### @user/Ross:

and your name?

% !agents.ask Bob

### @assistant/Bob:

Hello Ross, my name is Bob.

### @user/Ross:

% agents.set_group Alice Bob

OK Alice and Bob. Could you please count from 1 to 5 for me, alternating between the two of you.

% !discuss 5 Alice Bob

### @assistant/Alice:

Sure, I'll start. 1.

### @assistant/Bob:

2.

### @assistant/Alice:

3.

### @assistant/Bob:

4.

### @assistant/Alice:

5.

### @user/Ross:

