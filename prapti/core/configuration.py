"""
    The Configuration is a tree of namespaces with leaves that are pydantic models used to
    store configuration parameters for actions, responders, hooks, plugins, etc.
"""
from dataclasses import dataclass, field
from typing import Any, TypeVar, Callable
from types import SimpleNamespace
from collections import defaultdict
import json
import re

from pydantic import BaseModel, Field, ConfigDict, PrivateAttr, ValidationError

from .logger import DiagnosticsLogger
from .source_location import SourceLocation

class PraptiConfiguration(BaseModel):
    """Configuration that applies to Prapti as a whole"""
    model_config = ConfigDict(
        validate_assignment=True)

    config_root: bool = Field(default=False, description="Halt in-tree configuration file search once set to `true`.")
    dry_run: bool = Field(default=False, description="Simulate LLM responses. Disable plugin-specific side effects.")
    halt_on_error: bool = Field(default=False, description="Halt if errors are encountered. If `halt_on_error` is `false`, errors will be reported but prapti will try to continue whenever possible).")

    responder_stack: list[str] = Field(default_factory=list)

class PluginsConfiguration(SimpleNamespace):
    """Configuration entries for each loaded plugin"""

class EmptyPluginConfiguration(BaseModel):
    """No plugin-level configuration parameters available"""

class RespondersConfiguration(SimpleNamespace):
    """Configuration entries for each instantiated responder"""

class EmptyResponderConfiguration(BaseModel):
    """No responder configuration parameters available"""

class NotSetType:
    """Sentinel for vars that have not been set."""
    pass
NotSet = NotSetType()

@dataclass
class VarRef:
    var_name: str
    source_loc: SourceLocation = field(default_factory=SourceLocation)

@dataclass
class VarEntry:
    value: Any|VarRef|NotSetType = NotSet
    value_source_loc: SourceLocation|None = None # loc of value when assigned

    @property
    def value_is_set(self) -> bool:
        return self.value is not NotSet

class Vars(SimpleNamespace):
    # global/generic parameter aliases
    # if you set one of these in your markdown it will override the model-specific parameter that it aliases
    def __init__(self):
        self.model = VarEntry() # str
        self.temperature = VarEntry() # float
        self.n = VarEntry() # int, number of responses to generate

