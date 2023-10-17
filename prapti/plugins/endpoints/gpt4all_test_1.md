# Minimal GPT4All Prapti Configuration

[GPT4All](https://gpt4all.io/index.html) is a CPU-based LLM inference engine. To use GPT4All with Prapti you'll need to download a GGML model that is compatible with GPT4All. The easiest way to do this is to install the GPT4All GUI and use its built-in downloader to get a compatible model.

Note that you *do not* need to install the GPT4All GUI to use this Prapti responder. However you *do* need to download a compatible model file.

We believe that you can also download models from Hugging Face but you should ask the GPT4All community about that.

### Load GPT4All responder plugin

>%plugins.load experimental.gpt4all.chat
>%responder.new default experimental.gpt4all.chat

### Specify model path

The first thing that you need to do is specify the path where your GPT4All models are located. If you're using the GPT4All GUI, go to "Downloads" and the download path will be displayed. If you downloaded a model yourself, write the directory that contains your model.

>%responders.default.model_path = "F:/gpt4all/AppData/Local/nomic.ai/GPT4All/"

### Specify model file

Now specify the model file name. It must be a model file that exists in the directory that you specified above for `model_path`.

>%responders.default.model_name = "nous-hermes-13b.ggmlv3.q4_0.bin"

We also tried the following model. The `//` means the following configuration line is disabled.
>//%responders.default.model_name = "wizardLM-13B-Uncensored.ggmlv3.q4_0.bin"

### Additional parameters

Set n_threads according to the number of performance cores available on your machine. Or comment out that line (`//`) to let GPT4All decide.

%responders.default.n_threads = 8
%responders.default.streaming = true
%responders.default.temp = 1

### @user:

What is the largest known fish?
