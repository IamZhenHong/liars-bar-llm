import random
import json
import re
from typing import List, Dict
from llm_client import LLMClient
from websocket_manager import websocket_manager
import asyncio
from human_player_names import human_player_names
RULE_BASE_PATH = "prompt/rule_base.txt"
PLAY_CARD_PROMPT_TEMPLATE_PATH = "prompt/play_card_prompt_template.txt"
CHALLENGE_PROMPT_TEMPLATE_PATH = "prompt/challenge_prompt_template.txt"
REFLECT_PROMPT_TEMPLATE_PATH = "prompt/reflect_prompt_template.txt"

class Token:
    def __init__(self):
        self.position = None
        self.is_home = False


class Player:
    def __init__(self, name: str,color: str, is_human: bool = False, model_name: str = "human", personality: str = ""):

        self.name = name
        self.personality = personality
        # self.hand = []
        self.tokens: List[Token] = [Token() for _ in range(4)]
        self.color = color
        self.alive = True
        # self.bullet_position = random.randint(0, 5)
        # self.current_bullet_position = 0
        self.opinions = {}
        self.is_human = is_human
        self.llm_client = LLMClient()
        self.model_name = model_name

    async def _read_file(self, filepath: str) -> str:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            print(f"[ERROR] Failed to read file {filepath}: {str(e)}")
            await self.send_announcement(f"[ERROR] Failed to read file {filepath}: {str(e)}")
            return ""
    async def send_announcement(self, message: str) -> None:
        for name in human_player_names:
            await websocket_manager.send(name, {
                "type": "announcement",
                "message": message
            })

    def get_movable_tokens(self, roll: int) -> List[int]:
        movable = []
        for i, token in enumerate(self.tokens):
            print(f"Token {i}: position={token.position}, is_home={token.is_home}")
        for i, token in enumerate(self.tokens):
            if token.is_home:
                continue
            if token.position is None and roll == 6:
                movable.append(i)  # Can enter board
            elif token.position is not None and token.position + roll <= 56:
                movable.append(i)  # Can move forward
            elif token.position is not None and token.position + roll == 56:
                movable.append(i)
        
        return movable

    def move_token(self, token_index: int, roll: int):
        token = self.tokens[token_index]
        if token.position is None and roll == 6:
            token.position = 0  # Starting square
        elif token.position is not None:
            token.position += roll
            if token.position == 56:
                token.is_home = True
            
                
    def init_opinions(self, other_players: List["Player"]) -> None:
        self.opinions = {
            player.name: "还不了解这个玩家"
            for player in other_players
            if player.name != self.name
        }

    async def roll_dice(self) -> int:
        # Fallback to the first connected human player
        temp_name = next((name for name in human_player_names if name in websocket_manager.active_connections), None)

        if not temp_name:
            raise RuntimeError("❌ No active human WebSocket connection found")

        if self.is_human:
            await websocket_manager.send(temp_name, {
                "type": "roll_dice",
                "player": self.name
            })

            data = await websocket_manager.wait_for_response(temp_name)

            roll = random.randint(1, 6)

        else:
            # AI player rolls the dice
            roll = random.randint(1, 6)


        return roll
    
    def check_win(self) -> bool:
        if all(token.is_home for token in self.tokens):
            self.finished = True
            return True
        return False
    