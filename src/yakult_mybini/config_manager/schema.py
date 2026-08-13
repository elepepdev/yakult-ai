"""Build a serializable schema of the Config model for the frontend settings GUI.

Walks the pydantic ``Config`` model tree and produces a JSON-safe description
of every field (type, current value, description, options), using the existing
``I18nMixin.DESCRIPTIONS`` metadata. Secrets (api keys, passwords) are masked.
"""

from typing import Any, Dict, List, Literal, Optional, Union, get_args, get_origin
from types import UnionType

from pydantic import BaseModel
from pydantic_core import PydanticUndefined


def _is_model(inner: Any) -> bool:
    """True for pydantic BaseModel subclasses and pydantic dataclasses."""
    if isinstance(inner, type) and issubclass(inner, BaseModel):
        return True
    try:
        from pydantic.dataclasses import is_pydantic_dataclass

        return is_pydantic_dataclass(inner)
    except Exception:
        return False


def _model_fields(model: Any) -> dict:
    """Get pydantic field metadata for a BaseModel or pydantic dataclass."""
    return getattr(model, "model_fields", None) or getattr(
        model, "__pydantic_fields__", {}
    )


from .main import Config  # noqa: E402

SECRET_MASK = "********"

SECRET_FIELD_MARKERS = ("api_key", "password", "token", "secret")


def _is_secret(field_name: str) -> bool:
    return any(marker in field_name.lower() for marker in SECRET_FIELD_MARKERS)


def _mask(value: Any) -> Any:
    if value is None:
        return None
    return SECRET_MASK


def _type_name(annotation: Any) -> str:
    return getattr(annotation, "__name__", str(annotation))


def _literal_options(annotation: Any) -> Optional[List[str]]:
    origin = get_origin(annotation)
    if origin is None:
        return None
    if origin is Literal:
        return [str(a) for a in get_args(annotation)]
    for arg in get_args(annotation):
        opts = _literal_options(arg)
        if opts:
            return opts
    return None


def _is_optional(annotation: Any) -> bool:
    origin = get_origin(annotation)
    return origin in (Optional, Union, UnionType) and type(None) in get_args(annotation)


def _unwrap(annotation: Any) -> Any:
    """Strip Optional/Annotated wrappers to get the inner type."""
    from typing import Annotated

    origin = get_origin(annotation)
    if origin is Annotated:
        return _unwrap(get_args(annotation)[0])
    if origin in (Optional, Union, UnionType):
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return _unwrap(args[0])
    return annotation


def _field_value(obj: Any, field_name: str) -> Any:
    """Read a field value by its python name (alias may differ)."""
    if obj is None:
        return None
    try:
        return getattr(obj, field_name)
    except AttributeError:
        try:
            return getattr(obj, obj.model_fields[field_name].alias)
        except (KeyError, AttributeError):
            return None


def _to_schema(
    model: type[BaseModel],
    obj: Any,
    path: str,
    lang: str,
    max_depth: int,
    depth: int = 0,
) -> Dict[str, Any]:
    """Serialize one pydantic model into a schema node."""
    children = []
    model_fields = _model_fields(model)
    descriptions = getattr(model, "DESCRIPTIONS", {})

    for field_name, field in model_fields.items():
        annotation = field.annotation
        inner = _unwrap(annotation)
        value = _field_value(obj, field_name)
        field_path = f"{path}.{field_name}" if path else field_name

        desc = descriptions.get(field_name)
        description = desc.get_text(lang) if desc else None
        notes = desc.get_notes(lang) if desc else None
        if not description:
            description = field_name.replace("_", " ").title()

        node: Dict[str, Any] = {
            "name": field_name,
            "path": field_path,
            "description": description,
            "notes": notes,
            "secret": _is_secret(field_name),
            "default": None,
        }
        if field.default not in (None, PydanticUndefined):
            node["default"] = field.default

        # nested pydantic model -> recurse
        if _is_model(inner):
            node["type"] = "object"
            if depth < max_depth:
                node["children"] = _to_schema(
                    inner, value, field_path, lang, max_depth, depth + 1
                )["children"]
            else:
                node["children"] = []
            children.append(node)
            continue

        origin = get_origin(inner)
        if origin is None:
            if inner is bool:
                node["type"] = "boolean"
            elif inner is int:
                node["type"] = "number"
            elif inner is float:
                node["type"] = "number"
            else:
                node["type"] = "string"
                if isinstance(value, str) and len(value) > 80:
                    node["multiline"] = True
        elif origin is Literal:
            node["type"] = "enum"
            node["options"] = _literal_options(annotation)
        elif origin in (list, List):
            node["type"] = "array"
            args = get_args(inner)
            if args:
                elem = _unwrap(args[0])
                node["item_type"] = _type_name(elem)
                if (
                    isinstance(elem, type)
                    and issubclass(elem, BaseModel)
                    and depth < max_depth
                ):
                    node["children"] = [
                        _to_schema(
                            elem, v, f"{field_path}.{i}", lang, max_depth, depth + 1
                        )
                        for i, v in enumerate(value or [])
                    ]
                    node["item_model"] = True
        elif origin is dict:
            node["type"] = "dict"
            if isinstance(value, dict):
                node["keys"] = sorted(value.keys())
        else:
            node["type"] = "string"

        # mask secret values
        if node["secret"]:
            node["value"] = _mask(value)
        else:
            node["value"] = value

        children.append(node)

    return {
        "name": model.__name__,
        "path": path,
        "type": "object",
        "children": children,
    }


def build_config_schema(
    config: Config, lang: str = "en", max_depth: int = 6
) -> Dict[str, Any]:
    """Serialize the full ``Config`` model into a frontend-renderable schema.

    Args:
        config: The (validated) config object to serialize.
        lang: Language code for descriptions ("en" or "zh").
        max_depth: Recursion limit for nested models.

    Returns:
        dict: schema tree where every leaf carries ``path``, ``type``, ``value``,
            and (where available) ``description``/``options``/``secret``.
    """
    return _to_schema(Config, config, "", lang, max_depth)


def apply_updates(config: Config, updates: Dict[str, Any]) -> Config:
    """Apply dot-path updates to a config object, validating via pydantic.

    Secret fields sent as ``SECRET_MASK`` are skipped (keep existing value).

    Args:
        config: Existing config.
        updates: Mapping of ``"a.b.c"`` -> new value.

    Returns:
        Config: A new Config instance with updates applied.

    Raises:
        pydantic.ValidationError: if the merged config is invalid.
    """
    data = config.model_dump(by_alias=True)

    for path, value in updates.items():
        if value is None:
            continue
        parts = path.split(".")
        node = data
        for key in parts[:-1]:
            if isinstance(node, dict):
                node = node.setdefault(key, {})
            else:
                node = getattr(node, key, {})
        leaf = parts[-1]
        # skip masked secrets
        if value == SECRET_MASK:
            continue
        if isinstance(node, dict):
            node[leaf] = value
        else:
            setattr(node, leaf, value)

    return Config(**data)
