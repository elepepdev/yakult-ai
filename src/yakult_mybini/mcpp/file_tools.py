"""Local file tools (read/write/delete) executed on the server.

These tools are registered into ``ToolManager`` alongside the MCP-provided
tools, but are intercepted by ``ToolExecutor`` and run directly here instead
of being routed through an MCP server.

Dangerous operations (write/delete) go through a user-approval gate: the
server builds a payload (including a unified diff for writes) and asks the
frontend to accept or deny before executing.
"""

import asyncio
import difflib
import os
import shutil
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from loguru import logger

from .types import FormattedTool

FILE_TOOLS = {"read_file", "write_file", "delete_file"}
APPROVAL_REQUIRED = {"write_file", "delete_file"}

MAX_READ_BYTES = 256 * 1024  # 256 KB


# ---------------------------------------------------------------------------
# Tool definitions (OpenAI + Claude formats) + raw FormattedTool entries
# ---------------------------------------------------------------------------

def _openai_tool(name: str, description: str, properties: Dict[str, Any], required: List[str]) -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def get_local_tool_definitions() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, FormattedTool]]:
    """Return (openai_tools, claude_tools, raw_tools_dict) for the file tools."""
    openai_tools = [
        _openai_tool(
            "read_file",
            "Read the content of a text file on the user's computer. Safe operation, no approval needed. "
            "Use it to inspect files, configs, logs, or source code.",
            {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the file to read.",
                },
                "max_lines": {
                    "type": "integer",
                    "description": "Optional. Maximum number of lines to return (default: all).",
                },
            },
            ["path"],
        ),
        _openai_tool(
            "write_file",
            "Write text content to a file, creating or overwriting it. "
            "⚠️ This modifies the user's filesystem and REQUIRES user approval — "
            "the diff will be shown to the user first.",
            {
                "path": {
                    "type": "string",
                    "description": "Absolute path of the file to write.",
                },
                "content": {
                    "type": "string",
                    "description": "Full new content of the file.",
                },
                "create_dirs": {
                    "type": "boolean",
                    "description": "Create missing parent directories. Default: true.",
                },
            },
            ["path", "content"],
        ),
        _openai_tool(
            "delete_file",
            "Permanently delete a file or directory on the user's computer. "
            "⚠️ This is destructive and REQUIRES user approval.",
            {
                "path": {
                    "type": "string",
                    "description": "Absolute path of the file or directory to delete.",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Delete non-empty directories recursively. Default: false.",
                },
            },
            ["path"],
        ),
    ]

    claude_tools = []
    raw_tools: Dict[str, FormattedTool] = {}
    for tool in openai_tools:
        fn = tool["function"]
        properties = fn["parameters"]["properties"]
        claude_tools.append(
            {
                "name": fn["name"],
                "description": fn["description"],
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": fn["parameters"].get("required", []),
                },
            }
        )
        raw_tools[fn["name"]] = FormattedTool(
            input_schema=fn["parameters"],
            related_server=None,
            description=fn["description"],
            generic_schema=None,
        )

    return openai_tools, claude_tools, raw_tools


# ---------------------------------------------------------------------------
# Diff generation
# ---------------------------------------------------------------------------

def generate_diff(path: str, old_content: str, new_content: str) -> str:
    """Build a unified diff between the current file content and the new one."""
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        n=3,
    )
    return "".join(diff)


# ---------------------------------------------------------------------------
# Approval payloads
# ---------------------------------------------------------------------------

