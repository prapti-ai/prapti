from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True, slots=True)
class SourceLocation:
    file_path: Path|None = None
    line: int|None = None # 1-based
    column: int|None = None # 1-based
