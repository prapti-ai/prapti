"""
    Proof-of-concept for multiple agents

    - treat responder instances as agents
    - @-mentions cause responder to be prioritised for current message
    - filter separate system prompts for each agent by responder name (REVIEW: maybe this should be a global feature?)
    - when one agent is prompted, other agents appear as users
    - track pending @-mentions and give each mentioned agent a turn to respond
    - % !agents.discuss command can be used to run multi-turn agent conversations
    - % !agents.ask command can be used to address a specific agent
    - commands to run rounds of automatic agent prompting e.g.
        % !agents.discuss n [agent names] [--random]
        % agents.set_group <agent names>  # default set of agents used for rounds

    #TODO:
    - --random parameter to agents.discuss
    - setting to disable @-mention processing
    - provide a way for !discuss to specify the agent who should start (currently uses LRU and @-mentions)
"""
# ----------------------------------------------------------------------------
# /// DANGER -- UNDER CONSTRUCTION ///////////////////////////////////////////

import copy
import random
import re
from typing import AsyncGenerator
from asyncio import Semaphore

from pydantic import BaseModel, Field, ConfigDict
from cancel_token import CancellationToken

from ..core.plugin import Plugin, PluginCapabilities, PluginContext
from ..core.action import ActionNamespace, ActionContext
from ..core.command_message import Message
from ..core.responder import Responder, ResponderContext
from ..core.configuration import VarRef, resolve_var_refs
from ..core.builtins import delegate_generate_responses

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
        !agents.discuss n [agent_name1 ...]
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
    # we can kick-off the discussion by @-mentioning the first participant in a hidden message
    # right now the user has to @-mention the first user manually to get a specific user to start.
    #return [Message(role="_prapti.experimental.agents", name=None, content=[f"@{agent_name}"])]
    return None

@_actions.add_action("!agents.ask")
def ask(name: str, raw_args: str, context: ActionContext) -> None|str|Message:
    """prompt a single agent.
    usage:
        !agents.ask agent_name
    """
    args = raw_args.split()
    if len(args) != 1:
        context.log.info("agents.ask-usage", "usage: !agents.ask agent_name", context.source_loc)
        return None

    context.plugin_config.remaining_discussion_message_count = 1
    context.plugin_config.discussion_group = [args[0]]

class AgentsResponderConfiguration(BaseModel):
    """Configuration parameters for agents responder."""
    model_config = ConfigDict(
        validate_assignment=True)

async def _async_message_content_processor(message: Message, async_content: AsyncGenerator[str, None], sem: Semaphore) -> AsyncGenerator[str, None]:
    try:
        async for s in async_content:
            message.content.append(s)
            yield s
    finally:
        sem.release()

