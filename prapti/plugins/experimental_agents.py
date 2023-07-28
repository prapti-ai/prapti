""""
    Proof-of-concept for multiple agents

    - treat responder instances as agents
    - @-mentions cause responder to be prioritised for current message
    - filter separate system prompts for each agent by responder name (REVIEW: maybe this should be a global feature?)
    - when one agent is prompted, other agents appear as users
    - track pending @-mentions and give each mentioned agent a turn to respond
    - % !agents.discuss command can be used to run multi-turn agent conversations
    - commands to run rounds of automatic agent prompting e.g.
        % !agents.discuss n [agent names] [--random]
        % agents.set_group <agent names>  # default set of agents used for rounds

    #TODO:
    - --random parameter to agents.discuss
    - setting to disable @-mention processing

    ideas:
    - i don't like the way we're counting down the discussion. it's very brittle
      and its not resumable.
    - if actions had direct access to the containing message, instead of maintaining a counter,
    we could store a checkpoint (message, n) for the most recent discuss command
    then count backwards in the message history

"""
# ----------------------------------------------------------------------------
# /// DANGER -- UNDER CONSTRUCTION ///////////////////////////////////////////

import re
import typing

from pydantic import BaseModel, Field

from ..core.plugin import Plugin
from ..core.action import ActionNamespace, ActionContext
from ..core.hooks import Hooks, HooksContext
from ..core.command_message import Message

at_mention_regex = re.compile(r"@(\w+)")

_actions: ActionNamespace = ActionNamespace()

class AgentsPluginConfiguration(BaseModel):
    remaining_discussion_message_count: int = 0 # counter of remaining generations
    discussion_group: list[str] = Field(default_factory=list)

@_actions.add_action("agents.set_group")
def set_group(name: str, raw_args: str, context: ActionContext) -> None|str|Message:
    """set discussion group for manual cycling
    usage:
        agents.set_group agent_name1 [agent_name2 ...]
    """
    args = raw_args.split()
    context.plugin_config.discussion_group = args
    return None

@_actions.add_action("!agents.discuss")
def discuss(name: str, raw_args: str, context: ActionContext) -> None|str|Message:
    """run round-robin agent discussions
    usage:
        agents.discuss n [agent_name1 ...]
    will use the previously set agent group if none is specified
    """
    args = raw_args.split()
    if len(args) < 1:
        context.log.info("agents.discuss-usage", "usage: agents.discuss n [agent_name ...]", context.source_loc)
        return None

    context.plugin_config.remaining_discussion_message_count = int(args[0])
    if len(args) > 1:
        context.plugin_config.discussion_group = args[1:]

    # TODO: when we add the ability for actions to insert messages before/after the current message
    # we can kick-off the discussion by @-mentioning the first participant in a private message
    # right now the user has to @-mention the first user manually to get a specific user to start.
    #return [Message(role="_prapti.experimental.agents", name=None, content=[f"@{agent_name}"])]
    return None

