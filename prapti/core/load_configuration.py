"""
    Find and load configuration files:
    - at specified location
    - `config.md` at defined locations within the user's home directory
    - `.prapticonfig.md` from directory containing input file, and parent directories
"""
import os
import pathlib

from .logger import DiagnosticsLogger
from ..core.execution_state import ExecutionState
from ..core.command_message import Message
from ..core.chat_markdown_parser import parse_messages
from ..core.command_interpreter import interpret_commands, is_config_root

FALLBACK_CONFIG_FILE_DATA = """\
% plugins.load openai.chat
% responder.new default openai.chat
"""

def parse_messages_and_interpret_commands(lines: list[str], file_path: pathlib.Path, state: ExecutionState):
    message_sequence: list[Message] = parse_messages(lines, file_path)
    interpret_commands(message_sequence, state)
    state.message_sequence += message_sequence

def load_config_file(config_path: pathlib.Path, state: ExecutionState) -> bool:
    """Load the config file specified by `config_path` into `state`, if it exists.
    return `True` if the config file exists as a file, whether or not it
    loads without error.
    """
    if config_path.is_file():
        state.log.info("loading-config-file", "loading configuration file", config_path)
        state.config_file_paths.append(config_path)
        try:
            config_file_lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
            parse_messages_and_interpret_commands(config_file_lines, config_path, state)
        except Exception as ex:
            state.log.error("config-file-exception", f"exception while loading configuration file: {repr(ex)}", config_path)
            state.log.logger.debug(ex, exc_info=True)
        return True
    return False

def locate_user_prapti_config_dir(log: DiagnosticsLogger) -> pathlib.Path | None:
    """Compute the location of the user's prapti config directory.

    If the XDG_CONFIG_HOME environment variable is set and not empty,
    the user config dir must be located at:
        $XDG_CONFIG_HOME/prapti

    Otherwise, search the following locations in order:
        ~/.config/prapti (the XDG-compatible default location)
        ~/.prapti (the legacy location)

    The first location that exists will be used.
    """
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME", None)
    if xdg_config_home: # set, not empty
        log.detail("using user config dir '$XDG_CONFIG_HOME/prapti' because the XDG_CONFIG_HOME environment variable is set")
        xdg_config_home_path = pathlib.Path(xdg_config_home)
        if xdg_config_home_path.exists() and xdg_config_home_path.is_dir():
            result = xdg_config_home_path / "prapti"
        else:
            log.warning("bad-xdg-config-home", f"will not load user config. XDG_CONFIG_HOME environment variable is set to '{xdg_config_home}' but this is not an existing directory")
            return None
    else: # XDG_CONFIG_HOME environment var empty or not set
        # try the default XDG path
        log.detail("checking for user config dir at '$HOME/.config/prapti'")
        default_xdg_config_home = pathlib.Path.home() / ".config"
        if (default_xdg_config_home / "prapti").exists():
            # if there is an XDG-compatible prapti directory, always use it, don't check $HOME/.prapti
            result = default_xdg_config_home / "prapti"
        else:
            # fall back to legacy configuration file location
            log.detail("checking for user config dir at '$HOME/.prapti'")
            result = pathlib.Path.home() / '.prapti'

    if result.exists() and result.is_dir():
        log.detail(f"using user config dir '{result}'")
        return result
    else:
        log.detail("no user config dir found (not a problem unless you thought you'd created one)")
        return None

def locate_user_config_file(prapti_user_config_dir: pathlib.Path, log: DiagnosticsLogger) -> pathlib.Path | None:
    """Compute the location of the user's prapti `config.md` file.
    The `config.md` file must be located in the user config directory determined by
    `locate_user_prapti_config_dir()`
    """
    result = prapti_user_config_dir / "config.md"
    if result.exists() and result.is_file():
        log.detail(f"using user config.md file '{result}'")
        return result
    else:
        log.detail("no user config.md file found (not a problem unless you thought you'd created one)")
        return None

