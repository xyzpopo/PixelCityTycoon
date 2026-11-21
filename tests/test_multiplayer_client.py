"""Tests for desktop and browser WebSocket lobby transports."""
import json
import sys
import types
import unittest
from unittest.mock import patch

from multiplayer_client import MultiplayerClient


class FakeBrowserSocket:
    CONNECTING = 0
    OPEN = 1
    CLOSING = 2
    CLOSED = 3

    def __init__(self, url):
        self.url = url
        self.readyState = self.CONNECTING
        self.sent = []
        self.onopen = None
        self.onmessage = None
        self.onerror = None
        self.onclose = None

    def send(self, data):
        if self.readyState != self.OPEN:
            raise RuntimeError("socket is not open")
        self.sent.append(data)

    def open(self):
        self.readyState = self.OPEN
        if self.onopen is not None:
            self.onopen(types.SimpleNamespace())

    def receive(self, payload):
        if self.onmessage is not None:
            self.onmessage(types.SimpleNamespace(data=json.dumps(payload)))

    def receive_raw(self, raw):
        if self.onmessage is not None:
            self.onmessage(types.SimpleNamespace(data=raw))

    def close(self):
        self.readyState = self.CLOSED
        if self.onclose is not None:
            self.onclose(types.SimpleNamespace())


class FakeWebSocketConstructor:
    created = []

    @classmethod
    def new(cls, url):
        socket = FakeBrowserSocket(url)
        cls.created.append(socket)
        return socket


class BrowserMultiplayerClientTests(unittest.TestCase):
    def setUp(self):
        FakeWebSocketConstructor.created = []
        fake_platform = types.ModuleType("platform")
        fake_platform.window = types.SimpleNamespace(
            WebSocket=FakeWebSocketConstructor
        )
        self.platform_patch = patch.dict(sys.modules, {"platform": fake_platform})
        self.platform_patch.start()

    def tearDown(self):
        self.platform_patch.stop()

    def test_browser_connect_sends_first_message_and_queued_messages_in_order(self):
        client = MultiplayerClient(is_web=True)
        first_message = {"type": "create_room", "nickname": "Host"}
        client.connect("wss://example.test/ws", first_message)
        socket = FakeWebSocketConstructor.created[-1]

        self.assertTrue(client.running)
        self.assertEqual(socket.url, "wss://example.test/ws")
        client.send({"type": "ping"})
        self.assertEqual(socket.sent, [])

        socket.open()
        self.assertEqual(
            [json.loads(item) for item in socket.sent],
            [first_message, {"type": "ping"}],
        )
        self.assertEqual(
            client.poll(),
            [{"type": "transport_connected"}],
        )

    def test_browser_messages_are_decoded_and_bad_json_is_reported(self):
        client = MultiplayerClient(is_web=True)
        client.connect("wss://example.test/ws", {"type": "list_rooms"})
        socket = FakeWebSocketConstructor.created[-1]
        socket.open()
        client.poll()

        socket.receive({"type": "connected", "player_id": "abc"})
        socket.receive_raw("{invalid")
        messages = client.poll()
        self.assertEqual(messages[0], {"type": "connected", "player_id": "abc"})
        self.assertEqual(messages[1]["type"], "error")

    def test_browser_close_updates_running_state_and_emits_closed_event(self):
        client = MultiplayerClient(is_web=True)
        client.connect("wss://example.test/ws", {"type": "list_rooms"})
        socket = FakeWebSocketConstructor.created[-1]
        socket.open()
        client.poll()

        client.close()
        self.assertFalse(client.running)
        self.assertEqual(client.poll(), [{"type": "transport_closed"}])

    def test_browser_error_is_forwarded_to_game_ui(self):
        client = MultiplayerClient(is_web=True)
        client.connect("wss://example.test/ws", {"type": "list_rooms"})
        socket = FakeWebSocketConstructor.created[-1]
        socket.onerror(types.SimpleNamespace())
        messages = client.poll()
        self.assertEqual(messages[0]["type"], "error")
        self.assertIn("WebSocket", messages[0]["message"])


if __name__ == "__main__":
    unittest.main()
