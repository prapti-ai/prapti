"""
    Test the "start template" markdown file.
    The start template is text that the prapti tool responds with when run on an empty input file.
"""
import pathlib
import pytest

@pytest.fixture(scope="function")
def mock_prapti_config_home(mock_user_home: pathlib.Path, monkeypatch) -> pathlib.Path:
    # clear XDG_CONFIG_HOME, set up empty mocked user home directory
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

    # add prapti user config dir $HOME/.config/prapti
    result = mock_user_home / ".config" / "prapti"
    result.mkdir(parents=True)
    return result

INPUT_DIR_PRAPTISTART_MD = """\
### user:
loaded ./praptistart.md
"""
def test_load_praptistart_md_in_input_file_dir(tmp_path: pathlib.Path, no_user_config, monkeypatch):
    """Test loading `.praptistart.md` from input file dir"""

    # .praptistart.md
    praptistart_md_path = tmp_path / ".praptistart.md"
    praptistart_md_path.write_text(INPUT_DIR_PRAPTISTART_MD, encoding="utf-8")

    # empty md input file
    temp_md_path = tmp_path / "test_load_praptistart_md_in_input_file_dir.md"
    temp_md_path.write_text("", encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["prapti", "--halt-on-error", "--dry-run", str(temp_md_path)])

    import prapti.tool
    test_exfil = {}
    exit_status = prapti.tool.main(test_exfil=test_exfil)
    assert exit_status == 0

    output_file_data = temp_md_path.read_text(encoding="utf-8")
    assert "loaded ./praptistart.md" in output_file_data

PARENT_OF_INPUT_DIR_PRAPTISTART_MD = """\
### user:
loaded ../praptistart.md
"""
def test_load_praptistart_md_one_dir_up_from_input_file(tmp_path: pathlib.Path, no_user_config, monkeypatch):
    """Test loading `.praptistart.md` from config root one dir up from input file"""

    parent_path = tmp_path
    child_path = tmp_path / "child"
    child_path.mkdir()

    # .praptistart.md
    parent_praptistart_md_path = parent_path / ".praptistart.md"
    parent_praptistart_md_path.write_text(PARENT_OF_INPUT_DIR_PRAPTISTART_MD, encoding="utf-8")

    # empty md input file
    temp_md_path = child_path / "test_load_praptistart_md_one_dir_up_from_input_file.md"
    temp_md_path.write_text("", encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["prapti", "--halt-on-error", "--dry-run", str(temp_md_path)])

    import prapti.tool
    test_exfil = {}
    exit_status = prapti.tool.main(test_exfil=test_exfil)
    assert exit_status == 0

    output_file_data = temp_md_path.read_text(encoding="utf-8")
    assert "loaded ../praptistart.md" in output_file_data

CONFIG_HOME_START_MD = """\
### user:
loaded ~/.config/prapti/start.md
"""
def test_load_start_md_from_user_config_dir(tmp_path: pathlib.Path, mock_prapti_config_home: pathlib.Path, monkeypatch):
    """Test loading `start.md` from user home config"""

    # start.md
    start_md_path = mock_prapti_config_home / "start.md"
    start_md_path.write_text(CONFIG_HOME_START_MD, encoding="utf-8")

    # empty md input file
    temp_md_path = tmp_path / "test_load_start_md_from_user_config_dir.md"
    temp_md_path.write_text("", encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["prapti", "--halt-on-error", "--dry-run", str(temp_md_path)])

    import prapti.tool
    test_exfil = {}
    exit_status = prapti.tool.main(test_exfil=test_exfil)
    assert exit_status == 0

    output_file_data = temp_md_path.read_text(encoding="utf-8")
    assert "loaded ~/.config/prapti/start.md" in output_file_data

def test_load_praptistart_md_nearest_input_file(tmp_path: pathlib.Path, mock_prapti_config_home: pathlib.Path, monkeypatch):
    """Test putting start files in all three previous locations and check that the one closest to the input file is loaded"""

    # start.md
    start_md_path = mock_prapti_config_home / "start.md"
    start_md_path.write_text(CONFIG_HOME_START_MD, encoding="utf-8")

    parent_path = tmp_path
    child_path = tmp_path / "child"
    child_path.mkdir()

    # .praptistart.md
    parent_praptistart_md_path = parent_path / ".praptistart.md"
    parent_praptistart_md_path.write_text(PARENT_OF_INPUT_DIR_PRAPTISTART_MD, encoding="utf-8")

    child_praptistart_md_path = child_path / ".praptistart.md"
    child_praptistart_md_path.write_text(INPUT_DIR_PRAPTISTART_MD, encoding="utf-8")

    # empty md input file
    temp_md_path = child_path / "test_load_praptistart_md_nearest_input_file.md"
    temp_md_path.write_text("", encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["prapti", "--halt-on-error", "--dry-run", str(temp_md_path)])

    import prapti.tool
    test_exfil = {}
    exit_status = prapti.tool.main(test_exfil=test_exfil)
    assert exit_status == 0

    output_file_data = temp_md_path.read_text(encoding="utf-8")
    assert "loaded ./praptistart.md" in output_file_data
