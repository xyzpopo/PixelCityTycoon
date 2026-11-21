"""Threaded WebSocket client for the Pygame desktop build."""
from __future__ import annotations
import json
import queue
import threading
from typing import List, Optional
import websocket

class MultiplayerClient:
    """Keep all socket work off the Pygame/UI thread."""
    def __init__(self) -> None:
        self.incoming: "queue.Queue[dict]" = queue.Queue()
        self.outgoing: "queue.Queue[dict]" = queue.Queue()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._socket = None
        self._url = ""

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def connect(self, url: str, first_message: dict) -> None:
        if self.running:
            raise RuntimeError("이미 서버에 연결 중이에요.")
        self._stop.clear()
        self._url = url
        self._thread = threading.Thread(target=self._run, args=(dict(first_message),),
                                        name="PixelCityTycoonNetwork", daemon=True)
        self._thread.start()

    def send(self, payload: dict) -> None:
        if not isinstance(payload, dict):
            raise TypeError("네트워크 메시지는 dict여야 해요.")
        self.outgoing.put(dict(payload))

    def poll(self, limit: int = 100) -> List[dict]:
        messages: List[dict] = []
        for _ in range(max(1, min(limit, 500))):
            try:
                messages.append(self.incoming.get_nowait())
            except queue.Empty:
                break
        return messages

    def _run(self, first_message: dict) -> None:
        sock = None
        try:
            sock = websocket.create_connection(self._url, timeout=12,
                                               enable_multithread=True, suppress_origin=True)
            self._socket = sock
            sock.settimeout(0.15)
            self.incoming.put({"type": "transport_connected"})
            sock.send(json.dumps(first_message, ensure_ascii=False))
            while not self._stop.is_set():
                while True:
                    try:
                        payload = self.outgoing.get_nowait()
                    except queue.Empty:
                        break
                    sock.send(json.dumps(payload, ensure_ascii=False))
                try:
                    raw = sock.recv()
                    if raw:
                        try:
                            decoded = json.loads(raw)
                        except (TypeError, ValueError):
                            self.incoming.put({"type": "error",
                                               "message": "서버에서 읽을 수 없는 메시지를 받았어요."})
                            continue
                        if isinstance(decoded, dict):
                            self.incoming.put(decoded)
                except websocket.WebSocketTimeoutException:
                    continue
                except websocket.WebSocketConnectionClosedException:
                    break
        except Exception as exc:
            self.incoming.put({"type": "error", "message": f"서버 연결 실패: {exc}"})
        finally:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass
            self._socket = None
            self.incoming.put({"type": "transport_closed"})

    def close(self) -> None:
        self._stop.set()
        sock = self._socket
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass
