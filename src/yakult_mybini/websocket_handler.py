from typing import Dict, List, Optional, Callable, TypedDict
from fastapi import WebSocket, WebSocketDisconnect
import asyncio
import json
import re
from enum import Enum
import numpy as np
import httpx
from loguru import logger

from .service_context import ServiceContext
from .chat_group import (
    ChatGroupManager,
    handle_group_operation,
    handle_client_disconnect,
    broadcast_to_group,
)
from .message_handler import message_handler
from .utils.stream_audio import prepare_audio_payload
from .chat_history_manager import (
    create_new_history,
    get_history,
    delete_history,
    get_history_list,
)
from .config_manager.utils import (
    scan_config_alts_directory,
    scan_bg_directory,
    read_yaml,
    _auto_discover_vrm_models,
    save_config,
)
from .conversations.conversation_handler import (
    handle_conversation_trigger,
    handle_group_interrupt,
    handle_individual_interrupt,
)
from .mcpp.music_player_manager import music_player_manager
from .conversations.single_conversation import process_single_conversation
from .character_model import build_emotion_map_from_vrm_expressions


class MessageType(Enum):
    """Enum for WebSocket message types"""

    GROUP = ["add-client-to-group", "remove-client-from-group"]
    HISTORY = [
        "fetch-history-list",
        "fetch-and-set-history",
        "create-new-history",
        "delete-history",
    ]
    CONVERSATION = ["mic-audio-end", "text-input", "ai-speak-signal"]
    CONFIG = ["fetch-configs", "switch-config"]
    CONTROL = ["interrupt-signal", "audio-play-start"]
    DATA = ["mic-audio-data"]


class WSMessage(TypedDict, total=False):
    """Type definition for WebSocket messages"""

    type: str
    action: Optional[str]
    text: Optional[str]
    audio: Optional[List[float]]
    images: Optional[List[str]]
    history_uid: Optional[str]
    file: Optional[str]
    display_text: Optional[dict]


class WebSocketHandler:
    """Handles WebSocket connections and message routing"""

    def __init__(self, default_context_cache: ServiceContext):
        """Initialize the WebSocket handler with default context"""
        self.client_connections: Dict[str, WebSocket] = {}
        self.client_contexts: Dict[str, ServiceContext] = {}
        self.client_platforms: Dict[str, str] = {}
        self.chat_group_manager = ChatGroupManager()
        self.current_conversation_tasks: Dict[str, Optional[asyncio.Task]] = {}
        self.default_context_cache = default_context_cache
        self.received_data_buffers: Dict[str, np.ndarray] = {}

        # Message handlers mapping
        self._message_handlers = self._init_message_handlers()

    def _init_message_handlers(self) -> Dict[str, Callable]:
        """Initialize message type to handler mapping"""
        return {
            "add-client-to-group": self._handle_group_operation,
            "remove-client-from-group": self._handle_group_operation,
            "request-group-info": self._handle_group_info,
            "fetch-history-list": self._handle_history_list_request,
            "fetch-and-set-history": self._handle_fetch_history,
            "create-new-history": self._handle_create_history,
            "delete-history": self._handle_delete_history,
            "interrupt-signal": self._handle_interrupt,
            "mic-audio-data": self._handle_audio_data,
            "mic-audio-end": self._handle_conversation_trigger,
            "raw-audio-data": self._handle_raw_audio_data,
            "text-input": self._handle_conversation_trigger,
            "ai-speak-signal": self._handle_conversation_trigger,
            "fetch-configs": self._handle_fetch_configs,
            "switch-config": self._handle_config_switch,
            "fetch-backgrounds": self._handle_fetch_backgrounds,
            "audio-play-start": self._handle_audio_play_start,
            "request-init-config": self._handle_init_config_request,
            "save-config": self._handle_save_config,
            "fetch-available-models": self._handle_fetch_available_models,
            "set-grid-spec": self._handle_set_grid_spec,
            "heartbeat": self._handle_heartbeat,
            "fetch-memories": self._handle_fetch_memories,
            "delete-memory": self._handle_delete_memory,
            "update-memory": self._handle_update_memory,
            "music-next": self._handle_music_next,
            "music-prev": self._handle_music_prev,
            "music-stop": self._handle_music_stop,
            "music-play-pause": self._handle_music_play_pause,
            "music-feedback": self._handle_music_feedback,
            "fetch-todos": self._handle_fetch_todos,
            "add-todo": self._handle_add_todo,
            "delete-todo": self._handle_delete_todo,
            "update-todo": self._handle_update_todo,
            "restart-backend": self._handle_restart_backend,
            "discover-vrm-expressions": self._handle_discover_vrm_expressions,
            "set-ai-mode": self._handle_set_ai_mode,
        }

    async def handle_new_connection(
        self, websocket: WebSocket, client_uid: str, platform: str = "unknown"
    ) -> None:
        """
        Handle new WebSocket connection setup

        Args:
            websocket: The WebSocket connection
            client_uid: Unique identifier for the client
            platform: Client platform (e.g. "web", "electron")

        Raises:
            Exception: If initialization fails
        """
        try:
            session_service_context = await self._init_service_context(client_uid)

            # Set the agent's conf_uid for memory management
            if hasattr(session_service_context.agent_engine, "set_conf_uid"):
                session_service_context.agent_engine.set_conf_uid(
                    session_service_context.character_config.conf_uid
                )
                logger.debug(
                    f"Set agent conf_uid to {session_service_context.character_config.conf_uid}"
                )

            await self._store_client_data(
                websocket, client_uid, session_service_context, platform
            )

            await self._send_initial_messages(
                websocket, client_uid, session_service_context
            )

            logger.info(f"Connection established for client {client_uid}")

        except Exception as e:
            logger.error(
                f"Failed to initialize connection for client {client_uid}: {e}"
            )
            await self._cleanup_failed_connection(client_uid)
            raise

    async def _store_client_data(
        self,
        websocket: WebSocket,
        client_uid: str,
        session_service_context: ServiceContext,
        platform: str = "unknown",
    ):
        """Store client data and initialize group status"""
        self.client_connections[client_uid] = websocket
        self.client_contexts[client_uid] = session_service_context
        self.client_platforms[client_uid] = platform
        self.received_data_buffers[client_uid] = np.array([])

        self.chat_group_manager.client_group_map[client_uid] = ""
        await self.send_group_update(websocket, client_uid)

        asyncio.create_task(self._reminder_check_loop(client_uid))
        asyncio.create_task(self._idle_life_loop(client_uid))

        if platform == "web":
            await self._notify_electron_clients_hide_pet()

    async def _notify_electron_clients_hide_pet(self) -> None:
        """Send hide-pet signal to all Electron desktop clients."""
        for uid, ws in self.client_connections.items():
            if self.client_platforms.get(uid) == "electron":
                try:
                    await ws.send_text(json.dumps({"type": "hide-pet"}))
                except Exception as e:
                    logger.warning(f"Failed to send hide-pet to client {uid}: {e}")

    async def _send_initial_messages(
        self,
        websocket: WebSocket,
        client_uid: str,
        session_service_context: ServiceContext,
    ):
        """Send initial connection messages to the client"""
        await websocket.send_text(
            json.dumps({"type": "full-text", "text": "Connection established"})
        )

        active_model = session_service_context.model
        await websocket.send_text(
            json.dumps(
                {
                    "type": "set-model-and-conf",
                    "model_info": active_model.model_info if active_model else {},
                    "model_type": active_model.model_type if active_model else "live2d",
                    "conf_name": session_service_context.character_config.conf_name,
                    "conf_uid": session_service_context.character_config.conf_uid,
                    "client_uid": client_uid,
                    "agent_config": self._build_agent_config_data(
                        session_service_context
                    ),
                }
            )
        )

        # Send initial group status
        await self.send_group_update(websocket, client_uid)

    async def _init_service_context(self, client_uid: str) -> ServiceContext:
        """Initialize service context for a new session by cloning the default context"""
        session_service_context = ServiceContext()
        await session_service_context.load_cache(
            config=self.default_context_cache.config.model_copy(deep=True),
            system_config=self.default_context_cache.system_config.model_copy(
                deep=True
            ),
            character_config=self.default_context_cache.character_config.model_copy(
                deep=True
            ),
            live2d_model=self.default_context_cache.live2d_model,
            vrm_model=self.default_context_cache.vrm_model,
            asr_engine=self.default_context_cache.asr_engine,
            tts_engine=self.default_context_cache.tts_engine,
            vad_engine=self.default_context_cache.vad_engine,
            agent_engine=self.default_context_cache.agent_engine,
            translate_engine=self.default_context_cache.translate_engine,
            mcp_server_registery=self.default_context_cache.mcp_server_registery,
            tool_adapter=self.default_context_cache.tool_adapter,
            client_uid=client_uid,
        )
        return session_service_context

    async def handle_websocket_communication(
        self, websocket: WebSocket, client_uid: str
    ) -> None:
        """
        Handle ongoing WebSocket communication

        Args:
            websocket: The WebSocket connection
            client_uid: Unique identifier for the client
        """
        try:
            while True:
                try:
                    data = await websocket.receive_json()
                    message_handler.handle_message(client_uid, data)
                    await self._route_message(websocket, client_uid, data)
                except WebSocketDisconnect:
                    raise
                except json.JSONDecodeError:
                    logger.error("Invalid JSON received")
                    continue
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    await websocket.send_text(
                        json.dumps({"type": "error", "message": str(e)})
                    )
                    continue

        except WebSocketDisconnect:
            logger.info(f"Client {client_uid} disconnected")
            raise
        except Exception as e:
            logger.error(f"Fatal error in WebSocket communication: {e}")
            raise

    async def _route_message(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """
        Route incoming message to appropriate handler

        Args:
            websocket: The WebSocket connection
            client_uid: Client identifier
            data: Message data
        """
        msg_type = data.get("type")
        if not msg_type:
            logger.warning("Message received without type")
            return

        handler = self._message_handlers.get(msg_type)
        if handler:
            await handler(websocket, client_uid, data)
        else:
            if msg_type != "frontend-playback-complete":
                logger.warning(f"Unknown message type: {msg_type}")

    async def _handle_group_operation(
        self, websocket: WebSocket, client_uid: str, data: dict
    ) -> None:
        """Handle group-related operations"""
        operation = data.get("type")
        target_uid = data.get(
            "invitee_uid" if operation == "add-client-to-group" else "target_uid"
        )

        await handle_group_operation(
            operation=operation,
            client_uid=client_uid,
            target_uid=target_uid,
            chat_group_manager=self.chat_group_manager,
            client_connections=self.client_connections,
            send_group_update=self.send_group_update,
        )

    async def handle_disconnect(self, client_uid: str) -> None:
        """Handle client disconnection"""
        group = self.chat_group_manager.get_client_group(client_uid)
        if group:
            await handle_group_interrupt(
                group_id=group.group_id,
                heard_response="",
                current_conversation_tasks=self.current_conversation_tasks,
                chat_group_manager=self.chat_group_manager,
                client_contexts=self.client_contexts,
                broadcast_to_group=self.broadcast_to_group,
            )

        await handle_client_disconnect(
            client_uid=client_uid,
            chat_group_manager=self.chat_group_manager,
            client_connections=self.client_connections,
            send_group_update=self.send_group_update,
        )

        # Clean up other client data
        self.client_connections.pop(client_uid, None)
        self.client_contexts.pop(client_uid, None)
        self.client_platforms.pop(client_uid, None)
        self.received_data_buffers.pop(client_uid, None)
        if client_uid in self.current_conversation_tasks:
            task = self.current_conversation_tasks[client_uid]
            if task and not task.done():
                task.cancel()
            self.current_conversation_tasks.pop(client_uid, None)

        # Call context close to clean up resources (e.g., MCPClient)
        context = self.client_contexts.get(client_uid)
        if context:
            await context.close()

        logger.info(f"Client {client_uid} disconnected")
        message_handler.cleanup_client(client_uid)

    async def _cleanup_failed_connection(self, client_uid: str) -> None:
        """Clean up failed connection data"""
        self.client_connections.pop(client_uid, None)
        self.client_contexts.pop(client_uid, None)
        self.received_data_buffers.pop(client_uid, None)
        self.chat_group_manager.client_group_map.pop(client_uid, None)

        if client_uid in self.current_conversation_tasks:
            task = self.current_conversation_tasks[client_uid]
            if task and not task.done():
                task.cancel()
            self.current_conversation_tasks.pop(client_uid, None)

        message_handler.cleanup_client(client_uid)

    async def broadcast_to_group(
        self, group_members: list[str], message: dict, exclude_uid: str = None
    ) -> None:
        """Broadcasts a message to group members"""
        await broadcast_to_group(
            group_members=group_members,
            message=message,
            client_connections=self.client_connections,
            exclude_uid=exclude_uid,
        )

    async def send_group_update(self, websocket: WebSocket, client_uid: str):
        """Sends group information to a client"""
        group = self.chat_group_manager.get_client_group(client_uid)
        if group:
            current_members = self.chat_group_manager.get_group_members(client_uid)
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "group-update",
                        "members": current_members,
                        "is_owner": group.owner_uid == client_uid,
                    }
                )
            )
        else:
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "group-update",
                        "members": [],
                        "is_owner": False,
                    }
                )
            )

    async def _handle_interrupt(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle conversation interruption"""
        heard_response = data.get("text", "")
        context = self.client_contexts[client_uid]
        group = self.chat_group_manager.get_client_group(client_uid)

        if group and len(group.members) > 1:
            await handle_group_interrupt(
                group_id=group.group_id,
                heard_response=heard_response,
                current_conversation_tasks=self.current_conversation_tasks,
                chat_group_manager=self.chat_group_manager,
                client_contexts=self.client_contexts,
                broadcast_to_group=self.broadcast_to_group,
            )
        else:
            await handle_individual_interrupt(
                client_uid=client_uid,
                current_conversation_tasks=self.current_conversation_tasks,
                context=context,
                heard_response=heard_response,
            )

    async def _handle_history_list_request(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle request for chat history list"""
        context = self.client_contexts[client_uid]
        histories = get_history_list(context.character_config.conf_uid)
        await websocket.send_text(
            json.dumps({"type": "history-list", "histories": histories})
        )

    async def _handle_fetch_history(
        self, websocket: WebSocket, client_uid: str, data: dict
    ):
        """Handle fetching and setting specific chat history"""
        history_uid = data.get("history_uid")
        if not history_uid:
            return

        context = self.client_contexts[client_uid]
        # Update history_uid in service context
        context.history_uid = history_uid
        context.agent_engine.set_memory_from_history(
            conf_uid=context.character_config.conf_uid,
            history_uid=history_uid,
        )

        messages = [
            msg
            for msg in get_history(
                context.character_config.conf_uid,
                history_uid,
            )
            if msg["role"] != "system"
        ]
        await websocket.send_text(
            json.dumps({"type": "history-data", "messages": messages})
        )

    async def _handle_create_history(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle creation of new chat history"""
        context = self.client_contexts[client_uid]
        history_uid = create_new_history(context.character_config.conf_uid)
        if history_uid:
            context.history_uid = history_uid
            context.agent_engine.set_memory_from_history(
                conf_uid=context.character_config.conf_uid,
                history_uid=history_uid,
            )
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "new-history-created",
                        "history_uid": history_uid,
                    }
                )
            )

    async def _handle_delete_history(
        self, websocket: WebSocket, client_uid: str, data: dict
    ):
        """Handle deletion of chat history"""
        history_uid = data.get("history_uid")
        if not history_uid:
            return

        context = self.client_contexts[client_uid]
        success = delete_history(
            context.character_config.conf_uid,
            history_uid,
        )
        await websocket.send_text(
            json.dumps(
                {
                    "type": "history-deleted",
                    "success": success,
                    "history_uid": history_uid,
                }
            )
        )
        if history_uid == context.history_uid:
            context.history_uid = None

    async def _handle_audio_data(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle incoming audio data"""
        audio_data = data.get("audio", [])
        if audio_data:
            self.received_data_buffers[client_uid] = np.append(
                self.received_data_buffers[client_uid],
                np.array(audio_data, dtype=np.float32),
            )

    async def _handle_raw_audio_data(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle incoming raw audio data for VAD processing.
        Falls back to simple buffering if no VAD engine is available."""
        context = self.client_contexts[client_uid]
        chunk = data.get("audio", [])
        if not chunk:
            return

        if context.vad_engine is None:
            # No VAD available — just buffer the audio and notify
            self.received_data_buffers[client_uid] = np.append(
                self.received_data_buffers[client_uid],
                np.array(chunk, dtype=np.float32),
            )
            await websocket.send_text(
                json.dumps({"type": "control", "text": "mic-audio-end"})
            )
            return

        for audio_bytes in context.vad_engine.detect_speech(chunk):
            if audio_bytes == b"<|PAUSE|>":
                await websocket.send_text(
                    json.dumps({"type": "control", "text": "interrupt"})
                )
            elif audio_bytes == b"<|RESUME|>":
                pass
            elif len(audio_bytes) > 1024:
                # Detected audio activity (voice)
                self.received_data_buffers[client_uid] = np.append(
                    self.received_data_buffers[client_uid],
                    np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32),
                )
                await websocket.send_text(
                    json.dumps({"type": "control", "text": "mic-audio-end"})
                )

    async def _handle_conversation_trigger(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle triggers that start a conversation"""
        await handle_conversation_trigger(
            msg_type=data.get("type", ""),
            data=data,
            client_uid=client_uid,
            context=self.client_contexts[client_uid],
            websocket=websocket,
            client_contexts=self.client_contexts,
            client_connections=self.client_connections,
            chat_group_manager=self.chat_group_manager,
            received_data_buffers=self.received_data_buffers,
            current_conversation_tasks=self.current_conversation_tasks,
            broadcast_to_group=self.broadcast_to_group,
        )

    async def _handle_fetch_configs(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle fetching available configurations"""
        # Auto-discover any new VRM files dropped into vrm-models/
        _auto_discover_vrm_models()
        context = self.client_contexts[client_uid]
        config_files = scan_config_alts_directory(context.system_config.config_alts_dir)
        await websocket.send_text(
            json.dumps({"type": "config-files", "configs": config_files})
        )

    async def _handle_config_switch(
        self, websocket: WebSocket, client_uid: str, data: dict
    ):
        """Handle switching to a different configuration"""
        config_file_name = data.get("file")
        if config_file_name:
            context = self.client_contexts[client_uid]
            await context.handle_config_switch(websocket, config_file_name)

    async def _handle_fetch_backgrounds(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle fetching available background images"""
        bg_files = scan_bg_directory()
        await websocket.send_text(
            json.dumps({"type": "background-files", "files": bg_files})
        )

    async def _handle_audio_play_start(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """
        Handle audio playback start notification
        """
        group_members = self.chat_group_manager.get_group_members(client_uid)
        if len(group_members) > 1:
            display_text = data.get("display_text")
            if display_text:
                silent_payload = prepare_audio_payload(
                    audio_path=None,
                    display_text=display_text,
                    actions=None,
                    forwarded=True,
                )
                await self.broadcast_to_group(
                    group_members, silent_payload, exclude_uid=client_uid
                )

    async def _handle_group_info(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle group info request"""
        await self.send_group_update(websocket, client_uid)

    async def _handle_init_config_request(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle request for initialization configuration"""
        context = self.client_contexts.get(client_uid)
        if not context:
            context = self.default_context_cache

        active_model = context.model
        await websocket.send_text(
            json.dumps(
                {
                    "type": "set-model-and-conf",
                    "model_info": active_model.model_info if active_model else {},
                    "model_type": active_model.model_type if active_model else "live2d",
                    "conf_name": context.character_config.conf_name,
                    "conf_uid": context.character_config.conf_uid,
                    "client_uid": client_uid,
                    "agent_config": self._build_agent_config_data(context),
                }
            )
        )

    def _build_agent_config_data(self, context: ServiceContext) -> dict:
        """Build agent config data for the frontend (no API keys)."""
        agent_config = context.character_config.agent_config
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
            "available_models": [],
        }

    async def _handle_save_config(
        self, websocket: WebSocket, client_uid: str, data: dict
    ) -> None:
        """Handle saving agent configuration (provider/model) to conf.yaml."""
        context = self.client_contexts.get(client_uid)
        if not context:
            context = self.default_context_cache

        try:
            new_provider = data.get("llm_provider")
            new_model = data.get("model")

            agent_config = context.character_config.agent_config
            basic_memory = agent_config.agent_settings.basic_memory_agent

            if new_provider and new_provider != basic_memory.llm_provider:
                basic_memory.llm_provider = new_provider

            if new_model:
                provider_config = getattr(
                    agent_config.llm_configs, basic_memory.llm_provider, None
                )
                if provider_config:
                    if hasattr(provider_config, "model"):
                        provider_config.model = new_model
                    elif hasattr(provider_config, "model_path"):
                        provider_config.model_path = new_model

            save_config(context.config, "conf.yaml")

            # force=True because the config is mutated in place above — without it,
            # init_agent's "same config" guard sees identical (same) objects and
            # would skip rebuilding the agent, so the provider/model change would
            # only take effect after a restart.
            await context.init_agent(
                agent_config,
                context.character_config.persona_prompt,
                force=True,
            )

            await websocket.send_text(
                json.dumps(
                    {
                        "type": "config-saved",
                        "message": "Configuration saved successfully",
                        "agent_config": self._build_agent_config_data(context),
                    }
                )
            )

        except Exception as e:
            logger.error(f"Error saving config: {e}")
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "message": f"Error saving configuration: {str(e)}",
                    }
                )
            )

    async def _handle_fetch_available_models(
        self, websocket: WebSocket, client_uid: str, data: dict
    ) -> None:
        """Fetch available models from the provider's /v1/models endpoint."""
        provider_name = data.get("provider")
        if not provider_name:
            await websocket.send_text(
                json.dumps({"type": "available-models", "models": [], "provider": ""})
            )
            return

        context = self.client_contexts.get(client_uid)
        if not context:
            context = self.default_context_cache

        try:
            llm_configs = context.character_config.agent_config.llm_configs
            provider_config = getattr(llm_configs, provider_name, None)
            if not provider_config:
                await websocket.send_text(
                    json.dumps({"type": "available-models", "models": [], "provider": provider_name})
                )
                return

            base_url = getattr(provider_config, "base_url", None)
            api_key = getattr(provider_config, "llm_api_key", "")

            if not base_url:
                await websocket.send_text(
                    json.dumps({"type": "available-models", "models": [], "provider": provider_name})
                )
                return

            models_url = f"{base_url.rstrip('/')}/models"
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(models_url, headers=headers)
                resp.raise_for_status()
                body = resp.json()

            models = []
            for item in body.get("data", []):
                model_id = item.get("id")
                if model_id:
                    models.append(model_id)
            models.sort()

            await websocket.send_text(
                json.dumps({"type": "available-models", "models": models, "provider": provider_name})
            )
        except Exception as e:
            logger.warning(f"Failed to fetch models for '{provider_name}': {e}")
            await websocket.send_text(
                json.dumps({"type": "available-models", "models": [], "provider": provider_name})
            )

    async def _handle_discover_vrm_expressions(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle VRM expression auto-discovery from the frontend.

        The frontend reads all blend-shape names from the loaded VRM model
        and sends them here.  We rebuild the emotion map, persist it to
        ``model_dict.json``, update the in-memory model, and send the
        refreshed map back so the AI prompt and frontend stay in sync.
        """
        expressions = data.get("expressions", [])
        if not expressions:
            return

        context = self.client_contexts.get(client_uid)
        if not context or not context.model:
            return

        vrm_model = context.model
        if vrm_model.model_type != "vrm":
            return

        # Build merged emotion map (preserves any manual overrides)
        old_map = dict(vrm_model.model_info.get("emotionMap") or {})
        new_map = build_emotion_map_from_vrm_expressions(expressions, old_map)

        if new_map == old_map:
            # Nothing changed — just ack
            await websocket.send_text(
                json.dumps({"type": "model-emotions-updated", "emotionMap": new_map})
            )
            return

        logger.info(
            f"VRM expression discovery: model={vrm_model.model_name} "
            f"added={set(new_map) - set(old_map)} removed={set(old_map) - set(new_map)}"
        )

        # Update in-memory model
        vrm_model.model_info["emotionMap"] = new_map
        vrm_model._build_emo_map()

        # Persist to model_dict.json
        try:
            model_dict_path = vrm_model.model_dict_path
            with open(model_dict_path, "r", encoding="utf-8") as f:
                model_dict = json.load(f)
            for entry in model_dict:
                if entry.get("name") == vrm_model.model_name:
                    entry["emotionMap"] = new_map
                    break
            with open(model_dict_path, "w", encoding="utf-8") as f:
                json.dump(model_dict, f, indent=2, ensure_ascii=False)
            logger.info(f"Persisted updated emotionMap to {model_dict_path}")
        except Exception as e:
            logger.error(f"Failed to persist emotionMap: {e}")

        # Send updated map back to frontend
        await websocket.send_text(
            json.dumps({"type": "model-emotions-updated", "emotionMap": new_map})
        )

    async def _handle_heartbeat(
        self, websocket: WebSocket, client_uid: str, data: WSMessage
    ) -> None:
        """Handle heartbeat messages from clients"""
        try:
            await websocket.send_json({"type": "heartbeat-ack"})
        except Exception as e:
            logger.error(f"Error sending heartbeat acknowledgment: {e}")

    async def _handle_set_grid_spec(
        self, websocket: WebSocket, client_uid: str, data: dict
    ) -> None:
        """Handle grid resolution change from settings GUI."""
        grid_spec = data.get("grid_spec", "8x6")
        try:
            from .agentic.grid_state import set_grid_spec

            result = set_grid_spec(grid_spec)
            logger.info(f"Grid spec changed via settings GUI: {result}")
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "grid-spec-updated",
                        "grid_spec": grid_spec,
                        "message": result,
                    }
                )
            )
        except Exception as e:
            logger.error(f"Failed to set grid spec: {e}")
            await websocket.send_text(
                json.dumps(
                    {"type": "error", "message": f"Failed to set grid spec: {e}"}
                )
            )

    async def _handle_set_ai_mode(
        self, websocket: WebSocket, client_uid: str, data: dict
    ) -> None:
        """Handle AI mode switch from frontend."""
        mode = data.get("mode", "full_agent")
        context = self.client_contexts.get(client_uid)
        if not context:
            return
        try:
            context.set_ai_mode(mode)
            await context.reinit_agent_for_mode()
            await websocket.send_text(json.dumps({
                "type": "ai-mode-updated",
                "mode": mode,
            }))
            logger.info(f"AI mode updated to {mode} for {client_uid}")
        except Exception as e:
            logger.error(f"Failed to set AI mode: {e}")
            await websocket.send_text(
                json.dumps({"type": "error", "message": f"Failed to set AI mode: {e}"})
            )

    async def _handle_fetch_memories(
        self, websocket: WebSocket, client_uid: str, data: dict
    ) -> None:
        """Handle request for long-term memories."""
        context = self.client_contexts.get(client_uid)
        if not context or not context.memory_manager:
            await websocket.send_text(json.dumps({"type": "memories", "data": []}))
            return
        memories = context.memory_manager.load()
        await websocket.send_text(
            json.dumps({"type": "memories", "data": [m.to_dict() for m in memories]})
        )

    async def _handle_delete_memory(
        self, websocket: WebSocket, client_uid: str, data: dict
    ) -> None:
        """Handle deletion of a specific memory."""
        context = self.client_contexts.get(client_uid)
        if not context or not context.memory_manager:
            return
        memory_id = data.get("id")
        if not memory_id:
            return
        memories = context.memory_manager.load()
        memories = [m for m in memories if m.id != memory_id]
        context.memory_manager.save(memories)
        await websocket.send_text(
            json.dumps({"type": "delete-memory-result", "success": True})
        )

    async def _handle_update_memory(
        self, websocket: WebSocket, client_uid: str, data: dict
    ) -> None:
        """Handle updating a specific memory fact."""
        context = self.client_contexts.get(client_uid)
        if not context or not context.memory_manager:
            return
        memory_id = data.get("id")
        new_fact = data.get("fact")
        if not memory_id or not new_fact:
            return
        memories = context.memory_manager.load()
        for m in memories:
            if m.id == memory_id:
                m.fact = new_fact
                break
        context.memory_manager.save(memories)
        await websocket.send_text(
            json.dumps({"type": "update-memory-result", "success": True})
        )

    async def _handle_fetch_todos(
        self, websocket: WebSocket, client_uid: str, data: dict
    ) -> None:
        """Handle request for todos."""
        context = self.client_contexts.get(client_uid)
        if not context or not context.todo_manager:
            await websocket.send_text(json.dumps({"type": "todos", "data": []}))
            return
        items = context.todo_manager.load()
        await websocket.send_text(
            json.dumps({"type": "todos", "data": [i.to_dict() for i in items]})
        )

    async def _handle_add_todo(
        self, websocket: WebSocket, client_uid: str, data: dict
    ) -> None:
        """Handle adding a todo from the UI."""
        context = self.client_contexts.get(client_uid)
        if not context or not context.todo_manager:
            return
        text = data.get("text", "")
        dt = data.get("datetime", "")
        if not text:
            return
        item = context.todo_manager.add(text, dt)
        await websocket.send_text(
            json.dumps(
                {"type": "add-todo-result", "success": True, "todo": item.to_dict()}
            )
        )

    async def _handle_delete_todo(
        self, websocket: WebSocket, client_uid: str, data: dict
    ) -> None:
        """Handle deletion of a todo."""
        context = self.client_contexts.get(client_uid)
        if not context or not context.todo_manager:
            return
        todo_id = data.get("id")
        if not todo_id:
            return
        ok = context.todo_manager.delete(todo_id)
        await websocket.send_text(
            json.dumps({"type": "delete-todo-result", "success": ok})
        )

    async def _handle_update_todo(
        self, websocket: WebSocket, client_uid: str, data: dict
    ) -> None:
        """Handle updating a todo (text, datetime, completed)."""
        context = self.client_contexts.get(client_uid)
        if not context or not context.todo_manager:
            return
        todo_id = data.get("id")
        if not todo_id:
            return
        item = context.todo_manager.update(
            todo_id,
            text=data.get("text"),
            datetime_str=data.get("datetime"),
            completed=data.get("completed"),
        )
        await websocket.send_text(
            json.dumps({"type": "update-todo-result", "success": item is not None})
        )

    async def _reminder_check_loop(self, client_uid: str) -> None:
        """Background task: check for due todos every 60s and trigger AI response."""
        notified: set = set()
        while True:
            try:
                websocket = self.client_connections.get(client_uid)
                context = self.client_contexts.get(client_uid)
                if not websocket or not context or not context.todo_manager:
                    await asyncio.sleep(60)
                    continue
                due = context.todo_manager.get_due_todos()
                for item in due:
                    if item.id not in notified:
                        notified.add(item.id)
                        # Send frontend notification
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "reminder",
                                    "todo": item.to_dict(),
                                }
                            )
                        )
                        # Trigger AI to proactively respond about the reminder
                        # Skip if a conversation is already running
                        task = self.current_conversation_tasks.get(client_uid)
                        if not task or task.done():
                            user_input = f"⏰ Reminder: {item.text}"
                            self.current_conversation_tasks[client_uid] = (
                                asyncio.create_task(
                                    process_single_conversation(
                                        context=context,
                                        websocket_send=websocket.send_text,
                                        client_uid=client_uid,
                                        user_input=user_input,
                                    )
                                )
                            )
                            logger.info(
                                f"Reminder triggered AI for '{item.text}' to {client_uid}"
                            )
                        else:
                            logger.debug(
                                f"Reminder skipped: conversation already running for {client_uid}"
                            )
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Reminder check error for {client_uid}: {e}")
                await asyncio.sleep(60)

    async def _idle_life_loop(self, client_uid: str) -> None:
        """Background task: poll idle life manager every 5s."""
        while True:
            try:
                await asyncio.sleep(5)
                context = self.client_contexts.get(client_uid)
                if not context or not context.idle_life_manager:
                    continue
                mgr = context.idle_life_manager
                if not mgr.enabled:
                    continue

                # Wire websocket_send
                ws = self.client_connections.get(client_uid)
                if ws:
                    mgr.set_websocket_send(ws.send_text)

                # Wire proactive trigger (lazy, one-shot)
                if not hasattr(mgr, '_proactive_trigger_wired') or not mgr._proactive_trigger_wired:
                    async def _proactive_topic(topic: str):
                        ctx = self.client_contexts.get(client_uid)
                        wsock = self.client_connections.get(client_uid)
                        if not ctx or not wsock:
                            return
                        await wsock.send_text(json.dumps({
                            "type": "full-text",
                            "text": topic,
                        }))
                        from .conversations.conversation_handler import handle_conversation_trigger
                        await handle_conversation_trigger(
                            msg_type="ai-speak-signal",
                            data={"text": topic, "images": []},
                            client_uid=client_uid,
                            context=ctx,
                            websocket=wsock,
                            client_contexts=self.client_contexts,
                            client_connections=self.client_connections,
                            chat_group_manager=self.chat_group_manager,
                            received_data_buffers=self.received_data_buffers,
                            current_conversation_tasks=self.current_conversation_tasks,
                            broadcast_to_group=self.broadcast_to_group,
                        )
                        logger.info(f"IdleLife: proactive conversation triggered: '{topic[:40]}...'")
                    mgr.set_proactive_trigger(_proactive_topic)
                    mgr._proactive_trigger_wired = True

                # Wire music trigger (lazy, one-shot)
                if not hasattr(mgr, '_music_trigger_wired') or not mgr._music_trigger_wired:
                    async def _music_next():
                        wsock = self.client_connections.get(client_uid)
                        ctx = self.client_contexts.get(client_uid)
                        if not wsock or not ctx:
                            return
                        await self._handle_music_next(wsock, client_uid, {})
                    mgr.set_music_trigger(_music_next)
                    mgr._music_trigger_wired = True

                # Pass memory context
                try:
                    memory_text = context.agent_engine.get_memory_prompt()
                    mgr.set_memory_prompt(memory_text)
                except Exception:
                    pass

                # Pass screen context
                try:
                    screen_desc = context.screen_monitor.change_description
                    mgr.set_screen_context(screen_desc)
                except Exception:
                    pass

                # Handle wake greeting
                greeting = mgr.consume_wake_greeting()
                if greeting and ws:
                    await ws.send_text(json.dumps({
                        "type": "full-text",
                        "text": greeting,
                    }))

                await mgr.tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"IdleLife error for {client_uid}: {e}")
                await asyncio.sleep(5)

    async def _handle_music_next(
        self, websocket: WebSocket, client_uid: str, data: dict
    ) -> None:
        context = self.client_contexts.get(client_uid)
        if not context:
            return

        task_key = f"{client_uid}_music"
        if (
            task_key in self.current_conversation_tasks
            and not self.current_conversation_tasks[task_key].done()
        ):
            logger.warning("Music next already in progress, skipping")
            return

        async def _music_recommendation_task():
            llm = getattr(context.idle_life_manager, '_subconscious_llm', None) if context.idle_life_manager else None
            if not llm:
                llm = context.memory_manager._llm if hasattr(context.memory_manager, '_llm') and context.memory_manager._llm else None
            if not llm:
                logger.warning("Music next: no stateless LLM available, skipping")
                return

            current = music_player_manager.get_current()
            prompt = (
                "Kamu adalah assistant musik. Tugasmu merekomendasikan SATU lagu Indonesia. "
                "Kembalikan JSON tanpa markdown, tanpa teks lain:\n"
                '{"title": "judul lagu", "artist": "nama artis"}\n\n'
                "Pilih lagu yang terkenal dan benar-benar ada."
            )
            if current:
                prompt += f" Jangan pilih lagu yang mirip dengan '{current['title']}'."

            system = (
                "Kamu adalah assistant musik. Hanya output JSON tanpa teks lain."
            )

            try:
                chunks = []
                async for chunk in llm.chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    system=system,
                ):
                    if isinstance(chunk, str):
                        chunks.append(chunk)

                raw = "".join(chunks).strip()
                json_match = re.search(r'\{[^{}]*\}', raw)
                if not json_match:
                    logger.warning(f"Music next: no JSON in LLM response: {raw[:100]}")
                    return
                song_data = json.loads(json_match.group())
                title = song_data.get("title", "").strip()
                artist = song_data.get("artist", "").strip()
                if not title:
                    logger.warning("Music next: no title in LLM response")
                    return

                query = f"{title} {artist}".strip()

                # Search YouTube for the song
                import yt_dlp
                ydl_opts = {"quiet": True, "no_warnings": True, "extract_flat": "in_playlist"}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(f"ytsearch3:{query}", download=False)
                    entries = info.get("entries", [])
                    if not entries:
                        logger.warning(f"Music next: no YouTube results for '{query}'")
                        return
                    first = entries[0]
                    video_url = f"https://youtube.com/watch?v={first.get('id', '')}"

                # Extract stream URL
                ydl_opts2 = {"quiet": True, "no_warnings": True, "format": "bestaudio/best"}
                with yt_dlp.YoutubeDL(ydl_opts2) as ydl2:
                    info2 = ydl2.extract_info(video_url, download=False)
                    stream_url = info2.get("url", "")

                if not stream_url:
                    logger.warning(f"Music next: no stream for {video_url}")
                    return

                song_info = {
                    "title": first.get("title", title),
                    "stream_url": stream_url,
                    "video_url": video_url,
                }
                music_player_manager.play_song(song_info, is_recommended=True)

                await websocket.send_text(json.dumps({
                    "type": "music-play-song",
                    "title": song_info["title"],
                    "stream_url": stream_url,
                    "video_url": video_url,
                    "is_recommended": True,
                }))
                logger.info(f"Music next: playing '{song_info['title']}'")

            except Exception as e:
                logger.error(f"Music next error: {e}", exc_info=True)

        self.current_conversation_tasks[task_key] = asyncio.create_task(
            _music_recommendation_task()
        )

    async def _handle_music_prev(
        self, websocket: WebSocket, client_uid: str, data: dict
    ) -> None:
        prev_song = music_player_manager.get_prev_song()
        if not prev_song:
            await websocket.send_text(
                json.dumps(
                    {"type": "music-no-prev", "message": "Tidak ada lagu sebelumnya"}
                )
            )
            return

        stream_url = prev_song.get("stream_url")
        video_url = prev_song.get("video_url", "")
        if video_url:
            fresh_url = await music_player_manager.refresh_stream_url(video_url)
            if fresh_url:
                stream_url = fresh_url

        if not stream_url:
            await websocket.send_text(
                json.dumps(
                    {"type": "music-error", "message": "Gagal memuat lagu sebelumnya"}
                )
            )
            return

        music_player_manager.play_song(prev_song, is_recommended=False)

        await websocket.send_text(
            json.dumps(
                {
                    "type": "music-play-song",
                    "title": prev_song.get("title", "Unknown"),
                    "stream_url": stream_url,
                    "video_url": video_url,
                    "is_recommended": False,
                }
            )
        )

    async def _handle_music_stop(
        self, websocket: WebSocket, client_uid: str, data: dict
    ) -> None:
        music_player_manager.stop()
        await websocket.send_text(json.dumps({"type": "music-stopped"}))

    async def _handle_music_play_pause(
        self, websocket: WebSocket, client_uid: str, data: dict
    ) -> None:
        is_playing = data.get("is_playing", True)
        logger.debug(f"Music play/pause toggle: is_playing={is_playing}")

    async def _handle_music_feedback(
        self, websocket: WebSocket, client_uid: str, data: dict
    ) -> None:
        context = self.client_contexts.get(client_uid)
        if not context:
            return

        feedback = data.get("feedback", "")
        if feedback == "like":
            prompt = "Pengguna suka tipe lagu ini. Rekomendasikan dan putarkan lagu lain yang mirip dengan tema ini. Utamakan lagu Indonesia."
        elif feedback == "dislike":
            prompt = "Pengguna tidak suka tipe lagu ini. Rekomendasikan dan putarkan lagu dengan genre/style yang sangat berbeda. Utamakan lagu Indonesia."
        else:
            return

        async def _music_feedback_task():
            await process_single_conversation(
                context=context,
                websocket_send=websocket.send_text,
                client_uid=client_uid,
                user_input=prompt,
                metadata={"skip_history": True, "skip_memory": True},
            )

        task_key = f"{client_uid}_music"
        self.current_conversation_tasks[task_key] = asyncio.create_task(
            _music_feedback_task()
        )

    async def _handle_restart_backend(
        self, websocket: WebSocket, client_uid: str, data: dict
    ) -> None:
        """Restart the backend server process."""
        import os
        import sys

        logger.info("Backend restart requested by client")
        await websocket.send_text(
            json.dumps({"type": "control", "text": "backend-restarting"})
        )
        # Give time for the message to be sent
        await asyncio.sleep(0.5)
        # Restart the process
        os.execv(sys.executable, [sys.executable] + sys.argv)
