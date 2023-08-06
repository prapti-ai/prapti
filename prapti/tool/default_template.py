"""
    Find and load the default template.
"""
from pathlib import Path
from ..core.logger import DiagnosticsLogger

def get_default_template(log: DiagnosticsLogger) -> str:
    template_path = Path(__file__).resolve().parent / "default_template.md"
    try:
        result = template_path.read_text(encoding="utf-8")
    except Exception as ex:
        log.error("default-template-exception", f"exception while reading default template: {repr(ex)}", template_path)
        log.logger.debug(ex, exc_info=True)
        result = "### @user:\n\n"
    return result
