from dataclasses import dataclass, field
from typing import Optional


@dataclass
class HitObject:
    x: int
    y: int
    time_ms: int
    obj_type: int
    hit_sound: int
    end_time_ms: Optional[int] = None
    curve_type: Optional[str] = None
    curve_points: list = field(default_factory=list)
    slides: int = 0
    length: float = 0.0


@dataclass
class TimingPoint:
    time_ms: int
    beat_length: float
    meter: int
    sample_set: int
    sample_index: int
    volume: int
    uninherited: bool
    effects: int = 0

    @property
    def bpm(self) -> Optional[float]:
        return 60000.0 / self.beat_length if self.uninherited and self.beat_length > 0 else None

    @property
    def sv_multiplier(self) -> float:
        return -100.0 / self.beat_length if not self.uninherited else 1.0


@dataclass
class Beatmap:
    title: str
    artist: str
    creator: str
    version: str
    audio_filename: str
    audio_lead_in: int
    mode: int
    ar: float
    od: float
    cs: float
    hp: float
    slider_multiplier: float
    slider_tick_rate: float
    hit_objects: list[HitObject]
    timing_points: list[TimingPoint]
    file_path: str = ""

    @property
    def approach_duration_ms(self) -> float:
        if self.ar <= 5:
            return 1800.0 - 120.0 * self.ar
        else:
            return 1200.0 - 150.0 * (self.ar - 5)

    @property
    def overall_difficulty_ms(self) -> float:
        od = max(0, min(self.od, 10))
        if od <= 5:
            return 80.0 - 8.0 * od
        else:
            return 40.0 - 6.0 * (od - 5)

    @property
    def hit_window_300(self) -> float:
        return self.overall_difficulty_ms

    @property
    def hit_window_100(self) -> float:
        return self.overall_difficulty_ms * 1.5

    @property
    def hit_window_50(self) -> float:
        return self.overall_difficulty_ms * 2.0

    @property
    def total_hit_objects(self) -> int:
        return sum(1 for o in self.hit_objects if o.obj_type & 1)

    @property
    def duration_ms(self) -> int:
        if not self.hit_objects:
            return 0
        return max(o.end_time_ms or o.time_ms for o in self.hit_objects) + 1000


@dataclass
class PathPoint:
    x: float
    y: float
    time_ms: float


@dataclass
class MovementPath:
    start_time_ms: float
    end_time_ms: float
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    points: list[PathPoint] = field(default_factory=list)
    click_time_ms: Optional[float] = None
    hold_until_ms: Optional[float] = None

    @property
    def distance(self) -> float:
        return ((self.end_x - self.start_x) ** 2 + (self.end_y - self.start_y) ** 2) ** 0.5
