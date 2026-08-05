from typing import Type, Literal, Optional
from loguru import logger

from .agents.agent_interface import AgentInterface
from .agents.basic_memory_agent import BasicMemoryAgent
from .agents.split_agent import SplitAgent
from .agents.tool_agent import ToolAgent
from .stateless_llm_factory import LLMFactory as StatelessLLMFactory
from .agents.hume_ai import HumeAIAgent
from .agents.letta_agent import LettaAgent

from ..mcpp.tool_manager import ToolManager
from ..mcpp.tool_executor import ToolExecutor


class AgentFactory:
    @staticmethod
    def create_agent(
        conversation_agent_choice: str,
        agent_settings: dict,
        llm_configs: dict,
        system_prompt: str,
        live2d_model=None,
        tts_preprocessor_config=None,
        **kwargs,
    ) -> Type[AgentInterface]:
        """Create an agent based on the configuration.

        Args:
            conversation_agent_choice: The type of agent to create
            agent_settings: Settings for different types of agents
            llm_configs: Pool of LLM configurations
            system_prompt: The system prompt to use
            live2d_model: Live2D model instance for expression extraction
            tts_preprocessor_config: Configuration for TTS preprocessing
            **kwargs: Additional arguments
        """
        logger.info(f"Initializing agent: {conversation_agent_choice}")

        if conversation_agent_choice == "basic_memory_agent":
            # Get the LLM provider choice from agent settings
            basic_memory_settings: dict = agent_settings.get("basic_memory_agent", {})
            llm_provider: str = basic_memory_settings.get("llm_provider")

            if not llm_provider:
                raise ValueError("LLM provider not specified for basic memory agent")

            # Get the LLM config for this provider
            llm_config: dict = llm_configs.get(llm_provider)
            interrupt_method: Literal["system", "user"] = llm_config.pop(
                "interrupt_method", "user"
            )

            if not llm_config:
                raise ValueError(
                    f"Configuration not found for LLM provider: {llm_provider}"
                )

            # Create the persona LLM (Gemini/OpenAI for conversation)
            llm = StatelessLLMFactory.create_llm(
                llm_provider=llm_provider, system_prompt=system_prompt, **llm_config
            )

            tool_prompts = kwargs.get("system_config", {}).get("tool_prompts", {})

            # Extract MCP components/data needed by BasicMemoryAgent from kwargs
            tool_manager: Optional[ToolManager] = kwargs.get("tool_manager")
            tool_executor: Optional[ToolExecutor] = kwargs.get("tool_executor")
            mcp_prompt_string: str = kwargs.get("mcp_prompt_string", "")

            # === Check for SPLIT-AGENT mode (subagent_mode='split') ===
            subagent_mode: str = basic_memory_settings.get("subagent_mode", "none")
            subagent_configs: Optional[dict] = basic_memory_settings.get("subagent")

            if subagent_mode == "split" and subagent_configs and tool_manager and tool_executor:
                # Use tool_agent_system from kwargs if provided, else fallback
                tool_agent_system = kwargs.get(
                    "tool_agent_system",
                    "Kamu adalah tool specialist. Tugasmu memahami request user dan memanggil tools yang sesuai. Gunakan tools satu per satu.",
                )
                return _create_split_agent(
                    persona_llm=llm,
                    persona_system=system_prompt,
                    persona_llm_provider=llm_provider,
                    persona_llm_config=llm_config,
                    subagent_configs=subagent_configs,
                    llm_configs=llm_configs,
                    basic_memory_settings=basic_memory_settings,
                    tool_manager=tool_manager,
                    tool_executor=tool_executor,
                    live2d_model=live2d_model,
                    tts_preprocessor_config=tts_preprocessor_config,
                    interrupt_method=interrupt_method,
                    tool_agent_system=tool_agent_system,
                )

            # === HYBRID MODE: persona (Gemini) with simple tools + specialist Groq agents ===
            if subagent_mode == "hybrid" and tool_manager and tool_executor:
                simple_tool_names = basic_memory_settings.get("simple_tool_names", [])
                tool_llm_provider = basic_memory_settings.get("tool_llm_provider")
                specialist_llm = None
                if tool_llm_provider and tool_llm_provider in llm_configs:
                    tool_llm_cfg = llm_configs[tool_llm_provider].copy()
                    tool_llm_cfg.pop("interrupt_method", None)
                    specialist_llm = StatelessLLMFactory.create_llm(
                        llm_provider=tool_llm_provider, **tool_llm_cfg
                    )
                    logger.info(
                        f"Hybrid mode: specialist LLM = {tool_llm_provider}"
                    )
                else:
                    logger.warning(
                        "Hybrid mode: tool_llm_provider not configured, "
                        "summon_specialist will be unavailable"
                    )

                from .tool_groups import get_default_groups

                return BasicMemoryAgent(
                    llm=llm,
                    system=system_prompt,
                    live2d_model=live2d_model,
                    tts_preprocessor_config=tts_preprocessor_config,
                    faster_first_response=basic_memory_settings.get(
                        "faster_first_response", True
                    ),
                    segment_method=basic_memory_settings.get(
                        "segment_method", "pysbd"
                    ),
                    use_mcpp=True,
                    tool_routing="legacy",
                    interrupt_method=interrupt_method,
                    tool_prompts=tool_prompts,
                    tool_manager=tool_manager,
                    tool_executor=tool_executor,
                    mcp_prompt_string=mcp_prompt_string,
                    tool_agent=None,
                    simple_tool_names=simple_tool_names,
                    specialist_llm=specialist_llm,
                    tool_groups=get_default_groups(),
                )

            # === DUAL-AGENT: Create ToolAgent if separate tool LLM is configured ===
            tool_agent: Optional[ToolAgent] = None
            tool_llm_provider: Optional[str] = basic_memory_settings.get(
                "tool_llm_provider"
            )
            tool_llm_config_name: Optional[str] = basic_memory_settings.get(
                "tool_llm_config_name"
            )

            if tool_llm_provider and tool_manager and tool_executor:
                # Get the tool LLM config (same llm_configs pool)
                tool_llm_config_key = tool_llm_config_name or tool_llm_provider
                tool_llm_cfg: dict = llm_configs.get(tool_llm_config_key)

                if tool_llm_cfg:
                    # Don't pop interrupt_method from shared config dict
                    tool_llm_cfg_copy = tool_llm_cfg.copy()
                    tool_llm_cfg_copy.pop("interrupt_method", None)

                    logger.info(
                        f"Creating ToolAgent with LLM provider: {tool_llm_provider}"
                    )
                    tool_llm = StatelessLLMFactory.create_llm(
                        llm_provider=tool_llm_provider,
                        **tool_llm_cfg_copy,
                    )

                    # Load tool agent prompt
                    tool_agent_system = kwargs.get(
                        "tool_agent_system",
                        "You are a tool assistant. Call tools as requested.",
                    )

                    tool_agent = ToolAgent(
                        llm=tool_llm,
                        tool_executor=tool_executor,
                        tool_manager=tool_manager,
                        system_prompt=tool_agent_system,
                    )
                    logger.info(
                        f"ToolAgent created with {len(tool_manager.get_formatted_tools('OpenAI'))} tools"
                    )
                else:
                    logger.warning(
                        f"Tool LLM config '{tool_llm_config_key}' not found in llm_configs. "
                        "Falling back to legacy single-agent mode."
                    )
            else:
                logger.debug(
                    "ToolAgent not created: tool_llm_provider=%s, tool_manager=%s, "
                    "tool_executor=%s",
                    tool_llm_provider,
                    bool(tool_manager),
                    bool(tool_executor),
                )

            # Create the agent with the persona LLM and optional ToolAgent
            return BasicMemoryAgent(
                llm=llm,
                system=system_prompt,
                live2d_model=live2d_model,
                tts_preprocessor_config=tts_preprocessor_config,
                faster_first_response=basic_memory_settings.get(
                    "faster_first_response", True
                ),
                segment_method=basic_memory_settings.get("segment_method", "pysbd"),
                use_mcpp=basic_memory_settings.get("use_mcpp", False),
                tool_routing=basic_memory_settings.get("tool_routing", "legacy"),
                interrupt_method=interrupt_method,
                tool_prompts=tool_prompts,
                tool_manager=tool_manager,
                tool_executor=tool_executor,
                mcp_prompt_string=mcp_prompt_string,
                tool_agent=tool_agent,
            )

        elif conversation_agent_choice == "hume_ai_agent":
            settings = agent_settings.get("hume_ai_agent", {})
            return HumeAIAgent(
                api_key=settings.get("api_key"),
                host=settings.get("host", "api.hume.ai"),
                config_id=settings.get("config_id"),
                idle_timeout=settings.get("idle_timeout", 15),
            )

        elif conversation_agent_choice == "letta_agent":
            settings = agent_settings.get("letta_agent", {})
            return LettaAgent(
                live2d_model=live2d_model,
                id=settings.get("id"),
                tts_preprocessor_config=tts_preprocessor_config,
                faster_first_response=settings.get("faster_first_response"),
                segment_method=settings.get("segment_method"),
                host=settings.get("host"),
                port=settings.get("port"),
            )

        else:
            raise ValueError(f"Unsupported agent type: {conversation_agent_choice}")


