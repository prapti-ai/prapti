import importlib.metadata
import pydantic
from prapti.core.execution_state import ExecutionState
from prapti.core.plugin import Plugin
from prapti.core.builtins import installed_plugin_entry_points
from prapti.plugins.prapti_test_config import TestConfigConfiguration
from prapti.plugins.prapti_test_responder import TestResponderConfiguration

def test_test_plugins_available():
    """Test that the test plugins are available"""
    assert "prapti.test.test_config" in installed_plugin_entry_points
    assert "prapti.test.test_responder" in installed_plugin_entry_points
    assert "prapti.test.test_actions" in installed_plugin_entry_points

def test_entry_point_names_are_consistent_with_plugin_names():
    """A plugin's entry point name is set in `pyproject.toml`, whereas the plugin name is set
    in the prapti_plugin instance in the module containing the plugin.
    The two names must match. Prapti's plugin loading code depends on it."""
    entry_point: importlib.metadata.EntryPoint
    for _, entry_point in installed_plugin_entry_points.items():
        plugin: Plugin = entry_point.load()
        assert entry_point.name == plugin.name

LOAD_PlUGIN_PROMPT = """\
% plugins.load prapti.test.test_config
### @user:

Hello
"""
def test_load_plugin(tmp_path, no_user_config, monkeypatch):
    """Test loading a plugin"""
    temp_md_path = tmp_path / "test_load_plugin_temp.md"
    temp_md_path.write_text(LOAD_PlUGIN_PROMPT, encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["prapti", "--halt-on-error", "--dry-run", str(temp_md_path)])

    import prapti.tool
    test_exfil = {}
    exit_status = prapti.tool.main(test_exfil=test_exfil)
    assert exit_status == 0

    state: ExecutionState = test_exfil["state"]
    # test that plugin config was created in the expected location in the config tree:
    config: TestConfigConfiguration = state.root_config.plugins.prapti.test.test_config
    assert isinstance(config, pydantic.BaseModel)
    # check initial values
    assert config.a_bool == False
    assert config.an_int == 0
    assert config.a_float == 0.0
    assert config.a_string == "test"
    assert config.a_list_of_strings == []

SET_PLUGIN_CONFIG_FIELDS_PROMPT = """\
% plugins.load prapti.test.test_config
% plugins.prapti.test.test_config.a_bool = true
% plugins.prapti.test.test_config.an_int = 42
% plugins.prapti.test.test_config.a_float = 0.5
% plugins.prapti.test.test_config.a_string = "hello"
% plugins.prapti.test.test_config.a_list_of_strings = ["one", "two", "three"]
### @user:

Hello
"""
def test_set_plugin_config_fields(tmp_path, no_user_config, monkeypatch):
    """Test setting plugin config fields from markdown"""
    temp_md_path = tmp_path / "test_set_plugin_config_fields_temp.md"
    temp_md_path.write_text(SET_PLUGIN_CONFIG_FIELDS_PROMPT, encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["prapti", "--halt-on-error", "--dry-run", str(temp_md_path)])

    import prapti.tool
    test_exfil = {}
    exit_status = prapti.tool.main(test_exfil=test_exfil)
    assert exit_status == 0

    state: ExecutionState = test_exfil["state"]
    config: TestConfigConfiguration = state.root_config.plugins.prapti.test.test_config
    # check values set in the markdown file:
    assert config.a_bool == True
    assert config.an_int == 42
    assert config.a_float == 0.5
    assert config.a_string == "hello"
    assert config.a_list_of_strings == ["one", "two", "three"]

