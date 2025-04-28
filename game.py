# This version of game.py assumes you're adapting it for Ludo.
# Core assumptions:
# - Players have tokens.
# - You roll a dice and decide which token to move.
# - First player to get all tokens home wins.

import random
import asyncio
from typing import List, Dict
from player import Player  # Modified Player class for Ludo
from websocket_manager import websocket_manager
from human_player_names import human_player_names

class LudoGame:
    def __init__(self, player_configs: List[Dict[str, str]]):
        self.players = [
            Player(config["name"], config["color"], config.get("is_human", False))
            for config in player_configs
        ]
        self.current_player_idx = random.randint(0, len(self.players) - 1)
        self.game_over = False
        self.ring_len     = 52
        self.safe_offsets = {0, 7, 14, 21, 28, 35, 42, 49}
        self.start_offsets = {
            "yellow": 0,
            "green": 14,
            "blue": 28,
            "red": 42
        }

    async def send_announcement(self, message: str):
        for name in human_player_names:
            await websocket_manager.send(name, {
                "type": "announcement",
                "message": message
            })

    async def broadcast_board_update(self):
        player_data = []
        for player in self.players:
            token_positions = [t.position for t in player.tokens]
            player_data.append({
                "color": player.color,
                "tokens": token_positions
            })

        for name in human_player_names:
            if name in websocket_manager.active_connections:
                await websocket_manager.send(name, {
                    "type": "board_update",
                    "players": player_data
                })

    def next_player_idx(self) -> int:
        return (self.current_player_idx + 1) % len(self.players)

    async def play_turn(self, player: Player):
        # 0) Announce start of this player's turn
        await self.send_announcement(f"{player.name}'s turn! 🎲")
        await asyncio.sleep(1)

        # 1) Loop for extra rolls on a 6
        while True:
            # ─── Roll the dice ──────────────────────────────────────────────────────────
            roll = await player.roll_dice()
            await asyncio.sleep(1)
            await self.send_announcement(f"{player.name} rolled a {roll} 🎲")

            # ─── Figure out which tokens can move ───────────────────────────────────────
            movable = player.get_movable_tokens(roll)
            if not movable:
                await asyncio.sleep(1)
                await self.send_announcement(f"{player.name} has no valid moves")
                break

            # ─── Choose a token ────────────────────────────────────────────────────────
            if player.is_human:
                # find an active WebSocket connection
                temp_name = (
                    player.name
                    if player.name in websocket_manager.active_connections
                    else next(
                        (nm for nm in human_player_names
                        if nm in websocket_manager.active_connections),
                        None
                    )
                )
                if not temp_name:
                    raise RuntimeError(
                        "❌ No active WebSocket connection available for human players"
                    )

                # prompt the client to choose
                await websocket_manager.send(temp_name, {
                    "type": "your_turn",
                    "roll": roll,
                    "tokens": [t.position for t in player.tokens],
                    "movableIndexes": movable
                })

                # wait for their selection
                data = await websocket_manager.wait_for_response(temp_name)
                chosen_index = data.get("token_index")
            else:
                # AI picks the first movable
                await self.send_announcement(f"{player.name} is thinking…")
                await asyncio.sleep(1)
                chosen_index = movable[0]

            # ─── Move the token ────────────────────────────────────────────────────────
            player.move_token(chosen_index, roll)
            new_pos = player.tokens[chosen_index].position

            # ─── Capture logic ─────────────────────────────────────────────────────────
            if (
                new_pos is not None
                and new_pos < self.ring_len
                and new_pos not in self.safe_offsets
            ):
                moved_abs = (self.start_offsets[player.color] + new_pos) % self.ring_len
                for opponent in self.players:
                    if opponent is player:
                        continue
                    for idx, tok in enumerate(opponent.tokens):
                        if tok.position is not None and tok.position < self.ring_len:
                            opp_abs = (
                                self.start_offsets[opponent.color] + tok.position
                            ) % self.ring_len
                            if opp_abs == moved_abs:
                                tok.position = None
                                tok.is_home  = False
                                await self.send_announcement(
                                    f"{player.name} captured {opponent.name}'s token #{idx+1}!"
                                )

            # ─── Broadcast & announce move ────────────────────────────────────────────
            await self.broadcast_board_update()
            await self.send_announcement(
                f"{player.name} moved token {chosen_index} to {new_pos}"
            )

            # ─── Check for win ─────────────────────────────────────────────────────────
            if player.check_win():
                await self.send_announcement(f"{player.name} wins the game! 🎉")
                self.game_over = True
                return  # stop everything immediately

            # ─── Extra turn on 6? ──────────────────────────────────────────────────────
            if roll == 6:
                await asyncio.sleep(1)
                await self.send_announcement(
                    f"{player.name} rolled a 6 and gets another turn!"
                )
                continue  # go back to top of while → roll again

            # no extra turn, end this player's play
            break


    async def start_game(self):
        await self.send_announcement("Ludo Game Started!")
        await asyncio.sleep(1)
        await self.broadcast_board_update()
        while not self.game_over:
            current_player = self.players[self.current_player_idx]
            await self.play_turn(current_player)
            self.current_player_idx = self.next_player_idx()
            
    
        await self.send_announcement("Game Over!")
