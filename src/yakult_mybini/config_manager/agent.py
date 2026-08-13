"""
This module contains the pydantic model for the configurations of
different types of agents.
"""

from pydantic import BaseModel, Field
from typing import Dict, ClassVar, Optional, Literal, List
from .i18n import I18nMixin, Description
from .stateless_llm import StatelessLLMConfigs

# ======== Configurations for different Agents ========


class SubAgentConfig(I18nMixin, BaseModel):
    """Configuration for a sub-agent in split-agent mode."""

    llm_provider: str = Field(..., alias="llm_provider")

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "llm_provider": Description(
            en="LLM provider for this sub-agent",
            zh="此子代理的 LLM 提供者",
        ),
    }


class BasicMemoryAgentConfig(I18nMixin, BaseModel):
    """Configuration for the basic memory agent."""

    llm_provider: Literal[
        "stateless_llm_with_template",
        "openai_compatible_llm",
        "claude_llm",
        "llama_cpp_llm",
        "ollama_llm",
        "lmstudio_llm",
        "openai_llm",
        "gemini_llm",
        "zhipu_llm",
        "deepseek_llm",
        "groq_llm",
        "grok_llm",
        "mistral_llm",
        "openrouter_llm",
        "nvidia_nim_llm",
        "cloudflare_workers_llm",
        "opencode_zen_llm",
        "opencode_go_llm",
        "juan_router_llm",
    ] = Field(..., alias="llm_provider")

    faster_first_response: Optional[bool] = Field(True, alias="faster_first_response")
    segment_method: Literal["regex", "pysbd"] = Field("pysbd", alias="segment_method")
    use_mcpp: Optional[bool] = Field(False, alias="use_mcpp")
    mcp_enabled_servers: Optional[List[str]] = Field([], alias="mcp_enabled_servers")
    tool_routing: Literal["legacy", "persona_first"] = Field(
        "legacy", alias="tool_routing"
    )

    # Separate LLM for memory extraction (e.g. 'groq_llm' to save Gemini RPD)
    memory_llm_provider: Optional[str] = Field(None, alias="memory_llm_provider")

    # Dual-agent: separate LLM for tool execution (e.g. Groq for high rate limits)
    tool_llm_provider: Optional[str] = Field(None, alias="tool_llm_provider")
    tool_llm_config_name: Optional[str] = Field(None, alias="tool_llm_config_name")

    # Split-agent mode: one model → two agents (persona + tool)
    subagent_mode: Literal["none", "split", "hybrid"] = Field(
        "none", alias="subagent_mode"
    )
    subagent: Optional[Dict[str, "SubAgentConfig"]] = Field(None, alias="subagent")

    # Hybrid mode: simple tools handled by persona LLM, complex tools delegated to specialist
    simple_tool_names: Optional[List[str]] = Field(None, alias="simple_tool_names")

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "llm_provider": Description(
            en="LLM provider to use for this agent",
            zh="Basic Memory Agent 智能体使用的大语言模型选项",
        ),
        "faster_first_response": Description(
            en="Whether to respond as soon as encountering a comma in the first sentence to reduce latency (default: True)",
            zh="是否在第一句回应时遇上逗号就直接生成音频以减少首句延迟（默认：True）",
        ),
        "segment_method": Description(
            en="Method for segmenting sentences: 'regex' or 'pysbd' (default: 'pysbd')",
            zh="分割句子的方法：'regex' 或 'pysbd'（默认：'pysbd'）",
        ),
        "use_mcpp": Description(
            en="Whether to use MCP (Model Context Protocol) for the agent (default: True)",
            zh="是否使用为智能体启用 MCP (Model Context Protocol) Plus（默认：False）",
        ),
        "mcp_enabled_servers": Description(
            en="List of MCP servers to enable for the agent",
            zh="为智能体启用 MCP 服务器列表",
        ),
        "tool_routing": Description(
            en="Tool routing strategy: 'legacy' (single LLM handles everything) or 'persona_first' (Gemini for persona, Groq for tools)",
            zh="工具路由策略：'legacy'（单一 LLM 处理所有）或 'persona_first'（Gemini 处理人格，Groq 处理工具）",
        ),
        "memory_llm_provider": Description(
            en="Separate LLM provider for memory extraction (e.g. 'groq_llm'). Saves main LLM RPD by routing memory summarization to a cheaper/higher-limit provider.",
            zh="用于记忆提取的独立 LLM 提供者（例如 'groq_llm'）。将记忆总结路由到更便宜/更高限制的提供者，以节省主 LLM 的 RPD。",
        ),
        "tool_llm_provider": Description(
            en="Separate LLM provider for tool execution (e.g. 'groq_llm'). When set, enables dual-agent mode: persona LLM handles conversation, tool LLM handles tool calls.",
            zh="用于工具执行的独立 LLM 提供者（例如 'groq_llm'）。设置后启用双代理模式：对话 LLM 处理对话，工具 LLM 处理工具调用。",
        ),
        "tool_llm_config_name": Description(
            en="Provider name for tool LLM config lookup (usually same as tool_llm_provider, but can differ if needed)",
            zh="工具 LLM 配置查找的提供者名称（通常与 tool_llm_provider 相同，但需要时可不同）",
        ),
        "subagent_mode": Description(
            en="Sub-agent mode: 'none' (single-agent, default), 'split' (persona + tool agents), or 'hybrid' (persona handles simple tools + summon_specialist, Groq specialists handle complex tools)",
            zh="子代理模式：'none'（单一代理，默认）、'split'（人格 + 工具代理）或 'hybrid'（人格处理简单工具 + summon_specialist，Groq 专家处理复杂工具）",
        ),
        "subagent": Description(
            en="Sub-agent configurations for split mode (keys: 'persona', 'tool')",
            zh="分割模式的子代理配置（键：'persona'，'tool'）",
        ),
        "simple_tool_names": Description(
            en="Tool names that the persona LLM can call directly. Complex tools not in this list are delegated to specialist Groq agents via summon_specialist. Used only in 'hybrid' subagent_mode.",
            zh="人格 LLM 可以直接调用的工具名称。不在此列表中的复杂工具将通过 summon_specialist 委托给 Groq 专家代理。仅在 'hybrid' 子代理模式下使用。",
        ),
    }


