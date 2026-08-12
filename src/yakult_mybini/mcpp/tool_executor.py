import json
import datetime
import asyncio
from loguru import logger
from typing import (
    Dict,
    Any,
    List,
    Literal,
    Union,
    AsyncIterator,
    Optional,
    Callable,
)

from .types import ToolCallObject
from .mcp_client import MCPClient
from .tool_manager import ToolManager
from .music_player_manager import music_player_manager

PACKAGE_TOOLS = {"install_package", "remove_package", "update_system"}
BACKGROUND_COMMANDS = {"run_command", "run_sudo_command"}

DANGEROUS_COMMANDS = ["rm", "rmdir", "del", "format", "dd", "mkfs", "shutdown", "reboot", "poweroff"]

from .file_tools import FILE_TOOLS, run_file_operation

ApprovalCallback = Callable[[Dict[str, Any]], Any]


class ToolExecutor:
    def __init__(
        self,
        mcp_client: MCPClient,
        tool_manager: ToolManager,
        sudo_password: str = "",
    ):
        """Initialize the ToolExecutor."""
        self._mcp_client = mcp_client
        self._tool_manager = tool_manager
        self._sudo_password = sudo_password
        # Optional callback wired by the websocket layer: called with an
        # approval payload, must resolve to a truthy value to allow the
        # dangerous operation, falsy to cancel it.
        self._approval_callback: Optional[ApprovalCallback] = None

    def set_approval_callback(self, callback: Optional[ApprovalCallback]) -> None:
        """Set the user-approval callback for dangerous operations."""
        self._approval_callback = callback

    async def _request_approval(self, payload: Dict[str, Any]) -> bool:
        """Ask the user to approve a dangerous operation.

        Returns True if approved, False otherwise (denied / timeout / no UI).
        """
        if not self._approval_callback:
            logger.warning(
                "No approval callback configured — denying dangerous tool operation."
            )
            return False
        try:
            result = self._approval_callback(payload)
            if asyncio.iscoroutine(result):
                result = await result
            return bool(result)
        except Exception as e:
            logger.error(f"Approval callback error: {e}")
            return False

    def parse_tool_call(self, call: Union[Dict[str, Any], ToolCallObject]) -> tuple:
        """Parse tool call from different formats.

        Returns:
            tuple: (tool_name, tool_id, tool_input, is_error, result_content, parse_error)
        """
        tool_name: str = ""
        tool_id: str = ""
        tool_input: Any = None
        is_error: bool = False
        result_content: str | dict = ""
        parse_error: bool = False

        if isinstance(call, ToolCallObject):
            tool_name = call.function.name
            tool_id = call.id
            try:
                tool_input = json.loads(call.function.arguments)
            except json.JSONDecodeError:
                logger.error(
                    f"Failed to decode OpenAI tool arguments for '{tool_name}': {call.function.arguments}"
                )
                # Try to recover from concatenated JSON objects
                # e.g. {"y":750,"x":300}{"text":"hello"}{"target":"enter"}
                # by parsing ALL objects and merging them
                recovered_objects = []
                raw = call.function.arguments.strip()
                pos = 0
                while pos < len(raw):
                    if raw[pos] == "{":
                        brace_depth = 0
                        for i in range(pos, len(raw)):
                            if raw[i] == "{":
                                brace_depth += 1
                            elif raw[i] == "}":
                                brace_depth -= 1
                                if brace_depth == 0:
                                    try:
                                        obj = json.loads(raw[pos : i + 1])
                                        if isinstance(obj, dict):
                                            recovered_objects.append(obj)
                                    except json.JSONDecodeError:
                                        pass
                                    pos = i + 1
                                    break
                        else:
                            break
                    else:
                        pos += 1
                merged = {}
                for obj in recovered_objects:
                    merged.update(obj)
                if merged:
                    logger.info(f"Recovered tool arguments from malformed JSON (merged {len(recovered_objects)} objects): {merged}")
                    tool_input = merged
                else:
                    result_content = (
                        f"Error: Invalid arguments format for tool '{tool_name}'. "
                        f"Arguments received: {call.function.arguments}"
                    )
                    is_error = True
                    parse_error = True
        elif isinstance(call, dict):
            tool_id = call.get("id")
            tool_name = call.get("name")
            tool_input = call.get("input", call.get("args"))

            if tool_input is None:
                logger.warning(
                    f"Empty input for tool '{tool_name}' (ID: {tool_id}). Using empty object."
                )
                tool_input = {}

            if not tool_id or not tool_name:
                logger.error(f"Invalid Dict tool call structure: {call}")
                result_content = "Error: Invalid tool call structure from LLM."
                is_error = True
                parse_error = True
        else:
            logger.error(f"Unsupported tool call type: {type(call)}")
            result_content = "Error: Unsupported tool call type."
            is_error = True
            parse_error = True

        return tool_name, tool_id, tool_input, is_error, result_content, parse_error

    def format_tool_result(
        self,
        caller_mode: Literal["Claude", "OpenAI", "Prompt"],
        tool_id: str,
        result_content: str,
        is_error: bool,
    ) -> Dict[str, Any] | None:
        """Format tool result for LLM API."""
        if caller_mode == "Claude":
            # Claude expects content as a list of blocks or a simple string
            # We will return a list if there are multiple items or non-text items
            if isinstance(result_content, list):
                # Already formatted as list of blocks
                content_to_send = result_content
            elif isinstance(result_content, str) and result_content:
                # Simple text result
                content_to_send = result_content
            elif not result_content and is_error:
                # Error case, send error message as string
                content_to_send = "Error occurred during tool execution."
            else:
                # Fallback for empty or unexpected content
                content_to_send = ""

            return {
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": content_to_send,
                "is_error": is_error,
            }
        elif caller_mode == "OpenAI":
            return {
                "role": "tool",
                "tool_call_id": tool_id,
                "content": result_content if isinstance(result_content, list) else str(result_content),
            }
        elif caller_mode == "Prompt":
            return {
                "tool_id": tool_id,
                "content": result_content if isinstance(result_content, list) else str(result_content),
                "is_error": is_error,
            }
        return None

    def process_tool_from_prompt_json(
        self, data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Process tool data from JSON in prompt mode."""
        parsed_tools = []
        for item in data:
            server = item.get("mcp_server")
            tool_name = item.get("tool")
            arguments_str = item.get("arguments")
            if all([server, tool_name, arguments_str]):
                try:
                    args_dict = json.loads(arguments_str)
                    parsed_tools.append(
                        {
                            "name": tool_name,
                            "server": server,
                            "args": args_dict,
                            "id": f"prompt_tool_{len(parsed_tools)}",
                        }
                    )
                    logger.info(f"Parsed tool call from prompt JSON: {tool_name}")
                except json.JSONDecodeError:
                    logger.error(
                        "Failed to decode arguments JSON in prompt mode tool call"
                    )
                except Exception as e:
                    logger.error(f"Error processing prompt mode tool dict: {e}")
            else:
                logger.warning("Skipping invalid tool structure in prompt mode JSON")
        return parsed_tools

    async def execute_tools(
        self,
        tool_calls: Union[List[Dict[str, Any]], List[ToolCallObject]],
        caller_mode: Literal["Claude", "OpenAI", "Prompt"],
    ) -> AsyncIterator[Dict[str, Any]]:
        """Execute tools and yield status updates."""
        tool_results_for_llm = []
        seen_calls: dict[str, str] = {}  # (tool_name, args_json) -> tool_id of first call

        logger.info(f"Executing {len(tool_calls)} tool(s) for {caller_mode} caller.")
        for call in tool_calls:
            (
                tool_name,
                tool_id,
                tool_input,
                is_error,
                result_content,
                parse_error,
            ) = self.parse_tool_call(call)

            logger.info(f"Executing tool: {call}")

            # ---- Deduplicate: skip if same tool+args already executed ----
            if tool_name and not parse_error and tool_input is not None:
                call_key = f"{tool_name}:{json.dumps(tool_input, sort_keys=True, default=str)}"
                if call_key in seen_calls:
                    original_id = seen_calls[call_key]
                    logger.info(f"Skipping duplicate tool call: {tool_name} (same as {original_id})")
                    formatted_result = self.format_tool_result(
                        caller_mode, tool_id, f"[Duplicate of {original_id} — result reused]", True
                    )
                    if formatted_result:
                        tool_results_for_llm.append(formatted_result)
                    continue
                seen_calls[call_key] = tool_id

            # ---- Direct execution for package management tools with progress ----
            if tool_name in PACKAGE_TOOLS:
                async for result_item in self._execute_package_tool(tool_name, tool_id, tool_input, caller_mode):
                    yield result_item
                    if result_item.get("type") == "final_tool_results":
                        tool_results_for_llm.extend(result_item.get("results", []))
                continue

            # ---- Direct execution for background commands with output streaming ----
            if tool_name in BACKGROUND_COMMANDS:
                async for result_item in self._execute_background_command(tool_name, tool_id, tool_input, caller_mode):
                    yield result_item
                    if result_item.get("type") == "final_tool_results":
                        tool_results_for_llm.extend(result_item.get("results", []))
                continue

            # ---- Local file tools (read/write/delete) with approval gate ----
            if tool_name in FILE_TOOLS:
                async for result_item in self._execute_file_tool(
                    tool_name, tool_id, tool_input, caller_mode
                ):
                    yield result_item
                    if result_item.get("type") == "final_tool_results":
                        tool_results_for_llm.extend(result_item.get("results", []))
                continue

            if parse_error:
                logger.warning(
                    f"Skipping tool call due to parsing error: {result_content}"
                )
                status_update = {
                    "type": "tool_call_status",
                    "tool_id": tool_id
                    or f"parse_error_{datetime.datetime.now(datetime.timezone.utc).isoformat()}",
                    "tool_name": tool_name or "Unknown Tool",
                    "status": "error",
                    "content": result_content,
                    "timestamp": datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat()
                    + "Z",
                }
                yield status_update
                # Even on parse error, we might need to format a result for the LLM
                # Use dummy values or the error message
                formatted_result = self.format_tool_result(
                    caller_mode,
                    tool_id
                    or f"parse_error_{datetime.datetime.now(datetime.timezone.utc).isoformat()}",
                    result_content,
                    True,  # is_error
                )
                if formatted_result:
                    tool_results_for_llm.append(formatted_result)
                continue  # Skip execution logic for this call

            # Yield 'running' status before execution
            yield {
                "type": "tool_call_status",
                "tool_id": tool_id,
                "tool_name": tool_name,
                "status": "running",
                "content": "",
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                + "Z",
            }

            # Brief yield so the frontend can process 'running' status and enable passthrough
            await asyncio.sleep(0.05)

            # Execute the tool
            (
                is_error,
                text_content,
                metadata,
                content_items,
            ) = await self.run_single_tool(tool_name, tool_id, tool_input)

            # Determine content for status update and LLM result format
            status_content = text_content  # Default to text content
            llm_formatted_content = text_content  # Default to text content for LLM

            if content_items:
                image_items = [
                    item for item in content_items if item.get("type") == "image"
                ]
                if image_items:
                    num_images = len(image_items)
                    status_content = (
                        f"{text_content}\n[Tool returned {num_images} image(s)]".strip()
                    )

                    if caller_mode == "Claude":
                        # Format for Claude: list of blocks
                        claude_blocks = []
                        if text_content:
                            claude_blocks.append({"type": "text", "text": text_content})
                        for item in content_items:
                            if (
                                item.get("type") == "image"
                                and "data" in item
                                and "mimeType" in item
                            ):
                                claude_blocks.append(
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": item["mimeType"],
                                            "data": item["data"],
                                        },
                                    }
                                )
                        llm_formatted_content = (
                            claude_blocks if claude_blocks else ""
                        )
                    elif caller_mode == "OpenAI":
                        openai_parts = []
                        if text_content:
                            openai_parts.append({"type": "text", "text": text_content})
                        for item in content_items:
                            if (
                                item.get("type") == "image"
                                and "data" in item
                                and "mimeType" in item
                            ):
                                data_url = f"data:{item['mimeType']};base64,{item['data']}"
                                openai_parts.append(
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": data_url,
                                            "detail": "auto",
                                        },
                                    }
                                )
                        llm_formatted_content = (
                            openai_parts if openai_parts else text_content
                        )
                    elif caller_mode == "Prompt":
                        openai_parts = []
                        if text_content:
                            openai_parts.append({"type": "text", "text": text_content})
                        for item in content_items:
                            if (
                                item.get("type") == "image"
                                and "data" in item
                                and "mimeType" in item
                            ):
                                data_url = f"data:{item['mimeType']};base64,{item['data']}"
                                openai_parts.append(
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": data_url,
                                            "detail": "auto",
                                        },
                                    }
                                )
                        llm_formatted_content = (
                            openai_parts if openai_parts else text_content
                        )

            # Prepare and yield tool call status update
            status_update = {
                "type": "tool_call_status",
                "tool_id": tool_id,
                "tool_name": tool_name,
                "status": "error" if is_error else "completed",
                "content": status_content
                if not is_error
                else f"Error: {text_content}",  # Use descriptive content or error message
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                + "Z",
            }

            # For tools that return liveViewData (browser/automation), include browser view links if available
            if not is_error:
                live_view_data = metadata.get("liveViewData", {})
                if live_view_data:
                    logger.info(
                        f"Found live view data for {tool_name}: {live_view_data}"
                    )
                    status_update["browser_view"] = live_view_data

            yield status_update

            # Detect youtube playback invite
            if tool_name == "play_youtube" and not is_error:
                try:
                    yt_data = json.loads(text_content)
                    if yt_data.get("success"):
                        song_info = {
                            "title": yt_data.get("title", "Unknown"),
                            "stream_url": yt_data["stream_url"],
                            "video_url": yt_data.get("video_url", ""),
                        }
                        music_player_manager.play_song(
                            song_info,
                            is_recommended=False,
                        )
                        yield {
                            "type": "youtube-invite",
                            "tool_id": tool_id,
                            "stream_url": yt_data["stream_url"],
                            "title": yt_data.get("title", "Unknown"),
                            "video_url": yt_data.get("video_url", ""),
                            "request_id": tool_id,
                        }
                except Exception:
                    pass

            # Detect playlist play invite
            if tool_name == "play_playlist" and not is_error:
                try:
                    pl_data = json.loads(text_content)
                    if pl_data.get("success"):
                        yield {
                            "type": "playlist-invite",
                            "tool_id": tool_id,
                            "playlist_id": pl_data.get("playlist_id", ""),
                            "stream_url": pl_data.get("stream_url", ""),
                            "title": pl_data.get("title", "Unknown"),
                            "video_url": pl_data.get("video_url", ""),
                            "shuffle": pl_data.get("shuffle", False),
                            "request_id": tool_id,
                        }
                except Exception:
                    pass

            # Detect MV (music video) playback invite
            if tool_name == "play_mv" and not is_error:
                try:
                    mv_data = json.loads(text_content)
                    if mv_data.get("success"):
                        yield {
                            "type": "mv-invite",
                            "tool_id": tool_id,
                            "stream_url": mv_data.get("stream_url", ""),
                            "title": mv_data.get("title", "Unknown"),
                            "video_url": mv_data.get("video_url", ""),
                            "request_id": tool_id,
                        }
                except Exception:
                    pass

            # Format result for LLM and add to list
            formatted_result = self.format_tool_result(
                caller_mode, tool_id, llm_formatted_content, is_error
            )
            if formatted_result:
                tool_results_for_llm.append(formatted_result)

        logger.info(
            f"Finished executing tools with {len(tool_results_for_llm)} results."
        )
        yield {"type": "final_tool_results", "results": tool_results_for_llm}

    async def _execute_package_tool(
        self,
        tool_name: str,
        tool_id: str,
        tool_input: Any,
        caller_mode: Literal["Claude", "OpenAI", "Prompt"],
    ) -> AsyncIterator[Dict[str, Any]]:
        """Execute a package management tool with real-time progress."""
        from ..agentic.package_manager import run_package_operation

        pkg_name = tool_input.get("package_name", "") if isinstance(tool_input, dict) else ""
        mode = tool_input.get("mode", "cascade") if isinstance(tool_input, dict) else "cascade"
        use_aur = tool_input.get("use_aur", False) if isinstance(tool_input, dict) else False

        last_progress = 0
        async for progress, content_line, is_error in run_package_operation(
            operation=tool_name,
            sudo_password=self._sudo_password,
            package_name=pkg_name,
            mode=mode,
            use_aur=use_aur,
        ):
            if progress > last_progress or is_error:
                last_progress = progress
                is_final = progress >= 100 and not is_error
                status = "error" if is_error else ("completed" if is_final else "running")
                yield {
                    "type": "tool_call_status",
                    "tool_id": tool_id,
                    "tool_name": tool_name,
                    "status": status,
                    "progress": progress,
                    "content": content_line,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
                }
                if is_final or is_error:
                    try:
                        data = json.loads(content_line)
                        text_content = data.get("output", content_line) if data.get("success") else data.get("error", content_line)
                    except json.JSONDecodeError:
                        text_content = content_line
                    formatted_result = self.format_tool_result(
                        caller_mode, tool_id, text_content, is_error
                    )
                    if formatted_result:
                        yield {"type": "final_tool_results", "results": [formatted_result]}

    async def _execute_background_command(
        self,
        tool_name: str,
        tool_id: str,
        tool_input: Any,
        caller_mode: Literal["Claude", "OpenAI", "Prompt"],
    ) -> AsyncIterator[Dict[str, Any]]:
        """Execute a shell command asynchronously with real-time output streaming."""
        command = tool_input.get("target", "") if isinstance(tool_input, dict) else ""
        if not command:
            yield {
                "type": "tool_call_status",
                "tool_id": tool_id,
                "tool_name": tool_name,
                "status": "error",
                "content": "No command provided",
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
            }
            formatted_result = self.format_tool_result(caller_mode, tool_id, "Error: No command provided", True)
            if formatted_result:
                yield {"type": "final_tool_results", "results": [formatted_result]}
            return

        is_sudo = tool_name == "run_sudo_command"
        full_command = command

        yield {
            "type": "tool_call_status",
            "tool_id": tool_id,
            "tool_name": tool_name,
            "status": "running",
            "content": f"$ {full_command}",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
        }
        await asyncio.sleep(0.05)

        if not is_sudo:
            cmd_lower = full_command.lower()
            for dangerous in DANGEROUS_COMMANDS:
                if dangerous in cmd_lower:
                    yield {
                        "type": "tool_call_status",
                        "tool_id": tool_id,
                        "tool_name": tool_name,
                        "status": "error",
                        "content": f"Command blocked: '{dangerous}' is not allowed for safety reasons.",
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
                    }
                    formatted_result = self.format_tool_result(
                        caller_mode, tool_id, f"Error: Command blocked (contains '{dangerous}')", True
                    )
                    if formatted_result:
                        yield {"type": "final_tool_results", "results": [formatted_result]}
                    return

        try:
            if is_sudo:
                sudo_pw = self._sudo_password
                if not sudo_pw:
                    yield {
                        "type": "tool_call_status",
                        "tool_id": tool_id,
                        "tool_name": tool_name,
                        "status": "error",
                        "content": "sudo password not configured (set sudo_password in conf.yaml)",
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
                    }
                    formatted_result = self.format_tool_result(caller_mode, tool_id, "Error: sudo password not configured", True)
                    if formatted_result:
                        yield {"type": "final_tool_results", "results": [formatted_result]}
                    return
                process = await asyncio.create_subprocess_shell(
                    f"echo '{sudo_pw}' | sudo -S {full_command}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                process = await asyncio.create_subprocess_shell(
                    full_command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

            full_output_lines = []

            async def reader_task(stream, queue: asyncio.Queue):
                try:
                    while True:
                        line = await stream.readline()
                        if not line:
                            break
                        decoded = line.decode(errors="replace").rstrip()
                        if decoded:
                            await queue.put(decoded)
                except (BrokenPipeError, ValueError):
                    pass
                finally:
                    await queue.put(None)

            queue: asyncio.Queue = asyncio.Queue()
            stdout_task = asyncio.create_task(reader_task(process.stdout, queue))
            stderr_task = asyncio.create_task(reader_task(process.stderr, queue))

            streams_alive = 2
            timeout_sec = 120.0
            start_time = asyncio.get_event_loop().time()

            while streams_alive > 0:
                remaining = timeout_sec - (asyncio.get_event_loop().time() - start_time)
                if remaining <= 0:
                    break
                try:
                    line = await asyncio.wait_for(queue.get(), timeout=min(0.1, remaining))
                    if line is None:
                        streams_alive -= 1
                    else:
                        full_output_lines.append(line)
                        yield {
                            "type": "tool_call_status",
                            "tool_id": tool_id,
                            "tool_name": tool_name,
                            "status": "running",
                            "content": line,
                            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
                        }
                except asyncio.TimeoutError:
                    continue

            stdout_task.cancel()
            stderr_task.cancel()
            try:
                await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
            except Exception:
                pass

            returncode = await process.wait()

            output_text = "\n".join(full_output_lines) if full_output_lines else "(no output)"
            is_error = returncode != 0
            status = "error" if is_error else "completed"

            yield {
                "type": "tool_call_status",
                "tool_id": tool_id,
                "tool_name": tool_name,
                "status": status,
                "content": output_text,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
            }

            formatted_result = self.format_tool_result(
                caller_mode,
                tool_id,
                f"Command: {full_command}\nExit code: {returncode}\nOutput:\n{output_text}",
                is_error,
            )
            if formatted_result:
                yield {"type": "final_tool_results", "results": [formatted_result]}

        except asyncio.TimeoutError:
            yield {
                "type": "tool_call_status",
                "tool_id": tool_id,
                "tool_name": tool_name,
                "status": "error",
                "content": "Command timed out (120s)",
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
            }
            formatted_result = self.format_tool_result(caller_mode, tool_id, "Error: Command timed out", True)
            if formatted_result:
                yield {"type": "final_tool_results", "results": [formatted_result]}
        except Exception as e:
            logger.exception(f"Error executing command '{command}': {e}")
            yield {
                "type": "tool_call_status",
                "tool_id": tool_id,
                "tool_name": tool_name,
                "status": "error",
                "content": f"Error: {e}",
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
            }
            formatted_result = self.format_tool_result(caller_mode, tool_id, f"Error: {e}", True)
            if formatted_result:
                yield {"type": "final_tool_results", "results": [formatted_result]}

    async def _execute_file_tool(
        self,
        tool_name: str,
        tool_id: str,
        tool_input: Any,
        caller_mode: Literal["Claude", "OpenAI", "Prompt"],
    ) -> AsyncIterator[Dict[str, Any]]:
        """Execute a local file tool (read_file/write_file/delete_file).

        Dangerous operations (write/delete) are gated behind a user approval
        callback wired by the websocket layer.
        """
        yield {
            "type": "tool_call_status",
            "tool_id": tool_id,
            "tool_name": tool_name,
            "status": "running",
            "content": "",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
        }
        await asyncio.sleep(0.05)

        try:
            is_error, text_content = await run_file_operation(
                tool_name=tool_name,
                tool_input=tool_input if isinstance(tool_input, dict) else {},
                approval_callback=self._approval_callback,
            )
        except Exception as e:
            logger.exception(f"File tool '{tool_name}' failed: {e}")
            is_error, text_content = True, f"Error: {e}"

        yield {
            "type": "tool_call_status",
            "tool_id": tool_id,
            "tool_name": tool_name,
            "status": "error" if is_error else "completed",
            "content": text_content if not is_error else f"Error: {text_content}",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
        }

        formatted_result = self.format_tool_result(
            caller_mode, tool_id, text_content, is_error
        )
        if formatted_result:
            yield {"type": "final_tool_results", "results": [formatted_result]}

    async def run_single_tool(
        self, tool_name: str, tool_id: str, tool_input: Any
    ) -> tuple[bool, str, Dict[str, Any], List[Dict[str, Any]]]:
        """Run a single tool using MCPClient.

        Returns:
            tuple: (is_error, text_content, metadata, content_items)
        """
        logger.info(f"Executing tool: {tool_name} (ID: {tool_id})")
        tool_info = self._tool_manager.get_tool(tool_name)

        is_error = False
        text_content = ""
        metadata = {}
        content_items = []

        if tool_input is None:
            tool_input = {}

        if not tool_info:
            logger.error(f"Tool '{tool_name}' not found in ToolManager.")
            text_content = f"Error: Tool '{tool_name}' is not available."
            content_items = [{"type": "error", "text": text_content}]
            is_error = True
        elif not tool_info.related_server:
            logger.error(f"Tool '{tool_name}' does not have a related server defined.")
            text_content = f"Error: Configuration error for tool '{tool_name}'. No server specified."
            content_items = [{"type": "error", "text": text_content}]
            is_error = True
        else:
            try:
                result_dict = await self._mcp_client.call_tool(
                    server_name=tool_info.related_server,
                    tool_name=tool_name,
                    tool_args=tool_input,
                )

                metadata = result_dict.get("metadata", {})
                content_items = result_dict.get("content_items", [])

                # Check if the first content item is an error reported by MCPClient
                if content_items and content_items[0].get("type") == "error":
                    is_error = True
                    text_content = content_items[0].get(
                        "text", "Unknown error from tool execution."
                    )
                elif content_items and content_items[0].get("type") == "text":
                    text_content = content_items[0].get("text", "")
                # If no text item is first, text_content remains ""

                if not is_error:
                    logger.info(f"Tool '{tool_name}' executed successfully.")
                    if content_items:
                        logger.info(f"Content items from tool '{tool_name}':")
                        for item in content_items:
                            item_type = item.get("type", "unknown")
                            logger.info(f"  Type: {item_type}")
                            for key, value in item.items():
                                if (
                                    key != "type" and key != "data"
                                ):  # Avoid logging large data
                                    log_value = (
                                        f"(length: {len(value)})"
                                        if isinstance(value, str) and len(value) > 100
                                        else value
                                    )
                                    logger.info(f"    {key}: {log_value}")

            except (ValueError, RuntimeError, ConnectionError) as e:
                logger.exception(f"Error executing tool '{tool_name}': {e}")
                text_content = f"Error executing tool '{tool_name}': {e}"
                content_items = [{"type": "error", "text": text_content}]
                is_error = True
            except Exception as e:
                logger.exception(f"Unexpected error executing tool '{tool_name}': {e}")
                text_content = f"Unexpected error executing tool '{tool_name}': {e}"
                content_items = [{"type": "error", "text": text_content}]
                is_error = True

        return is_error, text_content, metadata, content_items
