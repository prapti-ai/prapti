"""
    Builtin actions.
"""
from typing import Any, AsyncGenerator
import types
import json
import importlib.metadata
from dataclasses import dataclass

import pydantic
from cancel_token import CancellationToken

from ._core_execution_state import get_private_core_state
from .execution_state import ExecutionState
from .configuration import EmptyPluginConfiguration, EmptyResponderConfiguration, RootConfiguration, VarRef, VarEntry, NotSet, resolve_var_ref, resolve_var_ref_field_assignment, setup_newly_constructed_config, get_subobject
from .command_message import Message
from .action import ActionNamespace, ActionContext
from .responder import ResponderContext
from .hooks import Hooks, HooksContext
from .source_location import SourceLocation
from .logger import DiagnosticsLogger, ScopedDiagnosticsLogger
from .plugin import Plugin, PluginCapabilities, PluginContext

builtin_actions: ActionNamespace = ActionNamespace()

# plugin version check -------------------------------------------------------

@dataclass
class Version:
    major: int
    minor: int
    patch: int

def parse_semver(version: str) -> Version:
    parts = version.split(".") # basic major.minor.patch semver only
    return Version(major=int(parts[0]), minor=int(parts[1]), patch=int(parts[2]))

def plugin_version_is_compatible(prapti_api_version: str, plugin_api_version: str):
    """determine compatibility based on semver semantics. see https://semver.org/"""
    prapti_api_version_v = parse_semver(prapti_api_version)
    plugin_api_version_v = parse_semver(plugin_api_version)
    if plugin_api_version_v.major != prapti_api_version_v.major:
        # incompatible major API versions
        return False
    if plugin_api_version_v.minor > prapti_api_version_v.minor:
        # plugin may use newer features that are unavailble in core
        return False
    return True

PRAPTI_API_VERSION = "1.0.0"

# plugin management ----------------------------------------------------------

# Plugin loading proceeds in the following steps:
#   1. at startup, eagerly create a dict of all available prapti.plugin `EntryPoint`s,
#      without loading anything. Plugin discovery is implemented using the standard
#      Python entry point mechanism via `importlib.metadata`.
#   2. on demand, load the entry point itself, which is an instance of prapti Plugin.
#      This step uses `importlib.metadata` to load the module that implements the plugin.
#   3. on demand, use the Plugin instance to instantiate the plugin's capabilities
#       and then load these capabilities into an execution state.
#
# The above steps are performed separately to minimise the amount of unnecessary work
# performed, and to allow multiple execution states to coexist, each with its own set
# of loaded plugins.

installed_plugin_entry_points: dict[str, importlib.metadata.EntryPoint] = {
    entry_point.name: entry_point
    for entry_point in importlib.metadata.entry_points(group="prapti.plugin")
}

if not installed_plugin_entry_points:
    print("warning: prapti: no plugins found. install with pip to register plugins.")

loaded_plugin_entry_points: dict[str, Plugin] = {}

def load_plugin_entry_point(plugin_name, source_loc: SourceLocation, log: DiagnosticsLogger) -> Plugin|None:
    result: Plugin|None = loaded_plugin_entry_points.get(plugin_name, None)
    if not result: # if not already loaded
        if plugin_entry_point := installed_plugin_entry_points.get(plugin_name, None):
            try:
                plugin = plugin_entry_point.load()
                if plugin.name != plugin_entry_point.name:
                    log.warning("plugin-name-inconsistency", f"plugin entry point name '{plugin_entry_point.name}' does not match plugin name '{plugin.name}'. get someone to fix the code.")

                if plugin_version_is_compatible(prapti_api_version=PRAPTI_API_VERSION, plugin_api_version=plugin.api_version):
                    result = plugin
                else:
                    log.error("incompatible-plugin-version", f"couldn't load plugin '{plugin_name}'. plugin API version {plugin.api_version} is not compatible with Prapti API version {PRAPTI_API_VERSION}. you need to upgrade the plugin or downgrade Prapti.")
            except Exception as ex:
                log.error("load-plugin-entry-point-exception", f"couldn't load plugin '{plugin_name}'. an error occurred: exception while loading plugin entry point '{plugin_entry_point.name}': {repr(ex)}", source_loc)
                log.debug_exception(ex)
                result = None
        else:
            log.error("plugin-not-found", f"couldn't load plugin '{plugin_name}'. plugin not found. use `%!plugins.list` to list available plugins.", source_loc)
    return result

