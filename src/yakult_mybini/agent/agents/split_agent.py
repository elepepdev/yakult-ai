"""
Split Agent v2 — Multi-tool-group routing.

- Persona Agent: handles personality, conversation, memory, emotions
- Tool Agent: routes intent to tool sub-group, calls tools with minimal prompt
- Each sub-group has 3-22 tools so system prompt stays small

Flow: User → Route → ToolGroup → results → Persona Agent → response
"""

from typing import AsyncIterator, List, Dict, Any, Optional, Callable
from loguru import logger

from .agent_interface import AgentInterface
from .basic_memory_agent import BasicMemoryAgent
from .tool_agent import ToolAgent, ToolResult
from ..input_types import BatchInput
from ..output_types import SentenceOutput, DisplayText
from ..tool_groups import get_default_groups, filter_tool_definitions, ROUTER_SYSTEM
from ...mcpp.tool_manager import ToolManager


class SplitAgent(AgentInterface):
    """Orchestrator that routes user intent to the right tool sub-group.

    Each tool sub-group has a minimal system prompt + only its own tool
    definitions, keeping the total request well under 8K chars for Groq.
    """

    def __init__(
        self,
        persona_agent: BasicMemoryAgent,
        tool_agent: ToolAgent,
        tool_manager: Optional[ToolManager] = None,
    ):
        super().__init__()
        self._persona = persona_agent
        self._tool_agent = tool_agent  # base ToolAgent (used for its LLM reference)
        self._tool_manager = tool_manager
        self._memory_manager = None
        self._todo_manager = None
        self._tool_groups = get_default_groups()
        logger.info(
            f"SplitAgent initialized: persona={type(persona_agent._llm).__name__}, "
            f"tool={type(tool_agent._llm).__name__}, "
            f"groups={list(self._tool_groups.keys())}"
        )

    async def chat(self, input_data: BatchInput) -> AsyncIterator[SentenceOutput]:
        """Route intent → tool group → result → persona response."""
        user_text = self._to_text(input_data)
        if not user_text:
            logger.warning("SplitAgent: empty user input")
            async for out in self._persona.chat(input_data):
                yield out
            return

        # 1. Route intent to a tool group
        route_tool_id = f"route_{int(time.time() * 1000)}"
        yield SentenceOutput(
            text="",
            display=DisplayText(text="", name="", avatar=""),
            extra_data={
                "type": "tool_call_status",
                "tool_id": route_tool_id,
                "tool_name": "route_intent",
                "status": "running",
                "content": "Delegating user request to specialist...",
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            },
        )

        group_name = await self._route_intent(user_text)

        yield SentenceOutput(
            text="",
            display=DisplayText(text="", name="", avatar=""),
            extra_data={
                "type": "tool_call_status",
                "tool_id": route_tool_id,
                "tool_name": f"delegated_to_{group_name}",
                "status": "completed" if group_name != "none" else "completed",
                "content": f"Delegated to group: {group_name}",
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            },
        )

        # 2. Get recent context from persona
        recent_context = self._persona.get_recent_context(n=2)
        logger.debug(
            f"SplitAgent: routed='{group_name}' ctx={len(recent_context)} msgs "
            f"for '{user_text[:60]}...'"
        )

        # 3. Run tool agent for the selected group (or skip if 'none')
        tool_result = ToolResult()
        if group_name != "none" and group_name in self._tool_groups:
            # Create a queue to stream status updates in real-time
            status_queue = asyncio.Queue()

            async def _on_status(status_dict: dict):
                await status_queue.put(status_dict)

            async def _run_task():
                res = await self._run_group_agent(
                    group_name, user_text, recent_context, on_status_update=_on_status
                )
                await status_queue.put(None)
                return res

            agent_task = asyncio.create_task(_run_task())

            while True:
                status_item = await status_queue.get()
                if status_item is None:
                    break
                yield SentenceOutput(
                    text="",
                    display=DisplayText(text="", name="", avatar=""),
                    extra_data=status_item,
                )

            tool_result = await agent_task

        # 4. Inject results into persona
        if tool_result.tool_was_called and tool_result.tool_results:
            logger.info(
                f"SplitAgent: {len(tool_result.tool_results)} tool result(s) "
                f"injected into persona"
            )
            summary_lines = []
            for r in tool_result.tool_results:
                content = ""
                if isinstance(r, dict):
                    content = r.get("content", str(r))
                else:
                    content = str(r)
                summary_lines.append(content)
            summary = "\n".join(summary_lines)
            self._persona._add_message(
                f"[Tool Results]\n{summary}",
                role="system",
                skip_memory=True,
            )
        elif tool_result.error:
            logger.warning(f"SplitAgent: tool error: {tool_result.error}")
            self._persona._add_message(
                f"[Tool Error] {tool_result.error}",
                role="system",
                skip_memory=True,
            )

        # 5. Persona generates final response
        async for out in self._persona.chat(input_data):
            yield out

    async def _route_intent(self, user_text: str) -> str:
        """Route user intent to a tool group via light LLM call."""
        try:
            stream = self._tool_agent._llm.chat_completion(
                messages=[{"role": "user", "content": user_text}],
                system=ROUTER_SYSTEM,
                tools=[],
            )
            full = ""
            async for chunk in stream:
                if isinstance(chunk, str):
                    full += chunk
                elif isinstance(chunk, dict) and chunk.get("type") == "text_delta":
                    full += chunk.get("text", "")
            group = full.strip().lower().split()[0] if full.strip() else "none"
            valid = set(self._tool_groups.keys()) | {"none"}
            if group not in valid:
                logger.debug(f"SplitAgent: unknown route '{group}', fallback to 'none'")
                return "none"
            return group
        except Exception as e:
            logger.warning(f"SplitAgent: routing failed: {e}")
            return "none"

    async def _run_group_agent(
        self,
        group_name: str,
        user_text: str,
        recent_context: List[Dict[str, Any]],
        on_status_update: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> ToolResult:
        """Run a ToolAgent for a specific tool group with minimal prompt."""
        group = self._tool_groups[group_name]
        logger.info(f"SplitAgent: running group '{group_name}' ({len(group.tool_names)} tools)")

        # Filter tool definitions to only this group
        tools = self._tool_manager.get_filtered_tools(
            "OpenAI",
            group.tool_names,
        ) if self._tool_manager else []

        if not tools:
            logger.warning(f"SplitAgent: no tools found for group '{group_name}'")
            return ToolResult(error=f"No tools for group '{group_name}'")

        # Create a temporary ToolAgent for this group
        group_agent = ToolAgent(
            llm=self._tool_agent._llm,
            tool_executor=self._tool_agent._tool_executor,
            tool_manager=self._tool_manager,
            system_prompt=group.system_prompt,
            max_tool_rounds=5,
        )
        # Override its tools with the filtered set
        group_agent._tools = tools

        return await group_agent.process(
            user_message=user_text,
            conversation_context=recent_context,
            on_status_update=on_status_update,
        )

    def handle_interrupt(self, heard_response: str) -> None:
        self._persona.handle_interrupt(heard_response)

    def set_memory_from_history(self, conf_uid: str, history_uid: str) -> None:
        self._persona.set_memory_from_history(conf_uid, history_uid)

    def set_memory_manager(self, memory_manager) -> None:
        self._memory_manager = memory_manager
        self._persona.set_memory_manager(memory_manager)

    def set_todo_manager(self, todo_manager) -> None:
        self._todo_manager = todo_manager
        self._persona.set_todo_manager(todo_manager)

    def set_conf_uid(self, conf_uid: str) -> None:
        self._persona.set_conf_uid(conf_uid)

    def get_memory_prompt(self) -> str:
        return self._persona.get_memory_prompt()

    @staticmethod
    def _to_text(input_data: BatchInput) -> str:
        parts = []
        for text_data in input_data.texts:
            parts.append(text_data.content)
        return "\n".join(parts).strip()
