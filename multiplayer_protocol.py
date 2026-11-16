"""Versioned, transport-independent command protocol for future multiplayer.

This module deliberately has no Firebase, socket, or Pygame dependency. The
server will own CommandGate and WorldSnapshot revisions; clients send commands
and render snapshots rather than writing shared city state directly.
"""
from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Mapping, Optional, Set
from uuid import uuid4

PROTOCOL_VERSION = 1
SNAPSHOT_SCHEMA_VERSION = 1
MAX_COMMAND_BYTES = 8192
MAX_RECENT_COMMAND_IDS = 4096
MAP_WIDTH = 44
MAP_HEIGHT = 44

# These are intent messages, not arbitrary Python method names. A future server
# must still re-check ownership, range, costs, terrain and queue rules.
ACTION_PAYLOAD_KEYS = {
    "move_worker": {"x", "y"},
    "queue_work": {"tool", "x", "y"},
    "cancel_work": {"order_id"},
    "rotate_road": {"x", "y"},
    "expand_land": set(),
    "upgrade_building": {"x", "y"},
}


class ProtocolError(ValueError):
    """Raised when a network message does not match the protocol."""


def _require_id(value: Any, field: str) -> str:
    if (not isinstance(value, str) or not value or len(value) > 80
            or value.strip() != value or not value.isprintable()):
        raise ProtocolError(f"{field} must be a printable string of at most 80 characters")
    return value


