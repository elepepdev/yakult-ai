import json
import re
import shlex
import uuid
import asyncio
from datetime import datetime, timezone
from typing import (
    AsyncIterator,
    List,
    Dict,
    Any,
    Callable,
    Literal,
    Union,
    Optional,
)
from loguru import logger
from .agent_interface import AgentInterface
from ..output_types import SentenceOutput, DisplayText
from ..stateless_llm.stateless_llm_interface import StatelessLLMInterface
from ..stateless_llm.claude_llm import AsyncLLM as ClaudeAsyncLLM
from ..stateless_llm.openai_compatible_llm import AsyncLLM as OpenAICompatibleAsyncLLM
from ...chat_history_manager import get_history
from ..transformers import (
    sentence_divider,
    actions_extractor,
    tts_filter,
    display_processor,
)
from ...config_manager import TTSPreprocessorConfig
from ..input_types import BatchInput, TextSource
from prompts import prompt_loader
from ...mcpp.tool_manager import ToolManager
from .tool_agent import ToolAgent

from ...mcpp.json_detector import StreamJSONDetector
from ...mcpp.types import ToolCallObject, ToolCallFunctionObject
from ...mcpp.tool_executor import ToolExecutor
from ..structured_response_manager import StructuredResponseManager
from ..tool_groups import get_summon_specialist_tool


