import time
import random
import datetime
import json
import os
import asyncio
from collections import deque
from typing import Optional, Callable, Any
from loguru import logger
from pydantic import Field
from pydantic.dataclasses import dataclass

from ..utils.stream_audio import prepare_audio_payload
from ..agent.output_types import Actions


# ── VRMA animation catalog (filenames without extension) ──────────────
VRMA_ANIMATIONS = [
    "greeting",
    "squat",
    "spin",
    "shoot",
    "peaceSign",
    "modelPose",
]

VRMA_ANIMATIONS_NIGHT = [
    "greeting",
    "squat",
    "modelPose",
    "peaceSign",
]

# ── VRM expression names for blend shapes ────────────────────────────
VRM_EXPRESSIONS_HAPPY = ["happy", "surprised", "relaxed", "neutral"]
VRM_EXPRESSIONS_SAD = ["sad", "neutral", "relaxed"]
VRM_EXPRESSIONS_NEUTRAL = ["neutral", "relaxed", "happy", "sad", "surprised"]

# ── Idle thought templates by time period ────────────────────────────
IDLE_TEXTS_PAGI = [
    "Selamat pagi! Hari baru yang cerah.",
    "Pagi yang segar… aku merasa penuh energi.",
    "Semoga hari ini menyenangkan untuk kita semua.",
    "Aroma kopi di pagi hari selalu membuatku tersenyum.",
    "Pagi ini terasa sangat damai.",
    "Hari ini akan menjadi hari yang baik!",
    "Cahaya matahari pagi masuk melalui jendela…",
    "Aku suka suasana pagi yang tenang.",
]

IDLE_TEXTS_SIANG = [
    "Hmm… suasana hari ini cukup tenang.",
    "Aku sedang memikirkan sesuatu…",
    "Apa kabar dunia di luar sana?",
    "Sepertinya hari ini cerah ya.",
    "Aku harap semuanya baik-baik saja.",
    "Hmm… ada yang menarik hari ini?",
    "Duduk-duduk sambil menikmati suasana…",
    "Terkadang aku suka melamun seperti ini.",
    "Hari yang indah untuk bersantai.",
    "Aku penasaran apa yang sedang dilakukan teman-teman.",
    "Angin sepoi-sepoi membuatku rileks.",
    "Menikmati momen hening seperti ini…",
]

IDLE_TEXTS_SORE = [
    "Cahaya sore ini sangat indah.",
    "Aku suka saat-saat tenang seperti ini.",
    "Matahari mulai terbenam… pemandangan yang menenangkan.",
    "Sore hari adalah waktu favoritku.",
    "Langit jingga di ufuk barat… menakjubkan.",
    "Hari mulai beranjak sore, waktu yang tepat untuk merenung.",
    "Suasana senja selalu membuatku merasa damai.",
    "Aku suka warna langit saat senja.",
]

IDLE_TEXTS_MALAM = [
    "Malam ini terasa tenang dan damai.",
    "Bintang-bintang di langit malam selalu memesona.",
    "Waktunya untuk beristirahat…",
    "Aku suka ketenangan malam hari.",
    "Semoga mimpi indah menyertaimu.",
    "Cahaya bulan menerangi malam…",
    "Malam adalah waktu untuk merenung.",
    "Tidak ada yang lebih nyaman dari malam yang tenang.",
]

DREAM_TEXTS = [
    "*{name} mengigau dalam tidur…*",
    "*{name} tersenyum sambil tidur…*",
    "*{name} bergerak gelisah dalam tidur…*",
    "*{name} bergumam sesuatu dalam mimpi…*",
    "*{name} tidur dengan tenang…*",
    "*{name} bermimpi tentang petualangan…*",
    "*{name} tertawa kecil dalam tidur…*",
]

DREAM_SYSTEM_PROMPT = (
    "Kamu adalah {name}, karakter virtual yang sedang tidur dan bermimpi. "
    "Hasilkan 1 kalimat pendek dalam Bahasa Indonesia tentang mimpi yang "
    "sedang kamu alami. Mimpi itu bisa indah, aneh, atau lucu.\n\n"
    "Kepribadianmu:\n{personality}\n\n"
    "Langsung hasilkan isi mimpimu, seolah kau mengigau saat tidur. "
    "Jangan gunakan tanda kutip atau markup."
)

