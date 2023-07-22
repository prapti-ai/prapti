from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True, slots=True)
class SourceLocation:
    """Represent the location of an entity in a source file.
    e.g. the location of a message, command, token, etc.
    used in error reporting to give targeted diagnostic output."""
    file_path: Path|None = None
    line: int|None = None # 1-based
    column: int|None = None # 1-based
