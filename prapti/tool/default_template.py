"""
    Find and load the default template.
"""
from pathlib import Path
from ..core.logger import DiagnosticsLogger

def get_default_template(log: DiagnosticsLogger) -> str:
    template_path = Path(__file__).resolve().parent / "default_template.md"
    try:
        result = template_path.read_text(encoding="utf-8")
    except Exception as e:
        state.log.error("default-template-exception", f"exception while reading default template: {repr(e)}", template_path)
        state.log.logger.debug(e, exc_info=True)
        result = "### @user:\n\n"
    return result
