import asyncio
from fastapi import WebSocket, APIRouter, WebSocketDisconnect

class WebSocketManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.pending_responses: dict[str, asyncio.Queue] = {}

    async def connect(self, player_name: str, websocket: WebSocket):
        print(f"🔌 WebSocket connected for: {player_name}")
        await websocket.accept()
        self.active_connections[player_name] = websocket
        self.pending_responses[player_name] = asyncio.Queue()

    def disconnect(self, player_name: str):
        if player_name in self.active_connections:
            del self.active_connections[player_name]
        if player_name in self.pending_responses:
            del self.pending_responses[player_name]

    async def send(self, player_name: str, data: dict):
        if player_name in self.active_connections:
            await self.active_connections[player_name].send_json(data)
    async def wait_for_response(self, player_name: str) -> dict:
        if player_name not in self.pending_responses:
            raise RuntimeError(f"❌ Player '{player_name}' has no active WebSocket connection")
        return await self.pending_responses[player_name].get()

    async def receive_response(self, player_name: str, data: dict):
        if player_name in self.pending_responses:
            await self.pending_responses[player_name].put(data)

# Create a global instance you can import elsewhere
websocket_manager = WebSocketManager()

# Optional router to include in your FastAPI app
websocket_router = APIRouter()

@websocket_router.websocket("/ws/{player_name}")
async def websocket_endpoint(websocket: WebSocket, player_name: str):
    await websocket_manager.connect(player_name, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await websocket_manager.receive_response(player_name, data)
    except WebSocketDisconnect:
        websocket_manager.disconnect(player_name)
