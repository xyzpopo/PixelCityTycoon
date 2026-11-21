"""Desktop-threaded and browser-native WebSocket lobby client."""
from __future__ import annotations

import json
import queue
import sys
import threading
from typing import List, Optional


class MultiplayerClient:
    """Use a worker thread on desktop and the browser WebSocket API on web."""

    def __init__(self, is_web: Optional[bool] = None) -> None:
        self.incoming: "queue.Queue[dict]" = queue.Queue()
        self.outgoing: "queue.Queue[dict]" = queue.Queue()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._socket = None
        self._url = ""
        self._is_web = sys.platform == "emscripten" if is_web is None else bool(is_web)
        self._browser_socket = None
        self._browser_callbacks = []
        self._browser_first_message: Optional[dict] = None

    @property
    def running(self) -> bool:
        if self._is_web:
            socket = self._browser_socket
            if socket is None:
                return False
            try:
                # CONNECTING and OPEN both count as an active connection.
                return int(socket.readyState) in (0, 1)
            except Exception:
                return False
        return self._thread is not None and self._thread.is_alive()

    def connect(self, url: str, first_message: dict) -> None:
        if self.running:
            raise RuntimeError("이미 서버에 연결 중이에요.")
        self._stop.clear()
        self._url = url
        if self._is_web:
            self._connect_browser(dict(first_message))
            return
        self._thread = threading.Thread(
            target=self._run,
            args=(dict(first_message),),
            name="PixelCityTycoonNetwork",
            daemon=True,
        )
        self._thread.start()

    def _connect_browser(self, first_message: dict) -> None:
        """Open a native browser WebSocket; browsers cannot use desktop TCP sockets."""
        try:
            from platform import window

            # Pygbag exposes the browser window and a small pyodide.ffi-compatible
            # bridge. Keep callback references alive for the lifetime of the socket.
            try:
                from pyodide.ffi import create_proxy
            except (ImportError, AttributeError):
                create_proxy = lambda callback: callback

            socket = window.WebSocket.new(self._url)
            self._browser_socket = socket
            self._browser_first_message = first_message
            self._browser_callbacks = [
                create_proxy(self._on_browser_open),
                create_proxy(self._on_browser_message),
                create_proxy(self._on_browser_error),
                create_proxy(self._on_browser_close),
            ]
            socket.onopen = self._browser_callbacks[0]
            socket.onmessage = self._browser_callbacks[1]
            socket.onerror = self._browser_callbacks[2]
            socket.onclose = self._browser_callbacks[3]
        except Exception as exc:
            self._browser_socket = None
            self._browser_callbacks = []
            self.incoming.put({
                "type": "error",
                "message": f"브라우저 서버 연결을 시작하지 못했어요: {exc}",
            })
            self.incoming.put({"type": "transport_closed"})

    def _browser_send_now(self, payload: dict) -> bool:
        socket = self._browser_socket
        if socket is None:
            return False
        try:
            if int(socket.readyState) != 1:  # WebSocket.OPEN
                return False
            socket.send(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
            return True
        except Exception as exc:
            self.incoming.put({
                "type": "error",
                "message": f"메시지를 보내지 못했어요: {exc}",
            })
            return True

    def _flush_browser_outgoing(self) -> None:
        while True:
            try:
                payload = self.outgoing.get_nowait()
            except queue.Empty:
                return
            if not self._browser_send_now(payload):
                # The socket may still be CONNECTING. Preserve order until open.
                self.outgoing.put(payload)
                return

    def _on_browser_open(self, _event=None) -> None:
        self.incoming.put({"type": "transport_connected"})
        first_message = self._browser_first_message
        self._browser_first_message = None
        if first_message is not None and not self._browser_send_now(first_message):
            self.outgoing.put(first_message)
        self._flush_browser_outgoing()

    def _on_browser_message(self, event=None) -> None:
        try:
            raw = getattr(event, "data", "")
            decoded = json.loads(str(raw))
        except (TypeError, ValueError):
            self.incoming.put({
                "type": "error",
                "message": "서버에서 읽을 수 없는 메시지를 받았어요.",
            })
            return
        if isinstance(decoded, dict):
            self.incoming.put(decoded)

    def _on_browser_error(self, _event=None) -> None:
        self.incoming.put({
            "type": "error",
            "message": "브라우저 WebSocket 연결에 문제가 생겼어요. 다시 시도해 주세요.",
        })

    def _on_browser_close(self, _event=None) -> None:
        self._browser_socket = None
        self._browser_first_message = None
        self._browser_callbacks = []
        self.incoming.put({"type": "transport_closed"})

    def send(self, payload: dict) -> None:
        if not isinstance(payload, dict):
            raise TypeError("네트워크 메시지는 dict여야 해요.")
        message = dict(payload)
        if self._is_web and self._browser_send_now(message):
            return
        self.outgoing.put(message)

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
            # Delayed import keeps the browser build free from desktop socket APIs.
            websocket = __import__("websocket")
            sock = websocket.create_connection(
                self._url,
                timeout=12,
                enable_multithread=True,
                suppress_origin=True,
            )
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
                            self.incoming.put({
                                "type": "error",
                                "message": "서버에서 읽을 수 없는 메시지를 받았어요.",
                            })
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
        if self._is_web:
            socket = self._browser_socket
            if socket is not None:
                try:
                    socket.close()
                except Exception:
                    self._on_browser_close()
            return
        sock = self._socket
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass
