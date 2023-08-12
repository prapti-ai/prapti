# Prapti Configuration Files

Prapti uses configuration files to store setup details and parameter settings. These files are regular Prapti markdown files that are loaded before the input markdown file. If no configuration files are found, Prapti uses an internal fallback configuration.

## Default Configuration File Search

Before processing the input markdown file, Prapti searches for configuration files. The search process includes:

1. Loading a user configuration file from the user's home directory, if such a file exists. The following locations are searched: `$XDG_CONFIG_HOME/prapti/config.md`, `~/.config/prapti/config.md`, and `~/.prapti/config.md`. Only the first user configuration file that is found is loaded. If the `$XDG_CONFIG_HOME` environment variable is set, only the first location is included in the search.
2. Searching for `.prapticonfig.md` files in the directory of the input markdown file and its parent directories. This search continues upwards until a configuration file with a line `% config_root = true` is found. These files form the in-tree configuration file set.
3. Loading the in-tree configuration files, starting from the root and moving towards the input file's directory. This way, settings in `.prapticonfig.md` files closer to the input file take precedence over settings from files closer to the root.

## Fallback Configuration

If no configuration files are found, Prapti loads a fallback configuration to ensure smooth operation. At the time of writing, this configuration is the minimum requirement to use the OpenAI chat completions API:

```
% plugins.load openai.chat
% responder.new default openai.chat
```

Any supplied configuration file should contain this or an equivalent set-up.

## Disabling Default Configuration

The `--no-default-config` command line option disables the default configuration file search and the fallback configuration. This is useful for providing a different configuration file or working in isolation in the input markdown file.

## Specifying Additional Configuration Files

The `--config-file` command line option specifies one or more configuration files. These files are loaded after any default configuration files. If multiple configuration files are supplied, they are loaded in the order they are specified on the command line.

## Configuration File Structure

Configuration files are standard Prapti markdown files containing messages and configuration lines. A file with only configuration would not contain any message headings, but it's valid to include messages in the configuration file. Such messages will be passed to the AI. For example, it may be useful to incorporate a system message in a configuration file.
