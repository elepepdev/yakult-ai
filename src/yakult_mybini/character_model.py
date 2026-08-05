"""
Character Model Module
=======================
Provides abstract base class for character models (Live2D and VRM)
and concrete implementations for each type.

Backward-compatible: Live2dModel in live2d_model.py remains unchanged.
"""

import json
from abc import ABC
from loguru import logger


# ---------------------------------------------------------------------------
# Standalone helpers (shared file-loading logic)
# ---------------------------------------------------------------------------


def _load_file_content(file_path: str) -> str:
    """Load the content of a file with robust encoding handling.

    Args:
        file_path: Path to the file to read.

    Returns:
        File content as a string.

    Raises:
        UnicodeError: If the file cannot be decoded with any encoding.
    """
    import chardet

    encodings = ["utf-8", "utf-8-sig", "gbk", "gb2312", "ascii"]
    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue

    try:
        with open(file_path, "rb") as f:
            raw = f.read()
        detected = chardet.detect(raw)
        enc = detected.get("encoding")
        if enc:
            return raw.decode(enc)
    except Exception as e:
        logger.error(f"Error detecting encoding for {file_path}: {e}")

    raise UnicodeError(f"Failed to decode {file_path} with any encoding")


def _lookup_model_dict(
    model_name: str, model_dict_path: str = "model_dict.json"
) -> dict:
    """Look up a model's information in *model_dict.json*.

    Args:
        model_name: Name of the model to look up.
        model_dict_path: Path to the model dictionary JSON file.

    Returns:
        Dictionary of model information.

    Raises:
        FileNotFoundError: If the model dictionary file doesn't exist.
        json.JSONDecodeError: If the JSON is malformed.
        KeyError: If the model name is not found.
    """
    try:
        content = _load_file_content(model_dict_path)
        model_dict = json.loads(content)
    except FileNotFoundError:
        logger.critical(f"Model dictionary file not found at {model_dict_path}.")
        raise
    except json.JSONDecodeError as e:
        logger.critical(f"Error decoding JSON from {model_dict_path}.")
        raise e
    except UnicodeError as e:
        logger.critical(f"Error reading {model_dict_path}.")
        raise e
    except Exception as e:
        logger.critical(f"Unexpected error reading {model_dict_path}.")
        raise e

    matched = next((m for m in model_dict if m.get("name") == model_name), None)
    if matched is None:
        logger.critical(f"Model '{model_name}' not found in {model_dict_path}.")
        raise KeyError(f"Model '{model_name}' not found in {model_dict_path}.")

    # Default type to 'live2d' for backward compatibility
    if "type" not in matched:
        matched["type"] = "live2d"

    return matched


# ---------------------------------------------------------------------------
# VRM expression auto-discovery
# ---------------------------------------------------------------------------

# Standard VRM blend-shape name → AI tag mapping
_VRM_BLEND_TO_TAG: dict[str, str] = {
    "neutral": "neutral",
    "happy": "joy",
    "angry": "anger",
    "sad": "sadness",
    "surprised": "surprise",
    "relaxed": "relaxed",
}

# Expressions that are NOT emotions (visemes, blinks, etc.)
_NON_EMOTION_EXPRESSIONS: set[str] = {
    "aa", "ee", "ih", "oh", "ou",           # visemes
    "blink", "blinkLeft", "blinkRight",       # auto-blink
}


