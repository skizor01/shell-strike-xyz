import os
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from pymongo.errors import PyMongoError

MONGO_URI = os.environ.get("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI environment variable is required")

SERVER_ID = 1470482329075060831
SEASON_ID = "4"

client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=10000,
    connectTimeoutMS=10000,
)
collection = client["shellbot_hosting"]["scrim_data"]

app = FastAPI(title="Shell Strike Leaderboard API", version="1.0.0")

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


@app.get("/")
def root():
    return {"service": "Shell Strike Leaderboard API", "status": "online"}


@app.get("/health")
def health():
    try:
        client.admin.command("ping")
        return {"status": "ok", "database": "connected"}
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Database unavailable")


@app.get("/api/leaderboard")
def get_leaderboard():
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
    players = []

    for player_id, stats in players_data.items():
        stats = stats or {}
        players.append({
            "playerId": str(player_id),
            "elo": int(stats.get("elo") or 0),
            "wins": int(stats.get("wins") or 0),
            "losses": int(stats.get("losses") or 0),
            "gamesPlayed": int(stats.get("games_played") or 0),
            "winLossRatio": float(stats.get("win_loss_ratio") or 0),
            "winStreak": int(stats.get("win_streak") or 0),
            "bestWinStreak": int(stats.get("best_win_streak") or 0),
        })

    # Official Shell Strike ranking metric: ELO.
    # Wins are used only as a deterministic tie-breaker.
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
