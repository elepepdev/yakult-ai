import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from loguru import logger
from uuid import uuid4

from ..agent.stateless_llm.stateless_llm_interface import StatelessLLMInterface

MEMORIES_FILE = "memories/memories.json"
MAX_MEMORIES = 100
INJECT_COUNT = 8

EXTRACT_SYSTEM_PROMPT = """You are an extremely strict fact extractor. Extract ONLY explicit, high-quality, long-term facts about the USER.

CRITICAL RULE — DO NOT INFER OR GUESS:
Only extract facts that the user EXPLICITLY and DIRECTLY stated about themselves. Never guess, infer, or conclude something from minimal context.

ABOUT NAMES:
- Only extract name if user says EXACT phrases like "my name is X", "nama saya X", "panggil aku X", "I'm X" (as self-introduction).
- A single word, greeting, or casual response is NEVER evidence of a name.
- "User's name is X" inferred from a single word is WRONG. Do not do this.

RULES:
1. ONLY extract from lines starting with "User:". NEVER extract from "AI:" lines.
2. Only extract EXPLICIT permanent facts: name, age, location, occupation, long-term hobbies, relationships.
3. DO NOT extract: inferred names, current mood, temporary states, one-time activities, opinions, greetings, jokes, casual remarks, single-word responses.
4. DO NOT extract obvious/redundant facts (e.g. "User speaks Indonesian").
5. A single mention in passing is NOT a long-term fact.
6. Each fact must be EXPLICITLY stated, not implied.
7. If nothing EXPLICIT and PERMANENT is stated, return [].

Return ONLY a JSON array of strings. No explanations.
Valid: ["User's name is Fatih.", "User is 14 years old.", "User has a cat."]
Invalid: ["User likes coffee.", "User said hi.", "User's name is Hawo.", "User is typing.", "User speaks Indonesian."]"""


class MemoryItem:
    def __init__(
        self,
        fact: str,
        category: str = "fact",
        confidence: float = 0.8,
        memory_id: Optional[str] = None,
        created_at: Optional[str] = None,
        accessed_count: int = 0,
    ):
        self.id = memory_id or f"mem_{uuid4().hex[:12]}"
        self.fact = fact
        self.category = category
        self.confidence = confidence
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.accessed_count = accessed_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "fact": self.fact,
            "category": self.category,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "accessed_count": self.accessed_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryItem":
        return cls(
            fact=data["fact"],
            category=data.get("category", "fact"),
            confidence=data.get("confidence", 0.8),
            memory_id=data.get("id"),
            created_at=data.get("created_at"),
            accessed_count=data.get("accessed_count", 0),
        )


