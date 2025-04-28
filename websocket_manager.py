import asyncio
from fastapi import WebSocket, APIRouter, WebSocketDisconnect
from game_state import games

class WebSocketManager:
    def __init__(self):
        # now nested by game_id → player_name
        self.active_connections: dict[str, dict[str, WebSocket]] = {}
        self.pending_responses: dict[str, dict[str, asyncio.Queue]] = {}

    async def connect(self, game_id: str, player_name: str, websocket: WebSocket):
        await websocket.accept()
        # ensure the game namespace exists
        self.active_connections.setdefault(game_id, {})[player_name] = websocket
        self.pending_responses.setdefault(game_id, {})[player_name] = asyncio.Queue()
        print(f"🔌 WS connected: game={game_id} player={player_name}")

    def disconnect(self, game_id: str, player_name: str):
        # remove that one player's connection
        self.active_connections.get(game_id, {}).pop(player_name, None)
        self.pending_responses.get(game_id, {}).pop(player_name, None)
        # if the game namespace is empty, clean it up
        if not self.active_connections.get(game_id):
            self.active_connections.pop(game_id, None)
            self.pending_responses.pop(game_id, None)
        print(f"🔌 WS disconnected: game={game_id} player={player_name}")

    async def send(self, game_id: str, player_name: str, data: dict):
        ws = self.active_connections.get(game_id, {}).get(player_name)
        if ws:
            await ws.send_json(data)

    async def wait_for_response(self, game_id: str, player_name: str) -> dict:
        queue = self.pending_responses.get(game_id, {}).get(player_name)
        if not queue:
            raise RuntimeError(f"No WS for {game_id}/{player_name}")
        return await queue.get()

    async def receive_response(self, game_id: str, player_name: str, data: dict):
        queue = self.pending_responses.get(game_id, {}).get(player_name)
        if queue:
            await queue.put(data)

# global instance
websocket_manager = WebSocketManager()

# new router
websocket_router = APIRouter()

@websocket_router.websocket("/ws/{game_id}/{player_name}")
async def websocket_endpoint(
    websocket: WebSocket,
    game_id: str,
    player_name: str
):
    # 1) accept & register this socket
    await websocket_manager.connect(game_id, player_name, websocket)

    # 2) fetch the Game instance
    game = games.get(game_id)
    if game is None:
        # invalid game_id: close immediately
        await websocket.close(code=1000)
        return

    # 3) on the very first WS connect, kick off the game loop
    if not getattr(game, "started", False):
        game.started = True
        # run in background so we can keep handling WS messages
        asyncio.create_task(game.start_game())

    try:
        # 4) forward all incoming messages to your manager
        while True:
            data = await websocket.receive_json()
            await websocket_manager.receive_response(game_id, player_name, data)

    except WebSocketDisconnect:
        websocket_manager.disconnect(game_id, player_name)