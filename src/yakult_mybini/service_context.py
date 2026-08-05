import os
import json
from loguru import logger
from fastapi import WebSocket

from prompts import prompt_loader
from .live2d_model import Live2dModel
from .character_model import VRMModel
from .asr.asr_interface import ASRInterface
from .tts.tts_interface import TTSInterface
from .vad.vad_interface import VADInterface
from .agent.agents.agent_interface import AgentInterface
from .translate.translate_interface import TranslateInterface

from .conversations.screen_monitor import ScreenMonitor
from .conversations.idle_life_manager import IdleLifeManager, IdleLifeConfig

from .mcpp.server_registry import ServerRegistry
from .mcpp.tool_manager import ToolManager
from .mcpp.mcp_client import MCPClient
from .mcpp.tool_executor import ToolExecutor
from .mcpp.tool_adapter import ToolAdapter

from .memory.memory_manager import MemoryManager
from .memory.todo_manager import TodoManager

from .asr.asr_factory import ASRFactory
from .tts.tts_factory import TTSFactory
from .vad.vad_factory import VADFactory
from .agent.agent_factory import AgentFactory
from .agent.stateless_llm_factory import LLMFactory as StatelessLLMFactory
from .translate.translate_factory import TranslateFactory

from .config_manager import (
    Config,
    AgentConfig,
    CharacterConfig,
    SystemConfig,
    ASRConfig,
    TTSConfig,
    VADConfig,
    TranslatorConfig,
    read_yaml,
    validate_config,
)


