from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Body
from websocket_manager import websocket_router, websocket_manager
from game import Game
import asyncio
from human_player_names import human_player_names
app = FastAPI(openapi_url="/api/openapi.json")
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

@app.post("/start_game")
async def start_game(data: dict = Body(...)):
    global current_game

    human_players = data.get("human_names", [])
    human_player_names.clear()
    human_player_names.extend(human_players)
    all_players = []

    print("Starting game with players!!!!!!!:", human_players)
    for name in human_players:
        all_players.append({"name": name, "model": "human", "is_human": True})

    ai_names = ["AI_Claude", "AI_Gemini", "AI_DeepSeek"]
    for name in ai_names:
        if len(all_players) >= 4:
            break
        all_players.append({"name": name, "model": "o3-mini", "is_human": False})

    current_game = Game(all_players)
    print("Game initialized with players:", all_players)
    for name in human_players:
        for _ in range(50):  # wait up to 5 seconds per user
            if name in websocket_manager.pending_responses:
                break
            await asyncio.sleep(0.1)
        else:
            raise RuntimeError(f"❌ Player '{name}' did not connect to WebSocket in time")
    await current_game.start_game()
    return {"status": "started", "players": [p["name"] for p in all_players]}

@app.on_event("startup")
async def startup_event():
    print("✅ Server ready at http://localhost:8000")

    # Example: game_server.py

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("game_server:app", host="0.0.0.0", port=8000, reload=False)