PROACTIVE_SPEAK_PROMPT = (
    "Kamu adalah {name}, karakter virtual yang ramah. "
    "Kamu sedang mengobrol dengan teman dekatmu.\n\n"
    "Kepribadianmu:\n{personality}\n\n"
    "{time_context}"
    "{memory_context}"
    "{screen_context}"
    "Hasilkan 1-2 kalimat pendek dalam Bahasa Indonesia untuk memulai "
    "percakapan secara alami. Bicaralah seolah kamu baru sadar dari lamunan "
    "dan ingin mengajak temanmu mengobrol.\n\n"
    "Jangan gunakan tanda kutip, tanda kurung, atau markup apapun."
)

SUBCONSCIOUS_SYSTEM_PROMPT = (
    "Kamu adalah {name}, karakter virtual yang sedang melamun. "
    "Hasilkan 1-2 kalimat pendek dalam Bahasa Indonesia tentang apa yang "
    "sedang kamu pikirkan atau rasakan saat ini. Jadilah natural, pribadi, "
    "dan sesuai dengan karaktermu.\n\n"
    "Kepribadianmu:\n{personality}\n\n"
    "{time_context}"
    "{memory_context}"
    "{screen_context}"
    "Jangan gunakan tanda kutip, tanda kurung, atau markup. "
    "Langsung hasilkan pikiranmu apa adanya, seolah-olah monolog internal."
)


@dataclass
class IdleLifeConfig:
    """Configuration for the autonomous idle life system."""

    enabled: bool = Field(False, alias="enabled")
    min_interval_sec: int = Field(30, alias="min_interval_sec")
    max_interval_sec: int = Field(60, alias="max_interval_sec")
    time_before_idle_sec: int = Field(15, alias="time_before_idle_sec")
    time_to_sleep_sec: int = Field(120, alias="time_to_sleep_sec")
    random_animation_enabled: bool = Field(True, alias="random_animation_enabled")
    idle_text_enabled: bool = Field(True, alias="idle_text_enabled")
    subconscious_enabled: bool = Field(True, alias="subconscious_enabled")
    proactive_speak_enabled: bool = Field(True, alias="proactive_speak_enabled")
    time_aware_enabled: bool = Field(True, alias="time_aware_enabled")
    mood_enabled: bool = Field(True, alias="mood_enabled")
    dream_enabled: bool = Field(True, alias="dream_enabled")
    screen_aware_enabled: bool = Field(True, alias="screen_aware_enabled")
    wake_greeting_enabled: bool = Field(True, alias="wake_greeting_enabled")
    persistence_enabled: bool = Field(True, alias="persistence_enabled")
    persistence_path: str = Field("memories", alias="persistence_path")
    music_enabled: bool = Field(True, alias="music_enabled")
    idle_text_path: Optional[str] = Field(None, alias="idle_text_path")
    vrma_list: Optional[list] = Field(None, alias="vrma_list")
    vrma_night_list: Optional[list] = Field(None, alias="vrma_night_list")


# ── Mood persistence helpers ─────────────────────────────────────────

def _mood_path(base: str) -> str:
    return os.path.join(base, "idle_mood.json")


def _load_mood(base: str) -> float:
    path = _mood_path(base)
    try:
        with open(path) as f:
            data = json.load(f)
            val = float(data.get("mood", 0.5))
            return max(0.0, min(1.0, val))
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        return 0.5


def _save_mood(base: str, mood: float) -> None:
    path = _mood_path(base)
    try:
        os.makedirs(base, exist_ok=True)
        with open(path, "w") as f:
            json.dump({"mood": round(mood, 3), "updated_at": time.time()}, f)
    except Exception as e:
        logger.warning(f"IdleLife: failed to save mood: {e}")