class AgentsHooks(Hooks):
    def __init__(self):
        self._disabled_messages: list[Message] = []
        self._assistant_messages_switched_to_user: list[Message] = []
        pass

    def on_plugin_loaded(self, context: HooksContext):
        pass

    def _update_pending_at_mentions(self, message: Message, pending_at_mentions: set[str]):
        if not message.is_enabled or message.role == "system":
            return

        # an @-mention is no longer pending once the named agent speaks
        if message.name:
            pending_at_mentions.discard(message.name)

        # accumulate @-mentions in this message
        for span in message.content:
            if isinstance(span, str):
                for match in at_mention_regex.finditer(span):
                    pending_at_mentions.add(match.group(1))

    def _compute_pending_at_mentions(self, context: HooksContext) -> set[str]:
        pending_at_mentions: set[str] = set()
        for message in context.state.message_sequence:
            self._update_pending_at_mentions(message, pending_at_mentions)
        return pending_at_mentions

    def _pop_valid_pending_at_mention(self, pending_at_mentions: set[str], context: HooksContext) -> str|None:
        """ find valid pending @-mentioned agent.
        limit to instantiated responder names (i.e. deal with the fact that
        some @-mentions in message text may not in-fact be agents/responders)."""
        while len(pending_at_mentions) > 0:
            name = pending_at_mentions.pop()
            # REVIEW: ^^^this is more-or-less random choice, we could
            # delegate choice to an LLM, or provide explicit commands
            if hasattr(context.root_config.responders, name): # a responder exists with /name/
                return name
        return None

    def _find_least_recenth_discussion_group_participant(self, context: HooksContext) -> str|None:
        if context.plugin_config.discussion_group:
            # find the least recently participating discussion participant and give them a turn
            # return an arbitrary element if not all participants have sent a message
            X = set(context.plugin_config.discussion_group)
            if len(X) > 1:
                for message in reversed(context.state.message_sequence):
                    if message.is_enabled and message.name in context.plugin_config.discussion_group and message.name in X:
                        X.remove(message.name)
                        if len(X) == 1:
                            break
            return X.pop()
        return None

    def _select_agent(self, context: HooksContext) -> str|None:
        if pending_at_mentions := self._compute_pending_at_mentions(context):
            return self._pop_valid_pending_at_mention(pending_at_mentions, context)
        return self._find_least_recenth_discussion_group_participant(context)

    def on_lookup_active_responder(self, responder_name: str, context: HooksContext) -> str:
        return self._select_agent(context) or responder_name

    def on_before_generate_responses(self, context: HooksContext):
        """switch roles in the input message sequence so that names and roles
          appear as if viewed from the selected agent's perspective. i.e. other agents
          appear as users, and only global and the selected agent's system prompts are active."""

        selected_agent_name = context.state.selected_responder_context.responder_name

        for message in context.state.message_sequence:
            match message.role:
                case "system":
                    # retain only global system messages (those without a name)
                    # and system messages for the active agent. disable other system messages.
                    if message.name and message.name != selected_agent_name:
                        message.is_enabled = False
                        self._disabled_messages.append(message)
                case "assistant":
                    if message.name != selected_agent_name:
                        message.role = "user" # other agents will appear to be users
                        self._assistant_messages_switched_to_user.append(message)
                case "user":
                    pass
                case _:
                    pass

    def on_after_generate_responses(self, context: HooksContext):
        """set name associated with response messages to agent's name"""

        # restore message enable and role for next round (in case there is a followup)
        for message in self._disabled_messages:
            message.is_enabled = True
        self._disabled_messages.clear()

        for message in self._assistant_messages_switched_to_user:
            message.role = "assistant"
        self._assistant_messages_switched_to_user.clear()

        # name assistant responses according to the name of the agent that generated them
        agent_name = context.state.selected_responder_context.responder_name
        for message in context.state.responses:
            if message.role == "assistant" and not message.name:
                message.name = agent_name

            # decrement discussion counter for any messages in discussion, whether @-mentions or other
            if message.name in context.plugin_config.discussion_group:
                context.plugin_config.remaining_discussion_message_count -= 1 if context.plugin_config.remaining_discussion_message_count else 0

    def on_response_completed(self, context: HooksContext):
        pass

    def on_followup(self, context: HooksContext) -> tuple[bool, list[Message]|None]:
        if context.plugin_config.discussion_group and context.plugin_config.remaining_discussion_message_count > 0:
            if agent_name := self._find_least_recenth_discussion_group_participant(context):
                # trigger the agent by @-mentioning them. This will be picked up in on_before_generate_responses
                # this hopefully ensures that all participants get a turn even if they are also @-messaging each other
                return True, [Message(role="_prapti.experimental.agents", name=None, content=[f"@{agent_name}"])]
        return False, None

# ^^^ END UNDER CONSTRUCTION /////////////////////////////////////////////////
# ----------------------------------------------------------------------------

class AgentsPlugin(Plugin):
    def __init__(self):
        super().__init__(
            api_version = "0.1.0",
            name = "prapti.experimental.agents",
            version = "0.0.1",
            description = "Multi-agent responses"
        )

    def construct_actions(self) -> ActionNamespace|None:
        return _actions

    def construct_configuration(self) -> typing.Any|None:
        return AgentsPluginConfiguration()

    def construct_hooks(self) -> Hooks|None:
        return AgentsHooks()

prapti_plugin = AgentsPlugin()
