from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Body
from websocket_manager import websocket_router, websocket_manager
from game import LudoGame  # updated to import LudoGame
import asyncio
from human_player_names import human_player_names

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

current_game: LudoGame = None  # Update type annotation

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/start_game")
async def start_game(data: dict = Body(...)):
    global current_game

    print("Received start_game request with data:", data)

    human_players = data.get("human_names", [])
    ai_players = data.get("ai_players", [])

    human_player_names.clear()
    human_player_names.extend(human_players)
    all_players = []

    print("Starting Ludo game with human players:", human_players)
    colors = ["red", "blue", "green", "yellow"]  # Ludo has 4 standard colors

    for i, name in enumerate(human_players):
        all_players.append({
            "name": name,
            "is_human": True,
            "color": colors[i % len(colors)]
        })
    

    print("Human players added:", all_players)
    
    for ai in ai_players:
        if len(all_players) >= 4:
            break
        all_players.append({
            "name": ai["name"],
            "model": "o3-mini",
            "is_human": False,
            "personality": ai.get("personality", ""),
            "color": colors[len(all_players) % len(colors)]
        })


    current_game = LudoGame(all_players)  # changed class name
    print("Game initialized with players:", all_players)

    for name in human_players:
        for _ in range(10):
            if name in websocket_manager.pending_responses:
                break
            await asyncio.sleep(0.1)

    await current_game.start_game()  # no change
    return {"status": "started", "players": [p["name"] for p in all_players]}

@app.on_event("startup")
async def startup_event():
    print("✅ Ludo Server ready at http://localhost:8000")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("game_server:app", host="0.0.0.0", port=8000, reload=False)
