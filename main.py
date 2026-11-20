import os
import json
import ast
import re
import base64
import urllib.request
import urllib.error
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from lobbycode.newtable import final_svg

MONGO_URI = os.environ.get("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI environment variable is required")

SERVER_ID = 1470482329075060831
SEASON_ID = "4"
METADATA_PATH = os.environ.get("METADATA_PATH", "leaderboard_metadata.json")
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
DISCORD_API = "https://discord.com/api/v10"

client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=10000,
    connectTimeoutMS=10000,
)
db = client["shellbot_hosting"]
collection = db["scrim_data"]
guild_collection = db["guild_data"]

app = FastAPI(title="Shell Strike API", version="1.1.0")

allowed_origins = [
    origin.strip()
    for origin in os.environ.get("FRONTEND_ORIGINS", "").split(",")
    if origin.strip()
]
if not allowed_origins:
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def load_discord_metadata():
    """Load the separately maintained Discord profile export."""
    try:
        with open(METADATA_PATH, "r", encoding="utf-8") as file:
            records = json.load(file)
        if not isinstance(records, list):
            return {}
        return {
            str(record.get("playerId") or record.get("discord_id")): record
            for record in records
            if isinstance(record, dict) and (record.get("playerId") or record.get("discord_id"))
        }
    except (OSError, json.JSONDecodeError):
        return {}


