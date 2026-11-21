"""Small in-memory lobby manager for Pixel City Tycoon multiplayer."""
from __future__ import annotations
import secrets
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

ROOM_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
MAX_PLAYERS_PER_ROOM = 4
MAX_ROOMS = 200

class LobbyError(ValueError):
    """Raised when a room/lobby operation is invalid."""

@dataclass
class LobbyPlayer:
    player_id: str
    nickname: str
    joined_at: float = field(default_factory=time.time)
    ready: bool = False

@dataclass
class LobbyRoom:
    room_code: str
    host_id: str
    players: Dict[str, LobbyPlayer] = field(default_factory=dict)
    status: str = "waiting"
    created_at: float = field(default_factory=time.time)

class LobbyManager:
    """Event-loop-owned ephemeral room registry."""
    def __init__(self) -> None:
        self.rooms: Dict[str, LobbyRoom] = {}
        self.player_rooms: Dict[str, str] = {}

    @staticmethod
    def clean_nickname(value: object) -> str:
        if not isinstance(value, str):
            raise LobbyError("닉네임을 입력해 주세요.")
        name = " ".join(value.strip().split())
        if not name or len(name) > 16 or any(ord(ch) < 32 for ch in name):
            raise LobbyError("닉네임은 1~16자로 입력해 주세요.")
        return name

    @staticmethod
    def clean_room_code(value: object) -> str:
        if not isinstance(value, str):
            raise LobbyError("방 코드를 입력해 주세요.")
        code = value.strip().upper()
        if len(code) != 6 or any(ch not in ROOM_CODE_ALPHABET for ch in code):
            raise LobbyError("방 코드는 영문 대문자·숫자 6자리예요.")
        return code

    def _new_code(self) -> str:
        for _ in range(40):
            code = "".join(secrets.choice(ROOM_CODE_ALPHABET) for _ in range(6))
            if code not in self.rooms:
                return code
        raise LobbyError("방 코드를 만들지 못했어요. 다시 시도해 주세요.")

    def leave(self, player_id: str) -> Optional[str]:
        code = self.player_rooms.pop(player_id, None)
        if code is None:
            return None
        room = self.rooms.get(code)
        if room is None:
            return code
        room.players.pop(player_id, None)
        if not room.players:
            self.rooms.pop(code, None)
        else:
            if room.host_id == player_id:
                room.host_id = next(iter(room.players))
            if room.status != "waiting":
                room.status = "waiting"
            for player in room.players.values():
                player.ready = False
        return code

    def create(self, player_id: str, nickname: object) -> str:
        if player_id in self.player_rooms:
            self.leave(player_id)
        if len(self.rooms) >= MAX_ROOMS:
            raise LobbyError("현재 만들 수 있는 방이 가득 찼어요.")
        room = LobbyRoom(self._new_code(), player_id)
        room.players[player_id] = LobbyPlayer(player_id, self.clean_nickname(nickname))
        self.rooms[room.room_code] = room
        self.player_rooms[player_id] = room.room_code
        return room.room_code

    def join(self, player_id: str, nickname: object, room_code: object) -> str:
        code = self.clean_room_code(room_code)
        room = self.rooms.get(code)
        if room is None:
            raise LobbyError("해당 방을 찾을 수 없어요.")
        if room.status != "waiting":
            raise LobbyError("이미 게임이 시작된 방이에요.")
        if len(room.players) >= MAX_PLAYERS_PER_ROOM:
            raise LobbyError("방 인원이 가득 찼어요. (최대 4명)")
        name = self.clean_nickname(nickname)
        self.leave(player_id)
        room.players[player_id] = LobbyPlayer(player_id, name)
        self.player_rooms[player_id] = code
        return code

    def set_ready(self, player_id: str, ready: object) -> str:
        code = self.player_rooms.get(player_id)
        room = self.rooms.get(code or "")
        if room is None:
            raise LobbyError("먼저 방에 참가해 주세요.")
        if type(ready) is not bool:
            raise LobbyError("준비 상태 값이 올바르지 않아요.")
        room.players[player_id].ready = ready
        return code

    def get_room(self, code: str) -> Optional[LobbyRoom]:
        return self.rooms.get(code)

    def room_for_player(self, player_id: str) -> Optional[LobbyRoom]:
        return self.rooms.get(self.player_rooms.get(player_id) or "")

    def view(self, code: str, viewer_id: str) -> dict:
        room = self.rooms.get(code)
        if room is None or viewer_id not in room.players:
            raise LobbyError("방 정보를 찾을 수 없어요.")
        return {
            "room_code": room.room_code, "status": room.status,
            "host_id": room.host_id, "is_host": room.host_id == viewer_id,
            "players": [
                {"player_id": p.player_id, "nickname": p.nickname,
                 "ready": p.ready, "is_host": p.player_id == room.host_id}
                for p in room.players.values()
            ],
            "capacity": MAX_PLAYERS_PER_ROOM,
        }

    def public_rooms(self) -> List[dict]:
        return [
            {"room_code": r.room_code, "host": r.players[r.host_id].nickname,
             "player_count": len(r.players), "capacity": MAX_PLAYERS_PER_ROOM}
            for r in self.rooms.values() if r.status == "waiting"
        ]