class MemoryManager:
    def __init__(self, llm: Optional[StatelessLLMInterface] = None):
        self._llm = llm
        self._cache: Optional[List[MemoryItem]] = None

    def set_llm(self, llm: StatelessLLMInterface) -> None:
        self._llm = llm

    def _get_path(self) -> str:
        return MEMORIES_FILE

    def load(self) -> List[MemoryItem]:
        if self._cache is not None:
            return self._cache
        path = self._get_path()
        if not os.path.exists(path):
            self._cache = []
            return []
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            items = [MemoryItem.from_dict(d) for d in data]
            self._cache = items
            return items
        except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
            logger.warning(f"Failed to load memories from {path}: {e}")
            self._cache = []
            return []

    def save(self, memories: List[MemoryItem]) -> None:
        path = self._get_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = [m.to_dict() for m in memories]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        self._cache = memories

    def get_relevant(self, top_k: int = INJECT_COUNT) -> List[MemoryItem]:
        memories = self.load()
        if not memories:
            return []
        now = datetime.now(timezone.utc)
        scored = []
        for m in memories:
            try:
                created = datetime.fromisoformat(m.created_at)
            except (ValueError, TypeError):
                created = now
            recency_hours = max(0, (now - created).total_seconds() / 3600)
            recency_score = max(0, 1.0 - recency_hours / (24 * 30))
            score = (
                (m.accessed_count * 0.3) + (recency_score * 0.7) + (m.confidence * 0.2)
            )
            scored.append((score, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        selected = [m for _, m in scored[:top_k]]
        for m in selected:
            m.accessed_count += 1
        self.save(memories)
        return selected

    def merge(
        self, existing: List[MemoryItem], new_facts: List[str], category: str = "fact"
    ) -> List[MemoryItem]:
        existing_facts = []
        for item in existing:
            if item.category == category:
                merged = False
                for nf in new_facts:
                    if self._is_duplicate(item.fact, nf):
                        item.confidence = min(1.0, item.confidence + 0.05)
                        item.accessed_count += 1
                        merged = True
                        new_facts.remove(nf)
                        break
                if not merged:
                    existing_facts.append(item)
            else:
                existing_facts.append(item)
        for nf in new_facts:
            existing_facts.append(MemoryItem(fact=nf, category=category))
        return existing_facts

    @staticmethod
    def _is_duplicate(existing_fact: str, new_fact: str) -> bool:
        """Check if new_fact is a duplicate or near-duplicate of existing_fact."""
        ef = existing_fact.lower().strip()
        nf = new_fact.lower().strip()
        if ef == nf:
            return True
        if nf in ef or ef in nf:
            return True
        we = set(re.findall(r"\w+", ef))
        wn = set(re.findall(r"\w+", nf))
        if we and wn:
            overlap = len(we & wn) / max(len(we), len(wn))
            if overlap > 0.75:
                return True
        return False

    def prune(
        self, memories: List[MemoryItem], max_count: int = MAX_MEMORIES
    ) -> List[MemoryItem]:
        if len(memories) <= max_count:
            return memories
        memories.sort(key=lambda m: (m.accessed_count, m.confidence))
        return memories[-max_count:]

    async def extract_memories(self, text: str) -> None:
        if not self._llm or not text:
            return
        try:
            stream = self._llm.chat_completion(
                messages=[{"role": "user", "content": text}],
                system=EXTRACT_SYSTEM_PROMPT,
                tools=None,
            )
            full = ""
            async for chunk in stream:
                if isinstance(chunk, str):
                    full += chunk
            json_str = self._extract_json(full)
            if not json_str:
                logger.debug("No JSON found in memory extraction response.")
                return
            extracted = json.loads(json_str)
            if not isinstance(extracted, list):
                extracted = [extracted]
            facts = [
                str(e) if isinstance(e, str) else json.dumps(e) for e in extracted if e
            ]
            if not facts:
                return
            facts = self._filter_inferred_facts(facts, text)
            if not facts:
                return
            existing = self.load()
            for fact in facts:
                category = self._classify_fact(fact)
                existing = self.merge(existing, [fact], category)
            existing = self.prune(existing)
            self.save(existing)
            logger.info(f"Extracted {len(facts)} memory fact(s)")
        except Exception as e:
            logger.warning(f"Memory extraction failed: {e}")

    def to_prompt_string(self) -> str:
        items = self.get_relevant()
        if not items:
            return ""
        lines = [f"- {m.fact}" for m in items]
        return "[LONG-TERM MEMORY]\n" + "\n".join(lines)

    @staticmethod
    def _word_overlap(a: str, b: str) -> float:
        wa = set(re.findall(r"\w+", a.lower()))
        wb = set(re.findall(r"\w+", b.lower()))
        if not wa or not wb:
            return 0.0
        return len(wa & wb) / max(len(wa), len(wb))

    @staticmethod
    def _filter_inferred_facts(facts: List[str], original_text: str) -> List[str]:
        """Remove facts that appear to be inferred/guessed rather than explicitly stated."""
        tl = original_text.lower()
        filtered = []
        for fact in facts:
            fl = fact.lower()
            if any(
                kw in fl
                for kw in (
                    "name",
                    "nama",
                    "umur",
                    "age",
                    "tinggal",
                    "live in",
                    "kerja",
                    "work at",
                    "sekolah",
                    "school at",
                    "berusia",
                )
            ):
                has_explicit = bool(
                    re.search(
                        r"(?:nama\s+saya|my\s+name\s+is|panggil\s+aku|namaku|name\'s)",
                        tl,
                    )
                )
                if not has_explicit:
                    logger.debug(f"Rejected inferred fact: {fact}")
                    continue
            filtered.append(fact)
        return filtered

    @staticmethod
    def _extract_json(text: str) -> Optional[str]:
        start = text.find("[")
        if start == -1:
            start = text.find("{")
            if start == -1:
                return None
            end = text.rfind("}")
            if end == -1 or end < start:
                return None
            return text[start : end + 1]
        end = text.rfind("]")
        if end == -1 or end < start:
            return None
        return text[start : end + 1]

    @staticmethod
    def _classify_fact(fact: str) -> str:
        fl = fact.lower()
        if any(
            kw in fl
            for kw in (
                "suka",
                "like",
                "love",
                "prefer",
                "favorit",
                "hobi",
                "hobby",
                "sering",
                "often",
            )
        ):
            return "preference"
        if any(
            kw in fl
            for kw in (
                "nama",
                "name",
                "umur",
                "age",
                "tinggal",
                "live",
                "kerja",
                "work",
                "sekolah",
                "school",
            )
        ):
            return "personal"
        if any(
            kw in fl
            for kw in (
                "lagi",
                "sedang",
                "currently",
                "mau",
                "akan",
                "going to",
                "proyek",
                "project",
                "tugas",
                "task",
            )
        ):
            return "task"
        return "fact"
