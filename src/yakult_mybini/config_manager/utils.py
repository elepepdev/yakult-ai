# config_manager/utils.py
import yaml
from pathlib import Path
from typing import Union, Dict, Any, TypeVar
from pydantic import BaseModel, ValidationError
import os
import re
import json
import chardet
from uuid import uuid4
from loguru import logger

from .main import Config

T = TypeVar("T", bound=BaseModel)


def _auto_discover_vrm_models() -> int:
    """
    Scan ``vrm-models/`` for .vrm files that are not yet registered in
    ``model_dict.json``.  For each unregistered file:
      1. Add an entry to ``model_dict.json`` with default emotion/viseme maps.
      2. Create a minimal ``characters/vrm_<name>.yaml`` config if missing.

    Returns the number of newly registered models.
    """
    vrm_dir = "vrm-models"
    model_dict_path = "model_dict.json"
    characters_dir = "characters"

    if not os.path.isdir(vrm_dir):
        return 0

    # Load existing model_dict
    model_dict: list[dict] = []
    if os.path.exists(model_dict_path):
        try:
            with open(model_dict_path, "r", encoding="utf-8") as f:
                model_dict = json.load(f)
        except Exception:
            model_dict = []

    # Build a set of already-registered VRM names
    registered_names = {
        e["name"] for e in model_dict if e.get("type") == "vrm"
    }

    # Collect .vrm files from the directory (flat only, skip subdirs)
    new_count = 0
    for entry in os.scandir(vrm_dir):
        if not (entry.is_file() and entry.name.lower().endswith(".vrm")):
            continue

        raw_name = entry.name[:-4]  # strip .vrm
        safe_name = "".join(c for c in raw_name if c.isalnum() or c in " _-_").strip()
        if not safe_name:
            safe_name = f"vrm_{uuid4().hex[:8]}"

        if safe_name in registered_names:
            continue

        # Register in model_dict.json
        new_entry = {
            "name": safe_name,
            "type": "vrm",
            "url": f"/vrm-models/{entry.name}",
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
        registered_names.add(safe_name)
        new_count += 1
        logger.info(f"Auto-discovered VRM model: {safe_name} ({entry.name})")

        # Create character config if missing
        os.makedirs(characters_dir, exist_ok=True)
        config_filepath = os.path.join(characters_dir, f"vrm_{safe_name}.yaml")
        if not os.path.exists(config_filepath):
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
            try:
                with open(config_filepath, "w", encoding="utf-8") as f:
                    f.write(config_yaml)
                logger.info(f"Created config for auto-discovered VRM: {config_filepath}")
            except Exception as e:
                logger.error(f"Failed to create config for {safe_name}: {e}")

    # Persist model_dict if there were new additions
    if new_count > 0:
        try:
            with open(model_dict_path, "w", encoding="utf-8") as f:
                json.dump(model_dict, f, indent=4)
            logger.info(f"model_dict.json updated with {new_count} new VRM model(s)")
        except Exception as e:
            logger.error(f"Failed to write model_dict.json: {e}")

    return new_count


def read_yaml(config_path: str) -> Dict[str, Any]:
    """
    Read the specified YAML configuration file with environment variable substitution
    and guess encoding. Return the configuration data as a dictionary.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Configuration data as a dictionary.

    Raises:
        FileNotFoundError: If the configuration file is not found.
        IOError: If the configuration file cannot be read.
    """

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    content = load_text_file_with_guess_encoding(config_path)
    if not content:
        raise IOError(f"Failed to read configuration file: {config_path}")

    # Replace environment variables
    pattern = re.compile(r"\$\{(\w+)\}")

    def replacer(match):
        env_var = match.group(1)
        return os.getenv(env_var, match.group(0))

    content = pattern.sub(replacer, content)

    try:
        return yaml.safe_load(content)
    except yaml.YAMLError as e:
        logger.critical(f"Error parsing YAML file: {e}")
        raise e


def validate_config(config_data: dict) -> Config:
    """
    Validate configuration data against the Config model.

    Args:
        config_data: Configuration data to validate.

    Returns:
        Validated Config object.

    Raises:
        ValidationError: If the configuration fails validation.
    """
    try:
        return Config(**config_data)
    except ValidationError as e:
        logger.critical(f"Error validating configuration: {e}")
        logger.error("Configuration data:")
        logger.error(config_data)
        raise e


def load_text_file_with_guess_encoding(file_path: str) -> str | None:
    """
    Load a text file with guessed encoding.

    Parameters:
    - file_path (str): The path to the text file.

    Returns:
    - str: The content of the text file or None if an error occurred.
    """
    encodings = ["utf-8", "utf-8-sig", "gbk", "gb2312", "ascii", "cp936"]

    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding) as file:
                return file.read()
        except UnicodeDecodeError:
            continue
    # If common encodings fail, try chardet to guess the encoding
    try:
        with open(file_path, "rb") as file:
            raw_data = file.read()
        detected = chardet.detect(raw_data)
        if detected["encoding"]:
            return raw_data.decode(detected["encoding"])
    except Exception as e:
        logger.error(f"Error detecting encoding for config file {file_path}: {e}")
    return None


def save_config(config: BaseModel, config_path: Union[str, Path]):
    """
    Saves a Pydantic model to a YAML configuration file.

    Args:
        config: The Pydantic model to save.
        config_path: Path to the YAML configuration file.
    """
    config_file = Path(config_path)
    config_data = config.model_dump(
        by_alias=True, exclude_none=True
    )

    try:
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, allow_unicode=True)
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Error writing YAML file: {e}")


def scan_config_alts_directory(config_alts_dir: str) -> list[dict]:
    """
    Scan the config_alts directory and return a list of config information.
    Each config info contains the filename and its display name from the config.

    Parameters:
    - config_alts_dir (str): The path to the config_alts directory.

    Returns:
    - list[dict]: A list of dicts containing config info:
        - filename: The actual config file name
        - name: Display name from config, falls back to filename if not specified
    """
    config_files = []

    # Add default config first
    default_config = read_yaml("conf.yaml")
    default_char: dict = (default_config or {}).get("character_config", {}) or {}
    default_name = default_char.get("conf_name") or "conf.yaml"
    default_type = default_char.get("model_type") or "live2d"
    config_files.append(
        {
            "filename": "conf.yaml",
            "name": default_name,
            "model_type": default_type,
        }
    )

    # Scan other configs
    for root, _, files in os.walk(config_alts_dir):
        for file in files:
            if file.endswith(".yaml"):
                config: dict = read_yaml(os.path.join(root, file))
                char: dict = (config or {}).get("character_config", {}) or {}
                char_name = char.get("conf_name") or file
                char_type = char.get("model_type") or "live2d"
                if (char_name, char_type) == (default_name, default_type):
                    logger.debug(
                        f"Skipping duplicate of active config in character list: {file}"
                    )
                    continue
                config_files.append(
                    {
                        "filename": file,
                        "name": char_name,
                        "model_type": char_type,
                    }
                )
    logger.debug(f"Found config files: {config_files}")
    return config_files


def scan_bg_directory() -> list[str]:
    bg_files = []
    bg_dir = "backgrounds"
    for root, _, files in os.walk(bg_dir):
        for file in files:
            if file.endswith((".jpg", ".jpeg", ".png", ".gif")):
                bg_files.append(file)
    return bg_files
