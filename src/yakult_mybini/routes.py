import os
import json
import shutil
from uuid import uuid4
import numpy as np
from datetime import datetime
from fastapi import APIRouter, WebSocket, UploadFile, File, Form, Response
from starlette.responses import JSONResponse
from starlette.websockets import WebSocketDisconnect
from loguru import logger
from .service_context import ServiceContext
from .websocket_handler import WebSocketHandler
from .proxy_handler import ProxyHandler


def init_client_ws_route(default_context_cache: ServiceContext) -> APIRouter:
    """
    Create and return API routes for handling the `/client-ws` WebSocket connections.

    Args:
        default_context_cache: Default service context cache for new sessions.

    Returns:
        APIRouter: Configured router with WebSocket endpoint.
    """

    router = APIRouter()
    ws_handler = WebSocketHandler(default_context_cache)

    @router.websocket("/client-ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for client connections"""
        await websocket.accept()
        client_uid = str(uuid4())
        platform = websocket.query_params.get("platform", "unknown")

        try:
            await ws_handler.handle_new_connection(websocket, client_uid, platform)
            await ws_handler.handle_websocket_communication(websocket, client_uid)
        except WebSocketDisconnect:
            await ws_handler.handle_disconnect(client_uid)
        except Exception as e:
            logger.error(f"Error in WebSocket connection: {e}")
            await ws_handler.handle_disconnect(client_uid)
            raise

    return router


def init_proxy_route(server_url: str) -> APIRouter:
    """
    Create and return API routes for handling proxy connections.

    Args:
        server_url: The WebSocket URL of the actual server

    Returns:
        APIRouter: Configured router with proxy WebSocket endpoint
    """
    router = APIRouter()
    proxy_handler = ProxyHandler(server_url)

    @router.websocket("/proxy-ws")
    async def proxy_endpoint(websocket: WebSocket):
        """WebSocket endpoint for proxy connections"""
        try:
            await proxy_handler.handle_client_connection(websocket)
        except Exception as e:
            logger.error(f"Error in proxy connection: {e}")
            raise

    return router


def init_webtool_routes(default_context_cache: ServiceContext) -> APIRouter:
    """
    Create and return API routes for handling web tool interactions.

    Args:
        default_context_cache: Default service context cache for new sessions.

    Returns:
        APIRouter: Configured router with WebSocket endpoint.
    """

    router = APIRouter()

    @router.get("/web-tool")
    async def web_tool_redirect():
        """Redirect /web-tool to /web_tool/index.html"""
        return Response(status_code=302, headers={"Location": "/web-tool/index.html"})

    @router.get("/web_tool")
    async def web_tool_redirect_alt():
        """Redirect /web_tool to /web_tool/index.html"""
        return Response(status_code=302, headers={"Location": "/web-tool/index.html"})

    @router.get("/live2d-models/info")
    async def get_live2d_folder_info():
        """Get information about available Live2D models"""
        live2d_dir = "live2d-models"
        if not os.path.exists(live2d_dir):
            return JSONResponse(
                {"error": "Live2D models directory not found"}, status_code=404
            )

        valid_characters = []
        supported_extensions = [".png", ".jpg", ".jpeg"]

        for entry in os.scandir(live2d_dir):
            if entry.is_dir():
                folder_name = entry.name.replace("\\", "/")
                model3_file = os.path.join(
                    live2d_dir, folder_name, f"{folder_name}.model3.json"
                ).replace("\\", "/")

                if os.path.isfile(model3_file):
                    # Find avatar file if it exists
                    avatar_file = None
                    for ext in supported_extensions:
                        avatar_path = os.path.join(
                            live2d_dir, folder_name, f"{folder_name}{ext}"
                        )
                        if os.path.isfile(avatar_path):
                            avatar_file = avatar_path.replace("\\", "/")
                            break

                    valid_characters.append(
                        {
                            "name": folder_name,
                            "type": "live2d",
                            "avatar": avatar_file,
                            "model_path": model3_file,
                        }
                    )
        return JSONResponse(
            {
                "type": "live2d-models/info",
                "count": len(valid_characters),
                "characters": valid_characters,
            }
        )

    @router.get("/models/info")
    async def get_all_models_info():
        """Get information about all available models (Live2D + VRM)."""
        all_models = []

        # --- Scan Live2D models ---
        live2d_dir = "live2d-models"
        if os.path.exists(live2d_dir):
            supported_extensions = [".png", ".jpg", ".jpeg"]
            for entry in os.scandir(live2d_dir):
                if entry.is_dir():
                    folder_name = entry.name.replace("\\", "/")
                    model3_file = os.path.join(
                        live2d_dir, folder_name, f"{folder_name}.model3.json"
                    ).replace("\\", "/")
                    if os.path.isfile(model3_file):
                        avatar_file = None
                        for ext in supported_extensions:
                            ap = os.path.join(
                                live2d_dir, folder_name, f"{folder_name}{ext}"
                            )
                            if os.path.isfile(ap):
                                avatar_file = ap.replace("\\", "/")
                                break
                        all_models.append(
                            {
                                "name": folder_name,
                                "type": "live2d",
                                "avatar": avatar_file,
                                "model_path": model3_file,
                            }
                        )

        # --- Scan VRM models ---
        vrm_dir = "vrm-models"
        if os.path.exists(vrm_dir):
            for entry in os.scandir(vrm_dir):
                if entry.is_file() and entry.name.lower().endswith(".vrm"):
                    model_name = entry.name[:-4]  # strip .vrm
                    all_models.append(
                        {
                            "name": model_name,
                            "type": "vrm",
                            "avatar": None,
                            "model_path": f"/vrm-models/{entry.name}",
                        }
                    )
                elif entry.is_dir():
                    # Also check for .vrm files inside subdirectories
                    for sub in os.scandir(entry.path):
                        if sub.is_file() and sub.name.lower().endswith(".vrm"):
                            model_name = sub.name[:-4]
                            all_models.append(
                                {
                                    "name": model_name,
                                    "type": "vrm",
                                    "avatar": None,
                                    "model_path": f"/vrm-models/{entry.name}/{sub.name}",
                                }
                            )

        return JSONResponse(
            {
                "type": "models/info",
                "count": len(all_models),
                "models": all_models,
            }
        )

    @router.post("/models/import")
    async def import_vrm_model(file: UploadFile = File(...)):
        """
        Import a VRM (.vrm) model file.

        The file is saved to ``vrm-models/`` and registered in
        ``model_dict.json`` so it can be selected immediately.
        """
        if not file.filename or not file.filename.lower().endswith(".vrm"):
            return JSONResponse(
                {"error": "Only .vrm files are supported."}, status_code=400
            )

        # Sanitize model name from filename
        raw_name = file.filename[:-4]  # strip .vrm
        safe_name = "".join(c for c in raw_name if c.isalnum() or c in " _-_").strip()
        if not safe_name:
            safe_name = f"vrm_model_{uuid4().hex[:8]}"

        # Check if model already exists — reuse if so
        model_dict_path = "model_dict.json"
        existing_model_entry = None
        if os.path.exists(model_dict_path):
            try:
                with open(model_dict_path, "r", encoding="utf-8") as f:
                    model_dict = json.load(f)
                for entry in model_dict:
                    if entry.get("name") == safe_name and entry.get("type") == "vrm":
                        existing_model_entry = entry
                        break
            except Exception:
                model_dict = []
        else:
            model_dict = []

        vrm_dir = "vrm-models"
        os.makedirs(vrm_dir, exist_ok=True)
        characters_dir = "characters"
        os.makedirs(characters_dir, exist_ok=True)
        config_filename = f"vrm_{safe_name}.yaml"
        config_filepath = os.path.join(characters_dir, config_filename)

        if existing_model_entry and os.path.exists(config_filepath):
            # Model already imported — overwrite the VRM file in case user has an updated copy
            existing_dest = os.path.join(vrm_dir, f"{safe_name}.vrm")
            try:
                with open(existing_dest, "wb") as f:
                    shutil.copyfileobj(file.file, f)
            except Exception as e:
                await file.close()
                logger.error(f"Failed to overwrite VRM file: {e}")
                return JSONResponse({"error": f"Failed to save file: {e}"}, status_code=500)
            await file.close()
            logger.info(f"VRM model re-imported (overwrote): {safe_name} -> {existing_dest}")
            return JSONResponse(
                {
                    "success": True,
                    "model": existing_model_entry,
                    "config_file": config_filename,
                    "reused": True,
                }
            )

        dest_path = os.path.join(vrm_dir, f"{safe_name}.vrm")

        # Avoid overwriting existing file (shouldn't happen after the reuse check above)
        if os.path.exists(dest_path):
            safe_name = f"{safe_name}_{uuid4().hex[:6]}"
            dest_path = os.path.join(vrm_dir, f"{safe_name}.vrm")
            config_filename = f"vrm_{safe_name}.yaml"
            config_filepath = os.path.join(characters_dir, config_filename)

        try:
            with open(dest_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
        except Exception as e:
            logger.error(f"Failed to save VRM file: {e}")
            return JSONResponse({"error": f"Failed to save file: {e}"}, status_code=500)
        finally:
            await file.close()

        logger.info(f"VRM model imported: {safe_name} -> {dest_path}")

        # Register in model_dict.json
        try:
            new_entry = {
                "name": safe_name,
                "type": "vrm",
                "url": f"/vrm-models/{safe_name}.vrm",
                "emotionMap": {
                    "neutral": "neutral",
                    "joy": "happy",
                    "anger": "angry",
                    "sadness": "sad",
                    "surprise": "surprised",
                    "relaxed": "relaxed",
                },
                "visemeMap": {
                    "aa": "aa",
                    "ee": "ee",
                    "ih": "ih",
                    "oh": "oh",
                    "ou": "ou",
                },
            }
            model_dict.append(new_entry)
            with open(model_dict_path, "w", encoding="utf-8") as f:
                json.dump(model_dict, f, indent=4)
            logger.info(f"VRM model '{safe_name}' registered in model_dict.json")

        except Exception as e:
            logger.error(f"Failed to register VRM model in model_dict.json: {e}")
            return JSONResponse(
                {
                    "success": True,
                    "model": {
                        "name": safe_name,
                        "type": "vrm",
                        "url": f"/vrm-models/{safe_name}.vrm",
                    },
                    "warning": f"Model saved but could not be registered: {e}",
                }
            )

        # Create a minimal character config YAML for the VRM model
        try:
            config_yaml = f"""# Auto-generated config for VRM model: {safe_name}
character_config:
  conf_name: '{safe_name}'
  conf_uid: 'vrm_{safe_name}_{uuid4().hex[:8]}'
  live2d_model_name: '{safe_name}'
  model_type: 'vrm'
  character_name: '{safe_name}'
  human_name: 'Human'
  persona_prompt: |
    You are a helpful AI companion.
"""
            if not os.path.exists(config_filepath):
                with open(config_filepath, "w", encoding="utf-8") as f:
                    f.write(config_yaml)
                logger.info(f"Config file created for VRM model: {config_filepath}")
        except Exception as e:
            logger.error(f"Failed to create config file for VRM model: {e}")

        return JSONResponse(
            {
                "success": True,
                "model": {
                    "name": safe_name,
                    "type": "vrm",
                    "url": f"/vrm-models/{safe_name}.vrm",
                },
                "config_file": config_filename,
            }
        )

    @router.post("/asr")
    async def transcribe_audio(file: UploadFile = File(...)):
        """
        Endpoint for transcribing audio using the ASR engine
        """
        logger.info(f"Received audio file for transcription: {file.filename}")

        try:
            contents = await file.read()

            # Validate minimum file size
            if len(contents) < 44:  # Minimum WAV header size
                raise ValueError("Invalid WAV file: File too small")

            # Decode the WAV header and get actual audio data
            wav_header_size = 44  # Standard WAV header size
            audio_data = contents[wav_header_size:]

            # Validate audio data size
            if len(audio_data) % 2 != 0:
                raise ValueError("Invalid audio data: Buffer size must be even")

            # Convert to 16-bit PCM samples to float32
            try:
                audio_array = (
                    np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
                    / 32768.0
                )
            except ValueError as e:
                raise ValueError(
                    f"Audio format error: {str(e)}. Please ensure the file is 16-bit PCM WAV format."
                )

            # Validate audio data
            if len(audio_array) == 0:
                raise ValueError("Empty audio data")

            if default_context_cache.asr_engine is None:
                raise ValueError("ASR is disabled")
            text = await default_context_cache.asr_engine.async_transcribe_np(
                audio_array
            )
            logger.info(f"Transcription result: {text}")
            return {"text": text}

        except ValueError as e:
            logger.error(f"Audio format error: {e}")
            return Response(
                content=json.dumps({"error": str(e)}),
                status_code=400,
                media_type="application/json",
            )
        except Exception as e:
            logger.error(f"Error during transcription: {e}")
            return Response(
                content=json.dumps(
                    {"error": "Internal server error during transcription"}
                ),
                status_code=500,
                media_type="application/json",
            )

    @router.websocket("/tts-ws")
    async def tts_endpoint(websocket: WebSocket):
        """WebSocket endpoint for TTS generation"""
        await websocket.accept()
        logger.info("TTS WebSocket connection established")

        try:
            while True:
                data = await websocket.receive_json()
                text = data.get("text")
                if not text:
                    continue

                logger.info(f"Received text for TTS: {text}")

                # Split text into sentences
                sentences = [s.strip() for s in text.split(".") if s.strip()]

                try:
                    # Generate and send audio for each sentence
                    for sentence in sentences:
                        sentence = sentence + "."  # Add back the period
                        file_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid4())[:8]}"
                        audio_path = (
                            await default_context_cache.tts_engine.async_generate_audio(
                                text=sentence, file_name_no_ext=file_name
                            )
                        )
                        logger.info(
                            f"Generated audio for sentence: {sentence} at: {audio_path}"
                        )

                        await websocket.send_json(
                            {
                                "status": "partial",
                                "audioPath": audio_path,
                                "text": sentence,
                            }
                        )

                    # Send completion signal
                    await websocket.send_json({"status": "complete"})

                except Exception as e:
                    logger.error(f"Error generating TTS: {e}")
                    await websocket.send_json({"status": "error", "message": str(e)})

        except WebSocketDisconnect:
            logger.info("TTS WebSocket client disconnected")
        except Exception as e:
            logger.error(f"Error in TTS WebSocket connection: {e}")
            await websocket.close()

    return router
