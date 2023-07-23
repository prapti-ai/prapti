"""
    The Configuration is a tree of dataclasses that are used to
    configure actions, responders, hooks, plugins, etc.
"""
from dataclasses import dataclass, field
import json
from .logger import DiagnosticsLogger
from .source_location import SourceLocation

class PluginsConfiguration:
    """contains a dynamic configuration entry for each loaded plugin"""
    pass

class EmptyPluginConfiguration:
    """used when the plugin provides no plugin-level configuration"""
    pass

class RespondersConfiguration:
    """contains a dynamic configuration entry for each instantiated responder"""
    pass

class EmptyResponderConfiguration:
    """used when the plugin provides no responder-level configuration"""
    pass

@dataclass
class RootConfiguration:
    """The root of the configuration tree"""
    config_root: bool = False # halt in-tree configuration file loading when true
    dry_run: bool = False # simulate LLM responses. disable side-effects (plugin specific)
    strict: bool = False # fail if errors are encountered (if strict is False, errors will be reported but prapti will try to continue where ever possible)

    plugins: PluginsConfiguration = field(default_factory=PluginsConfiguration)

    responders: RespondersConfiguration = field(default_factory=RespondersConfiguration)
    responder_stack: list[str] = field(default_factory=list)

    # global/generic parameter aliases
    # if you set one of these in your markdown it will override the model-specific parameter that it aliases
    # FIXME TODO: allow global vars to be |None or unset
    model: str = None
    temperature: float = None
    n: int = None # number of responses to generate

def assign_configuration_field(root_config: RootConfiguration, original_field_name: str, field_value: str, source_loc: SourceLocation, log: DiagnosticsLogger) -> None:
    field_name = original_field_name
    target = root_config
    while '.' in field_name:
        source, field_name = field_name.split('.', maxsplit=1)
        if not hasattr(target, source):
            log.error("unknown-field-component", f"skipping configuration assignment. unknown configuration field '{original_field_name}', component '{source}' does not exist", source_loc)
            return
        target = getattr(target, source)

    if hasattr(target, field_name):
        try:
            parsed_value = json.loads(field_value)
        except (ValueError, SyntaxError) as e:
            log.error("config-value-json-parse-error", f"could not parse configuration value '{field_value}' as JSON: {e}", source_loc)
            return
        field_type = target.__annotations__.get(field_name)
        try:
            assigned_value = field_type(parsed_value)
        except Exception as e:
            log.error("config-value-coercion-failure", f"could not coerce configuration value '{field_value}' to a '{field_type}'", source_loc)
            return
        setattr(target, field_name, assigned_value)
        log.detail("set-field", f"setting configuration field: {original_field_name} = {parsed_value}", source_loc)
    else:
        log.error("unknown-field", f"skipping configuration assignment. unknown configuration field '{original_field_name}'", source_loc)
