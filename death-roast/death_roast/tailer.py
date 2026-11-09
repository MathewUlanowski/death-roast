"""Tail PerkLog.txt and emit death events in real-time."""

import asyncio
import logging
from pathlib import Path

from .parser import DeathEvent, parse_death_line

logger = logging.getLogger(__name__)


class LogTailer:
    """Efficiently tail a log file for new lines, yielding parsed events."""

    def __init__(self, log_path: str, poll_interval: float = 1.0):
        self.log_path = Path(log_path)
        self.poll_interval = poll_interval
        self._offset = 0
        self._seen_steamids: set[str] = set()  # track deaths per session

    def _reset_seen(self) -> None:
        """Reset seen set when log file is rotated."""
        self._seen_steamids.clear()

    async def watch(self) -> asyncio.Queue[DeathEvent]:
        """Watch the log file and return a queue of death events."""
        queue: asyncio.Queue[DeathEvent] = asyncio.Queue()

        # Ensure file exists
        if not self.log_path.exists():
            logger.warning("Log file not found: %s", self.log_path)
            # Wait for it to appear
            while not self.log_path.exists():
                await asyncio.sleep(self.poll_interval)

        # Seek to end of file initially (only watch new deaths)
        self._offset = self.log_path.stat().st_size

        logger.info("Tail started: %s (starting at byte %d)", self.log_path, self._offset)

        while True:
            try:
                await self._process_lines(queue)
            except Exception as e:
                logger.error("Error tailing log: %s", e, exc_info=True)

            await asyncio.sleep(self.poll_interval)

    async def _process_lines(self, queue: asyncio.Queue[DeathEvent]) -> None:
        """Read new lines from the log file and parse death events."""
        try:
            current_size = self.log_path.stat().st_size
        except FileNotFoundError:
            self._reset_seen()
            self._offset = 0
            return

        # File was truncated/rotated
        if current_size < self._offset:
            logger.info("Log file rotated, resetting offset")
            self._reset_seen()
            self._offset = 0
            current_size = self.log_path.stat().st_size

        if current_size == self._offset:
            return

        # Read new content
        with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(self._offset)
            new_content = f.read()
            self._offset = f.tell()

        # Process line by line
        for line in new_content.splitlines():
            death = parse_death_line(line)
            if death:
                # Skip duplicate deaths (same steamid within a session)
                if death.steamid not in self._seen_steamids:
                    self._seen_steamids.add(death.steamid)
                    logger.info(
                        "Death detected: %s at (%d,%d,%d), survived %.1f hours",
                        death.username,
                        death.x,
                        death.y,
                        death.z,
                        death.hours_survived,
                    )
                    await queue.put(death)