class RootConfiguration(BaseModel):
    """The root of the configuration tree"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    prapti: PraptiConfiguration = Field(default_factory=PraptiConfiguration)

    plugins: PluginsConfiguration = Field(default_factory=PluginsConfiguration)

    responders: RespondersConfiguration = Field(default_factory=RespondersConfiguration)

    vars: Vars = Field(default_factory=Vars)

    _var_ref_assignments : defaultdict[int, dict[str, VarRef]] = PrivateAttr(default_factory=lambda: defaultdict(dict))
    # ^^^ NOTE: defaultdict behavior is that _var_ref_assignments[x] will instantiate an innner dict if x is missing;
    # therefore always use _var_ref_assignments.get(x) when you don't want to instantiate an inner dict

# ---------------------------------------------------------------------------

def get_subobject(obj, dotted_name: str, default: Any):
    for component in dotted_name.split("."):
        if not hasattr(obj, component):
            return default
        obj = getattr(obj, component)
    return obj

# ---------------------------------------------------------------------------

# Late-bound user-defined configuration variables implementation
# ==============================================================
#
# The user can store configuration variable in the `vars`` namespace. e.g.#
#
# % vars.model = "gpt-4"
#
# Which, due to the name resolution algorithm can also be written as:
#
# % model = "gpt-4"
#
# These variables can be assigned by-reference to configuration fields using the `var()` pseudo-function as follows:
#
# % responders.default.model = var(model)
#
# This associates a late-bound user defined variable `model` with the `default.model` field.
# The variable is resolved lazily: only when the responder needs the value, which allows the user
# to change the variable at any time within the markdown and the most recent assignment will be used.
#
# Key points of the implementation are:
#
# - assignments of var refs to configuration fields are stored in the side table root_config._var_ref_assignments,
#   which is keyed by the id() of the configuration model instance
# - typically, plugins will call resolve_var_refs to get the "resolved" version of the configuration,
#   with all var refs resolved to values.
# - the code below is concerned with managing variable references and field assignments for
#     - assign_field: the implementation of the assignment command
#     - resolve_var_refs: resolve late-bound var refs to values
#     - setup_newly_constructed_config: setup initial var refs for newly constructed configuration models

# ----------------------------------------------------------------------------
# assign_field

def _assign_var_ref(target: BaseModel, field_name: str, var_ref: VarRef, root_config: RootConfiguration) -> None:
    """Store target.field_name = VarRef(...) in _var_ref_assignments side-table"""
    root_config._var_ref_assignments[id(target)][field_name] = var_ref

def _get_assigned_var_ref(target: BaseModel, field_name: str, root_config: RootConfiguration) -> VarRef | None:
    """Retrieve the assigned VarRef for target.field_name from _var_ref_assignments side-table."""
    if target_var_ref_assignments := root_config._var_ref_assignments.get(id(target)):
        return target_var_ref_assignments.get(field_name)
    return None

def _clear_var_ref_assignment(target: BaseModel, field_name: str, root_config: RootConfiguration) -> None:
    """Remove target.field_name = VarRef(...) from _var_ref_assignments side-table if it exists."""
    if target_var_ref_assignments := root_config._var_ref_assignments.get(id(target)):
        if field_name in target_var_ref_assignments:
            del target_var_ref_assignments[field_name]
            if not target_var_ref_assignments:
                del root_config._var_ref_assignments[id(target)]

def _assign_var(root_config: RootConfiguration, var_field_name: str, parsed_field_value: Any, source_loc: SourceLocation, log: DiagnosticsLogger) -> None:
    """Assign `parsed_field_value` to the VarEntry corresponding to `var_field_name`, creating an entry
    if one does not already exist. Store VarRefs directly in VarEntrys, not in a side-table as is done for
    fields of pydatic models."""
    assert var_field_name.startswith("vars.")
    var_name = var_field_name[5:] # strip off "vars."
    value_str = f"var({parsed_field_value.var_name})" if isinstance(parsed_field_value, VarRef) else json.dumps(parsed_field_value)
    log.detail("set-var", f"setting variable: {var_field_name} = {value_str}", source_loc)
    setattr(root_config.vars, var_name, VarEntry(value=parsed_field_value, value_source_loc=source_loc)) # replace existing entry, if any

def _assign_configuration_field(root_config: RootConfiguration, config_field_path: str, parsed_field_value: Any, source_loc: SourceLocation, log: DiagnosticsLogger) -> None:
    """Assign `parsed_field_value` to the field corresponding to `config_field_path`.
    This will trigger pydantic validation for the field assignment.
    If `parsed_field_value` is a VarRef, store the assignment in the `_var_ref_assignments` side-table
    """
    assert not config_field_path.startswith("vars.")

    # navigate '.'-separated components from `config_root`` to the `target`` object that has field `field_name``
    field_name = config_field_path
    target = root_config
    while '.' in field_name:
        source, field_name = field_name.split('.', maxsplit=1)
        if not hasattr(target, source):
            log.error("unknown-field-component", f"didn't perform configuration assignment. unknown configuration field '{config_field_path}', component '{source}' does not exist", source_loc)
            return
        target = getattr(target, source)

    if hasattr(target, field_name):
        if not isinstance(target, BaseModel):
            log.error("internal-error-config-is-not-pydantic", f"internal error: target configuration object for `{config_field_path}` is not a pydantic BaseModel. you found a bug, please report it.")
            return
        if isinstance(parsed_field_value, VarRef):
            _assign_var_ref(target, field_name, parsed_field_value, root_config)
        else:
            try:
                log.detail("set-field", f"setting configuration field: {config_field_path} = {json.dumps(parsed_field_value)}", source_loc)
                setattr(target, field_name, parsed_field_value) # uses pydantic for coercion and validation, may raise exception
                _clear_var_ref_assignment(target, field_name, root_config) # clear any var ref assignment *only after* new value has been successfully assigned
            except ValidationError as validation_error:
                log.error("invalid-field-assignment", f"could not assign configuration value '{json.dumps(parsed_field_value)}' to field '{field_name}': {str(validation_error)}", source_loc)
                return
    else:
        log.error("unknown-field", f"didn't assign configuration field. unknown configuration field '{config_field_path}'", source_loc)

def _lookup_unscoped_field_name(root_config: RootConfiguration, unscoped_field_name: str, source_loc: SourceLocation, log: DiagnosticsLogger) -> str|None:
    """Given an unscoped field name (i.e. a simple name with no .s to specify a scope), find an appropriate scoped field name.
    Search `prapti` and `vars` namespaces. Report and fail on ambiguity."""
    assert "." not in unscoped_field_name

    prapti_config_field = None
    vars_field = None

    if hasattr(root_config.prapti, unscoped_field_name):
        prapti_config_field = "prapti." + unscoped_field_name

    if hasattr(root_config.vars, unscoped_field_name):
        vars_field = "vars." + unscoped_field_name

    if prapti_config_field and vars_field:
        alternatives = f"{prapti_config_field} or {vars_field}"
        log.error("ambiguous-field-name", f"didn't perform configuration assignment. field name '{unscoped_field_name}' is ambiguous, did you mean: {alternatives}", source_loc)
        return None
    elif prapti_config_field:
        scoped_field_name = prapti_config_field
    elif vars_field:
        scoped_field_name = vars_field
    else:
        # default to vars field whether or not it currently exists
        scoped_field_name = "vars." + unscoped_field_name

    log.detail(f"resolved unscoped name '{unscoped_field_name}' to '{scoped_field_name}'", source_loc)
    return scoped_field_name

var_ref_regex = re.compile(r"^\s*var\s*\(\s*([A-Za-z_][\w_]*)\s*\)")

def _parse_field_value(field_value_str: str, source_loc: SourceLocation, log: DiagnosticsLogger) -> tuple[bool, Any]:
    """Parse the right-hand-side of an assignment (the "field value"). This can take the form of
    valid JSON, or "var(<var-name>)"."""
    if match := re.match(var_ref_regex, field_value_str):
        parsed_value = VarRef(var_name=match.group(1), source_loc=source_loc)
    else:
        try:
            parsed_value = json.loads(field_value_str)
        except (ValueError, SyntaxError) as ex:
            log.error("config-value-json-parse-error", f"could not parse configuration value '{field_value_str}' as JSON: {repr(ex)}", source_loc)
            return False, None
    return True, parsed_value

def assign_field(root_config: RootConfiguration, original_field_name: str, field_value_str: str, source_loc: SourceLocation, log: DiagnosticsLogger) -> None:
    """Implementation of `% fieldname = value` command"""
    scoped_field_name = (original_field_name if "." in original_field_name
        else _lookup_unscoped_field_name(root_config=root_config, unscoped_field_name=original_field_name, source_loc=source_loc, log=log))
    if not scoped_field_name:
        return

    value_ok, parsed_field_value = _parse_field_value(field_value_str, source_loc, log)
    if not value_ok:
        return

    if scoped_field_name.startswith("vars."):
        _assign_var(root_config=root_config, var_field_name=scoped_field_name, parsed_field_value=parsed_field_value, source_loc=source_loc, log=log)
    else:
        _assign_configuration_field(root_config=root_config, config_field_path=scoped_field_name, parsed_field_value=parsed_field_value, source_loc=source_loc, log=log)

# ----------------------------------------------------------------------------
# resolve_var_refs and friends -- late-bound variable value resolution

_VAR_REF_CHAIN_LIMIT = 20

def _resolve_var_ref(var_ref: VarRef, trace: list[VarRef], root_config: RootConfiguration, log: DiagnosticsLogger) -> VarEntry:
    trace.append(var_ref)
    if len(trace) > _VAR_REF_CHAIN_LIMIT:
        chain = " = ".join(f"var({vr.var_name})" for vr in trace)
        log.error("var-ref-chain-limit-reached", f"did not resolve value for variable '{trace[0].var_name}'. halted on possible reference cycle: {chain}")
        return VarEntry()

    var_entry = getattr(root_config.vars, var_ref.var_name, None)
    if var_entry is None:
        return VarEntry(value=NotSet)
    if not isinstance(var_entry.value, VarRef): # JSON-compatible value or NotSet
        return var_entry
    return _resolve_var_ref(var_entry.value, trace, root_config, log)

def resolve_var_ref(var_ref: VarRef, root_config: RootConfiguration, log: DiagnosticsLogger) -> tuple[list[VarRef], VarEntry]:
    """Find the terminal VarEntry addressed by var_ref, if necessary, traverse chains of var_refs assigned to other var_refs.
    The returned VarRef is guaranteed to either have a JSON-compatible value, or be NotSet."""
    trace = []
    var_entry = _resolve_var_ref(var_ref, trace, root_config, log)
    return trace, var_entry

def resolve_var_ref_field_assignment(target: BaseModel, field_name: str, root_config: RootConfiguration, log: DiagnosticsLogger) -> tuple[list[VarRef], VarEntry]|None:
    """Find the terminal VarEntry for `target.field_name` if and only if a VarRef has been assigned to `field_name`,
    otherwise return None. Used for debugging/inspection only."""
    if initial_var_ref := _get_assigned_var_ref(target, field_name, root_config):
        return resolve_var_ref(initial_var_ref, root_config, log)
    return None

Model = TypeVar('Model', bound='BaseModel')

def resolve_var_refs(target: Model, root_config: RootConfiguration, log: DiagnosticsLogger) -> Model:
    """Return an instance of the model with all var_ref field assignments resolved to values.
    Note that this does not necessarily return a copy of the model but it is guaranteed to leave
    the input `target` unmodified."""
    target_var_ref_assignments = root_config._var_ref_assignments.get(id(target))
    if not target_var_ref_assignments:
        # target has no VarRef assignments
        return target

    result = target.model_copy()

    # iterate through all var_ref -> field assignments and assign to each field separately
    # so that we can give precise validation errors
    # NOTE: we don't use model_copy(update=...) because it doesn't peform validation
    for field_name, var_ref in target_var_ref_assignments.items():
        var_ref_trace, var_entry = resolve_var_ref(var_ref, root_config, log)
        if var_entry.value_is_set:
            try:
                setattr(result, field_name, var_entry.value) # uses pydantic for coercion and validation, may raise exception
            except ValidationError as validation_error:
                var_ref_chain = " = ".join(f"var({vr.var_name})" for vr in var_ref_trace)
                assignment_chain = f"{field_name} = {var_ref_chain} = {json.dumps(var_entry.value)}"
                log.error("invalid-late-bound-field-assignment", f"could not bind variable value to field: {assignment_chain}: {str(validation_error)}", var_entry.value_source_loc)
    return result

# ----------------------------------------------------------------------------

def setup_newly_constructed_config(constructed_config: BaseModel|tuple[BaseModel, list[tuple[str,VarRef]]]|None, empty_factory: Callable[[], BaseModel], root_config: RootConfiguration, log: DiagnosticsLogger) -> BaseModel:
    """Process the result of constructing a new plugin or responder configuration.
    Assign specified var refs to fields.
    If the constructed config is None construct an appropriate empty config."""
    if constructed_config:
        if isinstance(constructed_config, tuple):
            the_config, field_var_ref_assignments = constructed_config
            for field_name, var_ref in field_var_ref_assignments:
                if not field_name in the_config.model_fields:
                    log.warning("setup-assign-var-ref-to-nonexistant-field", f"setup: can't set field `{field_name}` to `var({var_ref.var_name})`. field doesn't exist.")
                _assign_var_ref(the_config, field_name, var_ref, root_config)
                if not hasattr(root_config.vars, var_ref.var_name):
                    # create entries for vars, if they don't already exist
                    setattr(root_config.vars, var_ref.var_name, VarEntry(value=NotSet, value_source_loc=SourceLocation()))
            return the_config
        else:
            return constructed_config
    return empty_factory()