def discord_get(path: str):
    """Call Discord REST API using the bot token kept on the server."""
    if not DISCORD_BOT_TOKEN:
        raise HTTPException(status_code=503, detail="DISCORD_BOT_TOKEN is not configured")
    request = urllib.request.Request(
        f"{DISCORD_API}{path}",
        headers={
            "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
            "User-Agent": "ShellStrikeStats/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise HTTPException(status_code=404, detail="The linked Discord message or archive channel was not found")
        if exc.code == 403:
            raise HTTPException(status_code=502, detail="The Discord bot cannot access the stats channel or message")
        if exc.code == 429:
            raise HTTPException(status_code=503, detail="Discord rate limit reached. Try again shortly")
        raise HTTPException(status_code=502, detail=f"Discord API returned HTTP {exc.code}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        raise HTTPException(status_code=502, detail="Could not retrieve data from Discord")


def get_game_record(season: int, game: int):
    try:
        doc = collection.find_one(
            {"server_id": SERVER_ID},
            {
                "_id": 0,
                f"seasons.{season}.games.{game}": 1,
            },
        )
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not query MongoDB")

    if not doc:
        raise HTTPException(status_code=404, detail="Shell Strike server data not found")

    season_data = (doc.get("seasons") or {}).get(str(season)) or {}
    game_data = (season_data.get("games") or {}).get(str(game))
    if not game_data:
        raise HTTPException(status_code=404, detail="That game was not found in the selected season")
    return game_data


def get_discord_message_link_parts(stats_link: str):
    match = re.fullmatch(
        r"https?://(?:www\.)?discord(?:app)?\.com/channels/(\d+)/(\d+)/(\d+)/?",
        stats_link.strip(),
    )
    if not match:
        raise HTTPException(status_code=502, detail="The stored stats_link is not a valid Discord message link")
    guild_id, channel_id, message_id = match.groups()
    if guild_id != str(SERVER_ID):
        raise HTTPException(status_code=502, detail="The stored stats link belongs to a different Discord server")
    return channel_id, message_id


def find_legacy_stats_message(channel_id: str, game_number: int):
    """Find legacy 'game_number: {python dict}' messages in the KOTC archive."""
    before = None
    matches = []
    for _ in range(50):  # At most 5,000 messages per request.
        query = "?limit=100" + (f"&before={before}" if before else "")
        messages = discord_get(f"/channels/{channel_id}/messages{query}")
        if not isinstance(messages, list) or not messages:
            break

        for message in messages:
            content = (message.get("content") or "").strip()
            match = re.match(r"^(\d+)\s*:\s*(\{[\s\S]*\})$", content)
            if match and int(match.group(1)) == game_number:
                matches.append(match.group(2))

        before = messages[-1].get("id")
        if not before or len(messages) < 100:
            break
        if len(matches) > 1:
            break

    if not matches:
        raise HTTPException(status_code=404, detail="No raw KOTC stats entry was found in the archive channel")
    if len(matches) > 1:
        raise HTTPException(
            status_code=409,
            detail="Multiple archive messages use this game number. The old archive format does not identify the season.",
        )

    try:
        data = ast.literal_eval(matches[0])
    except (ValueError, SyntaxError):
        raise HTTPException(status_code=502, detail="The archived raw stats message could not be parsed")
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="The archived raw stats entry has an unexpected format")
    return data


@app.get("/")
def root():
    return {"service": "Shell Strike API", "status": "online"}


@app.get("/health")
def health():
    try:
        client.admin.command("ping")
        return {"status": "ok", "database": "connected"}
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Database unavailable")


@app.get("/api/leaderboard")
def get_leaderboard():
    # Existing leaderboard endpoint retained.
    try:
        doc = collection.find_one(
            {"server_id": SERVER_ID},
            {"_id": 0, "server_id": 1, "seasons": 1},
        )
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not query MongoDB")

    if not doc:
        raise HTTPException(status_code=404, detail="Shell Strike server data not found")

    season = (doc.get("seasons") or {}).get(SEASON_ID)
    if not season:
        raise HTTPException(status_code=404, detail="Season 4 data not found")

    players_data = season.get("players") or {}
    discord_metadata = load_discord_metadata()
    players = []

    for player_id, stats in players_data.items():
        stats = stats or {}
        profile = discord_metadata.get(str(player_id), {})
        players.append({
            "playerId": str(player_id),
            "username": profile.get("username") or None,
            "globalName": profile.get("global_name") or None,
            "displayName": profile.get("display_name") or profile.get("global_name") or profile.get("username") or str(player_id),
            "avatarUrl": profile.get("avatar_url") or None,
            "isBot": bool(profile.get("is_bot", False)),
            "elo": int(stats.get("elo") or 0),
            "wins": int(stats.get("wins") or 0),
            "losses": int(stats.get("losses") or 0),
            "gamesPlayed": int(stats.get("games_played") or 0),
            "winLossRatio": float(stats.get("win_loss_ratio") or 0),
            "winStreak": int(stats.get("win_streak") or 0),
            "bestWinStreak": int(stats.get("best_win_streak") or 0),
        })

    players.sort(key=lambda player: (player["elo"], player["wins"]), reverse=True)

    for index, player in enumerate(players, start=1):
        player["rank"] = index

    return {
        "serverId": str(SERVER_ID),
        "season": SEASON_ID,
        "totalPlayers": len(players),
        "totalGames": len(season.get("games") or {}),
        "players": players,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/match-stats")
def get_match_stats(
    season: int = Query(..., ge=1, le=100),
    game: int = Query(..., ge=1, le=1000000),
):
    """
    Return image_url for the existing Match Stats frontend.
    S4+ uses stats_link -> Discord message attachment.
    Older seasons use raw KOTC stats in lobby.kotc_stats_log -> generated SVG data URL.
    """
    game_data = get_game_record(season, game)
    stats_link = game_data.get("stats_link")

    if stats_link:
        channel_id, message_id = get_discord_message_link_parts(str(stats_link))
        message = discord_get(f"/channels/{channel_id}/messages/{message_id}")
        attachments = message.get("attachments") or []
        image_attachment = next(
            (item for item in attachments if str(item.get("content_type") or "").startswith("image/")),
            attachments[0] if attachments else None,
        )
        if not image_attachment or not image_attachment.get("url"):
            raise HTTPException(status_code=404, detail="The linked Discord message has no image attachment")
        return {"image_url": image_attachment["url"]}

    try:
        guild_config = guild_collection.find_one(
            {"guild_id": SERVER_ID},
            {"_id": 0, "lobby.kotc_stats_log": 1},
        )
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Could not query guild configuration")

    archive_channel_id = ((guild_config or {}).get("lobby") or {}).get("kotc_stats_log")
    if not archive_channel_id:
        raise HTTPException(status_code=404, detail="The KOTC raw-stats archive channel is not configured")

    raw_stats = find_legacy_stats_message(str(archive_channel_id), game)
    try:
        svg = final_svg(raw_stats, game)
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise HTTPException(status_code=502, detail=f"Could not generate the legacy stats image: {type(exc).__name__}")

    image_data_url = "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return {"image_url": image_data_url}
