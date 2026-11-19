"""Bridge local single-player input to the future versioned game-command protocol.

The adapter intentionally depends on the game through a small duck-typed surface,
so the protocol module remains independent from Pygame and the game implementation.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from multiplayer_protocol import GameCommand, ProtocolError


class LocalGameCommandAdapter:
    """Translate local player intents into the same commands planned for multiplayer."""

    def __init__(self, game: Any, player_id: str = "local") -> None:
        self.game = game
        self.player_id = player_id
        self.sequence = 0
        self.revision = 0
        self.order_ids: Dict[str, Tuple[str, int, int]] = {}
        self.last_command: Optional[GameCommand] = None

    def reset_world(self) -> None:
        """Reset local ordering metadata when a new world is generated or loaded."""
        self.revision = 0
        self.order_ids.clear()
        self.last_command = None

    def dispatch(self, action: str, payload: Dict[str, Any]) -> bool:
        """Create, validate, and apply one local command through the protocol."""
        self.sequence += 1
        command = GameCommand.create(
            self.player_id, self.sequence, self.revision, action, payload
        )
        self.last_command = command
        accepted = self._apply(command)
        if accepted:
            self.revision += 1
        return accepted

    def _apply(self, command: GameCommand) -> bool:
        payload = command.payload
        action = command.action
        game = self.game

        if action == "move_worker":
            x, y = payload["x"], payload["y"]
            if not game.worker_can_stand(x, y):
                return False
            game.set_worker_destination(x, y)
            return True

        if action == "queue_work":
            tool, x, y = payload["tool"], payload["x"], payload["y"]
            target = (tool, x, y)
            was_queued = target in game.work_queue
            game.toggle_work_order(tool, x, y)
            is_queued = target in game.work_queue
            if is_queued and not was_queued:
                self.order_ids[command.command_id] = target
                return True
            if was_queued and not is_queued:
                for order_id, queued in list(self.order_ids.items()):
                    if queued[1:] == (x, y):
                        self.order_ids.pop(order_id, None)
                return True
            return False

        if action == "cancel_work":
            order_id = payload["order_id"]
            target = self.order_ids.pop(order_id, None)
            if target is None or target not in game.work_queue:
                return False
            game.toggle_work_order(target[0], target[1], target[2])
            return target not in game.work_queue

        if action == "rotate_road":
            tile = (payload["x"], payload["y"])
            if game.tool != "road" or tile not in game.roads:
                return False
            old_axis = game.road_directions.get(tile, "x")
            game.selected_road_tile = tile
            game.toggle_road_direction()
            return game.road_directions.get(tile, "x") != old_axis

        if action == "expand_land":
            old_level = game.expand_level
            game.expand_land()
            return game.expand_level > old_level

        if action == "upgrade_building":
            anchor = (payload["x"], payload["y"])
            previous_selection = game.selected_structure_anchor
            before = (
                game.population, game.money,
                game.house_levels.get(anchor),
                game.city_objects.get(anchor, {}).get("level"),
            )
            game.selected_structure_anchor = anchor
            game.upgrade_selected_structure()
            after = (
                game.population, game.money,
                game.house_levels.get(anchor),
                game.city_objects.get(anchor, {}).get("level"),
            )
            game.selected_structure_anchor = previous_selection
            return before != after

        raise ProtocolError(f"unsupported local command action: {action}")
