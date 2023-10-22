"""
    Find and load the start template.
"""
from pathlib import Path
from ..core.execution_state import ExecutionState

FALLBACK_START_TEMPLATE = "### @user:\n\n"

def locate_start_template(state: ExecutionState) -> Path:
    """Search for a start template file. Return the first file found.
    - First, search for a `.praptistart.md` file in the directory
      containing the input file and int all directories up to the config root.
    - Then search for a `start.md` file in the user's home config dir.
    NOTE: If Prapti is run with the --no-default-config flag, then none of the config
    directories will be searched."""

    for dir_ in state.prapticonfig_dirs:
        start_template_path = dir_ / ".praptistart.md"
        if start_template_path.is_file():
            return start_template_path

    if state.user_prapti_config_dir:
        start_template_path = state.user_prapti_config_dir / "start.md"
        if start_template_path.is_file():
            return start_template_path

    return Path(__file__).resolve().parent / "default_start.md"

def get_start_template(state: ExecutionState) -> str:
    """Locate the applicable start template file and return its contents."""
    start_template_path = locate_start_template(state)
    try:
        result = start_template_path.read_text(encoding="utf-8")
    except Exception as ex:
        state.log.error("start-template-exception", f"exception while reading start template: {repr(ex)}", start_template_path)
        state.log.logger.debug(ex, exc_info=True)
        result = FALLBACK_START_TEMPLATE
    return result