class Mem0VectorStoreConfig(I18nMixin, BaseModel):
    """Configuration for Mem0 vector store."""

    provider: str = Field(..., alias="provider")
    config: Dict = Field(..., alias="config")

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "provider": Description(
            en="Vector store provider (e.g., qdrant)", zh="向量存储提供者（如 qdrant）"
        ),
        "config": Description(
            en="Provider-specific configuration", zh="提供者特定配置"
        ),
    }


class Mem0LLMConfig(I18nMixin, BaseModel):
    """Configuration for Mem0 LLM."""

    provider: str = Field(..., alias="provider")
    config: Dict = Field(..., alias="config")

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "provider": Description(en="LLM provider name", zh="语言模型提供者名称"),
        "config": Description(
            en="Provider-specific configuration", zh="提供者特定配置"
        ),
    }


class Mem0EmbedderConfig(I18nMixin, BaseModel):
    """Configuration for Mem0 embedder."""

    provider: str = Field(..., alias="provider")
    config: Dict = Field(..., alias="config")

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "provider": Description(en="Embedder provider name", zh="嵌入模型提供者名称"),
        "config": Description(
            en="Provider-specific configuration", zh="提供者特定配置"
        ),
    }


class Mem0Config(I18nMixin, BaseModel):
    """Configuration for Mem0."""

    vector_store: Mem0VectorStoreConfig = Field(..., alias="vector_store")
    llm: Mem0LLMConfig = Field(..., alias="llm")
    embedder: Mem0EmbedderConfig = Field(..., alias="embedder")

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "vector_store": Description(en="Vector store configuration", zh="向量存储配置"),
        "llm": Description(en="LLM configuration", zh="语言模型配置"),
        "embedder": Description(en="Embedder configuration", zh="嵌入模型配置"),
    }