def build_approval_payload(tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
    """Build the payload sent to the frontend for a dangerous operation."""
    path = str(tool_input.get("path", "")).strip()
    payload: Dict[str, Any] = {
        "tool_name": tool_name,
        "operation": "write" if tool_name == "write_file" else "delete",
        "path": path,
    }

    if tool_name == "write_file":
        new_content = str(tool_input.get("content", ""))
        old_content = ""
        try:
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    old_content = f.read()
        except Exception as e:
            logger.warning(f"Could not read existing file for diff: {e}")
        payload["diff"] = generate_diff(path, old_content, new_content)
        payload["exists"] = os.path.exists(path)
        payload["content_preview"] = new_content[:2000]

    if tool_name == "delete_file":
        try:
            p = Path(path)
            payload["is_dir"] = p.is_dir()
            payload["size"] = _dir_size(p) if p.is_dir() else (p.stat().st_size if p.exists() else 0)
        except Exception:
            payload["is_dir"] = False
            payload["size"] = 0

    return payload


def _dir_size(path: Path) -> int:
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    except Exception:
        pass
    return total


# ---------------------------------------------------------------------------
# Actual operations
# ---------------------------------------------------------------------------

async def run_file_operation(
    tool_name: str,
    tool_input: Dict[str, Any],
    approval_callback: Optional[Callable[[Dict[str, Any]], Awaitable[bool]]] = None,
) -> Tuple[bool, str]:
    """Run a file tool operation.

    Args:
        tool_name: One of read_file / write_file / delete_file.
        tool_input: Parsed tool arguments.
        approval_callback: Awaitable called with the approval payload for
            dangerous operations. Must return True to proceed, False to cancel.

    Returns:
        tuple: (is_error, text_content)
    """
    path = str(tool_input.get("path", "")).strip() if isinstance(tool_input, dict) else ""
    if not path:
        return True, "Error: 'path' is required."

    if tool_name == "read_file":
        return _do_read(path, tool_input)

    if tool_name == "write_file":
        payload = build_approval_payload(tool_name, tool_input)
        approved = await _request_approval(approval_callback, payload)
        if not approved:
            return True, "Operation cancelled: the user denied the file write."
        return _do_write(path, tool_input)

    if tool_name == "delete_file":
        payload = build_approval_payload(tool_name, tool_input)
        approved = await _request_approval(approval_callback, payload)
        if not approved:
            return True, "Operation cancelled: the user denied the file deletion."
        return _do_delete(path, tool_input)

    return True, f"Error: unknown file tool '{tool_name}'."


async def _request_approval(
    callback: Optional[Callable[[Dict[str, Any]], Awaitable[bool]]],
    payload: Dict[str, Any],
) -> bool:
    if not callback:
        logger.warning("No approval callback configured — denying file operation by default.")
        return False
    try:
        return bool(await callback(payload))
    except asyncio.TimeoutError:
        logger.warning("Approval request timed out — denying file operation.")
        return False
    except Exception as e:
        logger.error(f"Approval callback failed: {e}")
        return False


def _do_read(path: str, tool_input: Dict[str, Any]) -> Tuple[bool, str]:
    try:
        p = Path(path)
        if not p.exists():
            return True, f"Error: file not found: {path}"
        if p.is_dir():
            try:
                entries = sorted(os.listdir(p))
                listing = "\n".join(entries) if entries else "(empty directory)"
                return False, f"[Directory listing of {path}]\n{listing}"
            except Exception as e:
                return True, f"Error listing directory: {e}"

        max_lines = tool_input.get("max_lines")
        size = p.stat().st_size
        if size > MAX_READ_BYTES:
            return True, (
                f"Error: file is too large to read ({size} bytes > "
                f"{MAX_READ_BYTES} limit). Ask the user to open it, or read it with a tool command."
            )

        with open(p, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        if max_lines:
            lines = content.splitlines()
            content = "\n".join(lines[: int(max_lines)])

        return False, content
    except Exception as e:
        logger.exception(f"read_file failed for {path}: {e}")
        return True, f"Error reading file: {e}"


def _do_write(path: str, tool_input: Dict[str, Any]) -> Tuple[bool, str]:
    content = str(tool_input.get("content", ""))
    create_dirs = bool(tool_input.get("create_dirs", True))
    try:
        p = Path(path)
        if p.exists() and p.is_dir():
            return True, f"Error: cannot write to a directory: {path}"
        if create_dirs:
            p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return False, f"Successfully wrote {len(content)} bytes to {path}"
    except Exception as e:
        logger.exception(f"write_file failed for {path}: {e}")
        return True, f"Error writing file: {e}"


def _do_delete(path: str, tool_input: Dict[str, Any]) -> Tuple[bool, str]:
    recursive = bool(tool_input.get("recursive", False))
    try:
        p = Path(path)
        if not p.exists():
            return True, f"Error: path not found: {path}"
        if p.is_dir():
            if not recursive:
                try:
                    p.rmdir()
                    return False, f"Deleted empty directory: {path}"
                except OSError:
                    return True, (
                        f"Error: directory is not empty. Use recursive=true to delete it "
                        f"and all its contents."
                    )
            shutil.rmtree(p)
            return False, f"Deleted directory (recursive): {path}"
        p.unlink()
        return False, f"Deleted file: {path}"
    except Exception as e:
        logger.exception(f"delete_file failed for {path}: {e}")
        return True, f"Error deleting: {e}"
