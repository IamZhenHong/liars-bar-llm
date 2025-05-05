import random
from typing import List, Optional, Dict
from player import Player
from game_record import GameRecord, PlayerInitialState

import asyncio
from human_player_names import human_player_names


class Game:
    def __init__(self, player_configs: List[Dict[str, str]], game_id: str):
        """
        Initialize a new game instance.
        
        Args:
            player_configs (List[Dict[str, str]]): List of player configurations
            game_id (str): Unique identifier for the game
        """
        self.game_id = game_id
        self.players = [
            Player(config["name"], config["model"], config.get("is_human", False), config.get("personality", ""), game_id)
            for config in player_configs
        ]

        for player in self.players:
            player.init_opinions(self.players)

        self.deck: List[str] = []
        self.target_card: Optional[str] = None
        self.current_player_idx: int = random.randint(0, len(self.players) - 1)
        self.last_shooter_name: Optional[str] = None
        self.game_over: bool = False

        self.game_record: GameRecord = GameRecord()
        self.game_record.start_game([p.name for p in self.players])
        self.round_count = 0

    async def send_announcement(self, message: str):
        """
        Send an announcement to all human players.
        
        Args:
            message (str): The announcement message to send
        """
        from websocket_manager import websocket_manager
        for name in human_player_names:
            
            await websocket_manager.send(self.game_id,name, {
                "type": "announcement",
                "message": message
            })
        await asyncio.sleep(1)

    def _create_deck(self) -> List[str]:
        """
        Create a new deck of cards.
        
        Returns:
            List[str]: A shuffled deck of cards
        """
        return ['Q'] * 6 + ['K'] * 6 + ['A'] * 6 + ['Joker'] * 2

    def deal_cards(self) -> None:
        """
        Deal cards to all alive players.
        """
        self.deck = self._create_deck()
        random.shuffle(self.deck)
        for player in self.players:
            if player.alive:
                player.hand.clear()
        for _ in range(5):
            for player in self.players:
                if player.alive and self.deck:
                    player.hand.append(self.deck.pop())

    def choose_target_card(self) -> None:
        """
        Randomly select a target card for the round.
        """
        self.target_card = random.choice(['Q', 'K', 'A'])

    def start_round_record(self) -> None:
        """
        Start recording a new round in the game record.
        """
        self.round_count += 1
        starting_player = self.players[self.current_player_idx].name
        player_initial_states = [
            PlayerInitialState(
                player_name=player.name,
                bullet_position=player.bullet_position,
                current_gun_position=player.current_bullet_position,
                initial_hand=player.hand.copy()
            ) 
            for player in self.players if player.alive
        ]
        round_players = [player.name for player in self.players if player.alive]
        player_opinions = {
            player.name: {target: opinion for target, opinion in player.opinions.items()}
            for player in self.players
        }
        self.game_record.start_round(
            round_id=self.round_count,
            target_card=self.target_card,
            round_players=round_players,
            starting_player=starting_player,
            player_initial_states=player_initial_states,
            player_opinions=player_opinions
        )

    def is_valid_play(self, cards: List[str]) -> bool:
        """
        Check if a play is valid.
        
        Args:
            cards (List[str]): Cards being played
            
        Returns:
            bool: Whether the play is valid
        """
        return all(card == self.target_card or card == 'Joker' for card in cards)

    def find_next_player_with_cards(self, start_idx: int) -> int:
        """
        Find the next player who has cards to play.
        
        Args:
            start_idx (int): Index to start searching from
            
        Returns:
            int: Index of the next player with cards
        """
        idx = start_idx
        for _ in range(len(self.players)):
            idx = (idx + 1) % len(self.players)
            if self.players[idx].alive and self.players[idx].hand:
                return idx
        return start_idx

    async def perform_penalty(self, player: Player) -> None:
        """
        Perform the penalty phase for a player.
        
        Args:
            player (Player): Player to perform penalty on
        """
        print(player.name, "fires the gun!")
        await self.send_announcement(f"[PENALTY] {player.name} is being penalized!")
        still_alive = await player.process_penalty()
        self.last_shooter_name = player.name
        self.game_record.record_shooting(
            shooter_name=player.name,
            bullet_hit=not still_alive
        )
        if not still_alive:
            print(f"{player.name} is eliminated!")
            await self.send_announcement(f"{player.name} is eliminated!")
        await asyncio.sleep(1)

    async def reset_round(self, record_shooter: bool) -> None:
        """
        Reset the game state for a new round.
        
        Args:
            record_shooter (bool): Whether to record the last shooter
        """
        print("Resetting round")
        await self.send_announcement("Resetting round")
        await asyncio.sleep(1)
        alive_players = await self.handle_reflection()
        self.deal_cards()
        self.choose_target_card()
        if record_shooter and self.last_shooter_name:
            shooter_idx = next((i for i, p in enumerate(self.players)
                                if p.name == self.last_shooter_name), None)
            if shooter_idx is not None and self.players[shooter_idx].alive:
                self.current_player_idx = shooter_idx
            else:
                self.current_player_idx = self.find_next_player_with_cards(shooter_idx or 0)
        else:
            self.last_shooter_name = None
            self.current_player_idx = self.players.index(random.choice(alive_players))
        self.start_round_record()
        print(f"New round starts with {self.players[self.current_player_idx].name}")
        await self.send_announcement(f"New round starts with {self.players[self.current_player_idx].name}")
        await asyncio.sleep(1)

    async def check_victory(self) -> bool:
        """
        Check if the game has been won.
        
        Returns:
            bool: Whether the game has been won
        """
        from websocket_manager import websocket_manager
        alive_players = [p for p in self.players if p.alive]
        if len(alive_players) == 1:
            winner = alive_players[0]
            print(f"{winner.name} wins!")
            await self.send_announcement(f"{winner.name} wins!")
            human_player = next((p for p in self.players if p.is_human), None)
            if human_player:
                await websocket_manager.send(human_player.name, {
                    "type": "game_over",
                    "message": f"No one else is alive! {winner.name} wins!"
                })
            self.game_record.finish_game(winner.name)
            self.game_over = True
            return True
        return False

    def check_other_players_no_cards(self, current_player: Player) -> bool:
        """
        Check if other players have no cards.
        
        Args:
            current_player (Player): Current player to exclude from check
            
        Returns:
            bool: Whether other players have no cards
        """
        others = [p for p in self.players if p != current_player and p.alive]
        return all(not p.hand for p in others)

    async def handle_play_cards(self, current_player: Player, next_player: Player) -> List[str]:
        """
        Handle a player playing cards.
        
        Args:
            current_player (Player): Player making the play
            next_player (Player): Next player in turn
            
        Returns:
            List[str]: Cards that were played
        """
        round_base_info = self.game_record.get_latest_round_info()
        round_action_info = self.game_record.get_latest_round_actions(current_player.name, include_latest=True)
        play_decision_info = self.game_record.get_play_decision_info(current_player.name, next_player.name)
        play_result, reasoning = await current_player.choose_cards_to_play(round_base_info, round_action_info, play_decision_info)
        self.game_record.record_play(
            player_name=current_player.name,
            played_cards=play_result["played_cards"].copy(),
            remaining_cards=current_player.hand.copy(),
            play_reason=play_result["play_reason"],
            behavior=play_result["behavior"],
            next_player=next_player.name,
            play_thinking=reasoning
        )
        await asyncio.sleep(1)
        return play_result["played_cards"]

    async def handle_challenge(self, current_player: Player, next_player: Player, played_cards: List[str]) -> Player:
        """
        Handle a challenge to a player's play.
        
        Args:
            current_player (Player): Player who made the play
            next_player (Player): Player making the challenge
            played_cards (List[str]): Cards that were played
            
        Returns:
            Player: Player who should be penalized, or None if no penalty
        """
        round_base_info = self.game_record.get_latest_round_info()
        round_action_info = self.game_record.get_latest_round_actions(next_player.name, include_latest=False)
        challenge_decision_info = self.game_record.get_challenge_decision_info(next_player.name, current_player.name)
        challenging_player_behavior = self.game_record.get_latest_play_behavior()
        extra_hint = "注意：其他玩家手牌均已打空。" if self.check_other_players_no_cards(next_player) else ""
        challenge_result, reasoning = await next_player.decide_challenge(
            round_base_info, round_action_info, challenge_decision_info, challenging_player_behavior, extra_hint
        )

        if challenge_result["was_challenged"]:
            is_valid = self.is_valid_play(played_cards)
            self.game_record.record_challenge(
                was_challenged=True,
                reason=challenge_result["challenge_reason"],
                result=not is_valid,
                challenge_thinking=reasoning
            )
            await self.send_announcement(f"{next_player.name} challenges {current_player.name}'s hand")
            await asyncio.sleep(1)
            if is_valid:
                print(f"{next_player.name}'s challenge failed")
                await self.send_announcement(f"{next_player.name}'s challenge failed")
            else:
                print(f"{current_player.name}'s hand is invalid → penalty")
                await self.send_announcement(f"{current_player.name}'s hand is invalid → penalty")
            return next_player if is_valid else current_player
        else:
            self.game_record.record_challenge(
                was_challenged=False,
                reason=challenge_result["challenge_reason"],
                result=None,
                challenge_thinking=reasoning
            )
            return None

    async def handle_system_challenge(self, current_player: Player) -> None:
        """
        Handle a system-initiated challenge.
        
        Args:
            current_player (Player): Player being challenged
        """
        print(f"System challenges {current_player.name}'s hand")
        await self.send_announcement(f"System challenges {current_player.name}'s hand")
        await asyncio.sleep(1)
        await self.send_announcement(f"{current_player.name} left with {len(current_player.hand)} cards")
        await asyncio.sleep(1)
        all_cards = current_player.hand.copy()
        current_player.hand.clear()
        self.game_record.record_play(
            player_name=current_player.name,
            played_cards=all_cards,
            remaining_cards=[],
            play_reason="最后一人，自动出牌",
            behavior="无",
            next_player="无",
            play_thinking=""
        )
        is_valid = self.is_valid_play(all_cards)
        self.game_record.record_challenge(
            was_challenged=True,
            reason="系统自动质疑",
            result=not is_valid,
            challenge_thinking=""
        )
        await asyncio.sleep(1)
        if is_valid:
            print(f"{current_player.name}'s hand is valid")
            await self.send_announcement(f"{current_player.name}'s hand is valid")
            self.game_record.record_shooting(
                shooter_name="无",
                bullet_hit=False
            )
            await self.reset_round(record_shooter=False)
        else:
            print(f"{current_player.name}'s hand is invalid → penalty")
            await self.send_announcement(f"{current_player.name}'s hand is invalid → penalty")
            await self.perform_penalty(current_player)

    async def handle_reflection(self) -> None:
        """
        Handle the reflection phase where players update their opinions.
        
        Returns:
            List[Player]: List of alive players
        """
        alive_players = [p for p in self.players if p.alive]
        alive_player_names = [p.name for p in alive_players]
        round_base_info = self.game_record.get_latest_round_info()
        for player in alive_players:
            round_action_info = self.game_record.get_latest_round_actions(player.name, include_latest=True)
            round_result = self.game_record.get_latest_round_result(player.name)
            await player.reflect(
                alive_players=alive_player_names,
                round_base_info=round_base_info,
                round_action_info=round_action_info,
                round_result=round_result
            )
        return alive_players

    def print_all_player_states(self):
        """
        Print the current state of all players.
        
        Returns:
            str: Formatted string of player states
        """
        state_lines = [f"{player.name} ({'Alive' if player.alive else 'Dead'}): {', '.join(player.hand)}" for player in self.players]
        return "\n".join(state_lines)
    
    def all_human_players_eliminated(self) -> bool:
        """
        Check if all human players have been eliminated.
        
        Returns:
            bool: Whether all human players are eliminated
        """
        return not any(player.is_human and player.alive for player in self.players)

    async def play_round(self) -> None:
        """
        Play a single round of the game.
        """
        print("Sending game state to all players")
        await self.announce_current_game_state()
        print("Sent game state to all players")
            
        current_player = self.players[self.current_player_idx]
        if not current_player.alive or not current_player.hand:
            self.current_player_idx = self.find_next_player_with_cards(self.current_player_idx)
            return

        if self.check_other_players_no_cards(current_player):
            await self.handle_system_challenge(current_player)
            if not current_player.alive:
                print("Last player with cards is eliminated!")
                await self.send_announcement("Last player with cards is eliminated!")
                self.game_record.record_shooting(
                    shooter_name="无",
                    bullet_hit=False
                )
                await self.send_announcement("Round ends")
                await self.reset_round(record_shooter=False)
                return

            if not current_player.hand:
                print("Last player with cards has no cards left!")
                await self.send_announcement("Last player with cards has no cards left!")
                self.game_over = True
                await self.send_announcement(f"{current_player.name} wins!")

            return

        print(f"Current player: {current_player.name}")
        await self.send_announcement(f"{current_player.name}'s turn — target: {self.target_card}")
        await asyncio.sleep(1)

        next_idx = self.find_next_player_with_cards(self.current_player_idx)
        next_player = self.players[next_idx]
        played_cards = await self.handle_play_cards(current_player, next_player)

        if next_player != current_player:
            player_to_penalize = await self.handle_challenge(current_player, next_player, played_cards)

            if player_to_penalize:
                await self.perform_penalty(player_to_penalize)
                if player_to_penalize == current_player and not current_player.alive:
                    return
            else:
                print(f"{next_player.name} did not challenge")
                await self.send_announcement(f"{next_player.name} did not challenge")
                self.game_record.record_challenge(
                    was_challenged=False,
                    reason="未质疑",
                    result=None,
                    challenge_thinking=""
                )
                await asyncio.sleep(1)

        self.current_player_idx = next_idx
        await asyncio.sleep(2)

    async def announce_current_game_state(self) -> None:
        """
        Announce the current game state to all players.
        """
        from websocket_manager import websocket_manager
        for name in human_player_names:
            await websocket_manager.send(self.game_id,name, {
                "type": "game_state",
                "message": self.print_all_player_states()
            })
        await asyncio.sleep(1)

    async def start_game(self) -> None:
        """
        Start the game and run the main game loop.
        """
        from websocket_manager import websocket_manager
        print("Active connections:", websocket_manager.active_connections)
        print("Connected to game server", self.game_id) 
        print("Waiting for players to connect...")
        print("Game loop begins")
        await self.send_announcement("Game loop begins")
        await asyncio.sleep(0.5)
        self.deal_cards()
        self.choose_target_card()
        self.start_round_record()
        while not self.game_over:
            await self.play_round()
