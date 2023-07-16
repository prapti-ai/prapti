import shutil
import pytest

def pytest_generate_tests(metafunc):
    if "markdown_file_path" in metafunc.fixturenames:
        # fixture markdown_file_path: all non-temporary markdown files in the project, as pathlib.Path objects
        rootpath = metafunc.config.rootpath
        paths = [p for p in rootpath.rglob("*.md") if (".pytest_cache" not in p.parts and "build" not in p.parts and "_pytest_tmp" not in p.name)]
        metafunc.parametrize("markdown_file_path", paths, ids=lambda p: str(p.relative_to(rootpath)))

@pytest.fixture(scope="function") # provide a fresh temporary copy for each test
def temp_markdown_file_path(request, markdown_file_path):
    # create temp files in-tree so that they pick up the in-tree prapticonfig.md:
    tmp_md_path = markdown_file_path.with_suffix("._pytest_tmp.md")
    shutil.copy(markdown_file_path, tmp_md_path)
    def cleanup():
        tmp_md_path.unlink(missing_ok=True)
    request.addfinalizer(cleanup)
    return tmp_md_path
