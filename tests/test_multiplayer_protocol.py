import unittest

from multiplayer_protocol import (
    CommandGate,
    GameCommand,
    ProtocolError,
    WorldSnapshot,
)


class GameCommandTests(unittest.TestCase):
    def test_command_round_trip(self):
        command = GameCommand.create(
            "player-a", 1, 0, "queue_work",
            {"tool": "road", "x": 12, "y": 9},
        )
        restored = GameCommand.from_dict(command.to_dict())
        from_json = GameCommand.from_json(command.to_json())
        self.assertEqual(restored, command)
        self.assertEqual(from_json, command)

    def test_rejects_out_of_map_coordinates(self):
        with self.assertRaises(ProtocolError):
            GameCommand.create(
                "player-a", 1, 0, "move_worker", {"x": 44, "y": 0}
            )

    def test_rejects_unknown_action_and_extra_payload(self):
        with self.assertRaises(ProtocolError):
            GameCommand.create("player-a", 1, 0, "run_python", {})
        with self.assertRaises(ProtocolError):
            GameCommand.create(
                "player-a", 1, 0, "expand_land", {"money": 0}
            )

    def test_gate_rejects_duplicate_and_stale_commands(self):
        gate = CommandGate()
        first = GameCommand.create(
            "player-a", 1, 0, "expand_land", {}
        )
        accepted = gate.accept(first)
        self.assertTrue(accepted.accepted)
        self.assertEqual(accepted.revision, 1)

        duplicate = gate.accept(first)
        self.assertFalse(duplicate.accepted)
        self.assertEqual(duplicate.reason, "duplicate_command")

        stale = GameCommand.create(
            "player-b", 1, 0, "expand_land", {}
        )
        rejected = gate.accept(stale)
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.reason, "stale_world_revision")

        fresh = GameCommand.create(
            "player-b", 2, 1, "expand_land", {}
        )
        self.assertTrue(gate.accept(fresh).accepted)

    def test_player_sequences_are_independent(self):
        gate = CommandGate()
        first = GameCommand.create("player-a", 1, 0, "expand_land", {})
        self.assertTrue(gate.accept(first).accepted)

        second = GameCommand.create("player-b", 1, 1, "expand_land", {})
        self.assertTrue(gate.accept(second).accepted)
        self.assertEqual(gate.last_sequence("player-a"), 1)
        self.assertEqual(gate.last_sequence("player-b"), 1)

    def test_snapshot_round_trip(self):
        snapshot = WorldSnapshot(
            revision=8,
            world={"money": 1200, "roads": [[2, 3]], "day": 4},
        )
        restored = WorldSnapshot.from_json(snapshot.to_json())
        self.assertEqual(restored, snapshot)

    def test_snapshot_rejects_non_json_values(self):
        with self.assertRaises((ProtocolError, ValueError, TypeError)):
            WorldSnapshot(revision=0, world={"money": float("nan")})


if __name__ == "__main__":
    unittest.main()
