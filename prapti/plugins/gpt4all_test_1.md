%plugins.load experimental.gpt4all.chat
%responder.new default experimental.gpt4all.chat
%responders.default.model_name = "ggml-mpt-7b-chat.bin"
//%responders.default.model_name = "wizardLM-13B-Uncensored.ggmlv3.q4_0.bin"
%responders.default.model_path = "F:/gpt4all/AppData/Local/nomic.ai/GPT4All/"
%responders.default.n_threads = 24
%responders.default.streaming = True
%responders.default.temp = 1

### @user:

What is the largest known fish?