NEW_RESPONDER_PROMPT = """\
% plugins.load prapti.test.test_responder
% responder.new default prapti.test.test_responder
### @user:

Hello
"""
def test_new_responder(tmp_path, no_user_config, monkeypatch):
    """Test creating a responder"""
    temp_md_path = tmp_path / "test_new_responder_temp.md"
    temp_md_path.write_text(NEW_RESPONDER_PROMPT, encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["prapti", "--halt-on-error", "--dry-run", "--no-default-config", str(temp_md_path)])

    import prapti.tool
    test_exfil = {}
    exit_status = prapti.tool.main(test_exfil=test_exfil)
    assert exit_status == 0

    state: ExecutionState = test_exfil["state"]
    # test that plugin config was created in the expected location in the config tree:
    config: TestResponderConfiguration = state.root_config.responders.default
    # check initial values
    assert config.a_bool == False
    assert config.an_int == 0
    assert config.a_float == 0.0
    assert config.a_string == "test"
    assert config.a_list_of_strings == []

TEST_SET_RESPONDER_CONFIG_FIELDS_PROMPT = """\
% plugins.load prapti.test.test_responder
% responder.new default prapti.test.test_responder
% responders.default.a_bool = true
% responders.default.an_int = 42
% responders.default.a_float = 0.5
% responders.default.a_string = "hello"
% responders.default.a_list_of_strings = ["one", "two", "three"]
### @user:

Hello
"""
def test_set_responder_config_fields(tmp_path, no_user_config, monkeypatch):
    """Test setting responder config fields from markdown"""
    temp_md_path = tmp_path / "test_set_plugin_config_fields_temp.md"
    temp_md_path.write_text(TEST_SET_RESPONDER_CONFIG_FIELDS_PROMPT, encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["prapti", "--halt-on-error", "--dry-run", "--no-default-config", str(temp_md_path)])

    import prapti.tool
    test_exfil = {}
    exit_status = prapti.tool.main(test_exfil=test_exfil)
    assert exit_status == 0

    state: ExecutionState = test_exfil["state"]
    config: TestResponderConfiguration = state.root_config.responders.default
    # check values set in the markdown file
    assert config.a_bool == True
    assert config.an_int == 42
    assert config.a_float == 0.5
    assert config.a_string == "hello"
    assert config.a_list_of_strings == ["one", "two", "three"]

TEST_SET_LATE_BOUND_VARS_PLUGIN_PROMPT = """\
% plugins.load prapti.test.test_responder
% responder.new default prapti.test.test_responder
% plugins.prapti.test.test_responder.an_int = var(intvar)
% plugins.prapti.test.test_responder.a_string = var(stringvar)
% vars.intvar = 1024
% vars.stringvar = "test 1 2 3"
### @user:

Hello
"""
# ^^^ tests both qualified (vars.) and unqualified variable assignment
def test_set_late_bound_vars_plugin_config(tmp_path, no_user_config, monkeypatch):
    """Test setting a late bound vars and checking that they are used in responder"""
    temp_md_path = tmp_path / "test_set_late_bound_vars_temp.md"
    temp_md_path.write_text(TEST_SET_LATE_BOUND_VARS_PLUGIN_PROMPT, encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["prapti", "--halt-on-error", "--dry-run", "--no-default-config", str(temp_md_path)])

    import prapti.tool
    test_exfil = {}
    exit_status = prapti.tool.main(test_exfil=test_exfil)
    assert exit_status == 0

    resolved_plugin_config: TestResponderConfiguration = test_exfil["test_responder_resolved_plugin_config"]
    # check values set in the markdown file
    assert resolved_plugin_config.an_int == 1024
    assert resolved_plugin_config.a_string == "test 1 2 3"

