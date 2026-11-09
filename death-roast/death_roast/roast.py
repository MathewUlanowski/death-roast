"""Generate roast stories from death events using Qwen via Runpod."""

import asyncio
import json
import logging
import os
from dataclasses import dataclass

from .parser import DeathEvent

logger = logging.getLogger(__name__)

# Prompt template for the LLM - tells it to generate a funny roast
ROAST_SYSTEM_PROMPT = """You are a merciless comedy roaster specializing in Project Zomboid player deaths.
Your job is to write a hilarious, creative short story (3-5 paragraphs) mocking how this player died.

Be creative and original each time. Use vivid imagery, dark humor, and exaggeration.
Reference the player's survival stats, location, and the absurdity of their demise.
Keep it fun and playful - we're roasting gamers, not actually being mean.
Never use actual slurs or genuinely offensive content.

Make it feel like a legendary ballad of failure that will be remembered in Zomboid history."""


@dataclass
class RoastResult:
    death_event: DeathEvent
    roast: str


def _build_user_prompt(death: DeathEvent) -> str:
    """Build the user prompt with death data for the LLM."""

    # Convert map coordinates to a rough location description
    if death.x > 7000 and death.y > 6000:
        area = "the suburban sprawl near Muldraugh"
    elif death.x > 7000 and death.y > 5000:
        area = "the wilds between Ludendorff and the suburbs"
    elif death.x > 6000 and death.y > 6000:
        area = "the farmlands east of Horseshoe"
    elif death.x > 6000 and death.y > 5000:
        area = "the countryside near the train tracks"
    elif death.x < 7000 and death.y < 5500:
        area = "the mysterious northern wilderness"
    else:
        area = "somewhere in the zombie-infested midwest"

    # Survival time commentary
    if death.hours_survived < 1:
        survival_commentary = (
            f"In a breathtaking display of incompetence, {death.username} survived "
            f"less than an hour. Not even enough time to find a pair of underwear, "
            f"let alone a weapon. This isn't a death - it's a speedrun to the grave."
        )
    elif death.hours_survived < 24:
        survival_commentary = (
            f"After a valiant {int(death.hours_survived)} hours of trying very hard "
            f"to die, {death.username} has finally succeeded. The zombie horde must "
            f"be disappointed - this was almost too easy."
        )
    elif death.hours_survived < 168:  # 1 week
        survival_commentary = (
            f"A respectable {int(death.hours_survived)} hours of scavenging, "
            f"hiding, and generally failing to stay alive. But it all ends here."
        )
    elif death.hours_survived < 720:  # 1 month
        survival_commentary = (
            f"{int(death.hours_survived)} hours of survival. {death.username} was "
            f"starting to think they might actually make it. How cute."
        )
    else:
        survival_commentary = (
            f"A legendary {int(death.hours_survived)} hours of survival! "
            f"{death.username} was practically a zombie-slaying legend. "
            f"And yet... it all comes to this. Even legends must fall."
        )

    return (
        f"Write a roast story for this Project Zomboid player death:\n\n"
        f"**Player:** {death.username}\n"
        f"**SteamID:** {death.steamid}\n"
        f"**Location:** {area} (map coords: {death.x}, {death.y}, {death.z})\n"
        f"**Time of Death:** {death.timestamp.strftime('%d/%m/%y at %H:%M')}\n"
        f"**Hours Survived:** {death.hours_survived:.1f}\n\n"
        f"{survival_commentary}\n\n"
        f"Now write the roast story. Make it epic."
    )


async def generate_roast(death_event: DeathEvent) -> RoastResult:
    """Generate a roast story for a death event using Qwen via Runpod."""

    user_prompt = _build_user_prompt(death_event)

    # Get API key from environment - this is the Qwen-Image endpoint on Runpod
    api_key = os.environ.get("RUNPOD_API_KEY", "")
    if not api_key:
        return RoastResult(
            death_event=death_event,
            roast="[ROAST FAILED] No RUNPOD_API_KEY configured. The zombies win by default.",
        )

    # Use the Qwen endpoint for text generation
    # Default to a reasonable endpoint - can be overridden via env var
    endpoint_id = os.environ.get(
        "ROAST_ENDPOINT_ID", "putzee8yi83xh1"
    )  # Qwen endpoint

    try:
        import urllib.request

        # Use /runsync for synchronous execution — waits for completion
        url = f"https://api.runpod.ai/v2/{endpoint_id}/runsync"
        payload = {
            "input": {
                "prompt": f"{ROAST_SYSTEM_PROMPT}\n\n---\n\n{user_prompt}",
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )

        with urllib.request.urlopen(req, timeout=300) as response:
            result = json.loads(response.read())

        # Runpod serverless returns output directly in the response
        output = result.get("output", {})
        if isinstance(output, dict):
            roast_text = output.get("text", "") or output.get("response", "") or json.dumps(output)
        else:
            roast_text = str(output)

        if not roast_text:
            roast_text = (
                f"[ROAST FAILED] The LLM returned nothing. "
                f"{death_event.username} died without even getting a proper roast. How fitting."
            )

    except Exception as e:
        roast_text = (
            f"[ROAST FAILED] The roast generator crashed: {e}. "
            f"{death_event.username}, you couldn't even die reliably enough to get roasted."
        )

    return RoastResult(death_event=death_event, roast=roast_text)


async def notify_webhook(death_event: DeathEvent) -> None:
    """Notify the canvas automation webhook about a death event."""
    webhook_url = os.environ.get("DEATH_ROAST_WEBHOOK_URL", "")
    if not webhook_url:
        logger.debug("No DEATH_ROAST_WEBHOOK_URL configured, skipping webhook notification")
        return

    try:
        import hmac
        import hashlib
        import urllib.request

        payload = {
            "type": "death",
            "username": death_event.username,
            "steamid": death_event.steamid,
            "x": death_event.x,
            "y": death_event.y,
            "z": death_event.z,
            "hours_survived": death_event.hours_survived,
            "timestamp": death_event.timestamp.isoformat(),
        }

        payload_bytes = json.dumps(payload).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
        }

        # Add authentication if available
        session_key = os.environ.get("OPENHANDS_AUTOMATION_API_KEY", "")
        if session_key:
            headers["X-Session-API-Key"] = session_key

        # Compute HMAC-SHA256 signature for webhook verification
        webhook_secret = os.environ.get("DEATH_ROAST_WEBHOOK_SECRET", "")
        if webhook_secret:
            signature = hmac.new(
                webhook_secret.encode("utf-8"),
                payload_bytes,
                hashlib.sha256,
            ).hexdigest()
            headers["X-Signature-256"] = f"sha256={signature}"

        req = urllib.request.Request(
            webhook_url,
            data=payload_bytes,
            headers=headers,
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                logger.info("Webhook notification sent for %s", death_event.username)
            else:
                logger.warning("Webhook returned status %d for %s", response.status, death_event.username)

    except Exception as e:
        logger.error("Failed to send webhook notification for %s: %s", death_event.username, e)