class BasicMemoryAgent(AgentInterface):
    """Agent with basic chat memory and tool calling support."""

    _system: str = "You are a helpful assistant."
    MAX_TOOL_ROUNDS: int = 20

    def __init__(
        self,
        llm: StatelessLLMInterface,
        system: str,
        live2d_model,
        tts_preprocessor_config: TTSPreprocessorConfig = None,
        faster_first_response: bool = True,
        segment_method: str = "pysbd",
        use_mcpp: bool = False,
        tool_routing: str = "legacy",
        interrupt_method: Literal["system", "user"] = "user",
        tool_prompts: Dict[str, str] = None,
        tool_manager: Optional[ToolManager] = None,
        tool_executor: Optional[ToolExecutor] = None,
        mcp_prompt_string: str = "",
        tool_agent: Optional[ToolAgent] = None,
        simple_tool_names: Optional[List[str]] = None,
        specialist_llm: Optional[StatelessLLMInterface] = None,
        tool_groups: Optional[Dict[str, Any]] = None,

    ):
        """Initialize agent with LLM and configuration.

        Args:
            llm: Main LLM for persona/conversation (e.g. Gemini)
            system: System prompt (NO tool prompts in dual-agent mode)
            live2d_model: Live2D/VRM model for expression extraction
            tts_preprocessor_config: TTS preprocessing configuration
            faster_first_response: Whether to respond faster at sentence boundaries
            segment_method: Sentence segmentation method
            use_mcpp: Whether to use MCP tools
            tool_routing: 'legacy' (single LLM) or 'persona_first' (dual-agent)
            interrupt_method: How to signal interruption to LLM
            tool_prompts: Dictionary of tool prompt names
            tool_manager: ToolManager instance
            tool_executor: ToolExecutor instance
            mcp_prompt_string: MCP prompt string
            tool_agent: Optional ToolAgent for dual-agent mode (e.g. Groq for tools)
        """
        super().__init__()
        self._memory = []
        self._max_history_messages = 40  # sliding window: keep last 40 messages (~20 exchanges)
        self._conf_uid = ""
        self._live2d_model = live2d_model
        self._tts_preprocessor_config = tts_preprocessor_config
        self._faster_first_response = faster_first_response
        self._segment_method = segment_method
        self._use_mcpp = use_mcpp
        self._tool_routing = tool_routing
        self.interrupt_method = interrupt_method
        self._tool_prompts = tool_prompts or {}
        self._interrupt_handled = False
        self.prompt_mode_flag = False
        self._tool_round_counter = 0
        self._pending_reflection = False

        self._tool_manager = tool_manager
        self._tool_executor = tool_executor
        self._mcp_prompt_string = mcp_prompt_string
        self._json_detector = StreamJSONDetector()

        # Dual-agent: separate ToolAgent for tool execution
        self._tool_agent: Optional[ToolAgent] = tool_agent
        self._is_dual_agent = tool_agent is not None and tool_routing == "persona_first"

        if self._is_dual_agent:
            logger.info(
                "Dual-agent mode enabled: persona LLM handles conversation, "
                "ToolAgent handles tool execution"
            )

        self._formatted_tools_openai = []
        self._formatted_tools_claude = []
        if self._tool_manager:
            self._formatted_tools_openai = self._tool_manager.get_formatted_tools(
                "OpenAI"
            )
            self._formatted_tools_claude = self._tool_manager.get_formatted_tools(
                "Claude"
            )
            logger.debug(
                f"Agent received pre-formatted tools - OpenAI: {len(self._formatted_tools_openai)}, Claude: {len(self._formatted_tools_claude)}"
            )
        else:
            logger.debug(
                "ToolManager not provided, agent will not have pre-formatted tools."
            )

        # Hybrid mode: persona LLM only sees simple tools + summon_specialist
        self._simple_tool_names = set(simple_tool_names or [])
        self._specialist_llm = specialist_llm
        self._tool_groups = tool_groups or {}

        if self._specialist_llm and self._formatted_tools_openai:
            if self._simple_tool_names:
                filtered = [
                    t for t in self._formatted_tools_openai
                    if t.get("function", {}).get("name") in self._simple_tool_names
                ]
            else:
                filtered = []
            filtered.append(get_summon_specialist_tool())
            self._formatted_tools_openai = filtered
            logger.info(
                f"Hybrid mode: persona LLM gets {len(filtered)} tools "
                f"({len(self._simple_tool_names)} simple + summon_specialist)"
            )

        # Initialize StructuredResponseManager untuk mengatur urutan response
        self._response_manager = StructuredResponseManager()

        self._set_llm(llm)
        self.set_system(system if system else self._system)

        if self._use_mcpp and not all(
            [
                self._tool_manager,
                self._tool_executor,
                self._json_detector,
            ]
        ):
            logger.warning(
                "use_mcpp is True, but some MCP components are missing in the agent. Tool calling might not work as expected."
            )
        elif not self._use_mcpp and any(
            [
                self._tool_manager,
                self._tool_executor,
                self._json_detector,
            ]
        ):
            logger.warning(
                "use_mcpp is False, but some MCP components were passed to the agent."
            )

        logger.info("BasicMemoryAgent initialized.")

    def _set_llm(self, llm: StatelessLLMInterface):
        """Set the LLM for chat completion."""
        self._llm = llm
        self.chat = self._chat_function_factory()

    def set_system(self, system: str):
        """Set the system prompt."""
        logger.debug(f"Memory Agent: Setting system prompt: '''{system}'''")

        if self.interrupt_method == "user":
            system = f"{system}\n\nIf you received `[interrupted by user]` signal, you were interrupted."

        self._system = system

    def _add_message(
        self,
        message: Union[str, List[Dict[str, Any]]],
        role: str,
        display_text: DisplayText | None = None,
        skip_memory: bool = False,
    ):
        """Add message to memory."""
        if skip_memory:
            return

        text_content = ""
        if isinstance(message, list):
            for item in message:
                if item.get("type") == "text":
                    text_content += item["text"] + " "
            text_content = text_content.strip()
        elif isinstance(message, str):
            text_content = message
        else:
            logger.warning(
                f"_add_message received unexpected message type: {type(message)}"
            )
            text_content = str(message)

        if not text_content and role == "assistant":
            return

        message_data = {
            "role": role,
            "content": text_content,
        }

        if display_text:
            if display_text.name:
                message_data["name"] = display_text.name
            if display_text.avatar:
                message_data["avatar"] = display_text.avatar

        if (
            self._memory
            and self._memory[-1]["role"] == role
            and self._memory[-1]["content"] == text_content
        ):
            return

        self._memory.append(message_data)

        # Sliding window: truncate oldest messages if over limit
        if len(self._memory) > self._max_history_messages:
            overflow = len(self._memory) - self._max_history_messages
            logger.debug(f"Memory sliding window: truncating {overflow} oldest messages")
            self._memory = self._memory[-self._max_history_messages:]

    def get_recent_context(self, n: int = 3) -> List[Dict[str, Any]]:
        """Return the last N message exchanges from memory.

        Args:
            n: Number of exchanges (user+assistant pairs) to return.

        Returns:
            List of message dicts with 'role' and 'content' keys.
        """
        recent = self._memory[-n * 2:] if n > 0 else []
        logger.debug(f"get_recent_context({n}): returning {len(recent)} messages")
        return recent

    def set_memory_from_history(self, conf_uid: str, history_uid: str) -> None:
        """Load memory from chat history."""
        self._conf_uid = conf_uid
        messages = get_history(conf_uid, history_uid)

        self._memory = []
        for msg in messages:
            role = "user" if msg["role"] == "human" else "assistant"
            content = msg["content"]
            if isinstance(content, str) and content:
                self._memory.append(
                    {
                        "role": role,
                        "content": content,
                    }
                )
            else:
                logger.warning(f"Skipping invalid message from history: {msg}")
        logger.info(f"Loaded {len(self._memory)} messages from history.")

        # Sliding window: truncate oldest messages if over limit
        if len(self._memory) > self._max_history_messages:
            overflow = len(self._memory) - self._max_history_messages
            logger.debug(f"History sliding window: truncating {overflow} oldest messages")
            self._memory = self._memory[-self._max_history_messages:]

    def handle_interrupt(self, heard_response: str) -> None:
        """Handle user interruption."""
        if self._interrupt_handled:
            return

        self._interrupt_handled = True

        if self._memory and self._memory[-1]["role"] == "assistant":
            if not self._memory[-1]["content"].endswith("..."):
                self._memory[-1]["content"] = heard_response + "..."
            else:
                self._memory[-1]["content"] = heard_response + "..."
        else:
            if heard_response:
                self._memory.append(
                    {
                        "role": "assistant",
                        "content": heard_response + "...",
                    }
                )

        interrupt_role = "system" if self.interrupt_method == "system" else "user"
        self._memory.append(
            {
                "role": interrupt_role,
                "content": "[Interrupted by user]",
            }
        )
        logger.info(f"Handled interrupt with role '{interrupt_role}'.")

    def _to_text_prompt(self, input_data: BatchInput) -> str:
        """Format input data to text prompt."""
        message_parts = []

        for text_data in input_data.texts:
            if text_data.source == TextSource.INPUT:
                message_parts.append(text_data.content)
            elif text_data.source == TextSource.CLIPBOARD:
                message_parts.append(
                    f"[User shared content from clipboard: {text_data.content}]"
                )

        if input_data.images:
            message_parts.append("\n[User has also provided images]")

        return "\n".join(message_parts).strip()

    def _to_messages(self, input_data: BatchInput) -> List[Dict[str, Any]]:
        """Prepare messages for LLM API call."""
        messages = self._memory.copy()
        user_content = []
        text_prompt = self._to_text_prompt(input_data)
        if text_prompt:
            user_content.append({"type": "text", "text": text_prompt})

        if input_data.images:
            image_added = False
            for img_data in input_data.images:
                if isinstance(img_data.data, str) and img_data.data.startswith(
                    "data:image"
                ):
                    user_content.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": img_data.data, "detail": "auto"},
                        }
                    )
                    image_added = True
                else:
                    logger.error(
                        f"Invalid image data format: {type(img_data.data)}. Skipping image."
                    )

            if not image_added and not text_prompt:
                logger.warning(
                    "User input contains images but none could be processed."
                )

        if not user_content and not input_data.images:
            logger.warning("No content generated for user message.")
            return []

        if user_content:
            user_message = {"role": "user", "content": user_content}
            messages.append(user_message)

            skip_memory = False
            if input_data.metadata and input_data.metadata.get("skip_memory", False):
                skip_memory = True

            if not skip_memory:
                self._add_message(
                    text_prompt if text_prompt else "[User provided image(s)]", "user"
                )

        return messages

    @staticmethod
    def _parse_bracket_tool_calls(text: str) -> List[ToolCallObject]:
        """Parse [tool_name(key=value, ...)] bracket-style tool calls from text.

        Returns a list of ToolCallObject instances.
        """
        pattern = re.compile(r'\[(\w+)\(([^)]*)\)\]')
        results: List[ToolCallObject] = []
        for match in pattern.finditer(text):
            tool_name = match.group(1)
            args_str = match.group(2).strip()
            args: Dict[str, Any] = {}
            if args_str:
                try:
                    lexer = shlex.shlex(args_str, posix=True)
                    lexer.whitespace = ','
                    lexer.whitespace_split = True
                    tokens = list(lexer)
                    for token in tokens:
                        if '=' in token:
                            k, _, v = token.partition('=')
                            k = k.strip()
                            v = v.strip()
                            if len(v) >= 2 and v[0] == v[-1] and v[0] in '"\'':
                                v = v[1:-1]
                            try:
                                if '.' in v:
                                    v = float(v)
                                else:
                                    v = int(v)
                            except (ValueError, TypeError):
                                pass
                            args[k] = v
                except ValueError:
                    logger.warning(f"Failed to parse bracket tool arguments: {args_str}")
                    continue
            tc = ToolCallObject(
                id=f"bracket_{uuid.uuid4().hex[:8]}",
                type="function",
                function=ToolCallFunctionObject(
                    name=tool_name,
                    arguments=json.dumps(args),
                ),
            )
            results.append(tc)
        return results

    @staticmethod
    def _strip_bracket_tool_calls(text: str) -> str:
        """Remove [tool_name(...)] patterns from text."""
        pattern = re.compile(r'\s*\[(\w+)\(([^)]*)\)\]\s*')
        return pattern.sub(' ', text).strip()

    async def _claude_tool_interaction_loop(
        self,
        initial_messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> AsyncIterator[Union[str, Dict[str, Any]]]:
        """Handle Claude interaction with tool support."""
        messages = initial_messages.copy()
        current_turn_text = ""
        pending_tool_calls = []
        current_assistant_message_content = []
        self._tool_round_counter = 0
        self._pending_reflection = False

        while True:
            self._tool_round_counter += 1
            if self._tool_round_counter > self.MAX_TOOL_ROUNDS:
                logger.warning(f"Tool interaction loop exceeded {self.MAX_TOOL_ROUNDS} rounds, stopping.")
                yield "[System: Maximum tool call rounds reached. Please summarize.]"
                return
            stream = self._llm.chat_completion(messages, self._system, tools=tools)
            pending_tool_calls.clear()
            current_assistant_message_content.clear()

            # Wrap stream dengan StructuredResponseManager
            structured_stream = self._response_manager.process_stream(stream)

            async for event in structured_stream:
                if isinstance(event, dict) and event.get("type") == "text_delta":
                    text = event["text"]
                    current_turn_text += text
                    if not self._pending_reflection:
                        yield text
                    if (
                        not current_assistant_message_content
                        or current_assistant_message_content[-1]["type"] != "text"
                    ):
                        current_assistant_message_content.append(
                            {"type": "text", "text": text}
                        )
                    else:
                        current_assistant_message_content[-1]["text"] += text
                elif isinstance(event, dict) and event.get("type") == "tool_use_complete":
                    tool_call_data = event["data"]
                    logger.info(
                        f"Tool request: {tool_call_data['name']} (ID: {tool_call_data['id']})"
                    )
                    pending_tool_calls.append(tool_call_data)
                    current_assistant_message_content.append(
                        {
                            "type": "tool_use",
                            "id": tool_call_data["id"],
                            "name": tool_call_data["name"],
                            "input": tool_call_data["input"],
                        }
                    )
                elif isinstance(event, dict) and event.get("type") == "message_stop":
                    break
                elif isinstance(event, dict) and event.get("type") == "error":
                    logger.error(f"LLM API Error: {event['message']}")
                    yield f"[Error from LLM: {event['message']}]"
                    return
                else:
                    # Pass through other events (including tool_call_status and final_tool_results)
                    yield event

            if pending_tool_calls:
                filtered_assistant_content = [
                    block
                    for block in current_assistant_message_content
                    if not (
                        block.get("type") == "text"
                        and not block.get("text", "").strip()
                    )
                ]

                if filtered_assistant_content:
                    messages.append(
                        {"role": "assistant", "content": filtered_assistant_content}
                    )
                    assistant_text_for_memory = "".join(
                        [
                            c["text"]
                            for c in filtered_assistant_content
                            if c["type"] == "text"
                        ]
                    ).strip()
                    if assistant_text_for_memory:
                        self._add_message(assistant_text_for_memory, "assistant")

                tool_results_for_llm = []
                if not self._tool_executor:
                    logger.error(
                        "Claude Tool interaction requested but ToolExecutor is not available."
                    )
                    yield "[Error: ToolExecutor not configured]"
                    return

                tool_executor_iterator = self._tool_executor.execute_tools(
                    tool_calls=pending_tool_calls,
                    caller_mode="Claude",
                )
                try:
                    while True:
                        update = await anext(tool_executor_iterator)
                        if update.get("type") == "final_tool_results":
                            tool_results_for_llm = update.get("results", [])
                            break
                        else:
                            yield update
                except StopAsyncIteration:
                    logger.warning(
                        "Tool executor finished without final results marker."
                    )

                if tool_results_for_llm:
                    messages.append({"role": "user", "content": tool_results_for_llm})

                # stop_reason = None
                continue
            else:
                if current_turn_text:
                    bracket_calls = self._parse_bracket_tool_calls(current_turn_text)
                    if bracket_calls:
                        clean_text = self._strip_bracket_tool_calls(current_turn_text)
                        if clean_text:
                            self._add_message(clean_text, "assistant")

                        tool_results_for_llm = []
                        if not self._tool_executor:
                            logger.error("Claude Tool interaction requested but ToolExecutor is not available.")
                            yield "[Error: ToolExecutor not configured for bracket tool calls]"
                            return

                        tool_executor_iterator = self._tool_executor.execute_tools(
                            tool_calls=bracket_calls,
                            caller_mode="Claude",
                        )
                        try:
                            while True:
                                update = await anext(tool_executor_iterator)
                                if update.get("type") == "final_tool_results":
                                    tool_results_for_llm = update.get("results", [])
                                    break
                                else:
                                    yield update
                        except StopAsyncIteration:
                            logger.warning("Tool executor finished without final results marker.")

                        if tool_results_for_llm:
                            messages.append({"role": "user", "content": tool_results_for_llm})
                        continue
                    else:
                        self._add_message(current_turn_text, "assistant")
                        if self._pending_reflection:
                            self._pending_reflection = False
                            return
                        else:
                            self._pending_reflection = True
                            messages.append(self._get_agentic_reflection_prompt())
                            continue
                return

    def _get_agentic_reflection_prompt(self) -> Dict[str, str]:
        """Load the agentic reflection prompt from prompts/utils/."""
        try:
            content = prompt_loader.load_util("agentic_reflection_prompt")
            return {"role": "system", "content": content}
        except Exception as e:
            logger.warning(f"Failed to load agentic reflection prompt: {e}")
            return {"role": "system", "content": "[System: If you need to call tools, call them now. Otherwise, do not respond.]"}

    async def _openai_tool_interaction_loop(
        self,
        initial_messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> AsyncIterator[Union[str, Dict[str, Any]]]:
        """Handle OpenAI interaction with tool support."""
        messages = initial_messages.copy()
        current_turn_text = ""
        pending_tool_calls: Union[List[ToolCallObject], List[Dict[str, Any]]] = []
        current_system_prompt = self._system
        self._tool_round_counter = 0
        self._pending_reflection = False

        while True:
            self._tool_round_counter += 1
            if self._tool_round_counter > self.MAX_TOOL_ROUNDS:
                logger.warning(f"Tool interaction loop exceeded {self.MAX_TOOL_ROUNDS} rounds, stopping.")
                yield "[System: Maximum tool call rounds reached. Please summarize.]"
                return
            if self.prompt_mode_flag:
                if self._mcp_prompt_string:
                    current_system_prompt = (
                        f"{self._system}\n\n{self._mcp_prompt_string}"
                    )
                else:
                    logger.warning("Prompt mode active but mcp_prompt_string is empty!")
                    current_system_prompt = self._system
                tools_for_api = None
            else:
                current_system_prompt = self._system
                tools_for_api = tools

            stream = self._llm.chat_completion(
                messages, current_system_prompt, tools=tools_for_api
            )
            pending_tool_calls.clear()
            current_turn_text = ""
            assistant_message_for_api = None
            detected_prompt_json = None
            goto_next_while_iteration = False

            # Wrap stream dengan StructuredResponseManager
            structured_stream = self._response_manager.process_stream(stream)

            async for event in structured_stream:
                if self.prompt_mode_flag:
                    if isinstance(event, str):
                        current_turn_text += event
                        if self._json_detector:
                            potential_json = self._json_detector.process_chunk(event)
                            if potential_json:
                                try:
                                    if isinstance(potential_json, list):
                                        detected_prompt_json = potential_json
                                    elif isinstance(potential_json, dict):
                                        detected_prompt_json = [potential_json]

                                    if detected_prompt_json:
                                        break
                                except Exception as e:
                                    logger.error(f"Error parsing detected JSON: {e}")
                                    if self._json_detector:
                                        self._json_detector.reset()
                                    yield f"[Error parsing tool JSON: {e}]"
                                    goto_next_while_iteration = True
                                    break
                        if not self._pending_reflection:
                            yield event
                    if isinstance(event, dict):
                        # Pass through dict events (tool_call_status, final_tool_results, etc)
                        yield event
                else:
                    if isinstance(event, str):
                        current_turn_text += event
                        if not self._pending_reflection:
                            yield event
                    elif isinstance(event, list) and all(
                        isinstance(tc, ToolCallObject) for tc in event
                    ):
                        pending_tool_calls = event
                        tool_calls_api = []
                        for tc in pending_tool_calls:
                            tc_id = tc.id if tc.id else f"tc_{uuid.uuid4().hex[:12]}"
                            tc.id = tc_id
                            # Repair concatenated JSON arguments before storing
                            # e.g. {"text":"..."}{"target":"enter"} -> {"text":"...","target":"enter"}
                            try:
                                json.loads(tc.function.arguments)
                            except json.JSONDecodeError:
                                merged = {}
                                raw = tc.function.arguments.strip()
                                pos = 0
                                while pos < len(raw):
                                    if raw[pos] == "{":
                                        depth = 0
                                        for i in range(pos, len(raw)):
                                            if raw[i] == "{":
                                                depth += 1
                                            elif raw[i] == "}":
                                                depth -= 1
                                                if depth == 0:
                                                    try:
                                                        obj = json.loads(raw[pos:i+1])
                                                        if isinstance(obj, dict):
                                                            merged.update(obj)
                                                    except json.JSONDecodeError:
                                                        pass
                                                    pos = i + 1
                                                    break
                                        else:
                                            break
                                    else:
                                        pos += 1
                                if merged:
                                    tc.function.arguments = json.dumps(merged)
                                    logger.info(f"Repaired arguments for '{tc.function.name}': {tc.function.arguments}")
                            tc_dict = {
                                "id": tc_id,
                                "type": tc.type,
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            # Gemini/Google's OpenAI-compat API requires thought_signature
                            # in functionCall parts when it was provided in the response
                            if tc.extra_content:
                                tc_dict["extra_content"] = tc.extra_content
                            tool_calls_api.append(tc_dict)

                        assistant_message_for_api = {
                            "role": "assistant",
                            "tool_calls": tool_calls_api,
                        }
                        if current_turn_text:
                            assistant_message_for_api["content"] = current_turn_text
                        break
                    elif event == "__API_NOT_SUPPORT_TOOLS__":
                        logger.warning(
                            f"LLM {getattr(self._llm, 'model', '')} has no native tool support. Switching to prompt mode."
                        )
                        self.prompt_mode_flag = True
                        if self._tool_manager:
                            self._tool_manager.disable()
                        if self._json_detector:
                            self._json_detector.reset()
                        goto_next_while_iteration = True
                        break
                    elif isinstance(event, dict):
                        # Pass through dict events (tool_call_status, final_tool_results, etc)
                        yield event
            if goto_next_while_iteration:
                continue

            if detected_prompt_json:
                logger.info("Processing tools detected via prompt mode JSON.")
                self._add_message(current_turn_text, "assistant")

                parsed_tools = self._tool_executor.process_tool_from_prompt_json(
                    detected_prompt_json
                )
                if parsed_tools:
                    tool_results_for_llm = []
                    if not self._tool_executor:
                        logger.error(
                            "Prompt Tool interaction requested but ToolExecutor/MCPClient is not available."
                        )
                        yield "[Error: ToolExecutor/MCPClient not configured for prompt mode]"
                        continue

                    tool_executor_iterator = self._tool_executor.execute_tools(
                        tool_calls=parsed_tools,
                        caller_mode="Prompt",
                    )
                    try:
                        while True:
                            update = await anext(tool_executor_iterator)
                            if update.get("type") == "final_tool_results":
                                tool_results_for_llm = update.get("results", [])
                                break
                            else:
                                yield update
                    except StopAsyncIteration:
                        logger.warning(
                            "Prompt mode tool executor finished without final results marker."
                        )

                    if tool_results_for_llm:
                        result_strings = [
                            res.get("content", "Error: Malformed result")
                            for res in tool_results_for_llm
                        ]
                        combined_results_str = "\n".join(result_strings)
                        messages.append(
                            {"role": "user", "content": combined_results_str}
                        )
                continue

            elif pending_tool_calls and assistant_message_for_api:
                messages.append(assistant_message_for_api)
                if current_turn_text:
                    self._add_message(current_turn_text, "assistant")

                # Split summon_specialist calls from regular tool calls
                summon_calls = [
                    tc for tc in pending_tool_calls
                    if tc.function.name == "summon_specialist"
                ]
                regular_calls = [
                    tc for tc in pending_tool_calls
                    if tc.function.name != "summon_specialist"
                ]

                all_tool_results = []

                # Handle summon_specialist calls directly (not via MCP)
                for tc in summon_calls:
                    if self._specialist_llm and self._tool_groups:
                        statuses, tool_result = await self._handle_summon_specialist(tc)
                        for s in statuses:
                            yield s
                    else:
                        logger.error(
                            "summon_specialist called but specialist LLM not configured"
                        )
                        tool_result = {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": "Error: Specialist LLM not configured",
                        }
                    all_tool_results.append(tool_result)

                # Handle regular tool calls via executor
                if regular_calls:
                    if not self._tool_executor:
                        logger.error(
                            "OpenAI Tool interaction requested but ToolExecutor/MCPClient is not available."
                        )
                        if all_tool_results:
                            messages.extend(all_tool_results)
                        continue

                    tool_executor_iterator = self._tool_executor.execute_tools(
                        tool_calls=regular_calls,
                        caller_mode="OpenAI",
                    )
                    try:
                        while True:
                            update = await anext(tool_executor_iterator)
                            if update.get("type") == "final_tool_results":
                                all_tool_results.extend(update.get("results", []))
                                break
                            else:
                                yield update
                    except StopAsyncIteration:
                        logger.warning(
                            "OpenAI tool executor finished without final results marker."
                        )

                if all_tool_results:
                    messages.extend(all_tool_results)
                continue

            else:
                if current_turn_text:
                    bracket_calls = self._parse_bracket_tool_calls(current_turn_text)
                    if bracket_calls:
                        clean_text = self._strip_bracket_tool_calls(current_turn_text)
                        if clean_text:
                            self._add_message(clean_text, "assistant")

                        tool_results_for_llm = []
                        if not self._tool_executor:
                            logger.error(
                                "OpenAI Tool interaction requested but ToolExecutor is not available."
                            )
                            yield "[Error: ToolExecutor not configured for bracket tool calls]"
                            return

                        tool_executor_iterator = self._tool_executor.execute_tools(
                            tool_calls=bracket_calls,
                            caller_mode="OpenAI",
                        )
                        try:
                            while True:
                                update = await anext(tool_executor_iterator)
                                if update.get("type") == "final_tool_results":
                                    tool_results_for_llm = update.get("results", [])
                                    break
                                else:
                                    yield update
                        except StopAsyncIteration:
                            logger.warning(
                                "Tool executor finished without final results marker."
                            )

                        if tool_results_for_llm:
                            messages.extend(tool_results_for_llm)
                        continue
                    else:
                        self._add_message(current_turn_text, "assistant")
                        if self._pending_reflection:
                            self._pending_reflection = False
                            return
                        else:
                            self._pending_reflection = True
                            messages.append(self._get_agentic_reflection_prompt())
                            continue
                return

    async def _handle_summon_specialist(
        self, tool_call: ToolCallObject
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Handle a summon_specialist tool call.

        Returns:
            tuple: (status_updates, tool_result_dict)
        """
        try:
            args = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            return [], {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": "Error: Invalid JSON arguments",
            }

        group_name = args.get("group")
        request = args.get("request")

        if not group_name or not request:
            return [], {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": "Error: 'group' and 'request' parameters required",
            }

        if group_name not in self._tool_groups:
            return [], {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": f"Error: Unknown specialist group '{group_name}'",
            }

        group = self._tool_groups[group_name]
        logger.info(
            f"Summoning specialist '{group_name}' for: {request[:120]}..."
        )

        filtered_tools = (
            self._tool_manager.get_filtered_tools("OpenAI", group.tool_names)
            if self._tool_manager
            else []
        )

        if not filtered_tools:
            return [], {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": f"Error: No tools available for group '{group_name}'",
            }

        specialist = ToolAgent(
            llm=self._specialist_llm,
            tool_executor=self._tool_executor,
            tool_manager=self._tool_manager,
            system_prompt=group.system_prompt,
            max_tool_rounds=5,
        )
        specialist._tools = filtered_tools

        result = await specialist.process(
            user_message=request,
            conversation_context=self.get_recent_context(n=3),
        )

        if result.error:
            content = f"[Specialist '{group_name}' error] {result.error}"
        elif result.tool_was_called and result.tool_results:
            summaries = []
            for r in result.tool_results:
                if isinstance(r, dict):
                    c = r.get("content", str(r))
                    if isinstance(c, list):
                        for item in c:
                            if isinstance(item, dict) and item.get("type") == "text":
                                summaries.append(item["text"][:2000])
                    elif c:
                        summaries.append(str(c)[:2000])
            content = "\n".join(summaries) if summaries else "Task completed (no output)"
        else:
            content = "Specialist: Task completed successfully."

        logger.info(f"Summon_specialist '{group_name}' result: {len(content)} chars")
        return result.tool_statuses, {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": content,
        }

    def _chat_function_factory(
        self,
    ) -> Callable[[BatchInput], AsyncIterator[Union[SentenceOutput, Dict[str, Any]]]]:
        """Create the chat pipeline function."""

        @tts_filter(self._tts_preprocessor_config)
        @display_processor(self._live2d_model)
        @actions_extractor(self._live2d_model)
        @sentence_divider(
            faster_first_response=self._faster_first_response,
            segment_method=self._segment_method,
            valid_tags=["think", "thought"],
        )
        async def chat_with_memory(
            input_data: BatchInput,
        ) -> AsyncIterator[Union[str, Dict[str, Any]]]:
            """Process chat with memory and tools."""
            self.reset_interrupt()
            self.prompt_mode_flag = False

            messages = self._to_messages(input_data)
            if not messages:
                logger.warning("No messages to send to LLM. Skipping.")
                return

            # === DUAL-AGENT MODE ===
            # Persona LLM (Gemini) focuses on conversation, ToolAgent (Groq) handles tools
            if self._is_dual_agent and self._tool_agent:
                user_text = self._to_text_prompt(input_data)
                if not user_text:
                    logger.warning("Dual-agent: No user text to process")
                    return

                logger.info("Dual-agent mode: processing with ToolAgent first")

                # Step 1: ToolAgent processes the request with tool access
                tool_result = await self._tool_agent.process(
                    user_message=user_text,
                    conversation_context=self.get_recent_context(n=3),
                )

                # Step 1.5: Stream any tool status updates to frontend
                for status in tool_result.tool_statuses:
                    yield status

                if tool_result.error:
                    logger.warning(f"Dual-agent: ToolAgent error: {tool_result.error}")
                    # Still continue to persona LLM with error context

                # Step 2: Inject tool results into messages for persona LLM
                if tool_result.tool_was_called and tool_result.tool_results:
                    # Summarize tool results into a user-like message
                    tool_summaries = []
                    for tr in tool_result.tool_results:
                        content = tr.get("content", "") if isinstance(tr, dict) else str(tr)
                        if isinstance(content, str) and content:
                            tool_summaries.append(content[:2000])
                        elif isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    tool_summaries.append(item["text"][:2000])

                    if tool_summaries:
                        combined = "\n".join(tool_summaries)
                        # Inject as a user message (tool results context)
                        messages.append({
                            "role": "user",
                            "content": f"[Your tool assistant executed tools and got these results:]\n{combined}"
                        })
                        logger.info(
                            f"Dual-agent: Injected {len(combined)} chars of tool results into persona LLM context"
                        )

                if input_data.images:
                    logger.warning(
                        "Dual-agent mode: images are processed by persona LLM but not by ToolAgent"
                    )

                # Step 3: Persona LLM generates response (NO tools in system prompt)
                logger.info("Dual-agent: Persona LLM generating response")
                token_stream = self._llm.chat_completion(
                    messages, self._system,
                    tools=None  # NO tools for persona LLM
                )
                complete_response = ""
                async for event in token_stream:
                    text_chunk = ""
                    if isinstance(event, dict) and event.get("type") == "text_delta":
                        text_chunk = event.get("text", "")
                    elif isinstance(event, str):
                        text_chunk = event
                    else:
                        continue
                    if text_chunk:
                        yield text_chunk
                        complete_response += text_chunk
                        # On first chunk, mark that tools were used in the response
                        if tool_result.tool_was_called and len(complete_response) == len(text_chunk):
                            logger.debug("Dual-agent: First response chunk from persona LLM (tools were used)")

                if complete_response:
                    self._add_message(complete_response, "assistant")

                if tool_result.tool_was_called:
                    logger.info(
                        f"Dual-agent: Completed. Tools called: {len(tool_result.tool_results)}, "
                        f"Response length: {len(complete_response)}"
                    )
                return

            # === LEGACY MODE (single LLM handles both conversation and tools) ===
            tools = None
            tool_mode = None
            llm_supports_native_tools = False

            if self._use_mcpp and self._tool_manager:
                tools = None
                if isinstance(self._llm, ClaudeAsyncLLM):
                    tool_mode = "Claude"
                    tools = self._formatted_tools_claude
                    llm_supports_native_tools = True
                elif isinstance(self._llm, OpenAICompatibleAsyncLLM):
                    tool_mode = "OpenAI"
                    tools = self._formatted_tools_openai
                    llm_supports_native_tools = True
                else:
                    logger.warning(
                        f"LLM type {type(self._llm)} not explicitly handled for tool mode determination."
                    )

                if llm_supports_native_tools and not tools:
                    logger.warning(
                        f"No tools available/formatted for '{tool_mode}' mode, despite MCP being enabled."
                    )

            if self._use_mcpp and tool_mode == "Claude":
                logger.debug(
                    f"Starting Claude tool interaction loop with {len(tools)} tools."
                )
                async for output in self._claude_tool_interaction_loop(
                    messages, tools if tools else []
                ):
                    yield output
                return
            elif self._use_mcpp and tool_mode == "OpenAI":
                logger.debug(
                    f"Starting OpenAI tool interaction loop with {len(tools)} tools."
                )
                async for output in self._openai_tool_interaction_loop(
                    messages, tools if tools else []
                ):
                    yield output
                return
            else:
                logger.info("Starting simple chat completion (legacy mode).")
                token_stream = self._llm.chat_completion(messages, self._system)
                complete_response = ""
                async for event in token_stream:
                    text_chunk = ""
                    if isinstance(event, dict) and event.get("type") == "text_delta":
                        text_chunk = event.get("text", "")
                    elif isinstance(event, str):
                        text_chunk = event
                    else:
                        continue
                    if text_chunk:
                        yield text_chunk
                        complete_response += text_chunk
                if complete_response:
                    self._add_message(complete_response, "assistant")

        return chat_with_memory

    async def chat(
        self,
        input_data: BatchInput,
    ) -> AsyncIterator[Union[SentenceOutput, Dict[str, Any]]]:
        """Run chat pipeline with long-term memory injection."""
        original_system = self._system
        try:
            extra_prompts = []
            if self._memory_manager:
                memory_prompt = self._memory_manager.to_prompt_string()
                if memory_prompt:
                    extra_prompts.append(memory_prompt)
            if self._todo_manager:
                todo_prompt = self._todo_manager.to_prompt_string()
                if todo_prompt:
                    extra_prompts.append(todo_prompt)
            if extra_prompts:
                combined = "\n\n".join(extra_prompts)
                self.set_system(f"{original_system}\n\n{combined}")
                logger.debug(f"Injected memory+todo ({len(combined)} chars) into system prompt.")
            chat_func_decorated = self._chat_function_factory()
            async for output in chat_func_decorated(input_data):
                yield output
        finally:
            if self._system != original_system:
                self.set_system(original_system)

    def reset_interrupt(self) -> None:
        """Reset interrupt flag."""
        self._interrupt_handled = False

    def set_conf_uid(self, conf_uid: str) -> None:
        """Set the configuration UID for this agent session."""
        self._conf_uid = conf_uid
        logger.debug(f"Agent conf_uid set to: {conf_uid}")

    def start_group_conversation(
        self, human_name: str, ai_participants: List[str]
    ) -> None:
        """Start a group conversation."""
        if not self._tool_prompts:
            logger.warning("Tool prompts dictionary is not set.")
            return

        other_ais = ", ".join(name for name in ai_participants)
        prompt_name = self._tool_prompts.get("group_conversation_prompt", "")

        if not prompt_name:
            logger.warning("No group conversation prompt name found.")
            return

        try:
            group_context = prompt_loader.load_util(prompt_name).format(
                human_name=human_name, other_ais=other_ais
            )
            self._memory.append({"role": "user", "content": group_context})
        except FileNotFoundError:
            logger.error(f"Group conversation prompt file not found: {prompt_name}")
        except KeyError as e:
            logger.error(f"Missing formatting key in group conversation prompt: {e}")
        except Exception as e:
            logger.error(f"Failed to load group conversation prompt: {e}")
