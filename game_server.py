from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Body
from websocket_manager import websocket_router
from game import Game
import asyncio
from human_player_names import human_player_names
from game_state import games

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(websocket_router)
templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

current_game: Game = None

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

from uuid import uuid4
import asyncio


@app.post("/start_game")
async def start_game(data: dict = Body(...)):
    # 1) Get or create the game_id
    game_id = data.get("game_id") or str(uuid4())

    # 2) Build all_players as before…
    human_players = data.get("human_names", [])
    ai_players    = data.get("ai_players", [])
    all_players = []
    for name in human_players:
        all_players.append({"name": name, "model": "human", "is_human": True})
    for ai in ai_players:
        if len(all_players) >= 4: break
        all_players.append({
            "name":        ai["name"],
            "model":       "o3-mini",
            "is_human":    False,
            "personality": ai.get("personality", "")
        })

    # 3) Create & store the game—but do *not* start it yet
    game = Game(all_players, game_id)
    games[game_id] = game
    print(f"🔸 Game {game_id} initialized with players:", all_players)

    # 4) Return immediately
    return {
        "status":  "created",
        "game_id": game_id,
        "players": [p["name"] for p in all_players]
    }

@app.on_event("startup")
async def startup_event():
    print("✅ Server ready at http://localhost:8000")

    # Example: game_server.py

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("game_server:app", host="0.0.0.0", port=8000, reload=False)
