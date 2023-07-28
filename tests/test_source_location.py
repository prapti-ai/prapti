from pathlib import Path
from prapti.core.source_location import SourceLocation

def test_source_location():
    file_path = Path("test/path")

    source_loc = SourceLocation()
    assert source_loc.file_path is None
    assert source_loc.line is None
    assert source_loc.column is None

    source_loc = SourceLocation(file_path=file_path)
    assert source_loc.file_path == file_path
    assert source_loc.line is None
    assert source_loc.column is None

    source_loc = SourceLocation(file_path=file_path, line=42)
    assert source_loc.file_path == file_path
    assert source_loc.line == 42
    assert source_loc.column is None

    source_loc = SourceLocation(file_path=file_path, line=42, column=101)
    assert source_loc.file_path == file_path
    assert source_loc.line == 42
    assert source_loc.column == 101
