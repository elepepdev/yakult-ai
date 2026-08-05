"""
Tool Agent — AI khusus untuk mengeksekusi tools.

Tidak punya persona, tidak membuat percakapan.
Tugasnya hanya: terima perintah → panggil tool → return hasil.
Menggunakan LLM dengan rate limit tinggi (Groq) agar tool calls cepat dan murah.
"""

import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from loguru import logger

from ..stateless_llm.stateless_llm_interface import StatelessLLMInterface
from ..stateless_llm.claude_llm import AsyncLLM as ClaudeAsyncLLM
from ...mcpp.tool_manager import ToolManager
from ...mcpp.tool_executor import ToolExecutor
from ...mcpp.types import ToolCallObject


@dataclass
class ToolResult:
    """Result from ToolAgent processing.

    Attributes:
        tool_was_called: Whether any tool was actually invoked
        tool_results: Formatted results ready for LLM consumption
        tool_statuses: Status updates for frontend streaming
        error: Error message if any
        needs_user_response: Whether Gemini needs to generate a response
        conversation_context: Updated conversation context after tool execution
    """
    tool_was_called: bool = False
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    tool_statuses: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    needs_user_response: bool = True
    conversation_context: Optional[List[Dict[str, Any]]] = None


class ToolAgent:
    """Agent khusus untuk mengeksekusi tools.

    Agent ini TIDAK memiliki persona, tidak membuat percakapan,
    dan hanya fokus pada pemilihan serta eksekusi tool.

    Menggunakan LLM dengan tool definitions (function calling).
    """

    def __init__(
        self,
        llm: StatelessLLMInterface,
        tool_executor: ToolExecutor,
        tool_manager: ToolManager,
        system_prompt: str = "",
        max_tool_rounds: int = 10,
    ):
        """Initialize ToolAgent.

        Args:
            llm: Stateless LLM instance (idealnya Groq — rate limit tinggi)
            tool_executor: ToolExecutor for executing tool calls
            tool_manager: ToolManager with pre-formatted tool definitions
            system_prompt: Minimal system prompt for tool agent
            max_tool_rounds: Maximum tool call rounds before stopping
        """
        self._llm = llm
        self._tool_executor = tool_executor
        self._tool_manager = tool_manager
        self._system = system_prompt or "You are a tool assistant. Call tools as requested."
        self._max_tool_rounds = max_tool_rounds

        # Determine tool format based on LLM type
        self._tools: List[Dict[str, Any]] = []
        self._caller_mode: str = "OpenAI"
        if isinstance(llm, ClaudeAsyncLLM):
            self._caller_mode = "Claude"
            self._tools = tool_manager.get_formatted_tools("Claude") if tool_manager else []
        else:
            self._caller_mode = "OpenAI"
            self._tools = tool_manager.get_formatted_tools("OpenAI") if tool_manager else []

        logger.info(
            f"ToolAgent initialized with {len(self._tools)} tools, "
            f"mode={self._caller_mode}"
        )

    async def process(
        self,
        user_message: str,
        conversation_context: Optional[List[Dict[str, Any]]] = None,
    ) -> ToolResult:
        """Process a user message with full tool access.

        Args:
            user_message: The user's input text
            conversation_context: Optional previous conversation context

        Returns:
            ToolResult with tool execution results
        """
        result = ToolResult()

        if not self._tools:
            logger.warning("ToolAgent: No tools available, skipping tool processing")
            result.error = "No tools configured"
            return result

        # Build messages
        messages = list(conversation_context or [])
        messages.append({"role": "user", "content": user_message})

        # Run tool interaction loop
        try:
            tool_round = 0
            while tool_round < self._max_tool_rounds:
                tool_round += 1
                logger.debug(f"ToolAgent: Round {tool_round}/{self._max_tool_rounds}")

                # Call LLM with tools
                stream = self._llm.chat_completion(
                    messages, self._system, tools=self._tools
                )

                pending_tool_calls = []
                text_response = ""

                async for event in stream:
                    if isinstance(event, str):
                        text_response += event
                    elif isinstance(event, dict) and event.get("type") == "text_delta":
                        text_response += event.get("text", "")
                    elif isinstance(event, list) and all(
                        isinstance(tc, ToolCallObject) for tc in event
                    ):
                        pending_tool_calls = event
                    elif isinstance(event, dict) and event.get("type") == "tool_use_complete":
                        # Claude format
                        pending_tool_calls.append(event["data"])
                    elif event == "__API_NOT_SUPPORT_TOOLS__":
                        logger.warning(
                            "ToolAgent: LLM does not support native tools"
                        )
                        result.error = "LLM does not support native tool calling"
                        return result

                if not pending_tool_calls:
                    # No tools called this round
                    logger.debug("ToolAgent: No tool calls, done")
                    break

                # We have tool calls!
                result.tool_was_called = True

                # Add assistant message with tool calls to context
                if self._caller_mode == "Claude":
                    assistant_content = []
                    if text_response:
                        assistant_content.append(
                            {"type": "text", "text": text_response}
                        )
                    for tc_data in pending_tool_calls:
                        assistant_content.append(
                            {
                                "type": "tool_use",
                                "id": tc_data.get("id", ""),
                                "name": tc_data.get("name", ""),
                                "input": tc_data.get("input", {}),
                            }
                        )
                    messages.append(
                        {"role": "assistant", "content": assistant_content}
                    )
                else:
                    # OpenAI format
                    tool_calls_api = []
                    for tc in pending_tool_calls:
                        tc_id = tc.id if hasattr(tc, "id") else (
                            tc.get("id") if isinstance(tc, dict) else 
                            f"tc_{uuid.uuid4().hex[:12]}"
                        )
                        if isinstance(tc, ToolCallObject):
                            tool_calls_api.append(
                                {
                                    "id": tc_id,
                                    "type": "function",
                                    "function": {
                                        "name": tc.function.name,
                                        "arguments": tc.function.arguments,
                                    },
                                }
                            )
                        elif isinstance(tc, dict):
                            tool_calls_api.append(tc)
                    
                    msg = {"role": "assistant", "tool_calls": tool_calls_api}
                    if text_response:
                        msg["content"] = text_response
                    messages.append(msg)

                # Execute tools
                logger.info(
                    f"ToolAgent: Executing {len(pending_tool_calls)} tool(s)"
                )
                tool_results_for_llm = []
                tool_statuses_batch = []

                tool_executor_stream = self._tool_executor.execute_tools(
                    tool_calls=pending_tool_calls,
                    caller_mode=self._caller_mode,
                )

                try:
                    while True:
                        update = await tool_executor_stream.__anext__()
                        if update.get("type") == "final_tool_results":
                            tool_results_for_llm = update.get("results", [])
                            break
                        else:
                            tool_statuses_batch.append(update)
                except StopAsyncIteration:
                    logger.warning("ToolAgent: Tool executor finished without final marker")

                result.tool_statuses.extend(tool_statuses_batch)
                result.tool_results.extend(tool_results_for_llm)

                # Add tool results to conversation context
                if tool_results_for_llm:
                    if self._caller_mode == "Claude":
                        # Claude expects user messages with tool results
                        claude_results = []
                        for tr in tool_results_for_llm:
                            if isinstance(tr, dict) and tr.get("type") == "tool_result":
                                claude_results.append(tr)
                            else:
                                claude_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": tr.get("tool_use_id", ""),
                                    "content": tr.get("content", ""),
                                    "is_error": tr.get("is_error", False),
                                })
                        messages.append({"role": "user", "content": claude_results})
                    else:
                        # OpenAI format: just extend with tool result messages
                        messages.extend(tool_results_for_llm)

                # Continue loop for potential follow-up tool calls
                continue

        except Exception as e:
            logger.exception(f"ToolAgent: Error during tool processing: {e}")
            result.error = str(e)
            return result

        result.conversation_context = messages
        return result

    async def detect_tool_need(
        self,
        user_message: str,
    ) -> bool:
        """Quick check if a user message likely needs tools.

        Uses a lightweight LLM call to determine if tools are needed.
        Falls back to True if uncertain.

        Args:
            user_message: The user's input text

        Returns:
            bool: True if tools are likely needed
        """
        if not self._tools:
            return False

        quick_prompt = (
            "Determine if the following user request requires calling any tools "
            "(web search, opening apps, clicking, file operations, etc.) "
            "or if it's just a conversational message. "
            "Reply with ONLY 'YES' or 'NO'.\n\n"
            f"User: {user_message}"
        )

        try:
            async for chunk in self._llm.chat_completion(
                messages=[{"role": "user", "content": quick_prompt}],
                system="You are a classifier. Reply YES or NO only.",
                tools=[],  # No tools for this check
            ):
                text = ""
                if isinstance(chunk, str):
                    text += chunk
                elif isinstance(chunk, dict) and chunk.get("type") == "text_delta":
                    text += chunk.get("text", "")

            result = text.strip().upper()
            logger.debug(f"ToolAgent: detect_tool_need='{result}' for '{user_message[:50]}...'")
            return result.startswith("YES")
        except Exception as e:
            logger.warning(f"ToolAgent: detect_tool_need failed: {e}")
            return True  # Fallback: assume tools needed
