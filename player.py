import random
import json
import re
from typing import List, Dict
from llm_client import LLMClient
import asyncio
from human_player_names import human_player_names
RULE_BASE_PATH = "prompt/rule_base.txt"
PLAY_CARD_PROMPT_TEMPLATE_PATH = "prompt/play_card_prompt_template.txt"
CHALLENGE_PROMPT_TEMPLATE_PATH = "prompt/challenge_prompt_template.txt"
REFLECT_PROMPT_TEMPLATE_PATH = "prompt/reflect_prompt_template.txt"

class Player:
    def __init__(self, name: str, model_name: str, is_human: bool = False, personality: str = "", game_id: str = ""):
        self.game_id = game_id
        self.name = name
        self.personality = personality
        self.hand = []
        self.alive = True
        self.bullet_position = random.randint(0, 5)
        self.current_bullet_position = 0
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
        from websocket_manager import websocket_manager
        for name in human_player_names:
            await websocket_manager.send(self.game_id, name, {
                "type": "announcement",
                "message": message
            })

    # async def send_status(self) -> None:
    #     for name in human_player_names:
    #         await websocket_manager.send(name, {
    #             "type": "status",
    #             "player": self.name,
    #             "hand": self.hand,
    #             "bullet_position": self.bullet_position,
    #             "current_bullet_position": self.current_bullet_position
    #         })
    async def print_status(self) -> None:
        print(f"[STATUS] {self.name} - 手牌: {', '.join(self.hand)} - 子弹位置: {self.bullet_position} - 当前弹舱位置: {self.current_bullet_position}")
        await self.send_announcement(f"[STATUS] {self.name} - 手牌: {', '.join(self.hand)} - 子弹位置: {self.bullet_position} - 当前弹舱位置: {self.current_bullet_position}")

    def init_opinions(self, other_players: List["Player"]) -> None:
        self.opinions = {
            player.name: "还不了解这个玩家"
            for player in other_players
            if player.name != self.name
        }

    async def choose_cards_to_play(self,
                                   round_base_info: str,
                                   round_action_info: str,
                                   play_decision_info: str) -> Dict:
        print(f"[INFO] {self.name} is choosing cards to play")
        await self.send_announcement(f"[TURN] {self.name} is choosing cards to play")

        await asyncio.sleep(2)

        if self.is_human:
            for name in human_player_names:
                from websocket_manager import websocket_manager
                if name in websocket_manager.pending_responses:
                    await websocket_manager.send(name, {
                        "type": "your_turn",
                        "player": self.name,
                        "hand": self.hand,
                        "round_info": round_base_info,
                        "action_info": round_action_info,
                        "decision_info": play_decision_info
                    })
                    temp_name = name

            
            data = await websocket_manager.wait_for_response(self.game_id, temp_name)   
            await self.send_announcement(f"[TURN] {self.name} played cards: {data['played_cards']}")
            for card in data["played_cards"]:
                if card in self.hand:
                    self.hand.remove(card)
            return {
                "played_cards": data["played_cards"],
                "play_reason": data.get("play_reason", ""),
                "behavior": data.get("behavior", "无")
            }, "(human input via websocket)"

        rules = await self._read_file(RULE_BASE_PATH)
        template = await self._read_file(PLAY_CARD_PROMPT_TEMPLATE_PATH)
        current_cards = ", ".join(self.hand)
        prompt = template.format(
            rules=rules,
            self_name=self.name,
            round_base_info=round_base_info,
            round_action_info=round_action_info,
            play_decision_info=play_decision_info,
            current_cards=current_cards
        )
        for attempt in range(5):
            prompt += f"This is your personality: {self.personality}"
            messages = [{"role": "user", "content": prompt}]
            try:
                content, reasoning_content = self.llm_client.chat(messages, model=self.model_name)
                json_match = re.search(r'({[\s\S]*})', content)
                if json_match:
                    json_str = json_match.group(1)
                    result = json.loads(json_str)
                    if all(key in result for key in ["played_cards", "behavior", "play_reason"]):
                        if not isinstance(result["played_cards"], list):
                            result["played_cards"] = [result["played_cards"]]
                        valid_cards = all(card in self.hand for card in result["played_cards"])
                        valid_count = 1 <= len(result["played_cards"]) <= 3
                        if valid_cards and valid_count:
                            # await self.send_announcement(f"[TURN] {self.name} played cards: {result['played_cards']}, reason: {result['play_reason']}, behavior: {result['behavior']}")
                            await self.send_announcement(f"[TURN] {self.name} played {len(result['played_cards'])} cards, behavior: {result['behavior']}")
                            await asyncio.sleep(1.5)
                            for card in result["played_cards"]:
                                self.hand.remove(card)
                            return result, reasoning_content
            except Exception as e:
                print(f"[ERROR] Attempt {attempt+1} failed to parse card choice: {str(e)}")
                await self.send_announcement(f"[ERROR] Attempt {attempt+1} failed to parse card choice: {str(e)}")
        raise RuntimeError(f"[FAIL] {self.name} failed to choose valid cards to play")

    async def decide_challenge(self,
                               round_base_info: str,
                               round_action_info: str,
                               challenge_decision_info: str,
                               challenging_player_performance: str,
                               extra_hint: str) -> bool:
        print(f"[INFO] {self.name} is deciding whether to challenge")
        from websocket_manager import websocket_manager
        await self.send_announcement(f"[CHALLENGE] {self.name} is deciding whether to challenge")

        if self.is_human:
            # self.name
            for name in human_player_names:
                if name in websocket_manager.pending_responses:
                    await websocket_manager.send(name, {
                        "type": "challenge_request",
                        "player": self.name,
                        "round_info": round_base_info,
                        "action_info": round_action_info,
                        "challenge_decision_info": challenge_decision_info,
                        "challenging_player_performance": challenging_player_performance,
                        "extra_hint": extra_hint
                    })
                    temp_name = name

            data = await websocket_manager.wait_for_response(self.game_id,temp_name)
            # if data["was_challenged"]:
            #     await self.send_announcement(f"[CHALLENGE] {self.name} decided to challenge")
            #     await asyncio.sleep(1)
            # else:
            #     await self.send_announcement(f"[CHALLENGE] {self.name} decided not to challenge")
            #     await asyncio.sleep(1)
            return {
                "was_challenged": data["was_challenged"],
                "challenge_reason": data["challenge_reason"]
            }, "(challenge input via websocket)"

        rules = await  self._read_file(RULE_BASE_PATH)
        template = await self._read_file(CHALLENGE_PROMPT_TEMPLATE_PATH)
        self_hand = f"你现在的手牌是: {', '.join(self.hand)}"
        prompt = template.format(
            rules=rules,
            self_name=self.name,
            round_base_info=round_base_info,
            round_action_info=round_action_info,
            self_hand=self_hand,
            challenge_decision_info=challenge_decision_info,
            challenging_player_performance=challenging_player_performance,
            extra_hint=extra_hint
        )
        for attempt in range(5):
            prompt += f"This is your personality: {self.personality}"
            messages = [{"role": "user", "content": prompt}]
            try:
                content, reasoning_content = self.llm_client.chat(messages, model=self.model_name)
                json_match = re.search(r'({[\s\S]*})', content)
                if json_match:
                    json_str = json_match.group(1)
                    result = json.loads(json_str)
                    if all(key in result for key in ["was_challenged", "challenge_reason"]):
                        if isinstance(result["was_challenged"], bool):
                            return result, reasoning_content
            except Exception as e:
                print(f"[ERROR] Attempt {attempt+1} failed to parse challenge decision: {str(e)}")
                # await self.send_announcement(f"[ERROR] Attempt {attempt+1} failed to parse challenge decision: {str(e)}")
        raise RuntimeError(f"[FAIL] {self.name} failed to decide challenge")

    async def reflect(self, alive_players: List[str], round_base_info: str, round_action_info: str, round_result: str) -> None:
        from websocket_manager import websocket_manager
        print(f"[INFO] {self.name} is reflecting on the game")
        await self.send_announcement(f"[REFLECT] {self.name} is reflecting")
        await asyncio.sleep(1.5)
        if self.is_human:
            async def send_reflection_prompt():
                await websocket_manager.send(self.name, {
                    "type": "reflect",
                    "player": self.name,
                    "alive_players": alive_players,
                    "round_info": round_base_info,
                    "action_info": round_action_info,
                    "round_result": round_result,
                    "opinions": {
                        other: self.opinions.get(other, "还不了解这个玩家")
                        for other in alive_players if other != self.name
                    }
                })

                data = await websocket_manager.wait_for_response(self.game_id,self.name)

                for player_name, new_opinion in data.get("updated_opinions", {}).items():
                    if new_opinion:
                        self.opinions[player_name] = new_opinion
                        print(f"[INFO] {self.name} updated opinion on {player_name}: {new_opinion}")
                        await self.send_announcement(f"[REFLECT] {self.name} updated opinion on {player_name}: {new_opinion}")
                        await asyncio.sleep(1)

            await send_reflection_prompt()
            return

        template = await self._read_file(REFLECT_PROMPT_TEMPLATE_PATH)
        rules = await self._read_file(RULE_BASE_PATH)
        for player_name in alive_players:
            if player_name == self.name:
                continue
            previous_opinion = self.opinions.get(player_name, "还不了解这个玩家")
            prompt = template.format(
                rules=rules,
                self_name=self.name,
                round_base_info=round_base_info,
                round_action_info=round_action_info,
                round_result=round_result,
                player=player_name,
                previous_opinion=previous_opinion
            )
            messages = [{"role": "user", "content": prompt}]
            try:
                content, _ = self.llm_client.chat(messages, model=self.model_name)
                self.opinions[player_name] = content.strip()
                print(f"[INFO] {self.name} updated opinion on {player_name}: {self.opinions[player_name]}")
                await self.send_announcement(f"[REFLECT] {self.name} updated opinion on {player_name}")
                await asyncio.sleep(1)
            except Exception as e:
                print(f"[ERROR] Failed to reflect on {player_name}: {str(e)}")
                # await self.send_announcement(f"[ERROR] Reflecting on {player_name} failed: {str(e)}")
                

    async def process_penalty(self) -> bool:
        print(f"{self.name} fires a shot")
        await self.send_announcement(f"{self.name} fires a shot")
        await asyncio.sleep(1)
        await self.print_status()
        await asyncio.sleep(1)

        if self.bullet_position == self.current_bullet_position:
            print(self.name, "was shot and died")
            await self.send_announcement(f"[PENALTY] {self.name} was shot and died")
            await asyncio.sleep(1)
            self.alive = False
        else:
            print(self.name, "survived the shot")
            await self.send_announcement(f"[PENALTY] {self.name} survived the shot")
            await asyncio.sleep(1)

        await asyncio.sleep(1.5)  # Let moment land in UI
        self.current_bullet_position = (self.current_bullet_position + 1) % 6
        return self.alive
