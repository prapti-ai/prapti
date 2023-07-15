"""
    Builtin actions.
"""
import traceback

from ._core_execution_state import get_private_core_state
from .execution_state import ExecutionState
from .configuration import EmptyPluginConfiguration, EmptyResponderConfiguration
from .command_message import Message
from .action import ActionNamespace
from .responder import ResponderContext
from . import hooks

builtin_actions: ActionNamespace = ActionNamespace()

# ----------------------------------------------------------------------------
# /// DANGER -- UNDER CONSTRUCTION ///////////////////////////////////////////

# plugin registry

# HACK: right now we manually import all of the plugins and add their entry points
# to the plugins array. in future we will want to avoid importing the module
# until loading the plugin, probably via setuptools entry points.
import prapti.plugins.openai_chat_responder
import prapti.plugins.gpt4all_chat_responder
import prapti.plugins.experimental_gitlog
import prapti.plugins.include
import prapti.plugins.prapti_test_actions
import prapti.plugins.experimental_agents
plugins = [
    prapti.plugins.openai_chat_responder.prapti_plugin,
    prapti.plugins.gpt4all_chat_responder.prapti_plugin,
    prapti.plugins.experimental_gitlog.prapti_plugin,
    prapti.plugins.include.prapti_plugin,
    prapti.plugins.prapti_test_actions.prapti_plugin,
    prapti.plugins.experimental_agents.prapti_plugin
]
plugins_dict = {plugin.name : plugin for plugin in plugins}

# ^^^ END UNDER CONSTRUCTION /////////////////////////////////////////////////

# ----------------------------------------------------------------------------
# plugin management

def load_plugin(plugin, state: ExecutionState):
    try:
        core_state = get_private_core_state(state)
        # setup
        plugin_config = plugin.construct_configuration() or EmptyPluginConfiguration()
        plugin_actions = plugin.construct_actions()
        plugin_hooks = plugin.construct_hooks()
        # commit
        setattr(state.root_config.plugins, plugin.name, plugin_config)
        if plugin_actions:
            plugin_actions.merge_into(core_state.actions)
        core_state.loaded_plugins.add(plugin)
        if plugin_hooks:
            hooks_context = hooks.HooksContext(state=state, root_config=state.root_config, plugin_config=plugin_config, hooks=plugin_hooks)
            plugin_hooks.on_plugin_loaded(hooks_context)
            core_state.hooks_distributor.add_hooks(hooks_context)
    except Exception as e:
        print(f"warning: exception caught while loading plugin {plugin.name}: {e}")
        traceback.print_exc()
        print("---")

@builtin_actions.add_action("plugins.load")
def plugins_load(name: str, raw_args: str, state: ExecutionState) -> None|str|Message:
    core_state = get_private_core_state(state)
    global plugins, plugins_dict
    plugin_name = raw_args.strip()
    if plugin := plugins_dict.get(plugin_name, None):
        if plugin not in core_state.loaded_plugins:
            load_plugin(plugin, state)
    else:
        print(f"warning: couldn't load plugin '{plugin_name}'. not found.")
    return None

@builtin_actions.add_action("!plugins.list")
def plugins_list(name: str, raw_args: str, state: ExecutionState) -> None|str|Message:
    core_state = get_private_core_state(state)
    global plugins
    if len(plugins) > 0:
        plugin_lines = [f"- **`{plugin.name}`**: {plugin.description}{' (loaded)' if plugin in core_state.loaded_plugins else ''}" for plugin in plugins]
        content = "Available plugins:\n\n" + "\n".join(plugin_lines)
    else:
        content = "No plugins found."

    return Message("_prapti", "plugins", [content], _is_enabled=False)

# ----------------------------------------------------------------------------
# responder management

def lookup_active_responder(state: ExecutionState) -> tuple[str, ResponderContext|None]:
    core_state = get_private_core_state(state)
    responder_name = state.root_config.responder_stack[-1] if state.root_config.responder_stack else "default"
    responder_name = core_state.hooks_distributor.on_lookup_active_responder(responder_name)
    return (responder_name, core_state.responder_contexts.get(responder_name, None))

@builtin_actions.add_action("responder.new")
def responder_new(name: str, raw_args: str, state: ExecutionState) -> None|str|Message:
    core_state = get_private_core_state(state)
    global plugins_dict
    responder_name, plugin_name = raw_args.split()
    if plugin := plugins_dict.get(plugin_name, None):
        if plugin not in core_state.loaded_plugins:
            load_plugin(plugin, state)
        if plugin in core_state.loaded_plugins:
            if responder := plugin.construct_responder():
                plugin_config = getattr(state.root_config.plugins, plugin_name, None)
                responder_context = ResponderContext(plugin_name=plugin_name,
                                                     root_config=state.root_config, plugin_config=plugin_config, responder_config=EmptyResponderConfiguration(),
                                                     responder_name=responder_name, responder=responder)
                responder_context.responder_config = responder.construct_configuration(responder_context) or responder_context.responder_config
                core_state.responder_contexts[responder_name] = responder_context
                setattr(state.root_config.responders, responder_name, responder_context.responder_config)
            else:
                print("warning: '{plugin_name}' did not construct responder.")
    else:
        print("warning: couldn't locate responder provider plugin '{plugin_name}'. not found.")

@builtin_actions.add_action("responder.push")
def responder_push(name: str, raw_args: str, state: ExecutionState) -> None|str|Message:
    responder_name = raw_args.strip()
    state.root_config.responder_stack.append(responder_name)

@builtin_actions.add_action("responder.pop")
def responder_pop(name: str, raw_args: str, state: ExecutionState) -> None|str|Message:
    if state.root_config.responder_stack:
        state.root_config.responder_stack.pop()

# ----------------------------------------------------------------------------
