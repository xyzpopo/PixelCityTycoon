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
                self.game.sound_volume = 0.25
                self.game.window_scale = 3
                self.game.key_bindings["move"] = main.pygame.K_m
                self.game.save_game(3)
                self.game.sandbox_mode = False
                self.game.sound_enabled = True
                self.game.sound_volume = 1.0
                self.game.window_scale = 1
                self.game.key_bindings = main.DEFAULT_KEY_BINDINGS.copy()
                self.game.load_game(3)
                self.assertTrue(self.game.sandbox_mode)
                self.assertFalse(self.game.sound_enabled)
                self.assertEqual(self.game.sound_volume, 0.25)
                self.assertEqual(self.game.window_scale, 3)
                self.assertEqual(self.game.key_bindings["move"], main.pygame.K_m)
                self.assertEqual(self.game.window.get_size(), (main.LOGICAL_W * 3, main.LOGICAL_H * 3))

        self.game.sandbox_mode = True
        self.game.money = 0
        sx, sy = main.MAP_W // 2, main.MAP_H // 2
        tree_pos = (sx + 1, sy + 1)
        rock_pos = (sx - 1, sy - 1)
        self.assertTrue(self.game.can_reserve_work_order("restore_tree", *tree_pos)[0])
        self.assertTrue(self.game.can_reserve_work_order("restore_rock", *rock_pos)[0])

    def test_city_utility_coverage_and_population_growth(self):
        sx, sy = main.MAP_W // 2, main.MAP_H // 2
        house = (sx, sy)
        self.game.houses = {house}
        self.game.house_levels = {house: 2}
        self.game.population = 4
        self.game.city_objects = {
            (sx + 1, sy): {"type": "power", "level": 1},
            (sx, sy + 1): {"type": "water", "level": 1},
            (sx + 2, sy): {"type": "commercial", "level": 1},
        }
        status = self.game.calculate_city_service_status()
        self.assertEqual(status["power_coverage"], 1.0)
        self.assertEqual(status["water_coverage"], 1.0)
        self.assertGreaterEqual(status["power_output"], status["power_demand"])
        self.assertGreaterEqual(status["water_output"], status["water_demand"])
        self.assertEqual(self.game.update_city_population(), 2)
        self.assertEqual(self.game.population, 6)

    def test_unserved_city_does_not_grow(self):
        sx, sy = main.MAP_W // 2, main.MAP_H // 2
        house = (sx, sy)
        self.game.houses = {house}
        self.game.house_levels = {house: 2}
        self.game.population = 4
        self.game.city_objects = {(sx + 2, sy): {"type": "commercial", "level": 1}}
        self.assertEqual(self.game.update_city_population(), 0)
        self.assertEqual(self.game.population, 4)

    def test_mouse_coordinates_follow_display_scale(self):
        original_size = self.game.window.get_size()
        try:
            self.game.window = main.pygame.display.set_mode((main.LOGICAL_W * 3, main.LOGICAL_H * 3))
            self.assertEqual(self.game.logical_mouse((300, 150)), (100, 50))
        finally:
            self.game.window = main.pygame.display.set_mode(original_size)

    def test_night_lighting_renders_with_street_lamps(self):
        self.game.canvas.fill((200, 200, 200))
        self.game.game_minutes = 22 * 60
        sx, sy = main.MAP_W // 2, main.MAP_H // 2
        self.game.city_objects = {(sx, sy): {"type": "lamp", "level": 1}}
        before = self.game.canvas.get_at((320, 180))
        self.game.draw_time_of_day()
        after = self.game.canvas.get_at((320, 180))
        self.assertNotEqual(before, after)

    def test_resident_walkers_render_on_roads(self):
        sx, sy = main.MAP_W // 2, main.MAP_H // 2
        self.game.population = 12
        self.game.roads = {(sx, sy), (sx + 1, sy), (sx + 2, sy)}
        self.game.road_directions = {(sx, sy): "x", (sx + 1, sy): "x", (sx + 2, sy): "x"}
        self.game.draw_resident_walkers()

    def test_json_save_text_import_is_transactional(self):
        with tempfile.TemporaryDirectory() as temporary:
            save_dir = Path(temporary)
            legacy_file = save_dir / "city_save.json"
            with patch.object(main, "IS_WEB", False), patch.object(main, "SAVE_DIR", save_dir), patch.object(main, "SAVE_FILE", legacy_file):
                self.game.money = 87654
                self.game.save_game(1)
                serialized = (save_dir / "city_slot_1.json").read_text(encoding="utf-8")
                self.game.money = 12
                self.game.load_game(save_text_override=serialized)
                self.assertTrue(self.game.last_load_success)
                self.assertEqual(self.game.money, 87654)
                self.game.money = 321
                self.game.load_game(save_text_override="{broken json")
                self.assertFalse(self.game.last_load_success)
                self.assertEqual(self.game.money, 321)

    def test_two_finger_gesture_pans_and_pinch_zooms(self):
        self.game.touch_fingers = {1: (100, 100), 2: (200, 100)}
        self.game.touch_gesture_mode = None
        original_zoom = self.game.zoom_index
        original_camera = (self.game.camera_x, self.game.camera_y)
        self.game.update_multi_touch_gesture()
        self.game.touch_fingers[2] = (260, 120)
        self.game.update_multi_touch_gesture()
        self.assertEqual(self.game.zoom_index, min(original_zoom + 1, len(main.ZOOM_LEVELS) - 1))
        self.assertNotEqual((self.game.camera_x, self.game.camera_y), original_camera)


    def test_generated_maps_remain_in_bounds_across_many_seeds(self):
        sx, sy = main.MAP_W // 2, main.MAP_H // 2
        for seed in range(100):
            self.game.generate_world(seed * 7919)
            self.assertEqual(len(self.game.terrain), main.MAP_W)
            self.assertTrue(all(len(column) == main.MAP_H for column in self.game.terrain))
            for column in self.game.terrain:
                for tile in column:
                    self.assertIn(tile.terrain, ("grass", "mountain", "water"))
                    self.assertGreaterEqual(tile.height, 0)
                    self.assertLessEqual(tile.height, 4)
            for pos in self.game.trees | self.game.rocks:
                self.assertNotEqual(self.game.terrain[pos[0]][pos[1]].terrain, "water")
            self.assertIn((sx, sy + 5), self.game.rocks)
            self.assertIn((sx, sy - 5), self.game.rocks)

    def test_legacy_save_versions_load_with_safe_defaults(self):
        for version in (1, 5, 12, 13):
            with self.subTest(version=version):
                payload = {"version": version, "seed": 24680, "money": 1234}
                self.game.sandbox_mode = True
                self.game.sound_enabled = False
                self.game.load_game(save_text_override=__import__("json").dumps(payload))
                self.assertTrue(self.game.last_load_success)
                self.assertEqual(self.game.money, 1234)
                self.assertFalse(self.game.sandbox_mode)
                self.assertTrue(self.game.sound_enabled)
                self.assertEqual(self.game.window_scale, 2)

    def test_newer_save_version_is_rejected_without_losing_city(self):
        self.game.money = 76543
        self.game.load_game(save_text_override='{"version": 999, "seed": 1}')
        self.assertFalse(self.game.last_load_success)
        self.assertEqual(self.game.money, 76543)

    def test_long_simulation_and_full_frame_render_smoke(self):
        self.game.population = 4
        self.game.houses = {(main.MAP_W // 2, main.MAP_H // 2)}
        for _ in range(600):
            self.game.update(0.25)
        self.assertGreaterEqual(self.game.day, 1)
        self.assertTrue(all(map(lambda value: isinstance(value, (int, float)),
                                (self.game.money, self.game.game_minutes, self.game.population))))
        self.game.draw()

    def test_key_rebinding_swaps_conflicting_keys(self):
        self.game.key_bindings = main.DEFAULT_KEY_BINDINGS.copy()
        self.game.rebind_action = "move"
        self.assertTrue(self.game.assign_rebound_key(main.pygame.K_F2))
        self.assertEqual(self.game.key_bindings["move"], main.pygame.K_F2)
        self.assertEqual(self.game.key_bindings["remove"], main.pygame.K_F1)
        self.assertIsNone(self.game.rebind_action)
        self.game.rebind_action = "road"
        self.assertFalse(self.game.assign_rebound_key(main.pygame.K_ESCAPE))
        self.assertEqual(self.game.rebind_action, "road")
if __name__ == "__main__":
    unittest.main()
