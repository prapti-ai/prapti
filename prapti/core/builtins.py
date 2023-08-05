"""
    Builtin actions.
"""
from typing import Any
import types
import json

import pydantic

from ._core_execution_state import get_private_core_state
from .execution_state import ExecutionState
from .configuration import EmptyPluginConfiguration, EmptyResponderConfiguration, RootConfiguration, VarRef, VarEntry, NotSet, resolve_var_ref, resolve_var_ref_field_assignment, setup_newly_constructed_config
from .command_message import Message
from .action import ActionNamespace, ActionContext
from .responder import ResponderContext
from . import hooks
from .source_location import SourceLocation
from .logger import DiagnosticsLogger

builtin_actions: ActionNamespace = ActionNamespace()

# ----------------------------------------------------------------------------
# /// DANGER -- UNDER CONSTRUCTION ///////////////////////////////////////////

# plugin registry (hard coded)

# HACK: right now we manually import all of the plugins and add their entry points
# to the plugins array. in future we will want to avoid importing the module
# until loading the plugin, probably via setuptools entry points.
import prapti.plugins.endpoints.openai_chat_responder
import prapti.plugins.endpoints.gpt4all_chat_responder
import prapti.plugins.endpoints.koboldcpp_text_responder
import prapti.plugins.experimental_gitlog
import prapti.plugins.include
import prapti.plugins.experimental_agents
import prapti.plugins.prapti_test_config
import prapti.plugins.prapti_test_responder
import prapti.plugins.prapti_test_actions
plugins = [
    prapti.plugins.endpoints.openai_chat_responder.prapti_plugin,
    prapti.plugins.endpoints.gpt4all_chat_responder.prapti_plugin,
    prapti.plugins.endpoints.koboldcpp_text_responder.prapti_plugin,
    prapti.plugins.experimental_gitlog.prapti_plugin,
    prapti.plugins.include.prapti_plugin,
    prapti.plugins.experimental_agents.prapti_plugin,
    prapti.plugins.prapti_test_config.prapti_plugin,
    prapti.plugins.prapti_test_responder.prapti_plugin,
    prapti.plugins.prapti_test_actions.prapti_plugin,
]
plugins_dict = {plugin.name : plugin for plugin in plugins}

# ^^^ END UNDER CONSTRUCTION /////////////////////////////////////////////////

# ----------------------------------------------------------------------------
# plugin management

def load_plugin(plugin, source_loc: SourceLocation, state: ExecutionState):
    try:
        core_state = get_private_core_state(state)

        plugin_config = setup_newly_constructed_config(plugin.construct_configuration(), empty_factory=EmptyPluginConfiguration, root_config=state.root_config, log=state.log)
        plugin_actions: ActionNamespace = plugin.construct_actions()
        plugin_hooks = plugin.construct_hooks()

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

        setattr(config_attach_point, plugin_name, plugin_config)

        if plugin_actions:
            plugin_actions.set_plugin_config(plugin_config)
            core_state.actions.merge(plugin_actions)

        core_state.loaded_plugins.add(plugin)

        if plugin_hooks:
            hooks_context = hooks.HooksContext(state=state, root_config=state.root_config, plugin_config=plugin_config, hooks=plugin_hooks)
            plugin_hooks.on_plugin_loaded(hooks_context)
            core_state.hooks_distributor.add_hooks(hooks_context)
    except Exception as e:
        state.log.error("load-plugin-exception", f"exception while loading plugin '{plugin.name}': {repr(e)}", source_loc)
        state.log.logger.debug(e, exc_info=True)

@builtin_actions.add_action("prapti.plugins.load")
def plugins_load(name: str, raw_args: str, context: ActionContext) -> None|str|Message:
    core_state = get_private_core_state(context.state)
    global plugins, plugins_dict
    plugin_name = raw_args.strip()
    if plugin := plugins_dict.get(plugin_name, None):
        if plugin not in core_state.loaded_plugins:
            load_plugin(plugin, context.source_loc, context.state)
    else:
        context.log.error("plugin-not-found", f"couldn't load plugin '{plugin_name}'. plugin not found. use `%!plugins.list` to list available plugins.", context.source_loc)
    return None

@builtin_actions.add_action("!prapti.plugins.list")
def plugins_list(name: str, raw_args: str, context: ActionContext) -> None|str|Message:
    core_state = get_private_core_state(context.state)
    global plugins
    if len(plugins) > 0:
        plugin_lines = [f"- **`{plugin.name}`**: {plugin.description}{' (loaded)' if plugin in core_state.loaded_plugins else ''}" for plugin in plugins]
        content = "Available plugins:\n\n" + "\n".join(plugin_lines)
    else:
        content = "No plugins found."

    return Message("_prapti", "plugins", [content], is_enabled=False)

# ----------------------------------------------------------------------------
# responder management

def lookup_active_responder(state: ExecutionState) -> tuple[str, ResponderContext|None]:
    core_state = get_private_core_state(state)
    responder_name = state.root_config.prapti.responder_stack[-1] if state.root_config.prapti.responder_stack else "default"
    responder_name = core_state.hooks_distributor.on_lookup_active_responder(responder_name)
    return (responder_name, core_state.responder_contexts.get(responder_name, None))

@builtin_actions.add_action("prapti.responder.new")
def responder_new(name: str, raw_args: str, context: ActionContext) -> None|str|Message:
    core_state = get_private_core_state(context.state)
    global plugins_dict
    responder_name, plugin_name = raw_args.split()
    if plugin := plugins_dict.get(plugin_name, None):
        if plugin not in core_state.loaded_plugins:
            load_plugin(plugin, context.source_loc, context.state)
        if plugin in core_state.loaded_plugins:
            if responder := plugin.construct_responder():
                plugin_config = getattr(context.root_config.plugins, plugin_name, None)
                responder_context = ResponderContext(state=context.state,
                                                     plugin_name=plugin_name,
                                                     root_config=context.root_config, plugin_config=plugin_config, responder_config=None,
                                                     responder_name=responder_name, responder=responder, log=context.log)
                responder_context.responder_config = setup_newly_constructed_config(responder.construct_configuration(responder_context), empty_factory=EmptyResponderConfiguration, root_config=context.root_config, log=context.log)
                core_state.responder_contexts[responder_name] = responder_context
                setattr(context.root_config.responders, responder_name, responder_context.responder_config)
            else:
                context.log.error("failed-responder-new", "couldn't construct responder '{responder_name}'. plugin '{plugin_name}' did not construct responder.", context.source_loc)
    else:
        context.log.error("plugin-not-found", "couldn't locate responder provider plugin '{plugin_name}'. plugin not found. use `%!plugins.list` to list available plugins.", context.source_loc)

@builtin_actions.add_action("prapti.responder.push")
def responder_push(name: str, raw_args: str, context: ActionContext) -> None|str|Message:
    responder_name = raw_args.strip()
    context.root_config.prapti.responder_stack.append(responder_name)

@builtin_actions.add_action("prapti.responder.pop")
def responder_pop(name: str, raw_args: str, context: ActionContext) -> None|str|Message:
    if context.root_config.prapti.responder_stack:
        context.root_config.prapti.responder_stack.pop()

# ----------------------------------------------------------------------------
# configuration inspection

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
    #core_state = get_private_core_state(context.state)
    root_config = context.root_config

    content = "Configuration parameters:\n\n" + _config_dump(None, "root", root_config, indent=0, root_config=root_config, log=context.log)

    return Message("_prapti", "inspect", [content], is_enabled=False)