# =================================


class HumeAIConfig(I18nMixin, BaseModel):
    """Configuration for the Hume AI agent."""

    api_key: str = Field(..., alias="api_key")
    host: str = Field("api.hume.ai", alias="host")
    config_id: Optional[str] = Field(None, alias="config_id")
    idle_timeout: int = Field(15, alias="idle_timeout")

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "api_key": Description(
            en="API key for Hume AI service", zh="Hume AI 服务的 API 密钥"
        ),
        "host": Description(
            en="Host URL for Hume AI service (default: api.hume.ai)",
            zh="Hume AI 服务的主机地址（默认：api.hume.ai）",
        ),
        "config_id": Description(
            en="Configuration ID for EVI settings", zh="EVI 配置 ID"
        ),
        "idle_timeout": Description(
            en="Idle timeout in seconds before disconnecting (default: 15)",
            zh="空闲超时断开连接的秒数（默认：15）",
        ),
    }


# =================================


class LettaConfig(I18nMixin, BaseModel):
    """Configuration for the Letta agent."""

    host: str = Field("localhost", alias="host")
    port: int = Field(8283, alias="port")
    id: str = Field(..., alias="id")
    faster_first_response: Optional[bool] = Field(True, alias="faster_first_response")
    segment_method: Literal["regex", "pysbd"] = Field("pysbd", alias="segment_method")

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "host": Description(
            en="Host address for the Letta server", zh="Letta服务器的主机地址"
        ),
        "port": Description(
            en="Port number for the Letta server (default: 8283)",
            zh="Letta服务器的端口号（默认：8283）",
        ),
        "id": Description(
            en="Agent instance ID running on the Letta server",
            zh="指定Letta服务器上运行的Agent实例id",
        ),
    }


class AgentSettings(I18nMixin, BaseModel):
    """Settings for different types of agents."""

    basic_memory_agent: Optional[BasicMemoryAgentConfig] = Field(
        None, alias="basic_memory_agent"
    )

    hume_ai_agent: Optional[HumeAIConfig] = Field(None, alias="hume_ai_agent")
    letta_agent: Optional[LettaConfig] = Field(None, alias="letta_agent")

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "basic_memory_agent": Description(
            en="Configuration for basic memory agent", zh="基础记忆代理配置"
        ),
        "hume_ai_agent": Description(
            en="Configuration for Hume AI agent", zh="Hume AI 代理配置"
        ),
        "letta_agent": Description(
            en="Configuration for Letta agent", zh="Letta 代理配置"
        ),
    }


class AgentConfig(I18nMixin, BaseModel):
    """This class contains all of the configurations related to agent."""

    conversation_agent_choice: Literal[
        "basic_memory_agent", "hume_ai_agent", "letta_agent"
    ] = Field(..., alias="conversation_agent_choice")
    agent_settings: AgentSettings = Field(..., alias="agent_settings")
    llm_configs: StatelessLLMConfigs = Field(..., alias="llm_configs")

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "conversation_agent_choice": Description(
            en="Type of conversation agent to use", zh="要使用的对话代理类型"
        ),
        "agent_settings": Description(
            en="Settings for different agent types", zh="不同代理类型的设置"
        ),
        "llm_configs": Description(
            en="Pool of LLM provider configurations", zh="语言模型提供者配置池"
        ),
        "faster_first_response": Description(
            en="Whether to respond as soon as encountering a comma in the first sentence to reduce latency (default: True)",
            zh="是否在第一句回应时遇上逗号就直接生成音频以减少首句延迟（默认：True）",
        ),
        "segment_method": Description(
            en="Method for segmenting sentences: 'regex' or 'pysbd' (default: 'pysbd')",
            zh="分割句子的方法：'regex' 或 'pysbd'（默认：'pysbd'）",
        ),
    }