def load_plugin(plugin: Plugin, source_loc: SourceLocation, state: ExecutionState) -> None:
    """Instantiate plugin capabilities and install them into execution state."""
    try:
        core_state = get_private_core_state(state)

        plugin_log = ScopedDiagnosticsLogger(sink=state.log, scopes=(plugin.name,))
        plugin_context = PluginContext(state=state, plugin_name=plugin.name, root_config=state.root_config, plugin_config=None, log=plugin_log)
        plugin_context.plugin_config = setup_newly_constructed_config(plugin.construct_configuration(plugin_context), empty_factory=EmptyPluginConfiguration, root_config=state.root_config, log=state.log)
        plugin_actions: ActionNamespace|None = plugin.construct_actions(plugin_context) if PluginCapabilities.ACTIONS in plugin.capabilities else None
        plugin_hooks: Hooks|None = plugin.construct_hooks(plugin_context) if PluginCapabilities.HOOKS in plugin.capabilities else None

        path = plugin.name.split(".")
        namespace_names, plugin_name = path[:-1], path[-1]

        # navigate path to attach-point, using existing namespaces under root_config.plugins
        config_attach_point = state.root_config.plugins
        for name in namespace_names:
            # if the namespace doesn't exist, create it
            if not (new_attach_point := getattr(config_attach_point, name, None)):
                new_attach_point = types.SimpleNamespace()
                setattr(config_attach_point, name, new_attach_point)
            config_attach_point = new_attach_point

        setattr(config_attach_point, plugin_name, plugin_context.plugin_config)

        if plugin_actions:
            plugin_actions.set_plugin_config_and_log(plugin_context.plugin_config, plugin_context.log)
            core_state.actions.merge(plugin_actions)

        core_state.loaded_plugins[plugin.name] = plugin

        if plugin_hooks:
            hooks_context = HooksContext(state=state, root_config=state.root_config, plugin_config=plugin_context.plugin_config, hooks=plugin_hooks, log=plugin_context.log)
            plugin_hooks.on_plugin_loaded(hooks_context)
            core_state.hooks_distributor.add_hooks(hooks_context)
    except Exception as ex:
        state.log.error("load-plugin-exception", f"exception while loading plugin '{plugin.name}': {repr(ex)}", source_loc)
        state.log.debug_exception(ex)

def load_plugin_by_name(plugin_name: str, source_loc: SourceLocation, state: ExecutionState) -> None:
    core_state = get_private_core_state(state)
    if plugin_name not in core_state.loaded_plugins:
        plugin: Plugin|None = load_plugin_entry_point(plugin_name, source_loc, state.log)
        if plugin:
            load_plugin(plugin, source_loc, state)

def get_loaded_plugins_info(state: ExecutionState) -> list[dict[str, str]]:
    core_state = get_private_core_state(state)
    return [
        {
            "name": plugin.name,
            "version": plugin.version,
            "description": plugin.description,
        }
        for plugin_name, plugin in core_state.loaded_plugins.items()
    ]

@builtin_actions.add_action("prapti.plugins.load")
def plugins_load(name: str, raw_args: str, context: ActionContext) -> None|str|Message:
    """Load a plugin. Installs hooks and makes commands/actions available."""
    plugin_name = raw_args.strip()
    load_plugin_by_name(plugin_name, context.source_loc, context.state)
    return None

def _s(count: int):
    return "s" if count != 1 else ""

@builtin_actions.add_action("!prapti.plugins.list")
def plugins_list(name: str, raw_args: str, context: ActionContext) -> None|str|Message:
    """List available plugins"""
    core_state = get_private_core_state(context.state)

    available_plugins: list[Plugin] = []
    bad_plugin_names: list[str] = []
    for plugin_name in installed_plugin_entry_points:
        plugin: Plugin|None = load_plugin_entry_point(plugin_name, context.source_loc, context.log)
        if plugin:
            available_plugins.append(plugin)
        else:
            bad_plugin_names.append(plugin_name)

    if len(available_plugins) > 0:
        plugin_lines = [f"- **`{plugin.name}`**: {plugin.description}{' (loaded)' if plugin.name in core_state.loaded_plugins else ''}" for plugin in available_plugins]
        content = f"Available plugin{_s(len(available_plugins))}:\n\n" + "\n".join(plugin_lines)
    else:
        content = "No plugins available."

    if len(bad_plugin_names) > 0:
        plugin_lines = "\n".join(f"- **`{name}`**" for name in bad_plugin_names)
        content += f"\n\nThe following plugin{_s(len(bad_plugin_names))} could not be accessed due to errors:\n\n{plugin_lines}"

    return Message("_prapti", "plugins", [content], is_enabled=False)