def _require_int(value: Any, field: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ProtocolError(f"{field} must be an integer >= {minimum}")
    return value


def _validate_payload(action: str, payload: Any) -> Dict[str, Any]:
    if not isinstance(action, str) or action not in ACTION_PAYLOAD_KEYS:
        raise ProtocolError(f"unsupported action: {action}")
    if not isinstance(payload, dict):
        raise ProtocolError("payload must be an object")
    if set(payload) != ACTION_PAYLOAD_KEYS[action]:
        raise ProtocolError(f"invalid payload fields for {action}")

    clean = dict(payload)
    if action in {"move_worker", "queue_work", "rotate_road", "upgrade_building"}:
        x = _require_int(clean.get("x"), "x")
        y = _require_int(clean.get("y"), "y")
        if x >= MAP_WIDTH or y >= MAP_HEIGHT:
            raise ProtocolError("tile coordinate is outside the map")
    if action == "queue_work":
        if not isinstance(clean["tool"], str) or clean["tool"] not in {
            "clear", "demolish", "road", "house", "dig", "mine", "restore",
            "commercial", "industrial", "public", "park", "lamp",
            "decor_tree", "logging",
        }:
            raise ProtocolError("unsupported work tool")
    if action == "cancel_work":
        _require_id(clean["order_id"], "order_id")
    return clean


@dataclass(frozen=True)
class GameCommand:
    """One player intent, ordered against a server-authoritative world revision."""

    command_id: str
    player_id: str
    sequence: int
    expected_revision: int
    action: str
    payload: Dict[str, Any]
    protocol_version: int = PROTOCOL_VERSION

    def __post_init__(self) -> None:
        _require_id(self.command_id, "command_id")
        _require_id(self.player_id, "player_id")
        _require_int(self.sequence, "sequence", 1)
        _require_int(self.expected_revision, "expected_revision")
        if type(self.protocol_version) is not int or self.protocol_version != PROTOCOL_VERSION:
            raise ProtocolError("unsupported protocol version")
        object.__setattr__(self, "payload", _validate_payload(self.action, self.payload))
        if len(self.to_json().encode("utf-8")) > MAX_COMMAND_BYTES:
            raise ProtocolError("command is too large")

    @classmethod
    def create(
        cls,
        player_id: str,
        sequence: int,
        expected_revision: int,
        action: str,
        payload: Mapping[str, Any],
    ) -> "GameCommand":
        return cls(
            command_id=str(uuid4()),
            player_id=player_id,
            sequence=sequence,
            expected_revision=expected_revision,
            action=action,
            payload=dict(payload),
        )

    @classmethod
    def from_dict(cls, raw: Any) -> "GameCommand":
        if not isinstance(raw, dict):
            raise ProtocolError("command must be an object")
        required = {
            "protocol_version", "command_id", "player_id", "sequence",
            "expected_revision", "action", "payload",
        }
        if set(raw) != required:
            raise ProtocolError("command has missing or unexpected fields")
        return cls(
            command_id=raw["command_id"],
            player_id=raw["player_id"],
            sequence=raw["sequence"],
            expected_revision=raw["expected_revision"],
            action=raw["action"],
            payload=raw["payload"],
            protocol_version=raw["protocol_version"],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "protocol_version": self.protocol_version,
            "command_id": self.command_id,
            "player_id": self.player_id,
            "sequence": self.sequence,
            "expected_revision": self.expected_revision,
            "action": self.action,
            "payload": dict(self.payload),
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(), ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        )


@dataclass(frozen=True)
class CommandDecision:
    accepted: bool
    reason: str
    revision: int


class CommandGate:
    """Server-side duplicate, sequence and stale-world protection.

    Call accept only after authenticating the player and checking that the
    command is allowed in the current game phase. The gate is not a substitute
    for validating game rules or player permissions.
    """

    def __init__(self, initial_revision: int = 0) -> None:
        self.revision = _require_int(initial_revision, "initial_revision")
        self._last_sequence: Dict[str, int] = {}
        self._recent_ids: Set[str] = set()
        self._recent_order: Deque[str] = deque()

    def accept(self, command: GameCommand) -> CommandDecision:
        if command.command_id in self._recent_ids:
            return CommandDecision(False, "duplicate_command", self.revision)
        last = self._last_sequence.get(command.player_id, 0)
        if command.sequence <= last:
            return CommandDecision(False, "out_of_order_sequence", self.revision)
        if command.expected_revision != self.revision:
            return CommandDecision(False, "stale_world_revision", self.revision)

        self._last_sequence[command.player_id] = command.sequence
        self._recent_ids.add(command.command_id)
        self._recent_order.append(command.command_id)
        while len(self._recent_order) > MAX_RECENT_COMMAND_IDS:
            expired = self._recent_order.popleft()
            self._recent_ids.discard(expired)
        self.revision += 1
        return CommandDecision(True, "accepted", self.revision)

    def last_sequence(self, player_id: str) -> int:
        return self._last_sequence.get(player_id, 0)


@dataclass(frozen=True)
class WorldSnapshot:
    """A versioned read-only view distributed by the authoritative host."""

    revision: int
    world: Dict[str, Any]
    schema_version: int = SNAPSHOT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_int(self.revision, "revision")
        if self.schema_version != SNAPSHOT_SCHEMA_VERSION:
            raise ProtocolError("unsupported snapshot schema")
        if not isinstance(self.world, dict):
            raise ProtocolError("world must be an object")
        # Validate JSON compatibility and prevent NaN/Infinity on the wire.
        try:
            encoded = json.dumps(
                self.world, ensure_ascii=False, sort_keys=True, allow_nan=False
            )
        except (TypeError, ValueError) as exc:
            raise ProtocolError("world snapshot must contain finite JSON data") from exc
        if len(encoded.encode("utf-8")) > 2_000_000:
            raise ProtocolError("snapshot is too large")

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema_version": self.schema_version,
                "revision": self.revision,
                "world": self.world,
            },
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        )

    @classmethod
    def from_json(cls, value: str) -> "WorldSnapshot":
        if not isinstance(value, str) or len(value.encode("utf-8")) > 2_000_000:
            raise ProtocolError("invalid snapshot payload size")
        try:
            raw = json.loads(value)
        except (TypeError, ValueError) as exc:
            raise ProtocolError("snapshot is not valid JSON") from exc
        if not isinstance(raw, dict) or set(raw) != {
            "schema_version", "revision", "world"
        }:
            raise ProtocolError("snapshot fields do not match schema")
        return cls(
            revision=raw["revision"],
            world=raw["world"],
            schema_version=raw["schema_version"],
        )
