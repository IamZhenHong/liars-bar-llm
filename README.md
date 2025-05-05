# Liar's Bar Game

A multiplayer turn-based card game with AI and human players, built using FastAPI and WebSockets.

## Game Overview

Liar's Bar is a strategic card game where players take turns playing cards while trying to avoid penalties. The game features:
- Support for both human and AI players
- Real-time gameplay using WebSockets
- Dynamic player interactions and challenges
- AI players with customizable personalities
- Reflection phase for players to update their opinions of others

## Architecture

The game follows a modular design that can be adapted for other turn-based games. Here's the core architecture:

### 1. Game Server (`game_server.py`)
- FastAPI-based web server
- Handles game initialization and WebSocket connections
- Manages game state and player interactions
- Routes:
  - `/`: Main game interface
  - `/start_game`: Initialize new game
  - `/ws/{game_id}/{player_name}`: WebSocket endpoint for real-time gameplay

### 2. Game Core (`game.py`)
- Core game logic and state management
- Turn management and round progression
- Handles game rules and validations
- Manages player interactions and challenges

### 3. Player System (`player.py`)
- Base player class with common functionality
- Support for both human and AI players
- Handles player actions and decisions
- Manages player state and hand

### 4. Web Interface (`templates/index.html`)
- Real-time game interface
- Handles player inputs and game state display
- Shows announcements and game logs
- Manages player interactions

## Adapting to Other Turn-Based Games

The modular design can be adapted for games like Ludo or Uno. Here's how:

### 1. Game Rules Module
```python
class GameRules:
    def __init__(self):
        self.rules = {}
        self.valid_moves = {}
        self.win_conditions = {}
```

### 2. Game Board Module
```python
class GameBoard:
    def __init__(self):
        self.board_state = {}
        self.pieces = {}
        self.positions = {}
```

### 3. Player Actions Module
```python
class PlayerActions:
    def __init__(self):
        self.available_actions = {}
        self.action_validators = {}
        self.action_handlers = {}
```

### Example: Adapting for Ludo

```python
class LudoGame(Game):
    def __init__(self, players):
        super().__init__(players)
        self.board = LudoBoard()
        self.rules = LudoRules()
        self.pieces = {player: [] for player in players}

    async def play_round(self):
        # Ludo-specific round logic
        current_player = self.get_current_player()
        dice_roll = await self.roll_dice()
        valid_moves = self.rules.get_valid_moves(current_player, dice_roll)
        move = await current_player.choose_move(valid_moves)
        await self.execute_move(current_player, move)
```

### Example: Adapting for Uno

```python
class UnoGame(Game):
    def __init__(self, players):
        super().__init__(players)
        self.deck = UnoDeck()
        self.discard_pile = []
        self.rules = UnoRules()

    async def play_round(self):
        # Uno-specific round logic
        current_player = self.get_current_player()
        valid_cards = self.rules.get_playable_cards(current_player.hand, self.discard_pile[-1])
        card = await current_player.choose_card(valid_cards)
        await self.play_card(current_player, card)
```

## Key Design Patterns

1. **State Management**
   - Centralized game state
   - Immutable state updates
   - Event-driven state changes

2. **Player Abstraction**
   - Common interface for human and AI players
   - Pluggable decision-making systems
   - Extensible player types

3. **Game Rules Engine**
   - Rule validation
   - Move generation
   - Win condition checking

4. **Real-time Communication**
   - WebSocket-based updates
   - Event broadcasting
   - State synchronization

## Getting Started

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Start the server:
```bash
python game_server.py
```

3. Open the game interface at `http://localhost:8000`

## Requirements

- Python 3.8+
- FastAPI
- WebSockets
- Jinja2
- Uvicorn

## Future Enhancements

1. **Game Variants**
   - Support for different rule sets
   - Custom game modes
   - Tournament play

2. **AI Improvements**
   - More sophisticated AI strategies
   - Learning capabilities
   - Personality customization

3. **UI Enhancements**
   - Mobile support
   - Animations
   - Sound effects

4. **Social Features**
   - Chat system
   - Player rankings
   - Game history

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.