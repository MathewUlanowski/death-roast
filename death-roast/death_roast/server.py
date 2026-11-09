"""FastAPI web server for the Death Roast sidecar."""

import logging
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .parser import DeathEvent
from .roast import RoastResult, generate_roast
from .tailer import LogTailer

logger = logging.getLogger(__name__)

app = FastAPI(title="PZ Death Roast", version="0.1.0")

# In-memory store of recent roasts
recent_roasts: list[tuple[DeathEvent, str]] = []
MAX_ROASTS = 50


class DeathWebhook(BaseModel):
    """Optional webhook payload for external death notifications."""

    username: str
    steamid: str
    x: int
    y: int
    z: int
    hours_survived: float
    timestamp: str


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Simple dashboard showing recent deaths and roasts."""

    roast_rows = ""
    for death, roast in reversed(recent_roasts):
        roast_rows += f"""
        <tr>
            <td>{death.timestamp.strftime('%d/%m %H:%M')}</td>
            <td><strong>{death.username}</strong></td>
            <td>{death.x}, {death.y}</td>
            <td>{int(death.hours_survived)}h {int(death.minutes_survived % 60)}m</td>
            <td style="white-space:pre-wrap; max-width:500px;">{roast}</td>
        </tr>"""

    if not recent_roasts:
        roast_rows = "<tr><td colspan='5' style='text-align:center; padding:2rem;'>No deaths yet. The zombies are working hard...</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PZ Death Roast</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Courier New', monospace;
            background: #1a1a2e;
            color: #e0e0e0;
            padding: 2rem;
        }}
        h1 {{
            color: #e94560;
            margin-bottom: 0.5rem;
            font-size: 2rem;
        }}
        .subtitle {{
            color: #888;
            margin-bottom: 2rem;
        }}
        .stats {{
            display: flex;
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .stat-card {{
            background: #16213e;
            border: 1px solid #0f3460;
            border-radius: 8px;
            padding: 1rem 1.5rem;
            min-width: 150px;
        }}
        .stat-card .label {{ color: #888; font-size: 0.85rem; }}
        .stat-card .value {{ color: #e94560; font-size: 1.5rem; font-weight: bold; margin-top: 0.25rem; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: #16213e;
            border-radius: 8px;
            overflow: hidden;
        }}
        th {{
            background: #0f3460;
            padding: 0.75rem 1rem;
            text-align: left;
            color: #e94560;
        }}
        td {{
            padding: 0.75rem 1rem;
            border-top: 1px solid #0f3460;
        }}
        .status {{
            display: inline-block;
            width: 8px; height: 8px;
            background: #4ade80;
            border-radius: 50%;
            margin-right: 0.5rem;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.3; }}
        }}
    </style>
</head>
<body>
    <h1>☠️ PZ Death Roast</h1>
    <p class="subtitle"><span class="status"></span>Watching for deaths...</p>

    <div class="stats">
        <div class="stat-card">
            <div class="label">Total Deaths</div>
            <div class="value">{len(recent_roasts)}</div>
        </div>
        <div class="stat-card">
            <div class="label">Last Roast</div>
            <div class="value" style="font-size:1rem;">
                {recent_roasts[-1][0].username if recent_roasts else '—'}
            </div>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th>Time</th>
                <th>Player</th>
                <th>Location</th>
                <th>Survived</th>
                <th>Roast</th>
            </tr>
        </thead>
        <tbody>
            {roast_rows}
        </tbody>
    </table>
</body>
</html>"""

    return html


@app.post("/webhook/death")
async def death_webhook(payload: DeathWebhook):
    """Receive death events from external sources (e.g., a PZ server mod)."""
    death = DeathEvent(
        timestamp=datetime.now(),
        steamid=payload.steamid,
        username=payload.username,
        x=payload.x,
        y=payload.y,
        z=payload.z,
        hours_survived=payload.hours_survived,
    )

    logger.info("Webhook death: %s at (%d,%d)", death.username, death.x, death.y)

    # Generate roast asynchronously
    result = await generate_roast(death)
    recent_roasts.append((result.death_event, result.roast))

    return {"status": "roasted", "username": death.username}


@app.get("/api/roasts")
async def list_roasts(limit: int = 20):
    """API endpoint to get recent roasts as JSON."""
    roasts = []
    for death, roast in reversed(recent_roasts[-limit:]):
        roasts.append({
            "timestamp": death.timestamp.isoformat(),
            "username": death.username,
            "steamid": death.steamid,
            "x": death.x,
            "y": death.y,
            "z": death.z,
            "hours_survived": death.hours_survived,
            "roast": roast,
        })
    return roasts


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "alive", "roasts_generated": len(recent_roasts)}