class ServiceContext:
    """Initializes, stores, and updates the asr, tts, and llm instances and other
    configurations for a connected client."""

    def __init__(self):
        self.config: Config = None
        self.system_config: SystemConfig = None
        self.character_config: CharacterConfig = None

        self.live2d_model: Live2dModel = None
        self.vrm_model: VRMModel | None = None
        self.asr_engine: ASRInterface = None
        self.tts_engine: TTSInterface = None
        self.agent_engine: AgentInterface = None
        # translate_engine can be none if translation is disabled
        self.vad_engine: VADInterface | None = None
        self.translate_engine: TranslateInterface | None = None

        self.mcp_server_registery: ServerRegistry | None = None
        self.tool_adapter: ToolAdapter | None = None
        self.tool_manager: ToolManager | None = None
        self.mcp_client: MCPClient | None = None
        self.tool_executor: ToolExecutor | None = None

        self.memory_manager: MemoryManager | None = None
        self.todo_manager: TodoManager | None = None

        # the system prompt is a combination of the persona prompt and live2d expression prompt
        self.system_prompt: str = None

        # Store the generated MCP prompt string (if MCP enabled)
        self.mcp_prompt: str = ""

        self.history_uid: str = ""  # Add history_uid field

        self.client_uid: str = None

        self.screen_monitor: ScreenMonitor = ScreenMonitor()
        self.idle_life_manager: IdleLifeManager | None = None
        self.last_proactive_response: str = ""

    @property
    def model(self) -> Live2dModel | VRMModel | None:
        """Return the active character model (Live2D or VRM)."""
        return self.vrm_model or self.live2d_model

    def __str__(self):
        return (
            f"ServiceContext:\n"
            f"  System Config: {'Loaded' if self.system_config else 'Not Loaded'}\n"
            f"    Details: {json.dumps(self.system_config.model_dump(), indent=6) if self.system_config else 'None'}\n"
            f"  Character Model: {self.model.model_name if self.model else 'Not Loaded'} (type: {self.model.model_type if self.model else '?'})\n"
            f"  ASR Engine: {type(self.asr_engine).__name__ if self.asr_engine else 'Not Loaded'}\n"
            f"    Config: {json.dumps(self.character_config.asr_config.model_dump(), indent=6) if self.character_config.asr_config else 'None'}\n"
            f"  TTS Engine: {type(self.tts_engine).__name__ if self.tts_engine else 'Not Loaded'}\n"
            f"    Config: {json.dumps(self.character_config.tts_config.model_dump(), indent=6) if self.character_config.tts_config else 'None'}\n"
            f"  LLM Engine: {type(self.agent_engine).__name__ if self.agent_engine else 'Not Loaded'}\n"
            f"    Agent Config: {json.dumps(self.character_config.agent_config.model_dump(), indent=6) if self.character_config.agent_config else 'None'}\n"
            f"  VAD Engine: {type(self.vad_engine).__name__ if self.vad_engine else 'Not Loaded'}\n"
            f"    Agent Config: {json.dumps(self.character_config.vad_config.model_dump(), indent=6) if self.character_config.vad_config else 'None'}\n"
            f"  System Prompt: {self.system_prompt or 'Not Set'}\n"
            f"  MCP Enabled: {'Yes' if self.mcp_client else 'No'}"
        )

    # ==== Initializers

    async def _init_mcp_components(self, use_mcpp, enabled_servers):
        """Initializes MCP components based on configuration, dynamically fetching tool info."""
        logger.debug(
            f"Initializing MCP components: use_mcpp={use_mcpp}, enabled_servers={enabled_servers}"
        )

        # Reset MCP components first
        self.mcp_server_registery = None
        self.tool_manager = None
        self.mcp_client = None
        self.tool_executor = None
        self.json_detector = None
        self.mcp_prompt = ""

        if use_mcpp and enabled_servers:
            # 1. Initialize ServerRegistry
            self.mcp_server_registery = ServerRegistry()
            logger.info("ServerRegistry initialized or referenced.")

            # Inject sudo password into desktop-controller server env
            sudo_pw = (
                self.config.system_config.sudo_password
                if self.config and self.config.system_config
                else None
            )
            if sudo_pw:
                dc_server = self.mcp_server_registery.get_server("desktop-controller")
                if dc_server:
                    if dc_server.env is None:
                        dc_server.env = {}
                    dc_server.env["SUDO_PASSWORD"] = sudo_pw
                    logger.info(
                        "Injected SUDO_PASSWORD into desktop-controller server env."
                    )
                else:
                    logger.warning(
                        "desktop-controller server not found in registry, cannot inject SUDO_PASSWORD."
                    )

            # 2. Use ToolAdapter to get the MCP prompt and tools
            if not self.tool_adapter:
                logger.error(
                    "ToolAdapter not initialized before calling _init_mcp_components."
                )
                self.mcp_prompt = "[Error: ToolAdapter not initialized]"
                return  # Exit if ToolAdapter is mandatory and not initialized

            try:
                (
                    mcp_prompt_string,
                    openai_tools,
                    claude_tools,
                ) = await self.tool_adapter.get_tools(enabled_servers)
                # Store the generated prompt string
                self.mcp_prompt = mcp_prompt_string
                logger.info(
                    f"Dynamically generated MCP prompt string (length: {len(self.mcp_prompt)})."
                )
                logger.info(
                    f"Dynamically formatted tools - OpenAI: {len(openai_tools)}, Claude: {len(claude_tools)}."
                )

                # 3. Initialize ToolManager with the fetched formatted tools

                _, raw_tools_dict = await self.tool_adapter.get_server_and_tool_info(
                    enabled_servers
                )
                self.tool_manager = ToolManager(
                    formatted_tools_openai=openai_tools,
                    formatted_tools_claude=claude_tools,
                    initial_tools_dict=raw_tools_dict,
                )
                logger.info("ToolManager initialized with dynamically fetched tools.")

            except Exception as e:
                logger.error(
                    f"Failed during dynamic MCP tool construction: {e}", exc_info=True
                )
                # Ensure dependent components are not created if construction fails
                self.tool_manager = None
                self.mcp_prompt = "[Error constructing MCP tools/prompt]"

            # 4. Initialize MCPClient
            if self.mcp_server_registery:
                self.mcp_client = MCPClient(self.mcp_server_registery, self.client_uid)
                logger.info("MCPClient initialized for this session.")
            else:
                logger.error(
                    "MCP enabled but ServerRegistry not available. MCPClient not created."
                )
                self.mcp_client = None  # Ensure it's None

            # 5. Initialize ToolExecutor
            if self.mcp_client and self.tool_manager:
                sudo_pw = (
                    self.config.system_config.sudo_password
                    if self.config and self.config.system_config
                    else ""
                )
                self.tool_executor = ToolExecutor(
                    self.mcp_client, self.tool_manager, sudo_password=sudo_pw
                )
                logger.info("ToolExecutor initialized for this session.")
            else:
                logger.warning(
                    "MCPClient or ToolManager not available. ToolExecutor not created."
                )
                self.tool_executor = None  # Ensure it's None

            logger.info("StreamJSONDetector initialized for this session.")

        elif use_mcpp and not enabled_servers:
            logger.warning(
                "use_mcpp is True, but mcp_enabled_servers list is empty. MCP components not initialized."
            )
        else:
            logger.debug(
                "MCP components not initialized (use_mcpp is False or no enabled servers)."
            )

    async def close(self):
        """Clean up resources, especially the MCPClient."""
        logger.info("Closing ServiceContext resources...")
        if self.mcp_client:
            logger.info(f"Closing MCPClient for context instance {id(self)}...")
            await self.mcp_client.aclose()
            self.mcp_client = None
        if self.agent_engine and hasattr(self.agent_engine, "close"):
            await self.agent_engine.close()  # Ensure agent resources are also closed
        logger.info("ServiceContext closed.")

    async def load_cache(
        self,
        config: Config,
        system_config: SystemConfig,
        character_config: CharacterConfig,
        live2d_model: Live2dModel,
        asr_engine: ASRInterface,
        tts_engine: TTSInterface,
        vad_engine: VADInterface,
        agent_engine: AgentInterface,
        translate_engine: TranslateInterface | None,
        vrm_model: VRMModel | None = None,
        mcp_server_registery: ServerRegistry | None = None,
        tool_adapter: ToolAdapter | None = None,
        client_uid: str = None,
    ) -> None:
        """
        Load the ServiceContext with the reference of the provided instances.
        Pass by reference so no reinitialization will be done.
        """
        if not character_config:
            raise ValueError("character_config cannot be None")
        if not system_config:
            raise ValueError("system_config cannot be None")

        self.config = config
        self.system_config = system_config
        self.character_config = character_config
        self.live2d_model = live2d_model
        self.vrm_model = vrm_model
        self.asr_engine = asr_engine
        self.tts_engine = tts_engine
        self.vad_engine = vad_engine
        self.agent_engine = agent_engine
        self.translate_engine = translate_engine
        # Load potentially shared components by reference
        self.mcp_server_registery = mcp_server_registery
        self.tool_adapter = tool_adapter
        self.client_uid = client_uid

        # Initialize session-specific MCP components
        await self._init_mcp_components(
            self.character_config.agent_config.agent_settings.basic_memory_agent.use_mcpp,
            self.character_config.agent_config.agent_settings.basic_memory_agent.mcp_enabled_servers,
        )

        # Initialize session-specific MemoryManager and wire it to the agent
        self.memory_manager = MemoryManager()
        agent_config = self.character_config.agent_config
        memory_llm = self._create_memory_llm(agent_config)
        if memory_llm is None and hasattr(self.agent_engine, "_llm") and self.agent_engine._llm:
            memory_llm = self.agent_engine._llm
        if memory_llm:
            self.memory_manager.set_llm(memory_llm)
            logger.debug("MemoryManager initialized with LLM for session")
        else:
            logger.warning(
                "Agent engine does not have _llm attribute, MemoryManager will work without LLM extraction"
            )

        if hasattr(self.agent_engine, "set_memory_manager"):
            self.agent_engine.set_memory_manager(self.memory_manager)
            logger.debug("MemoryManager wired to agent engine")
        else:
            logger.warning("Agent engine does not have set_memory_manager method")

        self.todo_manager = TodoManager()
        if hasattr(self.agent_engine, "set_todo_manager"):
            self.agent_engine.set_todo_manager(self.todo_manager)
            logger.debug("TodoManager wired to agent engine")
        logger.debug("TodoManager initialized.")

        idle_config = self.system_config.idle_life if self.system_config else None
        self.idle_life_manager = IdleLifeManager(
            config=idle_config,
            character_name=character_config.character_name,
            personality=character_config.persona_prompt or "",
            subconscious_llm=self._create_subconscious_llm(agent_config),
        ) if idle_config else None
        if self.idle_life_manager:
            logger.info(f"IdleLifeManager initialized (enabled={idle_config.enabled})")
        else:
            logger.debug("IdleLifeManager not initialized (no idle_life config)")

        logger.debug(f"Loaded service context with cache: {character_config}")

    async def load_from_config(self, config: Config) -> None:
        """
        Load the ServiceContext with the config.
        Reinitialize the instances if the config is different.

        Parameters:
        - config (Dict): The configuration dictionary.
        """
        if not self.config:
            self.config = config

        if not self.system_config:
            self.system_config = config.system_config

        if not self.character_config:
            self.character_config = config.character_config

        # update all sub-configs

        # init character model (Live2D or VRM) from config
        model_type = getattr(config.character_config, "model_type", "live2d")
        self.init_model(config.character_config.live2d_model_name, model_type)

        # init asr from character config
        self.init_asr(config.character_config.asr_config)

        # init tts from character config
        self.init_tts(config.character_config.tts_config)

        # init vad from character config
        self.init_vad(config.character_config.vad_config)

        # Initialize shared ToolAdapter if it doesn't exist yet
        if (
            not self.tool_adapter
            and config.character_config.agent_config.agent_settings.basic_memory_agent.use_mcpp
        ):
            if not self.mcp_server_registery:
                logger.info(
                    "Initializing shared ServerRegistry within load_from_config."
                )
                self.mcp_server_registery = ServerRegistry()
            logger.info("Initializing shared ToolAdapter within load_from_config.")
            self.tool_adapter = ToolAdapter(server_registery=self.mcp_server_registery)

        # Initialize MCP Components before initializing Agent
        await self._init_mcp_components(
            config.character_config.agent_config.agent_settings.basic_memory_agent.use_mcpp,
            config.character_config.agent_config.agent_settings.basic_memory_agent.mcp_enabled_servers,
        )

        # init agent from character config
        await self.init_agent(
            config.character_config.agent_config,
            config.character_config.persona_prompt,
        )

        self.init_translate(
            config.character_config.tts_preprocessor_config.translator_config
        )

        # store typed config references
        self.config = config
        self.system_config = config.system_config or self.system_config
        self.character_config = config.character_config

    def init_model(self, model_name: str, model_type: str = "live2d") -> None:
        """Initialize character model (Live2D or VRM)."""
        logger.info(f"Initializing model: {model_name} (type: {model_type})")
        try:
            if model_type == "vrm":
                from .character_model import VRMModel

                self.vrm_model = VRMModel(model_name)
                self.live2d_model = None
                logger.info(f"VRM model '{model_name}' loaded successfully.")
            else:
                self.live2d_model = Live2dModel(model_name)
                self.vrm_model = None
                logger.info(f"Live2D model '{model_name}' loaded successfully.")
            self.character_config.live2d_model_name = model_name
            self.character_config.model_type = model_type
        except Exception as e:
            logger.critical(f"Error initializing model '{model_name}': {e}")
            logger.critical("Try to proceed without character model...")
            # Clear both models to prevent stale Live2D fallback
            self.vrm_model = None
            self.live2d_model = None

    def init_live2d(self, live2d_model_name: str) -> None:
        """Backward-compatible wrapper that defaults to Live2D type."""
        self.init_model(live2d_model_name, model_type="live2d")

    def init_asr(self, asr_config: ASRConfig) -> None:
        if asr_config.asr_model is None:
            logger.info("ASR is disabled.")
            self.asr_engine = None
            self.character_config.asr_config = asr_config
            return
        if not self.asr_engine or (self.character_config.asr_config != asr_config):
            logger.info(f"Initializing ASR: {asr_config.asr_model}")
            self.asr_engine = ASRFactory.get_asr_system(
                asr_config.asr_model,
                **getattr(asr_config, asr_config.asr_model).model_dump(),
            )
            # saving config should be done after successful initialization
            self.character_config.asr_config = asr_config
        else:
            logger.info("ASR already initialized with the same config.")

    def init_tts(self, tts_config: TTSConfig) -> None:
        if not self.tts_engine or (self.character_config.tts_config != tts_config):
            logger.info(f"Initializing TTS: {tts_config.tts_model}")
            self.tts_engine = TTSFactory.get_tts_engine(
                tts_config.tts_model,
                **getattr(tts_config, tts_config.tts_model.lower()).model_dump(),
            )
            # saving config should be done after successful initialization
            self.character_config.tts_config = tts_config
        else:
            logger.info("TTS already initialized with the same config.")

    def init_vad(self, vad_config: VADConfig) -> None:
        if vad_config.vad_model is None:
            logger.info("VAD is disabled.")
            self.vad_engine = None
            return

        if not self.vad_engine or (self.character_config.vad_config != vad_config):
            logger.info(f"Initializing VAD: {vad_config.vad_model}")
            self.vad_engine = VADFactory.get_vad_engine(
                vad_config.vad_model,
                **getattr(vad_config, vad_config.vad_model.lower()).model_dump(),
            )
            # saving config should be done after successful initialization
            self.character_config.vad_config = vad_config
        else:
            logger.info("VAD already initialized with the same config.")

    def _create_memory_llm(self, agent_config: AgentConfig):
        """Create a separate LLM for memory extraction if configured."""
        basic_memory = agent_config.agent_settings.basic_memory_agent
        if basic_memory and basic_memory.memory_llm_provider:
            provider = basic_memory.memory_llm_provider
            llm_configs = agent_config.llm_configs.model_dump()
            provider_config = llm_configs.get(provider, {})
            if provider_config:
                provider_config.pop("interrupt_method", None)
                logger.info(f"Creating separate LLM for memory extraction: {provider}")
                return StatelessLLMFactory.create_llm(
                    llm_provider=provider,
                    **provider_config,
                )
            else:
                logger.warning(f"memory_llm_provider '{provider}' not found in llm_configs")
        return None

    def _create_subconscious_llm(self, agent_config: AgentConfig):
        """Create a lightweight LLM for idle subconscious generation.

        Uses the same groq_llm provider as memory extraction, but with
        lower max_tokens since subconscious thoughts are short (1-2 sentences).
        """
        basic_memory = agent_config.agent_settings.basic_memory_agent
        if basic_memory and basic_memory.memory_llm_provider:
            provider = basic_memory.memory_llm_provider
            llm_configs = agent_config.llm_configs.model_dump()
            provider_config = llm_configs.get(provider, {})
            if provider_config:
                provider_config.pop("interrupt_method", None)
                provider_config["max_tokens"] = 128
                logger.info(f"Creating subconscious LLM: {provider}")
                return StatelessLLMFactory.create_llm(
                    llm_provider=provider,
                    **provider_config,
                )
        return None

    async def init_agent(self, agent_config: AgentConfig, persona_prompt: str, force: bool = False) -> None:
        """Initialize or update the LLM engine based on agent configuration."""
        logger.info(f"Initializing Agent: {agent_config.conversation_agent_choice}")

        current_mode = getattr(self, '_ai_mode', self.system_config.ai_mode)

        if (
            not force
            and self.agent_engine is not None
            and agent_config == self.character_config.agent_config
            and persona_prompt == self.character_config.persona_prompt
            and getattr(self, '_last_init_mode', None) == current_mode
        ):
            logger.debug("Agent already initialized with the same config and mode.")
            return

        self._last_init_mode = current_mode
        mode = current_mode
        is_split = self._is_split_agent_mode()

        system_prompt = await self.construct_system_prompt(persona_prompt)

        # Build tool system prompt for dual or split agent mode
        tool_agent_system = ""
        if (self._is_dual_agent_mode() or is_split) and not self._is_hybrid_agent_mode():
            tool_agent_system = await self.build_tool_agent_system(split_mode=is_split)
            mode_label = "Split-agent" if is_split else "Dual-agent"
            logger.info(
                f"{mode_label}: Persona prompt={len(system_prompt)} chars, "
                f"ToolAgent prompt={len(tool_agent_system)} chars"
            )

        # Filter tools based on ai_mode
        tm = self.tool_manager
        te = self.tool_executor
        mcp_str = self.mcp_prompt

        if mode == "lite":
            tm = None
            te = None
            mcp_str = ""
            logger.info("Lite mode: tools disabled")

        elif mode == "minimal":
            if tm:
                allowed = {"web_search", "search_youtube", "play_youtube", "open_url"}
                tm.filter_tool_names(allowed)
            mcp_str = ""
            logger.info(f"Minimal mode: tools limited to {tm.get_formatted_tools('OpenAI') if tm else 'none'}")

        # Pass avatar to agent factory
        avatar = self.character_config.avatar or ""

        try:
            self.agent_engine = AgentFactory.create_agent(
                conversation_agent_choice=agent_config.conversation_agent_choice,
                agent_settings=agent_config.agent_settings.model_dump(),
                llm_configs=agent_config.llm_configs.model_dump(),
                system_prompt=system_prompt,
                live2d_model=self.model,
                tts_preprocessor_config=self.character_config.tts_preprocessor_config,
                character_avatar=avatar,
                system_config=self.system_config.model_dump(),
                tool_manager=tm,
                tool_executor=te,
                mcp_prompt_string=mcp_str,
                tool_agent_system=tool_agent_system,
            )

            # Preserve existing MemoryManager across re-initializations
            if self.memory_manager is None:
                self.memory_manager = MemoryManager()
            memory_llm = self._create_memory_llm(agent_config)
            if memory_llm is None and hasattr(self.agent_engine, "_llm"):
                memory_llm = self.agent_engine._llm
            if memory_llm:
                self.memory_manager.set_llm(memory_llm)
            self.agent_engine.set_memory_manager(self.memory_manager)

            # Preserve existing TodoManager across re-initializations
            if self.todo_manager is None:
                self.todo_manager = TodoManager()
            if hasattr(self.agent_engine, "set_todo_manager"):
                self.agent_engine.set_todo_manager(self.todo_manager)
                logger.debug("TodoManager wired to agent engine")
            logger.debug("TodoManager initialized.")

            logger.debug(f"Agent choice: {agent_config.conversation_agent_choice}")
            logger.debug(f"System prompt: {system_prompt}")

            # Save the current configuration
            self.character_config.agent_config = agent_config
            self.system_prompt = system_prompt

        except Exception as e:
            logger.error(f"Failed to initialize agent: {e}")
            raise

    def init_translate(self, translator_config: TranslatorConfig) -> None:
        """Initialize or update the translation engine based on the configuration."""

        if not translator_config.translate_audio:
            logger.debug("Translation is disabled.")
            return

        if (
            not self.translate_engine
            or self.character_config.tts_preprocessor_config.translator_config
            != translator_config
        ):
            logger.info(
                f"Initializing Translator: {translator_config.translate_provider}"
            )
            self.translate_engine = TranslateFactory.get_translator(
                translator_config.translate_provider,
                getattr(
                    translator_config, translator_config.translate_provider
                ).model_dump(),
            )
            self.character_config.tts_preprocessor_config.translator_config = (
                translator_config
            )
        else:
            logger.info("Translation already initialized with the same config.")

    # ==== utils

    def _is_dual_agent_mode(self) -> bool:
        """Check if dual-agent mode is enabled (separate LLM for tools)."""
        try:
            basic_memory = (
                self.character_config
                .agent_config
                .agent_settings
                .basic_memory_agent
            )
            return bool(
                basic_memory
                and basic_memory.tool_llm_provider
                and basic_memory.use_mcpp
            )
        except (AttributeError, TypeError):
            return False

    def _is_hybrid_agent_mode(self) -> bool:
        """Check if hybrid mode is enabled (Gemini simple tools + Groq specialists)."""
        try:
            basic_memory = (
                self.character_config
                .agent_config
                .agent_settings
                .basic_memory_agent
            )
            return bool(
                basic_memory
                and basic_memory.subagent_mode == "hybrid"
                and basic_memory.use_mcpp
            )
        except (AttributeError, TypeError):
            return False

    def _is_split_agent_mode(self) -> bool:
        """Check if split-agent mode is enabled (one model, two agents)."""
        try:
            basic_memory = (
                self.character_config
                .agent_config
                .agent_settings
                .basic_memory_agent
            )
            return bool(
                basic_memory
                and basic_memory.subagent_mode == "split"
                and basic_memory.subagent
                and basic_memory.use_mcpp
            )
        except (AttributeError, TypeError):
            return False

    @property
    def ai_mode(self) -> str:
        return getattr(self, '_ai_mode', self.system_config.ai_mode)

    def set_ai_mode(self, mode: str) -> None:
        if mode not in ("lite", "minimal", "full_agent"):
            logger.warning(f"Invalid ai_mode: {mode}, ignoring")
            return
        self._ai_mode = mode
        logger.info(f"AI mode set to: {mode}")

    async def reinit_agent_for_mode(self) -> None:
        """Re-initialize the agent after switching ai_mode at runtime."""
        mode = self.ai_mode
        logger.info(f"Re-initializing agent for mode: {mode}")

        # Restore full tools if switching from filtered mode
        if self.tool_manager:
            self.tool_manager.restore_tools()

        persona_prompt = self.character_config.persona_prompt
        agent_config = self.character_config.agent_config
        await self.init_agent(agent_config, persona_prompt)

    async def construct_system_prompt(self, persona_prompt: str) -> str:
        """
        Build the persona system prompt based on ai_mode.

        Modes:
        - lite: persona + time + emotion ONLY. No tool prompts.
        - minimal: persona + time + emotion + concise_style. Light tools.
        - full_agent: all prompts (current behavior).
        """
        mode = self.ai_mode
        logger.debug(f"construct_system_prompt: ai_mode={mode}")

        # Inject current time context
        from datetime import datetime
        from zoneinfo import ZoneInfo
        try:
            tz = ZoneInfo("Asia/Jakarta")
        except Exception:
            tz = ZoneInfo("UTC")
        now = datetime.now(tz)
        time_context = (
            f"\n\n[SYSTEM: Waktu sekarang = {now.strftime('%A, %d %B %Y, %H:%M')} WIB "
            f"({now.strftime('%Y-%m-%dT%H:%M:%S%z')})]"
        )
        persona_prompt += time_context

        skip_tool_prompts = self._is_dual_agent_mode() or self._is_split_agent_mode() or self._is_hybrid_agent_mode()

        tool_prompt_skip_names = (
            "tool_guidance_prompt",
            "agentic_capabilities_prompt",
            "agentic_reflection_prompt",
            "mcp_prompt",
        )

        for prompt_name, prompt_file in self.system_config.tool_prompts.items():
            # Skip tool-related prompts in multi-agent mode
            if skip_tool_prompts and prompt_name in tool_prompt_skip_names:
                continue

            # Skip group/proactive — they are not personality prompts
            if prompt_name in ("group_conversation_prompt", "proactive_speak_prompt"):
                continue

            # Lite mode: ONLY include live2d_expression_prompt (emotion)
            if mode == "lite":
                if prompt_name not in ("live2d_expression_prompt",):
                    continue

            # Minimal mode: include emotion + concise_style, skip heavy tool prompts
            if mode == "minimal":
                if prompt_name in tool_prompt_skip_names:
                    continue
                if prompt_name == "grid_overlay_note":
                    continue

            prompt_content = prompt_loader.load_util(prompt_file)

            if prompt_name == "live2d_expression_prompt":
                active_model = self.model
                if active_model:
                    prompt_content = prompt_content.replace(
                        "[<insert_emomap_keys>]", active_model.emo_str
                    )

            if prompt_name == "mcp_prompt":
                continue

            persona_prompt += prompt_content

        logger.debug(
            f"Persona system prompt length = {len(persona_prompt)} chars"
        )

        # Grid overlay note: skip in lite/minimal
        if mode == "full_agent":
            grid_note = (
                "\n\n[SYSTEM: Kamu MUNGKIN melihat grid overlay (A1, E4, dll) pada gambar layar. "
                "Grid itu HANYA untuk kamu menentukan posisi klik/ketik. "
                "JANGAN pernah menyebutkan koordinat grid (A1, E4, D3, dll) ke user — "
                "user TIDAK bisa melihat grid tersebut.]"
            )
            persona_prompt += grid_note

        return persona_prompt

    async def build_tool_agent_system(self, split_mode: bool = False) -> str:
        """Build system prompt for the ToolAgent.

        Collects tool-related prompts into a single system prompt.
        Returns empty string for lite/minimal modes.

        In split mode, only the essential tool prompt + MCP guide are included
        (skipping persona-heavy guidance/capabilities — those stay with persona).

        Args:
            split_mode: If True, build minimal prompt (tool + MCP only).

        Returns:
            str: The tool agent system prompt.
        """
        mode = self.ai_mode

        # Lite/minimal: no tool agent
        if mode in ("lite", "minimal"):
            logger.debug(f"build_tool_agent_system: {mode} mode, returning empty")
            return ""

        tool_system = ""

        # Load the tool agent prompt template
        try:
            tool_system = prompt_loader.load_util("tool_agent_prompt")
        except (FileNotFoundError, Exception) as e:
            logger.warning(f"Could not load tool_agent_prompt: {e}")
            tool_system = "Kamu adalah asisten tool. Panggil tool sesuai permintaan."

        # In split mode, skip persona-heavy prompts
        tool_prompt_names = ("tool_guidance_prompt", "agentic_capabilities_prompt", "agentic_reflection_prompt", "mcp_prompt")

        for prompt_name, prompt_file in self.system_config.tool_prompts.items():
            if prompt_name not in tool_prompt_names:
                continue
            if split_mode and prompt_name in (
                "tool_guidance_prompt",
                "agentic_capabilities_prompt",
                "agentic_reflection_prompt",
            ):
                logger.debug(
                    f"Split mode: skipping '{prompt_name}' from tool agent prompt"
                )
                continue
            try:
                content = prompt_loader.load_util(prompt_file)
                tool_system += f"\n\n{content}"
            except Exception as e:
                logger.warning(f"Could not load tool prompt '{prompt_name}': {e}")

        # Append MCP prompt string
        if self.mcp_prompt:
            tool_system += f"\n\n{self.mcp_prompt}"

        logger.debug(
            f"ToolAgent system prompt length = {len(tool_system)} chars"
        )
        return tool_system

    async def handle_config_switch(
        self,
        websocket: WebSocket,
        config_file_name: str,
    ) -> None:
        """
        Handle the configuration switch request.
        Change the configuration to a new config and notify the client.

        Parameters:
        - websocket (WebSocket): The WebSocket connection.
        - config_file_name (str): The name of the configuration file.
        """
        try:
            new_character_config_data = None

            if config_file_name == "conf.yaml":
                # Load base config
                new_character_config_data = read_yaml("conf.yaml").get(
                    "character_config"
                )
            else:
                # Load alternative config and merge with base config
                characters_dir = self.system_config.config_alts_dir
                file_path = os.path.normpath(
                    os.path.join(characters_dir, config_file_name)
                )
                if not file_path.startswith(characters_dir):
                    raise ValueError("Invalid configuration file path")

                alt_config_data = read_yaml(file_path).get("character_config")

                # Start with original config data and perform a deep merge
                new_character_config_data = deep_merge(
                    self.config.character_config.model_dump(), alt_config_data
                )

            if new_character_config_data:
                new_config = {
                    "system_config": self.system_config.model_dump(),
                    "character_config": new_character_config_data,
                }
                new_config = validate_config(new_config)
                await self.load_from_config(new_config)  # Await the async load
                logger.debug(f"New config: {self}")
                logger.debug(
                    f"New character config: {self.character_config.model_dump()}"
                )

                # Send responses to client
                active_model = self.model
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "set-model-and-conf",
                            "model_info": active_model.to_frontend_payload()
                            if active_model
                            else {},
                            "model_type": active_model.model_type
                            if active_model
                            else self.character_config.model_type,
                            "conf_name": self.character_config.conf_name,
                            "conf_uid": self.character_config.conf_uid,
                            "agent_config": self.get_agent_config_summary(),
                        }
                    )
                )

                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "config-switched",
                            "message": f"Switched to config: {config_file_name}",
                        }
                    )
                )

                logger.info(f"Configuration switched to {config_file_name}")
            else:
                raise ValueError(
                    f"Failed to load configuration from {config_file_name}"
                )

        except Exception as e:
            logger.error(f"Error switching configuration: {e}")
            logger.debug(self)
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "message": f"Error switching configuration: {str(e)}",
                    }
                )
            )
            raise e

    def get_agent_config_summary(self) -> dict:
        """Build agent config summary for the frontend (no API keys)."""
        agent_config = self.character_config.agent_config
        llm_configs = agent_config.llm_configs
        current_provider = agent_config.agent_settings.basic_memory_agent.llm_provider

        available_providers = []
        provider_models = {}

        for field_name in llm_configs.model_fields:
            provider = getattr(llm_configs, field_name)
            if provider is not None:
                available_providers.append(field_name)
                if hasattr(provider, "model"):
                    provider_models[field_name] = provider.model
                elif hasattr(provider, "model_path"):
                    provider_models[field_name] = provider.model_path

        current_model = provider_models.get(current_provider, "")

        return {
            "llm_provider": current_provider,
            "current_model": current_model,
            "available_providers": available_providers,
            "provider_models": provider_models,
        }


def deep_merge(dict1, dict2):
    """
    Recursively merges dict2 into dict1, prioritizing values from dict2.
    """
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result
