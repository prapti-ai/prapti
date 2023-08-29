
The `capture_everything` plugin stores each interaction with Prapti in a separate file in the specified capture directory.

The following is a minimal prapti user config file (usually located at `~/.config/prapti/config.md` or `~/.prapti/config.md`) that includes the `capture_everything` configuration. You'll need something similar. Recall that if you supply a user config then no fallback config is loaded.

```
% plugins.load openai.chat
% responder.new default openai.chat
% model = "gpt-4-0613"
% temperature = 0.2

% plugins.load prapti.capture_everything
% plugins.prapti.capture_everything.capture_dir = "C:\\Users\\Ross\\Desktop\\prapti-dev\\ross_prapti\\test_capture_everything"
```

This setup will cause all interactions with prapti to be logged. Alternatively, you could  place the `capture_everything` configuration in specific `.prapticonfig.md` files to control capture on a per-project basis.
