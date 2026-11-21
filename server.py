"""Pixel City Tycoon WebSocket lobby server.
Run: pip install -r requirements-server.txt && uvicorn server:app --host 0.0.0.0 --port 8765
This service currently handles lobby presence and chat, not shared game simulation.
"""
from __future__ import annotations
import json
import os
import secrets
from typing import Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from multiplayer_lobby import LobbyError, LobbyManager

MAX_MESSAGE_BYTES = 16_384
MAX_CHAT_LENGTH = 240
app = FastAPI(title="Pixel City Tycoon Lobby", docs_url=None, redoc_url=None)
lobby = LobbyManager()
connections: Dict[str, WebSocket] = {}

async def send_json(socket: WebSocket, payload: dict) -> bool:
    try:
        await socket.send_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        return True
    except Exception:
        return False

async def broadcast_room(room_code: str) -> None:
    room = lobby.get_room(room_code)
    if room is None:
        return
    for player_id in list(room.players):
        socket = connections.get(player_id)
        if socket is not None:
            await send_json(socket, {"type": "lobby_updated", "room": lobby.view(room_code, player_id)})

async def broadcast_chat(room_code: str, sender_id: str, nickname: str, message: str) -> None:
    room = lobby.get_room(room_code)
    if room is None:
        return
    payload = {"type": "chat_message", "room_code": room_code,
               "player_id": sender_id, "nickname": nickname, "message": message}
    for player_id in list(room.players):
        socket = connections.get(player_id)
        if socket is not None:
            await send_json(socket, payload)

@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"ok": True, "service": "pixel-city-tycoon-lobby",
                         "rooms": len(lobby.rooms), "players": len(connections)})

@app.websocket("/ws")
async def websocket_lobby(socket: WebSocket) -> None:
    await socket.accept()
    player_id = secrets.token_urlsafe(15)
    connections[player_id] = socket
    await send_json(socket, {"type": "connected", "player_id": player_id, "protocol": 1})
    try:
        while True:
            raw = await socket.receive_text()
            if len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
                await send_json(socket, {"type": "error", "message": "메시지가 너무 커요."})
                await socket.close(code=1009)
                break
            try:
                message = json.loads(raw)
            except (TypeError, ValueError):
                await send_json(socket, {"type": "error", "message": "JSON 형식이 올바르지 않아요."})
                continue
            if not isinstance(message, dict) or not isinstance(message.get("type"), str):
                await send_json(socket, {"type": "error", "message": "메시지 형식이 올바르지 않아요."})
                continue
            kind = message["type"]
            try:
                if kind == "create_room":
                    code = lobby.create(player_id, message.get("nickname"))
                    await send_json(socket, {"type": "room_created", "room_code": code})
                    await broadcast_room(code)
                elif kind == "join_room":
                    code = lobby.join(player_id, message.get("nickname"), message.get("room_code"))
                    await send_json(socket, {"type": "room_joined", "room_code": code})
                    await broadcast_room(code)
                elif kind == "leave_room":
                    old_code = lobby.leave(player_id)
                    if old_code:
                        await send_json(socket, {"type": "room_left", "room_code": old_code})
                        await broadcast_room(old_code)
                elif kind == "set_ready":
                    code = lobby.set_ready(player_id, message.get("ready"))
                    await broadcast_room(code)
                elif kind == "list_rooms":
                    await send_json(socket, {"type": "room_list", "rooms": lobby.public_rooms()})
                elif kind == "chat":
                    room = lobby.room_for_player(player_id)
                    text = message.get("message")
                    if room is None:
                        raise LobbyError("먼저 방에 참가해 주세요.")
                    if not isinstance(text, str) or not text.strip() or len(text) > MAX_CHAT_LENGTH:
                        raise LobbyError(f"채팅은 1~{MAX_CHAT_LENGTH}자로 입력해 주세요.")
                    await broadcast_chat(room.room_code, player_id,
                                         room.players[player_id].nickname, text.strip())
                elif kind == "ping":
                    await send_json(socket, {"type": "pong"})
                else:
                    raise LobbyError("지원하지 않는 요청이에요.")
            except LobbyError as exc:
                await send_json(socket, {"type": "error", "message": str(exc)})
    except WebSocketDisconnect:
        pass
    finally:
        old_code = lobby.leave(player_id)
        connections.pop(player_id, None)
        if old_code:
            await broadcast_room(old_code)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0",
                port=int(os.environ.get("PORT", "8765")),
                ws_max_size=MAX_MESSAGE_BYTES, reload=False)
