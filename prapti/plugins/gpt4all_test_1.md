# Minimal GPT4All Prapti Configuration

[GPT4All](https://gpt4all.io/index.html) is a CPU-based LLM inference engine. To use this with Prapti you'll need to download a GGML model that is compatible with GPT4All. The easiest way to do this is to install the GPT4All GUI and use their downloader to get a compatible model.

Note that you *do not* need to install the GPT4All GUI to use this Prapti responder. However you *do* need to download a compatible model file.

I believe that you can also download models from Hugging Face but you should ask the GPT4All community about that.

### Load GPT4All responder plugin

>%plugins.load experimental.gpt4all.chat
>%responder.new default experimental.gpt4all.chat

### Specify model path

The first thing you need to do is specify the path where your GPT4All models are located. If you're using the GPT4All GUI, go to settings and it will tell you the path. If you downloaded a model yourself, just put the directory you put the model in. I put mine in:

>%responders.default.model_path = "F:/gpt4all/AppData/Local/nomic.ai/GPT4All/"

### Specify model file

Now specify the model file name. It must be a file that exists in the directory that you specified above for `model_path`.

>%responders.default.model_name = "ggml-mpt-7b-chat.bin"

I also tried this one, but the `//` means the configuration line is disabled.
>//%responders.default.model_name = "wizardLM-13B-Uncensored.ggmlv3.q4_0.bin"

### Additional parameters

Probably don't specify 24 threads unless you have a multicore CPU.

%responders.default.n_threads = 24
%responders.default.streaming = True
%responders.default.temp = 1

### @user:

What is the largest known fish?
