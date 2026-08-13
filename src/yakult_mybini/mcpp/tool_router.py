import json
import re
import math
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from loguru import logger

from .types import ToolCallObject, ToolCallFunctionObject
from .tool_manager import ToolManager


CATEGORIES_PATH = Path(__file__).parent / "tool_router_categories.json"


def _load_categories(path: str | Path = None) -> Dict[str, Any]:
    path = path or CATEGORIES_PATH
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _tokenize(text: str) -> List[str]:
    text = text.lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    return tokens


_MULTI_INTENT_SEPARATORS = re.compile(
    r"\s*(?:,|\bd[ae]n\b|\bterus\b|\blalu\b|\btrus\b|\bteros\b|\blantas\b|\bkemudian\b)\s*",
    re.IGNORECASE,
)


class ToolRouter:
    def __init__(
        self,
        tool_manager: ToolManager = None,
        categories_path: str | Path = None,
    ):
        self._tool_manager = tool_manager
        self._categories = _load_categories(categories_path)
        self._compiled = {}

        for cat_name, cat_data in self._categories.items():
            compiled_patterns = []
            for pat in cat_data.get("patterns", []):
                try:
                    compiled_patterns.append(re.compile(pat, re.IGNORECASE))
                except re.error as e:
                    logger.warning(
                        f"ToolRouter: bad regex in category '{cat_name}': {e}"
                    )
            self._compiled[cat_name] = compiled_patterns

        self._cat_names = list(self._categories.keys())
        self._vocab = self._build_vocab()
        self._cat_vectors = self._compute_cat_vectors()

    def _build_vocab(self) -> Dict[str, int]:
        vocab = {}
        for cat_data in self._categories.values():
            for kw in cat_data.get("keywords", []):
                for t in _tokenize(kw):
                    if t not in vocab:
                        vocab[t] = len(vocab)
        return vocab

    def _compute_cat_vectors(self) -> Dict[str, List[float]]:
        vectors = {}
        for cat_name, cat_data in self._categories.items():
            vec = [0.0] * len(self._vocab)
            for kw in cat_data.get("keywords", []):
                for t in _tokenize(kw):
                    idx = self._vocab.get(t)
                    if idx is not None:
                        vec[idx] += 1.0
            norm = math.sqrt(sum(v * v for v in vec))
            if norm > 0:
                vec = [v / norm for v in vec]
            vectors[cat_name] = vec
        return vectors

    def _tfidf_similarity(self, text: str) -> List[Tuple[str, float]]:
        tokens = _tokenize(text)
        if not tokens:
            return []
        input_vec = [0.0] * len(self._vocab)
        for t in tokens:
            idx = self._vocab.get(t)
            if idx is not None:
                input_vec[idx] += 1.0
        inorm = math.sqrt(sum(v * v for v in input_vec))
        if inorm > 0:
            input_vec = [v / inorm for v in input_vec]
        scores = []
        for cat_name in self._cat_names:
            cat_vec = self._cat_vectors.get(cat_name, [])
            if not cat_vec:
                continue
            dot = sum(a * b for a, b in zip(input_vec, cat_vec))
            scores.append((cat_name, dot))
        scores.sort(key=lambda x: -x[1])
        return scores

    def _regex_match(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        best_cat = None
        best_len = -1
        for cat_name in self._cat_names:
            for pattern in self._compiled.get(cat_name, []):
                m = pattern.search(text_lower)
                if m:
                    matched_len = len(m.group(0))
                    if matched_len > best_len:
                        best_len = matched_len
                        best_cat = cat_name
        return best_cat

    def _multi_intent_split(self, text: str) -> List[str]:
        parts = _MULTI_INTENT_SEPARATORS.split(text)
        return [p.strip() for p in parts if p.strip()]

    def _extract_parameters(self, tool_name: str, user_text: str) -> Dict[str, Any]:
        params = {}
        text_lower = user_text.lower()

        if tool_name == "search_youtube":
            q = self._extract_query_after_keywords(
                text_lower, ["cari", "putar", "lagu", "musik", "search", "play"]
            )
            if q:
                params["query"] = q
            else:
                params["query"] = text_lower
            params["max_results"] = 5

        elif tool_name == "play_youtube":
            if "video_url" not in params:
                params["video_url"] = ""
            if "title" not in params:
                params["title"] = ""

        elif tool_name == "web_search":
            q = self._extract_query_after_keywords(
                text_lower,
                ["cari", "search", "google", "googling", "tentang", "cek", "info"],
            )
            if q:
                params["query"] = q
            else:
                params["query"] = text_lower
            params["max_results"] = 10

        elif tool_name == "search_news":
            q = self._extract_query_after_keywords(
                text_lower, ["berita", "news", "cari", "search"]
            )
            params["query"] = q or text_lower
            params["max_results"] = 10
            if any(
                w in text_lower
                for w in ["hari ini", "today", "baru", "terbaru", "recent"]
            ):
                params["timelimit"] = "d"
            elif any(w in text_lower for w in ["minggu ini", "this week", "seminggu"]):
                params["timelimit"] = "w"

        elif tool_name == "web_fetch":
            urls = re.findall(r"https?://[^\s,]+", user_text)
            if urls:
                params["url"] = urls[0]
            params["max_chars"] = 8000

        elif tool_name == "open_app":
            target = self._extract_query_after_keywords(
                text_lower, ["buka", "open", "jalankan", "start"]
            )
            params["target"] = target or text_lower

        elif tool_name == "close_app":
            target = self._extract_query_after_keywords(text_lower, ["tutup", "close"])
            params["target"] = target or text_lower

        elif tool_name == "focus_app":
            target = self._extract_query_after_keywords(
                text_lower, ["focus", "fokus", "pindah ke"]
            )
            params["target"] = target or text_lower

        elif tool_name == "open_url":
            urls = re.findall(r"https?://[^\s,]+", user_text)
            if urls:
                params["url"] = urls[0]
            else:
                params["url"] = user_text

        elif tool_name == "web_fetch":
            urls = re.findall(r"https?://[^\s,]+", user_text)
            if urls:
                params["url"] = urls[0]
            params["max_chars"] = 8000

        elif tool_name == "type_text":
            q = self._extract_query_after_keywords(
                text_lower, ["ketik", "tulis", "type"]
            )
            params["text"] = q or text_lower
            params["grid_cell"] = self._extract_grid_cell(user_text)

        elif tool_name == "press_key":
            key_map = {
                "enter": "enter",
                "esc": "escape",
                "escape": "escape",
                "tab": "tab",
                "spasi": "space",
                "space": "space",
                "backspace": "backspace",
                "delete": "delete",
                "up": "up",
                "down": "down",
                "left": "left",
                "right": "right",
            }
            k = self._extract_query_after_keywords(text_lower, ["tekan", "press"])
            if k:
                for alias, actual in key_map.items():
                    if alias in k:
                        params["target"] = actual
                        break
                if "target" not in params:
                    params["target"] = k.split()[0] if k.split() else k

        elif tool_name == "hotkey":
            params["keys"] = ["ctrl", "c"]

        elif tool_name in ("click", "x11_click"):
            params["grid_cell"] = self._extract_grid_cell(user_text)

        elif tool_name in ("run_command", "run_sudo_command"):
            q = self._extract_query_after_keywords(
                text_lower, ["run", "jalan", "jalankan", "command", "terminal", "sudo"]
            )
            params["target"] = q or text_lower

        elif tool_name == "install_package":
            q = self._extract_query_after_keywords(text_lower, ["install", "pasang"])
            params["package_name"] = q or text_lower
            if "aur" in text_lower or "a u r" in text_lower:
                params["use_aur"] = True

        elif tool_name == "remove_package":
            q = self._extract_query_after_keywords(
                text_lower, ["remove", "uninstall", "hapus"]
            )
            params["package_name"] = q or text_lower
            if "complete" in text_lower or "total" in text_lower:
                params["mode"] = "complete"
            elif "standard" in text_lower:
                params["mode"] = "standard"
            else:
                params["mode"] = "cascade"

        elif tool_name == "search_packages":
            q = self._extract_query_after_keywords(text_lower, ["cari", "search"])
            params["query"] = q or text_lower
            if (
                "local" in text_lower
                or "terinstall" in text_lower
                or "terpasang" in text_lower
            ):
                params["local_only"] = True

        elif tool_name == "delete_file":
            q = self._extract_query_after_keywords(
                text_lower, ["hapus", "delete", "remove"]
            )
            params["path"] = q or text_lower
            if "force" in text_lower or "paksa" in text_lower:
                params["force"] = True

        elif tool_name == "store_memory":
            q = self._extract_query_after_keywords(
                text_lower,
                ["ingat", "simpan", "catat", "remember", "store", "memorize"],
            )
            params["fact"] = q or text_lower
            for cat in ["preference", "personal", "task", "fact"]:
                if cat in text_lower:
                    params["category"] = cat
                    break

        elif tool_name == "set_grid_spec":
            m = re.search(r"(8x6|10x10|6x4)", user_text)
            params["grid_spec"] = m.group(1) if m else "8x6"

        elif tool_name == "get_pkgbuild":
            q = self._extract_query_after_keywords(text_lower, ["pkgbuild", "check"])
            params["package_name"] = q or text_lower

        return params

    def _extract_query_after_keywords(
        self, text: str, keywords: List[str]
    ) -> Optional[str]:
        for kw in keywords:
            pattern = re.compile(
                r"(?:^|\b)"
                + re.escape(kw)
                + r"\b\s*(?:tentang|soal|informasi|info)?\s*(.+)",
                re.IGNORECASE,
            )
            m = pattern.search(text)
            if m:
                rest = m.group(1).strip().rstrip(",.!?;")
                rest = _MULTI_INTENT_SEPARATORS.sub(" ", rest).strip()
                if rest and len(rest) > 1:
                    return rest
        return None

    def _extract_grid_cell(self, text: str) -> Optional[str]:
        m = re.search(r"\b([A-Ha-h][1-8])\b", text)
        return m.group(1).upper() if m else None

    def route(
        self, user_text: str, confidence_threshold: float = 0.15
    ) -> List[ToolCallObject]:
        intents = self._multi_intent_split(user_text)
        results: List[ToolCallObject] = []

        for intent in intents:
            cat_name = self._regex_match(intent)
            if cat_name is None:
                scores = self._tfidf_similarity(intent)
                if scores and scores[0][1] >= confidence_threshold:
                    cat_name = scores[0][0]

            if cat_name is None:
                logger.debug(f"ToolRouter: no match for intent '{intent[:60]}'")
                continue

            cat_data = self._categories.get(cat_name, {})
            tools_by_server = cat_data.get("tools", {})

            for server_name, tool_names in tools_by_server.items():
                for tool_name in tool_names:
                    if not tool_name:
                        continue
                    args = self._extract_parameters(tool_name, intent)
                    tc = ToolCallObject(
                        id=f"rt_{uuid.uuid4().hex[:8]}",
                        type="function",
                        function=ToolCallFunctionObject(
                            name=tool_name,
                            arguments=json.dumps(args),
                        ),
                    )
                    results.append(tc)

        return results
