"""Regression tests for Korean composition and the lobby touch keyboard."""
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import main
from virtual_keyboard import append_hangul_jamo, backspace_hangul


class HangulCompositionTests(unittest.TestCase):
    def type_keys(self, keys):
        value = ""
        for key in keys:
            value = append_hangul_jamo(value, key)
        return value

    def test_basic_syllables_compose_to_korean_words(self):
        self.assertEqual(self.type_keys("ㅎㅏㄴㄱㅡㄹ"), "한글")
        self.assertEqual(self.type_keys("ㄱㅗㅏ"), "과")

    def test_final_consonant_moves_to_next_syllable(self):
        self.assertEqual(self.type_keys("ㅎㅏㄴㅏ"), "하나")
        self.assertEqual(self.type_keys("ㅎㅏㄱㄱㅛ"), "학교")

    def test_backspace_removes_one_composition_step(self):
        self.assertEqual(backspace_hangul("한글"), "한그")
        self.assertEqual(backspace_hangul("한그"), "한ㄱ")
        self.assertEqual(backspace_hangul("가"), "ㄱ")


class TouchKeyboardGameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = main.CityGame()

    @classmethod
    def tearDownClass(cls):
        main.pygame.quit()

    def setUp(self):
        self.game.in_game = False
        self.game.menu_screen = "multi"
        self.game.multiplayer_nickname = "Player1234"
        self.game.multiplayer_join_code = ""
        self.game.multiplayer_chat_text = ""
        self.game.menu_input_focus = None
        self.game.menu_input_replace = False
        self.game.virtual_keyboard_open = False
        self.game.virtual_keyboard_mode = "ko"
        self.game.virtual_keyboard_shift = False

    def test_browser_nickname_focus_opens_keyboard_and_composes_hangul(self):
        with patch.object(main, "IS_WEB", True):
            self.game.focus_multiplayer_input("nickname")
        self.assertTrue(self.game.virtual_keyboard_open)
        for jamo in "ㅎㅏㄴㄱㅡㄹ":
            self.game.press_virtual_keyboard_key(jamo, "jamo")
        self.assertEqual(self.game.multiplayer_nickname, "한글")

    def test_room_code_keyboard_input_is_uppercase_and_limited_to_six(self):
        with patch.object(main, "IS_WEB", True):
            self.game.focus_multiplayer_input("room_code")
        self.assertEqual(self.game.virtual_keyboard_mode, "en")
        for char in "a2b3c4d5":
            self.game.press_virtual_keyboard_key(char, "character")
        self.assertEqual(self.game.multiplayer_join_code, "A2B3C4")

    def test_backspace_removes_one_complete_hangul_character(self):
        self.game.menu_input_focus = "nickname"
        self.game.multiplayer_nickname = "한글"
        self.game.backspace_virtual_keyboard()
        self.assertEqual(self.game.multiplayer_nickname, "한")

    def test_backspace_key_uses_supported_left_arrow_label(self):
        labels = [label for _rect, label, _value, _kind, _shifted
                  in self.game.virtual_keyboard_specs()]
        self.assertIn("←", labels)
        self.assertNotIn("⌫", labels)

    def test_keyboard_done_closes_overlay_and_input_focus(self):
        with patch.object(main, "IS_WEB", True):
            self.game.focus_multiplayer_input("chat")
        self.game.press_virtual_keyboard_key("", "done")
        self.assertFalse(self.game.virtual_keyboard_open)
        self.assertIsNone(self.game.menu_input_focus)

    def test_keyboard_panel_has_touch_sized_keys_inside_screen(self):
        with patch.object(main, "IS_WEB", True):
            self.game.focus_multiplayer_input("nickname")
        specs = self.game.virtual_keyboard_specs()
        self.assertGreaterEqual(len(specs), 35)
        for rect, *_ in specs:
            self.assertGreaterEqual(rect.x, 16)
            self.assertGreaterEqual(rect.y, 180)
            self.assertLessEqual(rect.right, 624)
            self.assertLessEqual(rect.bottom, 354)
            self.assertGreaterEqual(rect.height, 24)


if __name__ == "__main__":
    unittest.main()
