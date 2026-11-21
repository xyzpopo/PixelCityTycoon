"""Tests for desktop and Pygbag browser WebSocket lobby transports."""
import json
import sys
import types
import unittest
from unittest.mock import patch

from multiplayer_client import MultiplayerClient


class FakeBrowserBridge:
    def __init__(self):
        self.url = ""
        self.first_message = None
        self.ready_state = 3
        self.sent = []
        self.events = []

    def connect(self, url, first_message):
        self.url = url
        self.first_message = first_message
        self.ready_state = 0
        return True

    def state(self):
        return self.ready_state

    def open(self):
        self.ready_state = 1
        self.events.append({"type": "transport_connected"})
        if self.first_message is not None:
            self.sent.append(self.first_message)
            self.first_message = None

    def send(self, raw):
        if self.ready_state != 1:
            return False
        self.sent.append(raw)
        return True

    def receive(self, payload):
        self.events.append({"type": "raw", "data": json.dumps(payload)})

    def receive_raw(self, raw):
        self.events.append({"type": "raw", "data": raw})

    def fail(self):
        self.events.append({"type": "error", "message": "browser socket error"})

    def poll(self):
        result = json.dumps(self.events)
        self.events.clear()
        return result

    def close(self):
        self.ready_state = 3
        self.events.append({"type": "transport_closed", "code": 1000, "reason": ""})


class FakeWindow:
    def __init__(self):
        self.PCTLobbyBridge = FakeBrowserBridge()

    def eval(self, _source):
        # The real browser evaluates the bridge source; tests provide its equivalent.
        return None


class BrowserMultiplayerClientTests(unittest.TestCase):
    def setUp(self):
        self.window = FakeWindow()
        fake_platform = types.ModuleType("platform")
        fake_platform.window = self.window
        self.platform_patch = patch.dict(sys.modules, {"platform": fake_platform})
        self.platform_patch.start()

    def tearDown(self):
        self.platform_patch.stop()

    def test_browser_connect_sends_first_message_and_queued_messages_in_order(self):
        client = MultiplayerClient(is_web=True)
        first_message = {"type": "create_room", "nickname": "Host"}
        client.connect("wss://example.test/ws", first_message)
        bridge = self.window.PCTLobbyBridge

        self.assertTrue(client.running)
        self.assertEqual(bridge.url, "wss://example.test/ws")
        client.send({"type": "ping"})
        self.assertEqual(bridge.sent, [])

        bridge.open()
        messages = client.poll()
        self.assertEqual(messages, [{"type": "transport_connected"}])
        self.assertEqual(
            [json.loads(item) for item in bridge.sent],
            [first_message, {"type": "ping"}],
        )

    def test_browser_messages_are_decoded_and_bad_json_is_reported(self):
        client = MultiplayerClient(is_web=True)
        client.connect("wss://example.test/ws", {"type": "list_rooms"})
        bridge = self.window.PCTLobbyBridge
        bridge.open()
        client.poll()

        bridge.receive({"type": "connected", "player_id": "abc"})
        bridge.receive_raw("{invalid")
        messages = client.poll()
        self.assertEqual(messages[0], {"type": "connected", "player_id": "abc"})
        self.assertEqual(messages[1]["type"], "error")

    def test_browser_close_updates_running_state_and_emits_closed_event(self):
        client = MultiplayerClient(is_web=True)
        client.connect("wss://example.test/ws", {"type": "list_rooms"})
        bridge = self.window.PCTLobbyBridge
        bridge.open()
        client.poll()

        client.close()
        self.assertFalse(client.running)
        self.assertEqual(client.poll()[0]["type"], "transport_closed")

    def test_browser_error_is_forwarded_to_game_ui(self):
        client = MultiplayerClient(is_web=True)
        client.connect("wss://example.test/ws", {"type": "list_rooms"})
        bridge = self.window.PCTLobbyBridge
        bridge.fail()
        messages = client.poll()
        self.assertEqual(messages[0]["type"], "error")
        self.assertIn("browser socket error", messages[0]["message"])


if __name__ == "__main__":
    unittest.main()
