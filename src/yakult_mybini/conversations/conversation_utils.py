import asyncio
import re
from typing import Optional, Union, Any, List, Dict
import numpy as np
import json
from loguru import logger

from ..message_handler import message_handler
from .types import WebSocketSend, BroadcastContext
from .tts_manager import TTSTaskManager
from ..agent.output_types import SentenceOutput, AudioOutput
from ..agent.input_types import (
    BatchInput,
    TextData,
    ImageData,
    FileData,
    TextSource,
    ImageSource,
)
from ..asr.asr_interface import ASRInterface
from ..live2d_model import Live2dModel
from ..tts.tts_interface import TTSInterface
from ..utils.stream_audio import prepare_audio_payload
from ..agentic.grid_state import (
    is_grid_enabled,
    apply_grid_to_image,
    get_grid_rows,
    get_grid_cols,
    _col_label,
)


# Convert class methods to standalone functions
def create_batch_input(
    input_text: str,
    images: Optional[List[Dict[str, Any]]],
    from_name: str,
    metadata: Optional[Dict[str, Any]] = None,
    files: Optional[List[Dict[str, Any]]] = None,
) -> BatchInput:
    """Create batch input for agent processing"""
    image_width_hint = ""

    processed_images = []
    for img in images or []:
        data = img["data"]
        mime_type = img.get("mime_type", "image/jpeg")
        source = img.get("source", "screen")

        # Decode image to get actual dimensions (for coordinate scaling)
        img_width, img_height = 0, 0
        if data and "base64," in data:
            try:
                import base64
                from PIL import Image
                import io

                b64 = data.split("base64,")[1]
                pil_img = Image.open(io.BytesIO(base64.b64decode(b64)))
                img_width, img_height = pil_img.size
            except Exception:
                pass

        if source == "screen" and img_width > 0 and img_height > 0:
            image_width_hint = (
                f"\n[Shared screen image dimensions: {img_width}×{img_height} pixels. "
                f"Use these as image_width={img_width} and image_height={img_height} "
                f"when calling click/x11_click/type_text so coordinates map to the real screen.]"
            )
            if is_grid_enabled():
                data = apply_grid_to_image(data)
                gr = get_grid_rows()
                gc = get_grid_cols()
                image_width_hint += (
                    f"\n[Grid overlay ACTIVE: {gc}x{gr}. "
                    f"Cells labeled {_col_label(0)}1 – {_col_label(gc - 1)}{gr}. "
                    f"Use grid_cell='cellname' in click/type_text/x11_click – do NOT use raw x,y.]"
                )

        processed_images.append(
            ImageData(
                source=ImageSource(source),
                data=data,
                mime_type=mime_type,
            )
        )

    text_content = input_text + image_width_hint if image_width_hint else input_text

    processed_files = []
    for f in files or []:
        name = f.get("name", "")
        mime_type = f.get("mime_type", "application/octet-stream")
        data = f.get("data", "")
        kind = f.get("kind", "")
        if kind == "image":
            if data:
                processed_images.append(
                    ImageData(
                        source=ImageSource.UPLOAD,
                        data=data,
                        mime_type=mime_type,
                    )
                )
        elif data:
            processed_files.append(FileData(name=name, data=data, mime_type=mime_type))

    return BatchInput(
        texts=[
            TextData(source=TextSource.INPUT, content=text_content, from_name=from_name)
        ],
        images=processed_images if processed_images else None,
        files=processed_files if processed_files else None,
        metadata=metadata,
    )


async def process_agent_output(
    output: Union[AudioOutput, SentenceOutput],
    character_config: Any,
    live2d_model: Live2dModel,
    tts_engine: TTSInterface,
    websocket_send: WebSocketSend,
    tts_manager: TTSTaskManager,
    translate_engine: Optional[Any] = None,
) -> str:
    """Process agent output with character information and optional translation"""
    output.display_text.name = character_config.character_name
    output.display_text.avatar = character_config.avatar

    full_response = ""
    try:
        if isinstance(output, SentenceOutput):
            full_response = await handle_sentence_output(
                output,
                live2d_model,
                tts_engine,
                websocket_send,
                tts_manager,
                translate_engine,
            )
        elif isinstance(output, AudioOutput):
            full_response = await handle_audio_output(output, websocket_send)
        else:
            logger.warning(f"Unknown output type: {type(output)}")
    except Exception as e:
        logger.error(f"Error processing agent output: {e}")
        await websocket_send(
            json.dumps(
                {"type": "error", "message": f"Error processing response: {str(e)}"}
            )
        )

    return full_response


async def handle_sentence_output(
    output: SentenceOutput,
    live2d_model: Live2dModel,
    tts_engine: TTSInterface,
    websocket_send: WebSocketSend,
    tts_manager: TTSTaskManager,
    translate_engine: Optional[Any] = None,
) -> str:
    """Handle sentence output type with optional translation support"""
    full_response = ""
    async for display_text, tts_text, actions in output:
        logger.debug(f"🏃 Processing output: '''{tts_text}'''...")

        if translate_engine:
            if len(re.sub(r'[\s.,!?，。！？\'"』」）】\s]+', "", tts_text)):
                tts_text = await asyncio.to_thread(translate_engine.translate, tts_text)
            logger.info(f"🏃 Text after translation: '''{tts_text}'''...")
        else:
            logger.debug("🚫 No translation engine available. Skipping translation.")

        full_response += display_text.text
        await tts_manager.speak(
            tts_text=tts_text,
            display_text=display_text,
            actions=actions,
            live2d_model=live2d_model,
            tts_engine=tts_engine,
            websocket_send=websocket_send,
        )
    return full_response


