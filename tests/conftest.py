import shutil
import pathlib
import pytest

def pytest_generate_tests(metafunc):
    if "markdown_file_path" in metafunc.fixturenames:
        # fixture markdown_file_path: all non-temporary markdown files in the project, as pathlib.Path objects
        rootpath = metafunc.config.rootpath
        paths = [p for p in rootpath.rglob("*.md") if (".pytest_cache" not in p.parts and "build" not in p.parts and "_pytest_tmp" not in p.name)]
        metafunc.parametrize("markdown_file_path", paths, ids=lambda p: str(p.relative_to(rootpath)))

@pytest.fixture(scope="function") # provide a fresh temporary copy for each test
def temp_markdown_file_path(request, markdown_file_path) -> pathlib.Path:
    # create temp files in-tree so that they pick up the in-tree prapticonfig.md:
    tmp_md_path = markdown_file_path.with_suffix("._pytest_tmp.md")
    shutil.copy(markdown_file_path, tmp_md_path)
    def cleanup():
        tmp_md_path.unlink(missing_ok=True)
    request.addfinalizer(cleanup)
    return tmp_md_path

@pytest.fixture(scope="function")
def mock_user_home(tmp_path_factory, monkeypatch) -> pathlib.Path:
    result = tmp_path_factory.mktemp("mock_user_home")
    monkeypatch.setenv("HOME", str(result))
    def mock_home_func():
        return result
    monkeypatch.setattr(pathlib.Path, "home", mock_home_func)
    return result

@pytest.fixture(scope="function")
def tmp_xdg_config_home(tmp_path_factory, monkeypatch) -> pathlib.Path:
    result = tmp_path_factory.mktemp("tmp_xdg_config_home")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(result))
    return result

@pytest.fixture(scope="function")
def no_user_config(mock_user_home: pathlib.Path, monkeypatch) -> pathlib.Path:
    # clear XDG_CONFIG_HOME, set up empty mocked user home directory
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    # leave mock user home empty. i.e. no user config
    return mock_user_home
