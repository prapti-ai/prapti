"""
    Plugins are dynamically loaded extensions.
"""
from typing import Any, Optional

class Plugin:
    """Base class for plugins"""
    def __init__(self, name: str, version: str, description: str, api_version: str):
        self.api_version: str = api_version
        self.name: str = name
        self.version: str = version
        self.description: str = description

    def construct_configuration(self) -> Optional[Any]:
        return None

    def construct_actions(self) -> Optional['ActionNamespace']:
        return None

    def construct_hooks(self) -> Optional['Hooks']:
        return None

    def construct_responder(self) -> Optional['Responder']:
        return None