async def handle_audio_output(
    output: AudioOutput,
    websocket_send: WebSocketSend,
) -> str:
    """Process and send AudioOutput directly to the client"""
    full_response = ""
    async for audio_path, display_text, transcript, actions in output:
        full_response += transcript
        audio_payload = prepare_audio_payload(
            audio_path=audio_path,
            display_text=display_text,
            actions=actions.to_dict() if actions else None,
        )
        await websocket_send(json.dumps(audio_payload))
    return full_response


async def send_conversation_start_signals(websocket_send: WebSocketSend) -> None:
    """Send initial conversation signals"""
    await websocket_send(
        json.dumps(
            {
                "type": "control",
                "text": "conversation-chain-start",
            }
        )
    )
    await websocket_send(json.dumps({"type": "full-text", "text": "Thinking..."}))


async def process_user_input(
    user_input: Union[str, np.ndarray],
    asr_engine: Optional[ASRInterface],
    websocket_send: WebSocketSend,
) -> str:
    """Process user input, converting audio to text if needed"""
    if isinstance(user_input, np.ndarray):
        if asr_engine is None:
            logger.warning("Received audio but ASR is disabled.")
            return ""
        logger.info("Transcribing audio input...")
        input_text = await asr_engine.async_transcribe_np(user_input)
        await websocket_send(
            json.dumps({"type": "user-input-transcription", "text": input_text})
        )
        return input_text
    return user_input


async def finalize_conversation_turn(
    tts_manager: TTSTaskManager,
    websocket_send: WebSocketSend,
    client_uid: str,
    broadcast_ctx: Optional[BroadcastContext] = None,
) -> None:
    """Finalize a conversation turn"""
    # Wait for any remaining TTS tasks (already gathered in single_conversation,
    # but guard against edge cases)
    if tts_manager.task_list:
        await asyncio.gather(*tts_manager.task_list, return_exceptions=True)

    await websocket_send(json.dumps({"type": "backend-synth-complete"}))

    # Wait for frontend playback with timeout (15s) to prevent indefinite hang
    try:
        response = await message_handler.wait_for_response(
            client_uid, "frontend-playback-complete", timeout=15.0
        )
        if not response:
            logger.warning(
                f"No playback completion response from {client_uid} (timeout)"
            )
    except asyncio.TimeoutError:
        logger.warning(
            f"Timeout waiting for frontend-playback-complete from {client_uid}"
        )

    await websocket_send(json.dumps({"type": "force-new-message"}))

    if broadcast_ctx and broadcast_ctx.broadcast_func:
        await broadcast_ctx.broadcast_func(
            broadcast_ctx.group_members,
            {"type": "force-new-message"},
            broadcast_ctx.current_client_uid,
        )

    await send_conversation_end_signal(websocket_send, broadcast_ctx)


async def send_conversation_end_signal(
    websocket_send: WebSocketSend,
    broadcast_ctx: Optional[BroadcastContext],
    session_emoji: str = "😊",
) -> None:
    """Send conversation chain end signal"""
    chain_end_msg = {
        "type": "control",
        "text": "conversation-chain-end",
    }

    await websocket_send(json.dumps(chain_end_msg))

    if broadcast_ctx and broadcast_ctx.broadcast_func and broadcast_ctx.group_members:
        await broadcast_ctx.broadcast_func(
            broadcast_ctx.group_members,
            chain_end_msg,
        )

    logger.info(f"😎👍✅ Conversation Chain {session_emoji} completed!")


def cleanup_conversation(tts_manager: TTSTaskManager, session_emoji: str) -> None:
    """Clean up conversation resources"""
    tts_manager.clear()
    logger.debug(f"🧹 Clearing up conversation {session_emoji}.")


EMOJI_LIST = [
    "🐶",
    "🐱",
    "🐭",
    "🐹",
    "🐰",
    "🦊",
    "🐻",
    "🐼",
    "🐨",
    "🐯",
    "🦁",
    "🐮",
    "🐷",
    "🐸",
    "🐵",
    "🐔",
    "🐧",
    "🐦",
    "🐤",
    "🐣",
    "🐥",
    "🦆",
    "🦅",
    "🦉",
    "🦇",
    "🐺",
    "🐗",
    "🐴",
    "🦄",
    "🐝",
    "🌵",
    "🎄",
    "🌲",
    "🌳",
    "🌴",
    "🌱",
    "🌿",
    "☘️",
    "🍀",
    "🍂",
    "🍁",
    "🍄",
    "🌾",
    "💐",
    "🌹",
    "🌸",
    "🌛",
    "🌍",
    "⭐️",
    "🔥",
    "🌈",
    "🌩",
    "⛄️",
    "🎃",
    "🎄",
    "🎉",
    "🎏",
    "🎗",
    "🀄️",
    "🎭",
    "🎨",
    "🧵",
    "🪡",
    "🧶",
    "🥽",
    "🥼",
    "🦺",
    "👔",
    "👕",
    "👜",
    "👑",
]