class AgentsResponder(Responder):
    """Responder that controls discussion between agents."""

    def __init__(self):
        # state used for manipulating message_sequence during a single generate_responses call:
        self._disabled_messages: list[Message] = []
        self._assistant_messages_switched_to_user: list[Message] = []

    def construct_configuration(self, context: ResponderContext) -> BaseModel|tuple[BaseModel, list[tuple[str,VarRef]]]|None:
        return AgentsResponderConfiguration(), []

    def _update_pending_at_mentions(self, pending_at_mentions: set[str], message: Message):
        if not message.is_enabled or message.role == "system":
            return

        # an @-mention is no longer pending once the named agent speaks
        if message.name:
            pending_at_mentions.discard(message.name)

        # accumulate @-mentions in this message
        for span in message.content:
            if isinstance(span, str):
                for match in at_mention_regex.finditer(span):
                    agent_name = match.group(1)
                    pending_at_mentions.add(agent_name)

    def _compute_pending_at_mentions(self, message_sequence: list[Message], context: ResponderContext) -> set[str]:
        pending_at_mentions: set[str] = set()
        for message in message_sequence:
            self._update_pending_at_mentions(pending_at_mentions, message)
        return pending_at_mentions

    def _compute_participants_LRU(self, message_sequence: list[Message], participants: set[str], context: ResponderContext):
        MRU = [] # most recently mentioned at front
        for message in reversed(message_sequence):
            if not message.is_enabled or message.name not in participants:
                continue
            agent_name = message.name
            if agent_name not in MRU:
                MRU.append(agent_name)
            if len(MRU) == len(participants):
                break
        return list(participants - set(MRU)) + list(reversed(MRU)) # least recently (or never) mentioned at front

    def _switch_roles_for_selected_agent(self, message_sequence: list[Message], selected_agent_name: str):
        """switch roles in the input message sequence so that names and roles
          appear as if viewed from the selected agent's perspective. i.e. other agents
          appear as users, and only global and the selected agent's system prompts are active."""

        for message in message_sequence:
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

    def _restore_switched_roles(self):
        """set name associated with response messages to agent's name"""

        # restore message enable and role for next round (in case there is a followup)
        for message in self._disabled_messages:
            message.is_enabled = True
        self._disabled_messages.clear()

        for message in self._assistant_messages_switched_to_user:
            message.role = "assistant"
        self._assistant_messages_switched_to_user.clear()

    def _valid_discussion_group_participants(self, plugin_config: AgentsPluginConfiguration, context: ResponderContext) -> set[str]:
        result = set()
        for agent_name in plugin_config.discussion_group:
            if hasattr(context.root_config.responders, agent_name): # a responder exists with /name/
                result.add(agent_name)
            else:
                context.log.error("no-rexponder-for-agent", f"prapti.experimental.agents: discussion_group specifies agent '{agent_name}' but no responder exists with that name.")
        return result

    async def _async_response_generator(self, input_: list[Message], cancellation_token: CancellationToken, context: ResponderContext) -> AsyncGenerator[Message, None]:
        config: AgentsResponderConfiguration = context.responder_config
        context.log.debug(f"prapti.experimental.agents: input: {config = }", context.state.input_file_path)
        config = resolve_var_refs(config, context.root_config, context.log)
        context.log.debug(f"prapti.experimental.agents: resolved: {config = }", context.state.input_file_path)

        message_sequence = copy.deepcopy(input_)

        plugin_config = resolve_var_refs(context.plugin_config, context.root_config, context.log)
        participants: set[str] = self._valid_discussion_group_participants(plugin_config, context)

        if not participants:
            context.log.warning("agents-no-participants", "prapti.experimental.agents: could not continue discussion. no valid participants specified in discussion_group.")
            return

        all_pending_at_mentions: set[str] = self._compute_pending_at_mentions(message_sequence, context) # all @-mentions, not limited to participants or even agents/responders
        participants_LRU: list[str] = self._compute_participants_LRU(message_sequence, participants, context) # front is least recent
        assert len(participants_LRU) == len(participants)

        if context.plugin_config.remaining_discussion_message_count <= 0:
            context.plugin_config.remaining_discussion_message_count = 1

        while context.plugin_config.remaining_discussion_message_count > 0:

            # select agent
            if participant_at_mentions := (all_pending_at_mentions & participants):
                selected_agent_name = random.choice(list(participant_at_mentions))
                # REVIEW: ^^^ we could delegate choice to an LLM, or provide explicit commands to control choice
            else:
                selected_agent_name = participants_LRU[0] # participants_LRU is non-empty here

            self._switch_roles_for_selected_agent(message_sequence, selected_agent_name)

            async_agent_responses = delegate_generate_responses(context.state, selected_agent_name, message_sequence, cancellation_token)
            if cancellation_token.cancelled:
                return

            copied_agent_responses = [] # collect a local copy of the messages
            async_content_completion_sem = Semaphore(value=0)
            async_content_count = 0
            async for message in async_agent_responses:
                # name assistant responses according to the name of the agent that generated them
                if message.role == "assistant" and not message.name:
                    message.name = selected_agent_name

                async_content = message.async_content
                message.async_content = None # avoid deep copying the async content

                # collect a copy of generated messages for synchronous processing within the agent loop
                message_copy = copy.deepcopy(message)
                if async_content:
                    # _async_content_processor passes through the asynchronous stream of message content
                    # and simultaneously accumulates it into our local copy: message_copy.content
                    message.async_content = _async_message_content_processor(message_copy, async_content, async_content_completion_sem)
                    async_content_count += 1
                copied_agent_responses.append(message_copy)

                # yield the original generated messages to the client for output and streaming
                yield message

            # wait for all _async_message_content_processor processing to complete
            # i.e. for all async content to arrive
            for _ in range(0, async_content_count):
                await async_content_completion_sem.acquire()

            if cancellation_token.cancelled:
                return

            self._restore_switched_roles()

            for message in copied_agent_responses:
                message.content = ["".join(message.content).strip()] # flatten the message content to a single string

                # decrement discussion counter for any messages in discussion, whether @-mentions or other
                if message.name in context.plugin_config.discussion_group:
                    context.plugin_config.remaining_discussion_message_count -= 1 if context.plugin_config.remaining_discussion_message_count else 0

                self._update_pending_at_mentions(all_pending_at_mentions, message) # important: call this *after* setting message.name

                assert selected_agent_name in participants_LRU
                participants_LRU.remove(selected_agent_name)
                participants_LRU.append(selected_agent_name)

            message_sequence += copied_agent_responses

            if participant_at_mentions:
                participant_at_mentions.add(participants_LRU[0])
                # ^^^ fake @-mention of least-recent participant
                # this hopefully ensures that all participants get a turn even if they are also @-mentioning each other

    def generate_responses(self, input_: list[Message], cancellation_token: CancellationToken, context: ResponderContext) -> AsyncGenerator[Message, None]:
        return self._async_response_generator(input_, cancellation_token, context)

# ^^^ END UNDER CONSTRUCTION /////////////////////////////////////////////////
# ----------------------------------------------------------------------------

class AgentsPlugin(Plugin):
    def __init__(self):
        super().__init__(
            api_version = "0.1.0",
            name = "prapti.experimental.agents",
            version = "0.0.2",
            description = "Multi-agent responses",
            capabilities = PluginCapabilities.ACTIONS | PluginCapabilities.RESPONDER
        )

    def construct_configuration(self, context: PluginContext) -> BaseModel|tuple[BaseModel, list[tuple[str,VarRef]]]|None:
        return AgentsPluginConfiguration()

    def construct_actions(self, context: PluginContext) -> ActionNamespace|None:
        return _actions

    def construct_responder(self, context: PluginContext) -> Responder|None:
        return AgentsResponder()

prapti_plugin = AgentsPlugin()
