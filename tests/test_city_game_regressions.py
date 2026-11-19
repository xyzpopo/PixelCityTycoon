"""Regression tests for world generation, building elevations and save slots."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import main


class CityGameRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = main.CityGame()

    @classmethod
    def tearDownClass(cls):
        main.pygame.quit()

    def setUp(self):
        self.game.generate_world(12345)

    def test_two_starter_rocks_are_guaranteed_and_reachable(self):
        sx, sy = main.MAP_W // 2, main.MAP_H // 2
        for seed in range(40):
            self.game.generate_world(seed)
            expected = ((sx, sy + 5), (sx, sy - 5))
            for rock in expected:
                with self.subTest(seed=seed, rock=rock):
                    self.assertIn(rock, self.game.rocks)
                    self.assertIsNotNone(
                        self.game.find_worker_path_to_work_target(rock),
                        "starter stone must be reachable from the worker",
                    )

    def test_roads_and_buildings_can_use_raised_uneven_land(self):
        sx, sy = main.MAP_W // 2, main.MAP_H // 2
        road_pos = (sx + 1, sy)
        self.game.terrain[road_pos[0]][road_pos[1]].terrain = "mountain"
        self.game.terrain[road_pos[0]][road_pos[1]].height = 2
        self.assertTrue(self.game.can_build_on(*road_pos))
        self.assertTrue(self.game.can_build_road_on(*road_pos))

        anchor = (sx + 2, sy + 2)
        footprint = self.game.footprint_for("park", *anchor)
        for index, (x, y) in enumerate(sorted(footprint)):
            self.game.terrain[x][y].height = index
            self.game.terrain[x][y].terrain = "mountain" if index else "grass"
            self.game.trees.discard((x, y))
            self.game.rocks.discard((x, y))
        self.assertTrue(
            self.game.can_build_city_object(
                "park", *anchor, allow_worker=True, require_road=False
            )
        )

    def test_restore_mode_can_reserve_tree_and_rock(self):
        sx, sy = main.MAP_W // 2, main.MAP_H // 2
        tree_pos = (sx + 1, sy + 1)
        rock_pos = (sx - 1, sy - 1)
        self.game.money = 100_000
        self.assertTrue(self.game.can_reserve_work_order("restore_tree", *tree_pos)[0])
        self.assertTrue(self.game.can_reserve_work_order("restore_rock", *rock_pos)[0])
        self.assertEqual(
            self.game.order_costs("restore_tree", *tree_pos)[0],
            main.RESTORE_TREE_MONEY_COST,
        )
        self.assertEqual(
            self.game.order_costs("restore_rock", *rock_pos)[0],
            main.RESTORE_ROCK_MONEY_COST,
        )

    def test_three_save_slots_and_autosave_round_trip(self):
        with tempfile.TemporaryDirectory() as temporary:
            save_dir = Path(temporary)
            legacy_file = save_dir / "city_save.json"
            with patch.object(main, "IS_WEB", False), \
                 patch.object(main, "SAVE_DIR", save_dir), \
                 patch.object(main, "SAVE_FILE", legacy_file):
                self.game.money = 54321
                self.game.save_game(2)
                self.assertTrue((save_dir / "city_slot_2.json").is_file())
                exists, details = self.game.save_slot_info(2)
                self.assertTrue(exists)
                self.assertIn("DAY", details)

                self.game.money = 1
                self.game.load_game(2)
                self.assertEqual(self.game.money, 54321)

                self.game.save_game(autosave=True)
                self.assertTrue((save_dir / "city_autosave.json").is_file())
                self.game.money = 2
                self.game.load_game(autosave=True)
                self.assertEqual(self.game.money, 54321)


    def test_settings_round_trip_and_sandbox_restoration(self):
        with tempfile.TemporaryDirectory() as temporary:
            save_dir = Path(temporary)
            legacy_file = save_dir / "city_save.json"
            with patch.object(main, "IS_WEB", False), \
                 patch.object(main, "SAVE_DIR", save_dir), \
                 patch.object(main, "SAVE_FILE", legacy_file):
                self.game.sandbox_mode = True
                self.game.sound_enabled = False
                self.game.window_scale = 3
                self.game.save_game(3)
                self.game.sandbox_mode = False
                self.game.sound_enabled = True
                self.game.window_scale = 1
                self.game.load_game(3)
                self.assertTrue(self.game.sandbox_mode)
                self.assertFalse(self.game.sound_enabled)
                self.assertEqual(self.game.window_scale, 3)
                self.assertEqual(self.game.window.get_size(), (main.LOGICAL_W * 3, main.LOGICAL_H * 3))

        self.game.sandbox_mode = True
        self.game.money = 0
        sx, sy = main.MAP_W // 2, main.MAP_H // 2
        tree_pos = (sx + 1, sy + 1)
        rock_pos = (sx - 1, sy - 1)
        self.assertTrue(self.game.can_reserve_work_order("restore_tree", *tree_pos)[0])
        self.assertTrue(self.game.can_reserve_work_order("restore_rock", *rock_pos)[0])

if __name__ == "__main__":
    unittest.main()