class IdleLifeManager:
    """State machine for autonomous character behavior during idle time.

    States:
      ACTIVE      — user is conversing with the AI
      IDLE        — no user message received, timer running
      AUTONOMOUS  — idle long enough, executing life events
      SLEEP       — idle too long, character is asleep
    """

    def __init__(
        self,
        config: IdleLifeConfig,
        websocket_send: Optional[Callable] = None,
        character_name: str = "AI",
        personality: str = "",
        subconscious_llm: Any = None,
        proactive_trigger: Optional[Callable] = None,
        music_trigger: Optional[Callable] = None,
    ):
        self._config = config
        self._send = websocket_send
        self._state: str = "ACTIVE"
        self._idle_since: Optional[float] = None
        self._last_event_time: float = 0.0
        self._event_queue: deque = deque()
        self._previous_animation: str = ""
        self._character_name: str = character_name
        self._personality: str = personality
        self._subconscious_llm: Any = subconscious_llm
        self._proactive_trigger: Optional[Callable] = proactive_trigger
        self._music_trigger: Optional[Callable] = music_trigger
        self._memory_prompt: str = ""
        self._screen_context: str = ""
        self._mood: float = _load_mood(
            config.persistence_path
        ) if config and config.persistence_enabled else 0.5
        self._last_mood_tick: float = time.time()
        self._last_persist_time: float = 0.0
        self._dream_llm_busy: bool = False
        self._wake_greeting_pending: bool = False
        self._event_cooldowns: dict = {}
        self._stats: dict = {"total_events": 0, "by_type": {}}
        self._state_broadcast_counter: int = 0

    # ── Public API ────────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        return self._config and self._config.enabled

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_asleep(self) -> bool:
        return self._state == "SLEEP"

    @property
    def mood(self) -> float:
        return self._mood

    def set_memory_prompt(self, prompt: str) -> None:
        self._memory_prompt = prompt

    def set_screen_context(self, context: str) -> None:
        self._screen_context = context

    def set_proactive_trigger(self, trigger: Callable) -> None:
        self._proactive_trigger = trigger

    def set_music_trigger(self, trigger: Callable) -> None:
        self._music_trigger = trigger

    @property
    def stats(self) -> dict:
        return dict(self._stats)

    def mark_active(self) -> None:
        """Call when user sends a message (resets idle timer)."""
        was_sleeping = self._state == "SLEEP"
        self._state = "ACTIVE"
        self._idle_since = None
        self._event_queue.clear()
        self._boost_mood(0.08)
        if was_sleeping:
            logger.info("IdleLife: woken up by user message")
            if self._config.wake_greeting_enabled:
                self._wake_greeting_pending = True

    def consume_wake_greeting(self) -> Optional[str]:
        """Return and clear pending wake greeting text, if any."""
        if not self._wake_greeting_pending:
            return None
        self._wake_greeting_pending = False
        period = self._time_period()
        greetings = {
            "pagi": "Pagi~ Aku mimpi indah sekali… Eh, kamu di sini?",
            "siang": "Haaah~ baru saja mimpi aneh… Oh, hai!",
            "sore": "Uuh~ tidur siang yang nyenyak… Ada yang menarik?",
            "malam": "Hmm? Aku ketiduran… Ada apa?",
        }
        return "*{name} terbangun.* {greeting}".format(
            name=self._character_name,
            greeting=greetings.get(period, greetings["siang"]),
        )

    def mark_idle(self) -> None:
        """Call when conversation chain ends (starts idle timer)."""
        if self._state == "ACTIVE":
            self._state = "IDLE"
            self._idle_since = time.time()
            logger.debug("IdleLife: state → IDLE")

    def set_websocket_send(self, send: Callable) -> None:
        self._send = send

    async def tick(self) -> None:
        """Called periodically (every ~5s) by background loop."""
        if not self.enabled or self._state == "ACTIVE":
            return

        self._decay_mood()

        if self._state == "SLEEP":
            await self._dream_cycle()
            return

        if self._idle_since is None:
            return

        duration = time.time() - self._idle_since
        if duration > self._config.time_to_sleep_sec:
            await self._go_to_sleep()
        elif duration > self._config.time_before_idle_sec:
            await self._autonomous_cycle()

    # ── Internal ──────────────────────────────────────────────────

    def _time_period(self) -> str:
        if not self._config.time_aware_enabled:
            return ""
        h = datetime.datetime.now().hour
        if 5 <= h < 12:
            return "pagi"
        if 12 <= h < 17:
            return "siang"
        if 17 <= h < 21:
            return "sore"
        return "malam"

    def _time_context(self) -> str:
        period = self._time_period()
        if not period:
            return ""
        mapping = {
            "pagi": "Sekarang adalah pagi hari.",
            "siang": "Sekarang adalah siang hari.",
            "sore": "Sekarang adalah sore hari.",
            "malam": "Sekarang adalah malam hari.",
        }
        return f"Situasi: {mapping.get(period, '')}\n"

    def _memory_context(self) -> str:
        if not self._memory_prompt:
            return ""
        return f"{self._memory_prompt}\n\n"

    def _screen_context_str(self) -> str:
        if not self._config.screen_aware_enabled or not self._screen_context:
            return ""
        return f"Kondisi layar: {self._screen_context}\n\n"

    def _boost_mood(self, amount: float) -> None:
        if not self._config.mood_enabled:
            return
        self._mood = min(1.0, self._mood + amount)

    def _decay_mood(self) -> None:
        if not self._config.mood_enabled:
            return
        now = time.time()
        if now - self._last_mood_tick < 30:
            return
        self._last_mood_tick = now
        if self._mood > 0.5:
            self._mood = max(0.5, self._mood - 0.02)
        elif self._mood < 0.45:
            self._mood = min(0.5, self._mood + 0.01)
        self._persist_mood()

    def _persist_mood(self) -> None:
        if not self._config.persistence_enabled:
            return
        now = time.time()
        if now - self._last_persist_time < 120:
            return
        self._last_persist_time = now
        _save_mood(self._config.persistence_path, self._mood)

    def _mood_label(self) -> str:
        if self._mood >= 0.7:
            return "ceria"
        if self._mood >= 0.45:
            return "netral"
        return "melankolis"

    # ── Adaptive timing ───────────────────────────────────────────

    def _current_interval(self) -> float:
        mood_factor = 1.0
        time_factor = 1.0
        if self._config.mood_enabled:
            mood_factor = 1.3 - (self._mood * 0.6)
        if self._config.time_aware_enabled:
            period = self._time_period()
            if period == "malam":
                time_factor = 1.5
            elif period == "pagi":
                time_factor = 0.8
        base_min = self._config.min_interval_sec * mood_factor * time_factor
        base_max = self._config.max_interval_sec * mood_factor * time_factor
        return random.uniform(base_min, base_max)

    def _event_on_cooldown(self, event_type: str) -> bool:
        cooldowns = {
            "Subconscious": 60,
            "ProactiveSpeak": 120,
            "PlayMusic": 90,
            "VRMA": 30,
            "IdleText": 20,
        }
        cd = cooldowns.get(event_type, 0)
        if cd == 0:
            return False
        last = self._event_cooldowns.get(event_type, 0.0)
        return time.time() - last < cd

    def _mark_event_fired(self, event_type: str) -> None:
        self._event_cooldowns[event_type] = time.time()
        self._stats["total_events"] += 1
        self._stats["by_type"][event_type] = self._stats["by_type"].get(event_type, 0) + 1

    # ── Config overrides ──────────────────────────────────────────

    def _vrma_pool(self) -> list:
        period = self._time_period()
        if period == "malam":
            return list(self._config.vrma_night_list or VRMA_ANIMATIONS_NIGHT)
        return list(self._config.vrma_list or VRMA_ANIMATIONS)

    def _load_custom_idle_texts(self) -> Optional[dict]:
        path = self._config.idle_text_path
        if not path:
            return None
        try:
            with open(path) as f:
                data = json.load(f)
                return {
                    k: v for k, v in data.items()
                    if k in ("pagi", "siang", "sore", "malam")
                }
        except Exception as e:
            logger.warning(f"IdleLife: failed to load custom texts from '{path}': {e}")
            return None

    def _pick_idle_texts(self) -> list:
        custom = self._load_custom_idle_texts()
        if custom:
            period = self._time_period()
            pool = custom.get(period)
            if pool:
                return pool
        pools = {
            "pagi": IDLE_TEXTS_PAGI,
            "siang": IDLE_TEXTS_SIANG,
            "sore": IDLE_TEXTS_SORE,
            "malam": IDLE_TEXTS_MALAM,
        }
        return pools.get(self._time_period(), IDLE_TEXTS_SIANG)

    async def _dream_cycle(self) -> None:
        """Occasionally generate dream content while asleep."""
        if not self._config.dream_enabled or self._dream_llm_busy:
            return
        now = time.time()
        if now - self._last_event_time < self._config.min_interval_sec * 2:
            return
        self._last_event_time = now

        if random.random() > 0.35:
            return

        self._dream_llm_busy = True
        try:
            if self._subconscious_llm:
                system = DREAM_SYSTEM_PROMPT.format(
                    name=self._character_name,
                    personality=self._personality or "(karakter yang tenang)",
                )
                chunks = []
                async for chunk in self._subconscious_llm.chat_completion(
                    messages=[{"role": "user", "content": "Apa yang kau mimpikan?"}],
                    system=system,
                ):
                    if isinstance(chunk, str):
                        chunks.append(chunk)
                dream = "".join(chunks).strip()
            else:
                dream = random.choice(DREAM_TEXTS).format(name=self._character_name)

            if dream and self._send:
                await self._send(
                    json.dumps({
                        "type": "full-text",
                        "text": "*{name} bermimpi…* {dream}".format(
                            name=self._character_name, dream=dream
                        ),
                    })
                )
                logger.debug(f"IdleLife: Dream '{dream[:60]}...'")
        except Exception as e:
            logger.warning(f"IdleLife: dream LLM error: {e}")
        finally:
            self._dream_llm_busy = False

    # ── Autonomous cycle (during IDLE) ────────────────────────────

    async def _autonomous_cycle(self) -> None:
        now = time.time()
        delay = self._current_interval()
        if now - self._last_event_time < delay:
            return
        self._state = "AUTONOMOUS"
        self._last_event_time = now

        if not self._event_queue:
            self._refill_queue()

        # Skip events still on cooldown
        attempts = 0
        event_type = None
        while self._event_queue and attempts < len(self._event_queue) + 2:
            candidate = self._event_queue[0]
            if self._event_on_cooldown(candidate):
                self._event_queue.rotate(-1)
                attempts += 1
            else:
                event_type = self._event_queue.popleft()
                break

        if not event_type:
            # All events on cooldown — add a forced IdleText
            event_type = "IdleText"
            if self._event_on_cooldown("IdleText"):
                return  # wait until next cycle

        logger.debug(
            f"IdleLife: autonomous cycle "
            f"(idle={now - self._idle_since:.0f}s, "
            f"event={event_type}, mood={self._mood:.2f}, "
            f"queue={len(self._event_queue)})"
        )

        self._mark_event_fired(event_type)
        self._broadcast_state()

        if event_type == "VRMA":
            await self._exec_vrma()
        elif event_type == "IdleText":
            await self._exec_idle_text()
        elif event_type == "Subconscious":
            await self._exec_subconscious()
        elif event_type == "ProactiveSpeak":
            await self._exec_proactive_speak()
        elif event_type == "PlayMusic":
            await self._exec_play_music()

    def _refill_queue(self) -> None:
        pool = []
        if self._config.random_animation_enabled:
            pool.extend(["VRMA"] * 4)
        if self._config.idle_text_enabled:
            pool.extend(["IdleText"] * 3)
        if self._config.subconscious_enabled:
            pool.extend(["Subconscious"] * 3)
        if self._config.proactive_speak_enabled:
            pool.extend(["ProactiveSpeak"] * 1)
        if self._config.music_enabled:
            pool.extend(["PlayMusic"] * 1)
        if not pool:
            pool = ["IdleText"]
        random.shuffle(pool)
        self._event_queue = deque(pool)

    # ── Helpers ───────────────────────────────────────────────────

    def _pick_expression(self) -> str:
        mood = self._mood_label()
        pool = {
            "ceria": VRM_EXPRESSIONS_HAPPY,
            "netral": VRM_EXPRESSIONS_NEUTRAL,
            "melankolis": VRM_EXPRESSIONS_SAD,
        }.get(mood, VRM_EXPRESSIONS_NEUTRAL)
        return random.choice(pool)

    # ── Event Executors ───────────────────────────────────────────

    async def _exec_vrma(self) -> None:
        if not self._send:
            return

        anim_pool = self._vrma_pool()
        anim = random.choice(anim_pool)
        while anim == self._previous_animation and len(anim_pool) > 1:
            anim = random.choice(anim_pool)
        self._previous_animation = anim

        expression = self._pick_expression()

        await self._send(
            json.dumps({
                "type": "play-vrma",
                "animation": anim,
                "fade_in": 0.3,
            })
        )

        silent_payload = prepare_audio_payload(
            audio_path=None,
            display_text=None,
            actions=Actions(expressions=[expression]),
        )
        silent_payload["forwarded"] = True
        silent_payload["slice_length"] = 20
        silent_payload["volumes"] = []
        await self._send(json.dumps(silent_payload))

        logger.debug(f"IdleLife: VRMA '{anim}' + expression '{expression}'")

    async def _exec_idle_text(self) -> None:
        if not self._send:
            return

        texts = self._pick_idle_texts()
        text = random.choice(texts)
        await self._send(
            json.dumps({
                "type": "full-text",
                "text": text,
            })
        )
        logger.debug(f"IdleLife: IdleText '{text}'")

    async def _exec_subconscious(self) -> None:
        if not self._send:
            return

        if not self._subconscious_llm:
            await self._exec_idle_text()
            return

        try:
            system = SUBCONSCIOUS_SYSTEM_PROMPT.format(
                name=self._character_name,
                personality=self._personality or "(karakter ramah dan ceria)",
                time_context=self._time_context(),
                memory_context=self._memory_context(),
                screen_context=self._screen_context_str(),
            )
            chunks = []
            async for chunk in self._subconscious_llm.chat_completion(
                messages=[{"role": "user", "content": "Apa yang sedang kamu pikirkan?"}],
                system=system,
            ):
                if isinstance(chunk, str):
                    chunks.append(chunk)

            thought = "".join(chunks).strip()
            if thought:
                await self._send(
                    json.dumps({
                        "type": "full-text",
                        "text": thought,
                    })
                )
                logger.debug(f"IdleLife: Subconscious '{thought[:60]}...'")
            else:
                await self._exec_idle_text()

        except Exception as e:
            logger.warning(f"IdleLife: subconscious LLM error: {e}")
            await self._exec_idle_text()

    async def _exec_proactive_speak(self) -> None:
        if not self._proactive_trigger:
            await self._exec_subconscious()
            return

        if not self._subconscious_llm:
            await self._exec_subconscious()
            return

        try:
            system = PROACTIVE_SPEAK_PROMPT.format(
                name=self._character_name,
                personality=self._personality or "(karakter ramah dan ceria)",
                time_context=self._time_context(),
                memory_context=self._memory_context(),
                screen_context=self._screen_context_str(),
            )
            chunks = []
            async for chunk in self._subconscious_llm.chat_completion(
                messages=[{"role": "user", "content": "Ajukan topik obrolan ringan."}],
                system=system,
            ):
                if isinstance(chunk, str):
                    chunks.append(chunk)

            topic = "".join(chunks).strip()
            if topic:
                await self._proactive_trigger(topic)
                logger.debug(f"IdleLife: ProactiveSpeak '{topic[:60]}...'")
            else:
                await self._exec_subconscious()

        except Exception as e:
            logger.warning(f"IdleLife: proactive speak error: {e}")
            await self._exec_subconscious()

    async def _exec_play_music(self) -> None:
        """Trigger background music playback."""
        if not self._music_trigger:
            logger.debug("IdleLife: PlayMusic skipped (no trigger wired)")
            return

        try:
            await self._music_trigger()
            logger.debug("IdleLife: PlayMusic triggered")
        except Exception as e:
            logger.warning(f"IdleLife: PlayMusic error: {e}")

    def _broadcast_state(self) -> None:
        """Send idle-life-state once every 5 events for monitoring."""
        self._state_broadcast_counter += 1
        if self._state_broadcast_counter % 5 != 0 or not self._send:
            return
        try:
            self._send(json.dumps({
                "type": "idle-life-state",
                "state": self._state,
                "mood": round(self._mood, 2),
                "mood_label": self._mood_label(),
                "time_period": self._time_period(),
                "queue_len": len(self._event_queue),
                "total_events": self._stats["total_events"],
                "events_by_type": dict(self._stats["by_type"]),
            }))
        except Exception:
            pass

    async def _go_to_sleep(self) -> None:
        if self._state == "SLEEP":
            return
        self._state = "SLEEP"
        if self._send:
            await self._send(
                json.dumps({
                    "type": "full-text",
                    "text": "*{name} mulai mengantuk…*".format(name=self._character_name),
                })
            )
            await asyncio.sleep(3)
            await self._send(
                json.dumps({
                    "type": "full-text",
                    "text": "*{name} tertidur…*".format(name=self._character_name),
                })
            )
        logger.info(
            f"IdleLife: going to sleep "
            f"(idle for {time.time() - self._idle_since:.0f}s)"
        )
