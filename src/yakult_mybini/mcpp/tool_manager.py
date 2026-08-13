from loguru import logger
from typing import Dict, Any, List, Literal

from .types import FormattedTool


class ToolManager:
    """Tool Manager for managing pre-formatted tools for different LLM APIs."""

    def __init__(
        self,
        formatted_tools_openai: List[Dict[str, Any]] = None,
        formatted_tools_claude: List[Dict[str, Any]] = None,
        initial_tools_dict: Dict[str, FormattedTool] = None,
    ) -> None:
        """Initialize the Tool Manager with pre-formatted tool lists."""
        # Store the raw tool data (optional, for get_tool)
        self.tools: Dict[str, FormattedTool] = initial_tools_dict or {}

        # Store the pre-formatted lists
        self._original_openai = (formatted_tools_openai or [])[:]
        self._original_claude = (formatted_tools_claude or [])[:]
        self._formatted_tools_openai: List[Dict[str, Any]] = (
            formatted_tools_openai or []
        )
        self._formatted_tools_claude: List[Dict[str, Any]] = (
            formatted_tools_claude or []
        )

        logger.info(
            f"ToolManager initialized with {len(self._formatted_tools_openai)} OpenAI tools and {len(self._formatted_tools_claude)} Claude tools."
        )

    def filter_tool_names(self, allowed_names: set) -> None:
        """Filter both tool lists to only include tools in allowed_names."""
        self._formatted_tools_openai = [
            t
            for t in self._original_openai
            if t.get("function", {}).get("name") in allowed_names
        ]
        self._formatted_tools_claude = [
            t
            for t in self._original_claude
            if t.get("function", {}).get("name") in allowed_names
        ]
        logger.info(
            f"ToolManager filtered to {len(self._formatted_tools_openai)} tools "
            f"({allowed_names})"
        )

    def restore_tools(self) -> None:
        """Restore both tool lists to their original unfiltered state."""
        self._formatted_tools_openai = self._original_openai[:]
        self._formatted_tools_claude = self._original_claude[:]
        logger.info(
            f"ToolManager restored to {len(self._formatted_tools_openai)} tools"
        )

    def get_tool(self, tool_name: str) -> FormattedTool | None:
        """Get a tool's raw information by its name."""
        tool = self.tools.get(tool_name)
        if isinstance(tool, FormattedTool):
            return tool
        logger.warning(
            f"TM: Raw tool info for '{tool_name}' not found (was initial_tools_dict provided?)."
        )
        return None

    def get_formatted_tools(
        self, mode: Literal["OpenAI", "Claude"]
    ) -> List[Dict[str, Any]] | Any:
        """Get the pre-formatted list of tools for the specified API mode."""

        if mode == "OpenAI":
            return self._formatted_tools_openai
        elif mode == "Claude":
            return self._formatted_tools_claude

    def get_filtered_tools(
        self,
        mode: Literal["OpenAI", "Claude"],
        tool_names: List[str],
    ) -> List[Dict[str, Any]]:
        """Get tools filtered by name. Keeps prompt small for sub-agents."""
        all_tools = self.get_formatted_tools(mode)
        names = set(tool_names)
        return [t for t in all_tools if t.get("function", {}).get("name") in names]

    def add_local_tools(
        self,
        openai_tools: List[Dict[str, Any]],
        claude_tools: List[Dict[str, Any]],
        raw_tools: Dict[str, FormattedTool],
    ) -> None:
        """Register locally-implemented tools (e.g. file read/write/delete).

        Appends to both the active and the "original" lists so that
        ``filter_tool_names`` / ``restore_tools`` keep working correctly.
        """
        self._original_openai.extend(openai_tools)
        self._original_claude.extend(claude_tools)
        self._formatted_tools_openai.extend(openai_tools)
        self._formatted_tools_claude.extend(claude_tools)
        self.tools.update(raw_tools)
        logger.info(
            f"ToolManager: registered {len(openai_tools)} local tools "
            f"({', '.join(t.get('function', {}).get('name', '?') for t in openai_tools)})"
        )
