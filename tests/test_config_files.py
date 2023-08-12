import pathlib

from prapti.core.execution_state import ExecutionState
from prapti.plugins.prapti_test_responder import TestResponderConfiguration

MINIMAL_PROMPT_MD = """\
### @user:
Hello
"""

MOCK_RESPONDER_CONFIG = """\
Load a responder, but we don't expect this to load
% plugins.load prapti.test.test_responder
% responder.new default prapti.test.test_responder
"""
def test_no_default_config(tmp_path: pathlib.Path, monkeypatch):
    """Test that when the --no-default-config flag is specified, no default responder is loaded"""

    # set up mock user config.md and prapticonfig.md in all the places, so we can check that none of them load

    # set up mocked XDG_CONFIG_HOME and write config.md
    mock_xdg_config_home = tmp_path / "mock_xdg_config_home"
    mock_xdg_config_home.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(mock_xdg_config_home))

    mock_prapti_config_dir_1 = mock_xdg_config_home / "prapti"
    mock_prapti_config_dir_1.mkdir()

    mock_user_home = tmp_path / "mock_user_home"

    mock_prapti_config_dir_2 = mock_user_home / ".config" / "prapti"
    mock_prapti_config_dir_2.mkdir(parents=True)

    mock_prapti_config_dir_3 = mock_user_home / ".prapti"
    mock_prapti_config_dir_3.mkdir(parents=True)

    for mock_prapti_config_dir in (mock_prapti_config_dir_1, mock_prapti_config_dir_2, mock_prapti_config_dir_3):
        (mock_prapti_config_dir / "config.md").write_text(MOCK_RESPONDER_CONFIG, encoding="utf-8")

    # minimal md input file
    temp_md_path = tmp_path / "test_no_default_config.md"
    temp_md_path.write_text(MINIMAL_PROMPT_MD, encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["prapti", "--strict", "--dry-run", "--no-default-config", str(temp_md_path)])

    import prapti.tool
    test_exfil = {}
    exit_status = prapti.tool.main(test_exfil=test_exfil)
    assert exit_status != 0 # expect error: no default responder

    state: ExecutionState = test_exfil["state"]
    assert not hasattr(state.root_config.responders, "default")

def test_fallback_config(tmp_path: pathlib.Path, monkeypatch):
    """Test that when no .prapticonfig.md nor user config.md is present, a default responder is loaded (via the fallback configuration)"""

    # clear XDG_CONFIG_HOME, set up mocked user home directory
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

    mock_user_home = tmp_path / "mock_user_home"
    mock_user_home.mkdir()
    monkeypatch.setenv("HOME", str(mock_user_home))
    def mock_home_func():
        return mock_user_home
    monkeypatch.setattr(pathlib.Path, "home", mock_home_func)

    # leave mock user home empty. i.e. no user config

    # minimal md input file
    temp_md_path = tmp_path / "test_fallback_config.md"
    temp_md_path.write_text(MINIMAL_PROMPT_MD, encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["prapti", "--strict", "--dry-run", str(temp_md_path)])

    import prapti.tool
    test_exfil = {}
    exit_status = prapti.tool.main(test_exfil=test_exfil)
    assert exit_status == 0

    state: ExecutionState = test_exfil["state"]
    assert hasattr(state.root_config.responders, "default")

XDG_CONFIG_HOME_CONFIG = """\
% plugins.load prapti.test.test_responder
% responder.new default prapti.test.test_responder
% responders.default.a_string = "Loaded from $XDG_CONFIG_HOME/prapti/config.md"
"""
def test_load_user_config_from_xdg_config_home(tmp_path: pathlib.Path, monkeypatch):
    """Test loading user config from $XDG_CONFIG_HOME/prapti/config.md when present"""

    # set up mocked XDG_CONFIG_HOME and write config.md
    mock_xdg_config_home = tmp_path / "mock_xdg_config_home"
    mock_xdg_config_home.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(mock_xdg_config_home))

    mock_prapti_config_dir = mock_xdg_config_home / "prapti"
    mock_prapti_config_dir.mkdir()

    (mock_prapti_config_dir / "config.md").write_text(XDG_CONFIG_HOME_CONFIG, encoding="utf-8")

    # minimal md input file
    temp_md_path = tmp_path / "test_load_user_config_from_xdg_config_home.md"
    temp_md_path.write_text(MINIMAL_PROMPT_MD, encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["prapti", "--strict", "--dry-run", str(temp_md_path)])

    import prapti.tool
    test_exfil = {}
    exit_status = prapti.tool.main(test_exfil=test_exfil)
    assert exit_status == 0

    state: ExecutionState = test_exfil["state"]
    assert state.root_config.responders.default.a_string == "Loaded from $XDG_CONFIG_HOME/prapti/config.md"