def _create_split_agent(
    persona_llm,
    persona_system: str,
    persona_llm_provider: str,
    persona_llm_config: dict,
    subagent_configs: dict,
    llm_configs: dict,
    basic_memory_settings: dict,
    tool_manager: ToolManager,
    tool_executor: ToolExecutor,
    live2d_model,
    tts_preprocessor_config,
    interrupt_method: str,
    tool_agent_system: str = "",
) -> SplitAgent:
    """Create a SplitAgent with persona + tool sub-agents.

    Both sub-agents can use the same LLM provider or different ones.
    """
    # ── Tool sub-agent ──
    tool_cfg = subagent_configs.get("tool", {})
    tool_llm_provider = tool_cfg.get("llm_provider", persona_llm_provider)
    tool_llm_config = llm_configs.get(tool_llm_provider, persona_llm_config)

    logger.info(f"SplitAgent tool sub-agent: provider={tool_llm_provider}")

    tool_llm_cfg_copy = tool_llm_config.copy()
    tool_llm_cfg_copy.pop("interrupt_method", None)

    tool_llm = StatelessLLMFactory.create_llm(
        llm_provider=tool_llm_provider,
        **tool_llm_cfg_copy,
    )

    if not tool_agent_system:
        tool_agent_system = (
            "Kamu adalah tool specialist. "
            "Tugasmu memahami request user dan memanggil tools yang sesuai. "
            "Gunakan tools satu per satu. Setelah selesai, ringkas hasilnya."
        )

    tool_agent = ToolAgent(
        llm=tool_llm,
        tool_executor=tool_executor,
        tool_manager=tool_manager,
        system_prompt=tool_agent_system,
    )

    # ── Persona sub-agent ──
    logger.info(
        f"SplitAgent persona sub-agent: provider={persona_llm_provider}"
    )

    persona_agent = BasicMemoryAgent(
        llm=persona_llm,
        system=persona_system,
        live2d_model=live2d_model,
        tts_preprocessor_config=tts_preprocessor_config,
        faster_first_response=basic_memory_settings.get(
            "faster_first_response", True
        ),
        segment_method=basic_memory_settings.get("segment_method", "pysbd"),
        use_mcpp=False,
        tool_routing="legacy",
        interrupt_method=interrupt_method,
        tool_prompts=basic_memory_settings.get("tool_prompts", {}),
        tool_manager=None,
        tool_executor=None,
        mcp_prompt_string="",
        tool_agent=None,
    )

    logger.info(
        f"SplitAgent created: persona={persona_llm_provider}, "
        f"tool={tool_llm_provider}"
    )
    return SplitAgent(
        persona_agent=persona_agent,
        tool_agent=tool_agent,
        tool_manager=tool_manager,
    )
