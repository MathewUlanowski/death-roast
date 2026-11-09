"""Main entrypoint for the PZ Death Roast sidecar."""

import asyncio
import logging
import os
import sys

import uvicorn
from fastapi import FastAPI

from .parser import DeathEvent
from .roast import generate_roast, notify_webhook
from .server import app as web_app
from .tailer import LogTailer

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("death_roast")


def create_app() -> FastAPI:
    """Create the FastAPI app with background tasks."""
    app = FastAPI(title="PZ Death Roast", version="0.1.0")

    # Mount the web server routes
    for route in web_app.routes:
        app.add_route(route.path, route.endpoint, methods=route.methods)

    return app


async def death_handler(death: DeathEvent) -> None:
    """Handle a death event: notify automation webhook and optionally generate local roast."""
    from .server import recent_roasts

    logger.info(
        "Death detected: %s (%.1f hours survived at %d,%d)",
        death.username,
        death.hours_survived,
        death.x,
        death.y,
    )

    # Notify the automation webhook (canvas instance) to generate roast
    await notify_webhook(death)

    # Also generate a local roast as fallback
    result = await generate_roast(death)
    recent_roasts.append((result.death_event, result.roast))
    logger.info("Local roast complete for %s", death.username)


async def run_tailer_and_server(
    log_path: str,
    host: str,
    port: int,
    poll_interval: float = 1.0,
) -> None:
    """Start the log tailer and web server together."""
    app = create_app()
    tailer = LogTailer(log_path, poll_interval=poll_interval)

    async def process_deaths():
        """Consume death events from the tailer queue and roast them."""
        queue = await tailer.watch()
        while True:
            death = await queue.get()
            await death_handler(death)

    # Start both tasks
    server_task = asyncio.create_task(
        uvicorn.ASGIServer(
            uvicorn.Server(
                uvicorn.Config(app, host=host, port=port, log_level="info")
            )
        )
    )
    tailer_task = asyncio.create_task(process_deaths())

    logger.info("Death Roast sidecar starting on %s:%d", host, port)
    logger.info("Tailing log: %s", log_path)

    # Wait for both tasks
    await asyncio.gather(server_task, tailer_task)


def main():
    """CLI entrypoint."""
    log_path = os.environ.get(
        "PZ_LOG_PATH", "/logs/2026-11-08_01-19_PerkLog.txt"
    )
    host = os.environ.get("ROAST_HOST", "0.0.0.0")
    port = int(os.environ.get("ROAST_PORT", "8080"))
    poll_interval = float(os.environ.get("LOG_POLL_INTERVAL", "1.0"))

    logger.info("PZ Death Roast v0.1.0")
    logger.info("Config: log_path=%s, server=%s:%d, poll=%.1fs",
                log_path, host, port, poll_interval)

    try:
        asyncio.run(run_tailer_and_server(log_path, host, port, poll_interval))
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == "__main__":
    main()