# responder management -------------------------------------------------------

def lookup_active_responder(state: ExecutionState) -> tuple[str, ResponderContext|None]:
    core_state = get_private_core_state(state)
    responder_name = state.root_config.prapti.responder_stack[-1] if state.root_config.prapti.responder_stack else "default"
    responder_name = core_state.hooks_distributor.on_lookup_active_responder(responder_name)
    return (responder_name, core_state.responder_contexts.get(responder_name, None))

async def _empty_async_generator() -> AsyncGenerator[Message, None]:
    # for alternatives see: https://stackoverflow.com/questions/77295311/how-to-define-an-empty-async-generator-in-python
    if False:
        yield Message(role="", name=None, content=[]) # need the yield keyword here to make it an async generator

def delegate_generate_responses(state: ExecutionState, responder_name: str, input_: list[Message], cancellation_token: CancellationToken) -> AsyncGenerator[Message, None]:
    core_state = get_private_core_state(state)
    delegate_responder_context: ResponderContext|None = core_state.responder_contexts.get(responder_name, None)
    if delegate_responder_context is None:
        state.log.error("delegation-to-nonexistant-responder", "could not delegate to responder '{responder_name}'. responder does not exist.")
        return _empty_async_generator()
    return delegate_responder_context.responder.generate_responses(input_, cancellation_token, delegate_responder_context)

@builtin_actions.add_action("prapti.responder.new")
def responder_new(name: str, raw_args: str, context: ActionContext) -> None|str|Message:
    """Create a new responder"""
    core_state = get_private_core_state(context.state)
    responder_name, plugin_name = raw_args.split()
    load_plugin_by_name(plugin_name, context.source_loc, context.state)
    if plugin := core_state.loaded_plugins.get(plugin_name, None):
        if PluginCapabilities.RESPONDER in plugin.capabilities:
            plugin_config = get_subobject(context.root_config.plugins, plugin_name, None)
            plugin_log = ScopedDiagnosticsLogger(sink=context.state.log, scopes=(plugin.name,))
            plugin_context = PluginContext(
                    state=context.state, plugin_name=plugin_name,
                    root_config=context.root_config, plugin_config=plugin_config, log=plugin_log)
            if responder := plugin.construct_responder(plugin_context):
                responder_context = ResponderContext(
                        state=context.state, plugin_name=plugin_name,
                        root_config=context.root_config, plugin_config=plugin_config, responder_config=None,
                        responder_name=responder_name, responder=responder, log=plugin_context.log)
                responder_context.responder_config = setup_newly_constructed_config(responder.construct_configuration(responder_context), empty_factory=EmptyResponderConfiguration, root_config=context.root_config, log=context.log)
                core_state.responder_contexts[responder_name] = responder_context
                setattr(context.root_config.responders, responder_name, responder_context.responder_config)
            else:
                context.log.error("responder-new-failed", f"couldn't construct responder '{responder_name}'. plugin '{plugin_name}' did not construct responder.", context.source_loc)
        else:
            context.log.error("responder-new-not-a-responder", f"couldn't construct responder '{responder_name}'. plugin '{plugin_name}' does not provide a responder.", context.source_loc)
    else:
        context.log.error("failed-responder-new", f"couldn't construct responder '{responder_name}'. plugin '{plugin_name}' not loaded.", context.source_loc)

@builtin_actions.add_action("prapti.responder.push")
def responder_push(name: str, raw_args: str, context: ActionContext) -> None|str|Message:
    responder_name = raw_args.strip()
    context.root_config.prapti.responder_stack.append(responder_name)

@builtin_actions.add_action("prapti.responder.pop")
def responder_pop(name: str, raw_args: str, context: ActionContext) -> None|str|Message:
    if context.root_config.prapti.responder_stack:
        context.root_config.prapti.responder_stack.pop()

# configuration inspection ---------------------------------------------------

def _collect_leaf_configs(config_obj, accumulated_path, result) -> None:
    if isinstance(config_obj, pydantic.BaseModel):
        result.append((accumulated_path, config_obj))
    else:
        assert isinstance(config_obj, types.SimpleNamespace)
        for field_name,field_value in config_obj.__dict__.items():
            if field_name.startswith("_"):
                continue
            field_path = field_name if not accumulated_path else f"{accumulated_path}.{field_name}"
            _collect_leaf_configs(field_value, field_path, result)

