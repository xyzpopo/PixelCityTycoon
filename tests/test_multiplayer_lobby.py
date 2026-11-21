import unittest

from multiplayer_lobby import LobbyError, LobbyManager, MAX_PLAYERS_PER_ROOM


class LobbyManagerTests(unittest.TestCase):
    def setUp(self):
        self.lobby = LobbyManager()

    def test_create_room_and_join_updates_presence(self):
        code = self.lobby.create("p1", "Host")
        self.assertEqual(len(code), 6)
        self.lobby.join("p2", "Guest", code.lower())
        host_view = self.lobby.view(code, "p1")
        guest_view = self.lobby.view(code, "p2")
        self.assertEqual(len(host_view["players"]), 2)
        self.assertTrue(host_view["is_host"])
        self.assertFalse(guest_view["is_host"])
        self.assertEqual(host_view["players"][1]["nickname"], "Guest")

    def test_ready_state_is_per_player(self):
        code = self.lobby.create("p1", "Host")
        self.lobby.join("p2", "Guest", code)
        self.lobby.set_ready("p2", True)
        view = self.lobby.view(code, "p1")
        self.assertFalse(view["players"][0]["ready"])
        self.assertTrue(view["players"][1]["ready"])

    def test_room_capacity_is_limited_to_four(self):
        code = self.lobby.create("p1", "Host")
        for player in range(2, MAX_PLAYERS_PER_ROOM + 1):
            self.lobby.join(f"p{player}", f"Player {player}", code)
        with self.assertRaises(LobbyError):
            self.lobby.join("p5", "Fifth", code)

    def test_host_leaving_transfers_host_and_empty_room_is_deleted(self):
        code = self.lobby.create("p1", "Host")
        self.lobby.join("p2", "Guest", code)
        self.lobby.leave("p1")
        view = self.lobby.view(code, "p2")
        self.assertTrue(view["is_host"])
        self.lobby.leave("p2")
        self.assertIsNone(self.lobby.get_room(code))

    def test_joining_the_same_room_does_not_orphan_it(self):
        code = self.lobby.create("p1", "Host")
        self.assertEqual(self.lobby.join("p1", "Host", code), code)
        self.assertEqual(len(self.lobby.public_rooms()), 1)
        self.assertEqual(len(self.lobby.view(code, "p1")["players"]), 1)

    def test_invalid_nickname_and_room_code_are_rejected(self):
        with self.assertRaises(LobbyError):
            self.lobby.create("p1", " ")
        code = self.lobby.create("p1", "Host")
        with self.assertRaises(LobbyError):
            self.lobby.join("p2", "Guest", "bad")
        with self.assertRaises(LobbyError):
            self.lobby.join("p2", "x" * 17, code)

    def test_public_room_list_contains_only_waiting_rooms(self):
        code = self.lobby.create("p1", "Host")
        rooms = self.lobby.public_rooms()
        self.assertEqual(rooms[0]["room_code"], code)
        self.assertEqual(rooms[0]["player_count"], 1)


if __name__ == "__main__":
    unittest.main()
