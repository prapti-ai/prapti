"""
    The Configuration is a tree of namespaces with leaves that are pydantic models used to
    store configuration parameters for actions, responders, hooks, plugins, etc.
"""
from types import SimpleNamespace
import json

from pydantic import BaseModel, Field, ConfigDict

from .logger import DiagnosticsLogger
from .source_location import SourceLocation

class PraptiConfiguration(BaseModel):
    """Configuration that applies to Prapti as a whole"""
    model_config = ConfigDict(
        validate_assignment=True)

    config_root: bool = Field(default=False, description="Halt in-tree configuration file search once set to `true`.")
    dry_run: bool = Field(default=False, description="Simulate LLM responses. Disable plugin-specific side effects.")
    strict: bool = Field(default=False, description="Halt if errors are encountered. If `strict` is `false`, errors will be reported but prapti will try to continue whenever possible).")

    responder_stack: list[str] = Field(default_factory=list)

class PluginsConfiguration(SimpleNamespace):
    """Configuration entries for each loaded plugin"""

class EmptyPluginConfiguration(BaseModel):
    """No plugin-level configuration parameters available"""

class RespondersConfiguration(SimpleNamespace):
    """Configuration entries for each instantiated responder"""

class EmptyResponderConfiguration(BaseModel):
    """No responder configuration parameters available"""

class Vars(SimpleNamespace):
    # global/generic parameter aliases
    # if you set one of these in your markdown it will override the model-specific parameter that it aliases
    # TODO: generalise, support user defined variables
    def __init__(self):
        super().__init__(
            model = None, # str
            temperature = None, # float
            n = None) # int, number of responses to generate

class RootConfiguration(BaseModel):
    """The root of the configuration tree"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    prapti: PraptiConfiguration = Field(default_factory=PraptiConfiguration)

    plugins: PluginsConfiguration = Field(default_factory=PluginsConfiguration)

    responders: RespondersConfiguration = Field(default_factory=RespondersConfiguration)

    vars: Vars = Field(default_factory=Vars)

def _resolve_unqualified_field_name(root_config: RootConfiguration, unqualified_field_name: str, source_loc: SourceLocation, log: DiagnosticsLogger) -> str|None:
    # search `prapti` and `vars` namespaces. report and fail on ambiguity
    assert "." not in unqualified_field_name

    prapti_config_field = None
    vars_field = None

    if hasattr(root_config.prapti, unqualified_field_name):
        prapti_config_field = "prapti." + unqualified_field_name

    if hasattr(root_config.vars, unqualified_field_name):
        vars_field = "vars." + unqualified_field_name

    if prapti_config_field and vars_field:
        alternatives = f"{prapti_config_field} or {vars_field}"
        log.error("ambiguous-field-name", f"didn't perform configuration assignment. field name '{unqualified_field_name}' is ambiguous, did you mean: {alternatives}", source_loc)
        return None
    elif prapti_config_field:
        resolved_field_name = prapti_config_field
    elif vars_field:
        resolved_field_name = vars_field
    else:
        # default to vars field whether or not it currently exists
        resolved_field_name = "vars." + unqualified_field_name

    log.detail(f"resolved unqualified name '{unqualified_field_name}' to '{resolved_field_name}'", source_loc)
    return resolved_field_name

def _assign_var(root_config: RootConfiguration, var_field_name: str, field_value: str, source_loc: SourceLocation, log: DiagnosticsLogger) -> None:
    assert var_field_name.startswith("vars.")
    var_name = var_field_name[5:] # strip off "var."
    try:
        parsed_value = json.loads(field_value)
    except (ValueError, SyntaxError) as e:
        log.error("var-value-json-parse-error", f"could not parse variable value '{field_value}' as JSON: {e}", source_loc)
        return

    log.detail("set-var", f"setting variable: {var_field_name} = {json.dumps(parsed_value)}", source_loc)
    setattr(root_config.vars, var_name, parsed_value)
    # TODO:
    # - store VarEntry objects in vars namespace: VarEntry(value, is_set, last_assignment_loc)

def _assign_configuration_field(root_config: RootConfiguration, config_field_name: str, field_value: str, source_loc: SourceLocation, log: DiagnosticsLogger) -> None:
    assert not config_field_name.startswith("vars.")

    # navigate '.'-separated components from `config_root`` to the `target`` object that has field `field_name``
    field_name = config_field_name
    target = root_config
    while '.' in field_name:
        source, field_name = field_name.split('.', maxsplit=1)
        if not hasattr(target, source):
            log.error("unknown-field-component", f"didn't perform configuration assignment. unknown configuration field '{config_field_name}', component '{source}' does not exist", source_loc)
            return
        target = getattr(target, source)

    if hasattr(target, field_name):
        if not isinstance(target, BaseModel):
            log.error("internal-error-config-is-not-pydantic", f"internal error: target configuration object for `{config_field_name}` is not a pydantic BaseModel. you found a bug, please report it.")
            return

        try:
            parsed_value = json.loads(field_value)
        except (ValueError, SyntaxError) as e:
            log.error("config-value-json-parse-error", f"could not parse configuration value '{field_value}' as JSON: {repr(e)}", source_loc)
            return
        try:
            log.detail("set-field", f"setting configuration field: {config_field_name} = {parsed_value}", source_loc)
            setattr(target, field_name, parsed_value) # use pydantic for coercion and validation validation
        except Exception as e:
            log.error("invalid-field-assignment", f"could not assign configuration value '{field_value}': {repr(e)}", source_loc)
            return
    else:
        log.error("unknown-field", f"didn't assign configuration field. unknown configuration field '{config_field_name}'", source_loc)

def assign_field(root_config: RootConfiguration, original_field_name: str, field_value: str, source_loc: SourceLocation, log: DiagnosticsLogger) -> None:
    resolved_field_name = (original_field_name if "." in original_field_name
        else _resolve_unqualified_field_name(root_config=root_config, unqualified_field_name=original_field_name, source_loc=source_loc, log=log))
    if not resolved_field_name:
        return

    if resolved_field_name.startswith("vars."):
        _assign_var(root_config=root_config, var_field_name=resolved_field_name, field_value=field_value, source_loc=source_loc, log=log)
    else:
        _assign_configuration_field(root_config=root_config, config_field_name=resolved_field_name, field_value=field_value, source_loc=source_loc, log=log)