def locate_and_parse_in_tree_prapticonfig_md_files(state: ExecutionState) -> tuple[bool, list[tuple[pathlib.Path, list[Message]|None]]]:
    """Search for in-tree `.prapticonfig.md` files and parse each file.
    Algorithm: (.editorconfig algorithm) starting from the directory containing the input markdown file,
    check for `.prapticonfig.md` files. Iterate upwards through parent directories, terminate at the root,
    or when a config file sets config_root = true (but do not load/execute the config file at this step).
    Return `True` if a config file exists as a file, whether or not it loads without error.
    Returns a list of valid config file paths and their associated message sequence (if any), the order
    of returned paths starts from the directory that contains the input file, and proceeds towards the root.
    """
    found_config_file = False
    prapticonfig_mds: list[tuple[pathlib.Path, list[Message]|None]] = [] # [(config_path, message_sequence)]
    # find and parse .prapticonfig.md files
    for parent in state.input_file_path.resolve().parents: # traverse from containing dir to root
        config_path = parent / ".prapticonfig.md"
        message_sequence: list[Message]|None = None
        if config_path.is_file():
            found_config_file = True
            state.log.detail("reading-in-tree-config", "reading configuration file", config_path)
            try:
                config_file_lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
                message_sequence = parse_messages(config_file_lines, config_path)
            except Exception as ex:
                state.log.error("read-config-file-exception", f"exception while reading configuration file: {repr(ex)}", config_path)
                state.log.logger.debug(ex, exc_info=True)
        prapticonfig_mds.append((config_path, message_sequence))
        if message_sequence and is_config_root(message_sequence): # stop once we hit a config file with `%config_root = true`
            break
    return found_config_file, prapticonfig_mds

def execute_in_tree_prapticonfig_md_files(prapticonfig_mds: list[tuple[pathlib.Path, list[Message]|None]], state: ExecutionState) -> None:
    """Using the list of .prapticonfig.md files parsed by locate_and_parse_in_tree_prapticonfig_md_files,
    run the commands in each file. Execute each found config file starting with the file closest to the root.
    """
    state.root_config.prapti.config_root = False
    for config_path, message_sequence in reversed(prapticonfig_mds):
        if message_sequence:
            try:
                state.log.info("loading-in-tree-config", "loading configuration file", config_path)
                state.config_file_paths.append(config_path)
                interpret_commands(message_sequence, state)
                state.message_sequence += message_sequence
                state.root_config.prapti.config_root = False
            except Exception as ex:
                state.log.error("load-config-file-exception", f"exception while loading configuration file: {repr(ex)}", config_path)
                state.log.logger.debug(ex, exc_info=True)

def default_load_config_files(state: ExecutionState):
    """Default configuration loading. Load configuration from:
    - `$XDG_CONFIG_HOME/prapti/config.md` or `~/.config/prapti/config.md` or  `~/.config/prapti/config.md`
    - then `.prapticonfig.md` in containing directories up to when %config_root = true
    - if no config files found, fallback to FALLBACK_CONFIG_FILE_DATA (just so that we work out of the box)

    Stores configuration directory paths in `state.user_prapti_config_dir` and `state.prapticonfig_dirs`
    """
    found_config_file = False

    # user home config.md
    state.user_prapti_config_dir = locate_user_prapti_config_dir(state.log)
    if state.user_prapti_config_dir:
        if user_config_file_path := locate_user_config_file(state.user_prapti_config_dir, state.log):
            found_config_file |= load_config_file(user_config_file_path, state)

    # in-tree .prapticonfig.md files
    _found_config_file, prapticonfig_mds = locate_and_parse_in_tree_prapticonfig_md_files(state)
    found_config_file |= _found_config_file
    state.prapticonfig_dirs = [config_path.parent for config_path, _ in prapticonfig_mds]
    execute_in_tree_prapticonfig_md_files(prapticonfig_mds, state)

    # if no config file is present, use fallback config
    if not found_config_file:
        state.log.info("loading-fallback-config", "loading fallback configuration", state.input_file_path)
        parse_messages_and_interpret_commands(FALLBACK_CONFIG_FILE_DATA.splitlines(keepends=True), pathlib.Path("<fallback-config>"), state)