DEFAULT_XDG_CONFIG_HOME_CONFIG = """\
% plugins.load prapti.test.test_responder
% responder.new default prapti.test.test_responder
% responders.default.a_string = "Loaded from ~/.config/prapti/config.md"
"""
def test_load_user_config_from_default_xdg_config_home(tmp_path: pathlib.Path, monkeypatch):
    """Test loading user config from ~/.config/prapti/config.md when present"""

    # clear XDG_CONFIG_HOME, set up mocked user home directory, and write config.md
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

    mock_user_home = tmp_path / "mock_user_home"
    mock_user_home.mkdir()
    monkeypatch.setenv("HOME", str(mock_user_home))
    def mock_home_func():
        return mock_user_home
    monkeypatch.setattr(pathlib.Path, "home", mock_home_func)

    mock_default_xdg_config_home = mock_user_home / ".config"
    mock_default_xdg_config_home.mkdir()

    mock_prapti_config_dir = mock_default_xdg_config_home / "prapti"
    mock_prapti_config_dir.mkdir()

    (mock_prapti_config_dir / "config.md").write_text(DEFAULT_XDG_CONFIG_HOME_CONFIG, encoding="utf-8")

    # minimal md input file
    temp_md_path = tmp_path / "test_load_user_config_from_default_xdg_config_home.md"
    temp_md_path.write_text(MINIMAL_PROMPT_MD, encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["prapti", "--strict", "--dry-run", str(temp_md_path)])

    import prapti.tool
    test_exfil = {}
    exit_status = prapti.tool.main(test_exfil=test_exfil)
    assert exit_status == 0

    state: ExecutionState = test_exfil["state"]
    assert state.root_config.responders.default.a_string == "Loaded from ~/.config/prapti/config.md"

LEGACY_CONFIG_HOME_CONFIG = """\
% plugins.load prapti.test.test_responder
% responder.new default prapti.test.test_responder
% responders.default.a_string = "Loaded from ~/.prapti/config.md"
"""
def test_load_user_config_from_legacy_config_home(tmp_path: pathlib.Path, monkeypatch):
    """Test loading user config from ~/.prapti/config.md when present"""

    # clear XDG_CONFIG_HOME, set up mocked user home directory, and write config.md
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

    mock_user_home = tmp_path / "mock_user_home"
    mock_user_home.mkdir()
    monkeypatch.setenv("HOME", str(mock_user_home))
    def mock_home_func():
        return mock_user_home
    monkeypatch.setattr(pathlib.Path, "home", mock_home_func)

    mock_prapti_config_dir = mock_user_home / ".prapti"
    mock_prapti_config_dir.mkdir()

    (mock_prapti_config_dir / "config.md").write_text(LEGACY_CONFIG_HOME_CONFIG, encoding="utf-8")

    # minimal md input file
    temp_md_path = tmp_path / "test_load_user_config_from_legacy_config_home.md"
    temp_md_path.write_text(MINIMAL_PROMPT_MD, encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["prapti", "--strict", "--dry-run", str(temp_md_path)])

    import prapti.tool
    test_exfil = {}
    exit_status = prapti.tool.main(test_exfil=test_exfil)
    assert exit_status == 0

    state: ExecutionState = test_exfil["state"]
    assert state.root_config.responders.default.a_string == "Loaded from ~/.prapti/config.md"

XDG_CONFIG_HOME_CONFIG_NO_RESPONDER = """\
% plugins.load prapti.test.test_config
% plugins.prapti.test.test_config.a_string = "Loaded from $XDG_CONFIG_HOME/prapti/config.md"
"""
def test_load_user_config_inhibits_fallback_config(tmp_path: pathlib.Path, monkeypatch):
    """Test that when a user config.md is provided, no fallback default responder is loaded"""

    # set up mocked XDG_CONFIG_HOME and write config.md
    mock_xdg_config_home = tmp_path / "mock_xdg_config_home"
    mock_xdg_config_home.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(mock_xdg_config_home))

    mock_prapti_config_dir = mock_xdg_config_home / "prapti"
    mock_prapti_config_dir.mkdir()

    (mock_prapti_config_dir / "config.md").write_text(XDG_CONFIG_HOME_CONFIG_NO_RESPONDER, encoding="utf-8")

    # minimal md input file
    temp_md_path = tmp_path / "test_load_user_config_inhibits_fallback_config.md"
    temp_md_path.write_text(MINIMAL_PROMPT_MD, encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["prapti", "--strict", "--dry-run", str(temp_md_path)])

    import prapti.tool
    test_exfil = {}
    exit_status = prapti.tool.main(test_exfil=test_exfil)
    assert exit_status == 1 # expect error: no default responder

    state: ExecutionState = test_exfil["state"]
    assert state.root_config.plugins.prapti.test.test_config.a_string == "Loaded from $XDG_CONFIG_HOME/prapti/config.md"

PRAPTI_CONFIG_MD = """\
% plugins.load prapti.test.test_responder
% responder.new default prapti.test.test_responder
% responders.default.a_string = "Loaded from .prapticonfig.md"
"""
def test_prapticonfig_md(tmp_path: pathlib.Path, monkeypatch):
    """Test loading configuration from prapticonfig.md"""

    # clear XDG_CONFIG_HOME, set up empty mocked user home directory
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

    mock_user_home = tmp_path / "mock_user_home"
    mock_user_home.mkdir()
    monkeypatch.setenv("HOME", str(mock_user_home))
    def mock_home_func():
        return mock_user_home
    monkeypatch.setattr(pathlib.Path, "home", mock_home_func)

    # leave mock user home empty. i.e. no user config

    # .prapticonfig.md
    temp_prapticonfig_md_path = tmp_path / ".prapticonfig.md"
    temp_prapticonfig_md_path.write_text(PRAPTI_CONFIG_MD, encoding="utf-8")

    # minimal md input file
    temp_md_path = tmp_path / "test_prapticonfig_md.md"
    temp_md_path.write_text(MINIMAL_PROMPT_MD, encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["prapti", "--strict", "--dry-run", str(temp_md_path)])

    import prapti.tool
    test_exfil = {}
    exit_status = prapti.tool.main(test_exfil=test_exfil)
    assert exit_status == 0

    state: ExecutionState = test_exfil["state"]
    assert state.root_config.responders.default.a_string == "Loaded from .prapticonfig.md"

PRAPTI_CONFIG_MD_NO_RESPONDER = """\
% plugins.load prapti.test.test_config
% plugins.prapti.test.test_config.a_string = "Loaded from .prapticonfig.md"
"""
def test_load_prapticonfig_md_inhibits_fallback_config(tmp_path: pathlib.Path, monkeypatch):
    """Test that when a prapticonfig.md is provided, no fallback default responder is loaded"""

    # clear XDG_CONFIG_HOME, set up empty mocked user home directory
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

    mock_user_home = tmp_path / "mock_user_home"
    mock_user_home.mkdir()
    monkeypatch.setenv("HOME", str(mock_user_home))
    def mock_home_func():
        return mock_user_home
    monkeypatch.setattr(pathlib.Path, "home", mock_home_func)

    # leave mock user home empty. i.e. no user config

    # .prapticonfig.md
    temp_prapticonfig_md_path = tmp_path / ".prapticonfig.md"
    temp_prapticonfig_md_path.write_text(PRAPTI_CONFIG_MD_NO_RESPONDER, encoding="utf-8")

    # minimal md input file
    temp_md_path = tmp_path / "test_load_prapticonfig_md_inhibits_fallback_config.md"
    temp_md_path.write_text(MINIMAL_PROMPT_MD, encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["prapti", "--strict", "--dry-run", str(temp_md_path)])

    import prapti.tool
    test_exfil = {}
    exit_status = prapti.tool.main(test_exfil=test_exfil)
    assert exit_status == 1 # expect error: no default responder

    state: ExecutionState = test_exfil["state"]
    assert state.root_config.plugins.prapti.test.test_config.a_string == "Loaded from .prapticonfig.md"