def _flat_config_dump(contained_in: Any, field_name: str, config_obj, indent, root_config: RootConfiguration, log: DiagnosticsLogger) -> str:
    result = ""
    leaf_configs: list[tuple[str,pydantic.BaseModel]] = []
    _collect_leaf_configs(config_obj, "", leaf_configs)
    for path, config in leaf_configs:
        value_dump = _config_dump(contained_in, path, config, indent+4, root_config, log) # REVIEW not sure we have contained_in correct here
        if "\n" in value_dump:
            result += f"{' '*indent}- `{path}`\n{value_dump}"
        elif not value_dump.strip():
            result += f"{' '*indent}- `{path}` *(no parameters)*\n"
        else:
            result += f"{' '*indent}- `{path} = {value_dump}`\n"
    return result

def _config_dump(contained_in: Any, field_name: str, config_obj, indent, root_config: RootConfiguration, log: DiagnosticsLogger) -> str:
    result = ""
    if isinstance(config_obj, pydantic.BaseModel):
        #if config_obj.__doc__:
        #    result += f"{' '*indent}{config_obj.__doc__}\n"
        for field_name, field_info in config_obj.model_fields.items():
            if field_name.startswith("_"):
                continue
            field_value = getattr(config_obj, field_name)
            field_description = "" # f" -- {field_info.description}" if field_info.description else ""

            if field_name == "plugins":
                value_dump = _flat_config_dump(config_obj, field_name, field_value, indent+4, root_config, log)
            else:
                value_dump = _config_dump(config_obj, field_name, field_value, indent+4, root_config, log)
            if "\n" in value_dump:
                result += f"{' '*indent}- `{field_name}`{field_description}\n{value_dump}"
            elif not value_dump.strip():
                result += f"{' '*indent}- `{field_name}` *(no parameters)*\n"
            else:
                result += f"{' '*indent}- `{field_name} = {value_dump}`{field_description}\n"
    elif isinstance(config_obj, types.SimpleNamespace):
        for field_name,field_value in config_obj.__dict__.items():
            if field_name.startswith("_"):
                continue
            value_dump = _config_dump(config_obj, field_name, field_value, indent+4, root_config, log)
            if "\n" in value_dump:
                result += f"{' '*indent}- `{field_name}`\n{value_dump}"
            elif not value_dump.strip():
                result += f"{' '*indent}- `{field_name}` *(empty)*\n"
            else:
                result += f"{' '*indent}- `{field_name} = {value_dump}`\n"
    elif isinstance(config_obj, VarEntry):
        if config_obj.value is NotSet:
            result += "(not set)"
        elif isinstance(config_obj.value, VarRef):
            var_ref_trace, var_entry = resolve_var_ref(config_obj.value, root_config, log)
            var_ref_chain = " = ".join(f"var({vr.var_name})" for vr in var_ref_trace)
            if var_entry.value is NotSet:
                terminal_value_str = f"(not set) ~> {json.dumps(config_obj.value)}"
            else:
                terminal_value_str = json.dumps(var_entry.value)
            result += f"{var_ref_chain} = {terminal_value_str}"
        else:
            result += json.dumps(config_obj.value)
    else:
        var_ref_resolution : tuple[list[VarRef], VarEntry]|None = resolve_var_ref_field_assignment(target=contained_in, field_name=field_name, root_config=root_config, log=log)
        if var_ref_resolution is None:
            result += json.dumps(config_obj)
        else:
            var_ref_trace, var_entry = var_ref_resolution
            var_ref_chain = " = ".join(f"var({vr.var_name})" for vr in var_ref_trace)
            if var_entry.value is NotSet:
                terminal_value_str = f"(not set) ~> {json.dumps(config_obj)}"
            else:
                terminal_value_str = json.dumps(var_entry.value)
            result += f"{var_ref_chain} = {terminal_value_str}"
    return result

@builtin_actions.add_action("!prapti.inspect")
def inspect_config(name: str, raw_args: str, context: ActionContext) -> None|str|Message:
    root_config = context.root_config

    content = "Configuration parameters:\n\n" + _config_dump(None, "root", root_config, indent=0, root_config=root_config, log=context.log)

    return Message("_prapti", "inspect", [content], is_enabled=False)