TEST_SET_LATE_BOUND_VARS_RESPONDER_PROMPT = """\
% plugins.load prapti.test.test_responder
% responder.new default prapti.test.test_responder
% vars.temperature = 100
% model = "test model"
% vars.n = 101
### @user:

Hello
"""
# ^^^ tests both qualified (vars.) and unqualified variable assignment
def test_set_late_bound_vars_responder_config(tmp_path, no_user_config, monkeypatch):
    """Test setting a late bound vars and checking that they are used in responder"""
    temp_md_path = tmp_path / "test_set_late_bound_vars_temp.md"
    temp_md_path.write_text(TEST_SET_LATE_BOUND_VARS_RESPONDER_PROMPT, encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["prapti", "--halt-on-error", "--dry-run", "--no-default-config", str(temp_md_path)])

    import prapti.tool
    test_exfil = {}
    exit_status = prapti.tool.main(test_exfil=test_exfil)
    assert exit_status == 0

    resolved_config: TestResponderConfiguration = test_exfil["test_responder_resolved_responder_config"]
    # check values set in the markdown file
    assert resolved_config.temperature == 100
    assert resolved_config.model == "test model"
    assert resolved_config.n == 101

def collect_logged_message_ids(caplog):
    message_ids = set()
    for record in caplog.records:
        if getattr(record, "message_id", None):
            message_ids.add(record.message_id)
    return message_ids

# NOTE: in the tests below, load a default responder so we don't get false-positive failures
# due to "no default responder" errors.

TEST_SET_FIELD_OF_NONEXISTANT_PLUGIN = """\
% plugins.load prapti.test.test_responder
% responder.new default prapti.test.test_responder
% plugins.nonexistant.alsononexistant.x = 100
### @user:

Hello
"""
def test_set_field_of_nonexistant_plugin(tmp_path, no_user_config, monkeypatch, caplog):
    """Test that we get an error when setting a field of a non-existant plugin"""
    temp_md_path = tmp_path / "test_set_field_of_nonexistant_plugin_temp.md"
    temp_md_path.write_text(TEST_SET_FIELD_OF_NONEXISTANT_PLUGIN, encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["prapti", "--halt-on-error", "--dry-run", "--no-default-config", str(temp_md_path)])

    import prapti.tool
    exit_status = prapti.tool.main()
    assert exit_status != 0 # expect failure

    message_ids = collect_logged_message_ids(caplog)
    assert "unknown-field-component" in message_ids

TEST_SET_NONEXISTANT_PLUGIN_FIELD = """\
% plugins.load prapti.test.test_responder
% responder.new default prapti.test.test_responder
% plugins.load prapti.test.test_config
% plugins.prapti.test.test_config.nonexistant = 100
### @user:

Hello
"""
def test_set_nonexistant_plugin_field(tmp_path, no_user_config, monkeypatch, caplog):
    """Test that we get an error when setting a non-existant field of plugin configuration"""
    temp_md_path = tmp_path / "test_set_nonexistant_plugin_field_temp.md"
    temp_md_path.write_text(TEST_SET_NONEXISTANT_PLUGIN_FIELD, encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["prapti", "--halt-on-error", "--dry-run", "--no-default-config", str(temp_md_path)])

    import prapti.tool
    exit_status = prapti.tool.main()
    assert exit_status != 0 # expect failure

    message_ids = collect_logged_message_ids(caplog)
    assert "unknown-field" in message_ids

TEST_SET_PLUGIN_FIELD_WITH_INVALID_VALUE = """\
% plugins.load prapti.test.test_responder
% responder.new default prapti.test.test_responder
% plugins.load prapti.test.test_config
% plugins.prapti.test.test_config.an_int = "test"
### @user:

Hello
"""
def test_set_plugin_field_with_invalid_value(tmp_path, no_user_config, monkeypatch, caplog):
    """Test that we get a validation error when setting a field to an invalid value (assign non-numeric string to int field)"""
    temp_md_path = tmp_path / "test_set_plugin_field_with_invalid_value_temp.md"
    temp_md_path.write_text(TEST_SET_PLUGIN_FIELD_WITH_INVALID_VALUE, encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["prapti", "--halt-on-error", "--dry-run", "--no-default-config", str(temp_md_path)])

    import prapti.tool
    exit_status = prapti.tool.main()
    assert exit_status != 0 # expect failure

    message_ids = collect_logged_message_ids(caplog)
    assert "invalid-field-assignment" in message_ids
