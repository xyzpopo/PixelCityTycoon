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
        self._browser_bridge = None

    @property
    def running(self) -> bool:
        if self._is_web:
            bridge = self._browser_bridge
            if bridge is None:
                return False
            try:
                # CONNECTING and OPEN both count as an active connection.
                return int(bridge.state()) in (0, 1)
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
        """Use a small JavaScript bridge; Pygbag is CPython-WASM, not Pyodide."""
        try:
            from platform import window

            # Browser callbacks stay entirely in JavaScript. This avoids relying on
            # Pyodide's create_proxy API, which is not part of the Pygbag runtime.
            window.eval("""
                (() => {
                    if (window.PCTLobbyBridge) return;
                    window.PCTLobbyBridge = (() => {
                        let socket = null;
                        let events = [];
                        return {
                            connect(url, firstMessage) {
                                events = [];
                                try {
                                    socket = new WebSocket(url);
                                    socket.onopen = () => {
                                        events.push({type: "transport_connected"});
                                        if (firstMessage) {
                                            try {
                                                socket.send(firstMessage);
                                            } catch (error) {
                                                events.push({type: "error", message: "첫 메시지를 보내지 못했어요: " + String(error)});
                                            }
                                        }
                                    };
                                    socket.onmessage = (event) => {
                                        events.push({type: "raw", data: String(event.data)});
                                    };
                                    socket.onerror = () => {
                                        events.push({type: "error", message: "브라우저 WebSocket 연결 오류가 발생했어요. 서버 주소나 서버 상태를 확인해 주세요."});
                                    };
                                    socket.onclose = (event) => {
                                        events.push({
                                            type: "transport_closed",
                                            code: event.code,
                                            reason: event.reason || ""
                                        });
                                    };
                                    return true;
                                } catch (error) {
                                    socket = null;
                                    events.push({type: "error", message: "WebSocket을 만들지 못했어요: " + String(error)});
                                    events.push({type: "transport_closed"});
                                    return false;
                                }
                            },
                            send(raw) {
                                if (!socket || socket.readyState !== WebSocket.OPEN) return false;
                                try {
                                    socket.send(raw);
                                    return true;
                                } catch (error) {
                                    events.push({type: "error", message: "메시지 전송 실패: " + String(error)});
                                    return false;
                                }
                            },
                            poll() {
                                return JSON.stringify(events.splice(0, events.length));
                            },
                            state() {
                                return socket ? socket.readyState : WebSocket.CLOSED;
                            },
                            close() {
                                if (socket && socket.readyState < WebSocket.CLOSING) socket.close();
                            }
                        };
                    })();
                })();
            """)
            self._browser_bridge = window.PCTLobbyBridge
            self._browser_first_message = None
            started = bool(self._browser_bridge.connect(
                self._url,
                json.dumps(first_message, ensure_ascii=False, separators=(",", ":")),
            ))
            if not started:
                self.incoming.put({
                    "type": "error",
                    "message": "브라우저가 서버 연결을 시작하지 못했어요.",
                })
        except Exception as exc:
            self._browser_bridge = None
            self.incoming.put({
                "type": "error",
                "message": f"브라우저 연결 기능을 초기화하지 못했어요: {exc}",
            })
            self.incoming.put({"type": "transport_closed"})

    def _browser_send_now(self, payload: dict) -> bool:
        bridge = self._browser_bridge
        if bridge is None:
            return False
        try:
            if int(bridge.state()) != 1:  # WebSocket.OPEN
                return False
            raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            return bool(bridge.send(raw))
        except Exception as exc:
            self.incoming.put({
                "type": "error",
                "message": f"메시지를 보내지 못했어요: {exc}",
            })
            return False

    def _flush_browser_outgoing(self) -> None:
        while True:
            try:
                payload = self.outgoing.get_nowait()
            except queue.Empty:
                return
            if not self._browser_send_now(payload):
                self.outgoing.put(payload)
                return

    def _poll_browser_events(self) -> List[dict]:
        bridge = self._browser_bridge
        if bridge is None:
            return []
        try:
            raw_events = bridge.poll()
            events = json.loads(str(raw_events))
        except Exception as exc:
            self.incoming.put({
                "type": "error",
                "message": f"브라우저 메시지를 읽지 못했어요: {exc}",
            })
            return []
        messages: List[dict] = []
        if not isinstance(events, list):
            return messages
        for event in events:
            if not isinstance(event, dict):
                continue
            if event.get("type") == "raw":
                try:
                    decoded = json.loads(event.get("data", ""))
                except (TypeError, ValueError):
                    messages.append({
                        "type": "error",
                        "message": "서버에서 읽을 수 없는 메시지를 받았어요.",
                    })
                    continue
                if isinstance(decoded, dict):
                    messages.append(decoded)
            else:
                messages.append(event)
        return messages

    def send(self, payload: dict) -> None:
        if not isinstance(payload, dict):
            raise TypeError("네트워크 메시지는 dict여야 해요.")
        message = dict(payload)
        if self._is_web:
            if self._browser_send_now(message):
                return
            bridge = self._browser_bridge
            if bridge is not None:
                try:
                    if int(bridge.state()) == 0:  # WebSocket.CONNECTING
                        self.outgoing.put(message)
                        return
                except Exception:
                    pass
                raise RuntimeError("서버 연결이 종료됐어요. 다시 연결해 주세요.")
        self.outgoing.put(message)

    def poll(self, limit: int = 100) -> List[dict]:
        if self._is_web:
            for message in self._poll_browser_events():
                self.incoming.put(message)
            if self._browser_bridge is not None:
                self._flush_browser_outgoing()
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
            bridge = self._browser_bridge
            if bridge is not None:
                try:
                    bridge.close()
                except Exception:
                    self.incoming.put({"type": "transport_closed"})
            return
        sock = self._socket
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass
