# state.py
from typing import Dict
from game_server import Game   # or wherever your Game class lives

# this lives in its own module, so nothing else imports *from* game_server
games: Dict[str, Game] = {}
