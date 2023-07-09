"""
    Find and load the default template.
"""
from pathlib import Path

def get_default_template() -> str:
    template_path = Path(__file__).resolve().parent / "default_template.md"
    try:
        result = template_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"warning: error encountered while reading default_template.md: {e}")
        result = "### @user:\n\n"
    return result