def build_emotion_map_from_vrm_expressions(
    vrm_expressions: list[str],
    existing_map: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build an emotion map from VRM expression names discovered on the model.

    * Standard blend shapes (happy, angry, …) are mapped to canonical AI tags
      (joy, anger, …).
    * Any *additional* custom expressions (e.g. ``wink``, ``pout``) are added
      using the expression name as both the tag and blend-shape name.
    * Entries already present in *existing_map* are kept as-is so manual
      overrides are never lost.

    Returns:
        A ``{tag: blend_shape}`` dictionary suitable for ``model_dict.json``.
    """
    merged: dict[str, str] = dict(existing_map or {})

    for expr in vrm_expressions:
        expr_lower = expr.lower()
        if expr_lower in _NON_EMOTION_EXPRESSIONS:
            continue
        tag = _VRM_BLEND_TO_TAG.get(expr_lower, expr_lower)
        if tag in merged:
            continue  # keep existing override
        merged[tag] = expr_lower

    return merged


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class CharacterModel(ABC):
    """Abstract base class for all character display models.

    Attributes:
        model_name: The name of this model.
        model_info: Full dictionary from *model_dict.json*.
        emo_map:  Lowercase-keyed emotion map (key → expression value).
        emo_str:  Space-separated string of ``[emotion]`` tags.
        model_type: ``"live2d"`` or ``"vrm"``.
    """

    model_name: str
    model_info: dict
    emo_map: dict
    emo_str: str
    model_type: str = "unknown"

    def __init__(
        self, model_name: str, model_dict_path: str = "model_dict.json"
    ) -> None:
        self.model_name = model_name
        self.model_dict_path = model_dict_path
        self.model_info = _lookup_model_dict(model_name, model_dict_path)
        self.model_type = self.model_info.get("type", "live2d")
        self._build_emo_map()

    def _build_emo_map(self) -> None:
        """Build *emo_map* from ``model_info["emotionMap"]``."""
        raw = self.model_info.get("emotionMap") or {}
        self.emo_map = {k.lower(): v for k, v in raw.items()}
        self.emo_str = " ".join(f"[{key}]," for key in self.emo_map)

    # ------------------------------------------------------------------
    # Public helpers (identical behaviour to the original Live2dModel)
    # ------------------------------------------------------------------

    def extract_emotion(self, str_to_check: str) -> list:
        """Parse emotion tags (``[joy]`` etc) from *str_to_check*.

        Returns a list of expression values (int for Live2D,
        string for VRM).
        """
        result = []
        lower = str_to_check.lower()
        i = 0
        while i < len(lower):
            if lower[i] != "[":
                i += 1
                continue
            for key in self.emo_map:
                tag = f"[{key}]"
                if lower[i : i + len(tag)] == tag:
                    result.append(self.emo_map[key])
                    i += len(tag) - 1
                    break
            i += 1
        return result

    def remove_emotion_keywords(self, target_str: str) -> str:
        """Strip emotion tags from *target_str* and return the cleaned text."""
        lower = target_str.lower()
        patterns = [("[", "]"), ("(", ")"), ("(*", "*)"), ("*", "*")]
        for key in self.emo_map:
            for left, right in patterns:
                lkey = f"{left}{key}{right}".lower()
                while lkey in lower:
                    start = lower.find(lkey)
                    end = start + len(lkey)
                    target_str = target_str[:start] + target_str[end:]
                    lower = lower[:start] + lower[end:]
        return target_str

    def to_frontend_payload(self) -> dict:
        """Serialize model info for sending to the frontend.

        Adds the ``type`` field so the frontend knows which renderer to use.
        """
        return {**self.model_info, "type": self.model_type}


# ---------------------------------------------------------------------------
# VRM model implementation
# ---------------------------------------------------------------------------

DEFAULT_VRM_VISEME_MAP: dict[str, str] = {
    "aa": "aa",
    "ee": "ee",
    "ih": "ih",
    "oh": "oh",
    "ou": "ou",
}

DEFAULT_VRM_EMOTION_MAP: dict[str, str] = {
    "neutral": "neutral",
    "joy": "happy",
    "anger": "angry",
    "sadness": "sad",
    "surprise": "surprised",
    "relaxed": "relaxed",
}


class VRMModel(CharacterModel):
    """Character model for VRM (VRoid) 3D avatars.

    Emotion values are **strings** (VRM blend-shape names) rather than
    int indexes.  The frontend Three.js / three-vrm renderer uses these
    names to call ``VRMExpressionManager.setValue(name, weight)``.
    """

    model_type: str = "vrm"

    def __init__(
        self, model_name: str, model_dict_path: str = "model_dict.json"
    ) -> None:
        super().__init__(model_name, model_dict_path)

        # Fall back to default emotion map if the model entry doesn't have one
        if not self.model_info.get("emotionMap"):
            self.model_info["emotionMap"] = dict(DEFAULT_VRM_EMOTION_MAP)
            self._build_emo_map()

        # Build viseme map for lip-sync (always populated)
        self.viseme_map: dict[str, str] = {
            **DEFAULT_VRM_VISEME_MAP,
            **(self.model_info.get("visemeMap") or {}),
        }

    def to_frontend_payload(self) -> dict:
        """Include viseme mapping for frontend lip-sync."""
        payload = super().to_frontend_payload()
        payload["visemeMap"] = self.viseme_map
        return payload


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_character_model(
    model_name: str,
    model_type: str | None = None,
    model_dict_path: str = "model_dict.json",
) -> CharacterModel:
    """Instantiate the correct ``CharacterModel`` subclass.

    Args:
        model_name: Name of the model (must exist in *model_dict.json*).
        model_type:  ``"live2d"`` or ``"vrm"``.  If ``None``, the type is
            read from the model dictionary entry (defaults to ``"live2d"``).
        model_dict_path: Path to the model dictionary JSON file.

    Returns:
        A ``Live2dModel`` or ``VRMModel`` instance.

    Raises:
        KeyError: If *model_name* is not found in the dictionary.
    """
    if model_type is None:
        # Probe the dict to discover the type
        info = _lookup_model_dict(model_name, model_dict_path)
        model_type = info.get("type", "live2d")

    if model_type == "vrm":
        logger.info(f"Creating VRM model: {model_name}")
        return VRMModel(model_name, model_dict_path)

    logger.info(f"Creating Live2D model: {model_name}")
    # Use the original Live2dModel from live2d_model.py for full backward compat
    # (but we can also return a CharacterModel-based wrapper if needed later)
    from .live2d_model import Live2dModel as OrigLive2dModel

    return OrigLive2dModel(model_name, model_dict_path)
