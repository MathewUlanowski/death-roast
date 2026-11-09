"""Parse PerkLog.txt for death events."""

import re
from dataclasses import dataclass
from datetime import datetime


@dataclass
class DeathEvent:
    timestamp: datetime
    steamid: str
    username: str
    x: int
    y: int
    z: int
    hours_survived: float

    @property
    def minutes_survived(self) -> float:
        return self.hours_survived * 60


# Format: [08-11-26 22:34:30.448] [76561198087695600][GhengisDong][6655,5256,-1][Died][Hours Survived: 787].
PERKLOG_DEATH_RE = re.compile(
    r"^\[(\d{2}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)\]\s*"
    r"\[([^\]]+)\]\s*"
    r"\[([^\]]+)\]\s*"
    r"\[(\d+),(\d+),(-?\d+)\]\s*"
    r"\[Died\]\s*"
    r"\[Hours Survived:\s*([\d.]+)\]\.$"
)


def parse_timestamp(ts_str: str) -> datetime:
    """Parse PerkLog timestamp (DD-MM-YY HH:MM:SS.mmm)."""
    return datetime.strptime(ts_str, "%d-%m-%y %H:%M:%S.%f")


def parse_death_line(line: str) -> DeathEvent | None:
    """Parse a single PerkLog line. Returns DeathEvent if it's a death, else None."""
    line = line.strip()
    m = PERKLOG_DEATH_RE.match(line)
    if not m:
        return None
    return DeathEvent(
        timestamp=parse_timestamp(m.group(1)),
        steamid=m.group(2),
        username=m.group(3),
        x=int(m.group(4)),
        y=int(m.group(5)),
        z=int(m.group(6)),
        hours_survived=float(m.group(7)),
    )
