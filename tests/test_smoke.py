"""
    Smoke tests. Simple integration tests that check basic functionality.
"""

def test_dry_run_tool(temp_markdown_file_path, no_user_config, monkeypatch):
    """Dry-run prapti tool against every markdown file in the repository
    and check for expected exit status. This should catch basic crashes.
    By using the `--strict` option we aim to catch other errors,
    as these will be cause a failure exit status.

    Note that if a test is expected to fail (i.e. it has the _fail suffix),
    it may fail for the expected reason, or for an unrelated reason. This test
    can not tell the difference.
    """
    monkeypatch.setattr("sys.argv", ["prapti", "--dry-run", "--strict", str(temp_markdown_file_path)])

    import prapti.tool
    exit_status = prapti.tool.main()

    if temp_markdown_file_path.stem.endswith("_fail"):
        # expect failure
        assert exit_status != 0
    else:
        # expect success
        assert exit_status == 0


CAPITAL_CITY_OF_ENGLAND_PROMPT = """\
### @user:

What is the capital city of England? Give your answer as a single word.
"""
def test_live_tool(tmp_path, no_user_config, monkeypatch):
    """Live-run prapti tool with default responder (OpenAI). Check that we got a reasonable response."""
    temp_md_path = tmp_path / "test_live_tool_temp.md"
    temp_md_path.write_text(CAPITAL_CITY_OF_ENGLAND_PROMPT, encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["prapti", "--strict", str(temp_md_path)])

    import prapti.tool
    exit_status = prapti.tool.main()
    assert exit_status == 0

    output_file_data = temp_md_path.read_text(encoding="utf-8")
    assert "London" in output_file_data
