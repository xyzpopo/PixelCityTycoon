"""Pixel City Tycoon - Prototype 0.1
A small isometric city-builder prototype using Pygame and procedural pixel-style art.
"""
from __future__ import annotations

import asyncio
import copy
import json
import math
from array import array
import os
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pygame

# -----------------------------------------------------------------------------
# Paths and configuration
# -----------------------------------------------------------------------------
APP_NAME = "Pixel City Tycoon"
BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
IS_WEB = sys.platform == "emscripten"
WEB_SAVE_KEY = "pixel-city-tycoon-save-v1"

# Native builds use the user's Documents folder. Browser builds use localStorage
# so that saves remain available across page reloads on the same browser.
if IS_WEB:
    SAVE_DIR = None
    SAVE_FILE = None
else:
    SAVE_DIR = Path.home() / "Documents" / "PixelCityTycoon" / "saves"
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    SAVE_FILE = SAVE_DIR / "city_save.json"

LOGICAL_W, LOGICAL_H = 640, 360
WINDOW_SCALE = 2
WINDOW_W, WINDOW_H = LOGICAL_W * WINDOW_SCALE, LOGICAL_H * WINDOW_SCALE
TOP_H = 32
BOTTOM_Y = 288
VIEW_RECT = pygame.Rect(0, TOP_H, LOGICAL_W, BOTTOM_Y - TOP_H)
MAP_W = 44
MAP_H = 44
TILE_W = 32
TILE_H = 16
ZOOM_LEVELS = [0.70, 0.82, 0.94, 1.06, 1.18, 1.30]
WORKER_SIZE = 0.76
ACTION_RANGE = 3
MAX_WORK_QUEUE = 50
WORK_ACTION_DURATION = 0.86
WORK_ACTION_HIT_TIMES = {"chop": 0.47, "mine": 0.44, "build": 0.52}
ROAD_MONEY_COST = 100
ROAD_WOOD_COST = 1
HOUSE_MONEY_COST = 3000
HOUSE_WOOD_COST = 1
HOUSE_STONE_COST = 1
DIG_STONE_REWARD = 3
BRIDGE_MONEY_COST = 250
BRIDGE_WOOD_COST = 2
BRIDGE_STONE_COST = 1
MINE_MONEY_COST = 5000
MINE_WOOD_COST = 4
MINE_STONE_COST = 3
MINE_LAYER_DURATION_MINUTES = 6 * 60
MINE_STONE_PER_LAYER = 8
TERRAIN_RESTORE_STONE_COST = 2
RESTORE_TREE_MONEY_COST = 100
RESTORE_ROCK_MONEY_COST = 200
ELEVATION_STEP = 8
CAMERA_SPEED = 210.0
DAILY_INCOME_PER_RESIDENT = 25

# Palette: restrained 16-bit-inspired colors.
C = {
    "sky": (112, 167, 180),
    "grass_a": (107, 166, 88),
    "grass_b": (100, 157, 82),
    "grass_c": (116, 174, 94),
    "grass_edge": (78, 129, 72),
    "water": (55, 126, 165),
    "water_light": (83, 163, 190),
    "water_dark": (35, 91, 132),
    "mountain_top": (132, 137, 132),
    "mountain_light": (164, 166, 151),
    "mountain_side": (91, 99, 91),
    "mountain_dark": (66, 76, 74),
    "tree_dark": (34, 91, 56),
    "tree_mid": (45, 125, 65),
    "tree_light": (75, 156, 75),
    "trunk": (112, 73, 42),
    "rock": (121, 126, 119),
    "road": (111, 111, 111),
    "road_light": (147, 145, 131),
    "road_center": (232, 197, 78),
    "road_edge": (75, 77, 72),
    "panel": (35, 43, 49),
    "panel2": (48, 59, 65),
    "panel3": (67, 81, 85),
    "text": (240, 235, 207),
    "muted": (169, 184, 174),
    "gold": (239, 191, 74),
    "red": (203, 90, 73),
    "green": (115, 190, 107),
    "white": (255, 255, 245),
}

TOOL_NAMES = [
    "F1 이동", "F2 제거", "F3 도로", "F4 건설", "F8 복원"
]
TOOL_KEYS = ["move", "remove", "road", "house", "restore"]
REMOVE_MODE_OPTIONS = (
    ("clear", "자연"),
    ("dig", "굴착"),
    ("demolish", "인공"),
)
REMOVE_MODE_LABELS = {
    "clear": "자연 제거",
    "dig": "산 굴착",
    "demolish": "인공 철거",
}
RESTORE_MODE_OPTIONS = (("terrain", "지형"), ("tree", "나무"), ("rock", "바위"))
RESTORE_MODE_LABELS = {"terrain": "지형 복원", "tree": "나무 복원", "rock": "바위 복원"}
REMOVE_MODE_HINTS = {
    "clear": "나무·바위를 제거해 목재·석재를 얻습니다.",
    "dig": "산 타일을 한 층 낮춰 석재를 얻습니다.",
    "demolish": "도로·다리·주택·시설을 철거합니다.",
}
TOOL_HINTS = {
    "move": "이동: 빈 땅을 클릭해 작업자를 이동합니다.",
    "remove": "제거: 자연·굴착·인공 중 대상을 선택 · [ ] 또는 하단 버튼으로 변경",
    "road": "도로: 드래그 건설 · 물 위로 연결하면 다리 · R 회전",
    "house": "건설: 빈 땅 클릭 → 건물 선택 · [ ] 종류 변경 · G 업그레이드",
    "restore": "복원: 지형·나무·바위를 선택해 되돌립니다 · [ ]로 변경",
}

CITY_OBJECT_DEFS = {
    "commercial": {
        "label": "상업 건물", "w": 2, "h": 2,
        "money": 8500, "wood": 3, "stone": 2,
        "road": True, "jobs": 8, "income": 120, "maintenance": 20,
        "power_use": 2, "water_use": 2,
    },
    "industrial": {
        "label": "공업 건물", "w": 3, "h": 2,
        "money": 12000, "wood": 5, "stone": 4,
        "road": True, "jobs": 12, "income": 180, "maintenance": 40,
        "power_use": 4, "water_use": 3, "pollution": 12,
    },
    "public": {
        "label": "공공시설", "w": 2, "h": 2,
        "money": 9500, "wood": 3, "stone": 4,
        "road": True, "jobs": 4, "income": 0, "maintenance": 45,
        "power_use": 1, "water_use": 1,
    },
    "park": {
        "label": "공원", "w": 2, "h": 2,
        "money": 2500, "wood": 2, "stone": 1,
        "road": True, "jobs": 0, "income": 0, "maintenance": 5,
    },
    "lamp": {
        "label": "가로등", "w": 1, "h": 1,
        "money": 500, "wood": 1, "stone": 0,
        "road": True, "jobs": 0, "income": 0, "maintenance": 2,
    },
    "decor_tree": {
        "label": "조경수", "w": 1, "h": 1,
        "money": 350, "wood": 1, "stone": 0,
        "road": False, "jobs": 0, "income": 0, "maintenance": 0,
    },
    "logging": {
        "label": "벌목장", "w": 2, "h": 2,
        "money": 7000, "wood": 3, "stone": 2,
        "road": True, "jobs": 6, "income": 0, "maintenance": 18,
        "power_use": 1, "water_use": 1,
    },
    "power": {
        "label": "발전소", "w": 2, "h": 2,
        "money": 11000, "wood": 4, "stone": 4,
        "road": True, "jobs": 3, "income": 0, "maintenance": 45,
        "power_output": 48, "service_range": 9, "pollution": 16,
    },
    "water": {
        "label": "급수탑", "w": 2, "h": 2,
        "money": 7000, "wood": 2, "stone": 4,
        "road": True, "jobs": 2, "income": 0, "maintenance": 22,
        "water_output": 48, "service_range": 9, "pollution": 0,
    },
}
BUILDING_CYCLE = [
    "house", "commercial", "industrial", "public", "park",
    "lamp", "decor_tree", "mine", "logging"
]
BUILD_MENU_ITEMS = [
    ("house", "집", "1×1"),
    ("commercial", "상가", "2×2"),
    ("industrial", "공장", "3×2"),
    ("public", "공공", "2×2"),
    ("park", "공원", "2×2"),
    ("lamp", "가로등", "1×1"),
    ("decor_tree", "조경수", "1×1"),
    ("mine", "채굴장", "1×1"),
    ("logging", "벌목장", "2×2"),
    ("power", "발전소", "2×2"),
    ("water", "급수탑", "2×2"),
]
LUMBER_CAMP_DURATION_MINUTES = 6 * 60
LUMBER_CAMP_WOOD_PER_CYCLE = 4
UPGRADABLE_OBJECTS = {"house", "commercial", "industrial", "public"}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def tile_key(x: int, y: int) -> str:
    return f"{x},{y}"


def valid_tile_set(raw: object) -> Set[Tuple[int, int]]:
    """Parse a save-file tile list without trusting its shape or coordinates."""
    if not isinstance(raw, list):
        return set()
    result: Set[Tuple[int, int]] = set()
    for entry in raw:
        if (isinstance(entry, (list, tuple)) and len(entry) == 2
                and type(entry[0]) is int and type(entry[1]) is int
                and 0 <= entry[0] < MAP_W and 0 <= entry[1] < MAP_H):
            result.add((entry[0], entry[1]))
    return result


def safe_saved_int(value: object, default: int, low: int, high: int) -> int:
    """Read a bounded integer from untrusted or older save data."""
    if type(value) is not int:
        return default
    return max(low, min(high, value))


@dataclass
class TileInfo:
    terrain: str = "grass"
    variation: int = 0
    height: int = 0


class CityGame:
    def __init__(self) -> None:
        pygame.init()
        self.worker_sounds: Dict[str, pygame.mixer.Sound] = {}
        self.init_worker_sounds()
        pygame.display.set_caption(APP_NAME + " - Prototype 0.1")
        self.window = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        self.canvas = pygame.Surface((LOGICAL_W, LOGICAL_H))
        # Player-authored house sprites (transparent PNGs, one image per level).
        self.house_sprites: Dict[int, pygame.Surface] = {}
        self.house_sprite_cache: Dict[Tuple[int, int], pygame.Surface] = {}
        for house_level in range(1, 4):
            sprite_path = BASE_DIR / "assets" / "buildings" / f"house_lv{house_level}.png"
            try:
                self.house_sprites[house_level] = pygame.image.load(str(sprite_path)).convert_alpha()
            except (pygame.error, OSError):
                # Keep the procedural drawing as a fallback if an asset is missing.
                pass
        # Reuse the transparent cliff layer instead of allocating a new surface each frame.
        self.cliff_layer = pygame.Surface((LOGICAL_W, LOGICAL_H), pygame.SRCALPHA)
        self.clock = pygame.time.Clock()
        self.running = True

        self.font_path = self._find_font()
        self.font_cache: Dict[int, pygame.font.Font] = {}

        self.seed = random.randint(100000, 9999999)
        self.rng = random.Random(self.seed)
        self.terrain: List[List[TileInfo]] = []
        self.trees: Set[Tuple[int, int]] = set()
        self.rocks: Set[Tuple[int, int]] = set()
        self.roads: Set[Tuple[int, int]] = set()
        self.road_directions: Dict[Tuple[int, int], str] = {}
        self.road_direction = "x"  # Legacy default; road tiles infer direction from neighbors.
        self.selected_road_tile: Optional[Tuple[int, int]] = None
        self.map_rotation = 0
        self.camera_follow_worker = False
        self.underground_view = False
        self.underground_layer = 1
        self.underground_mined: Set[Tuple[int, int, int]] = set()
        self.houses: Set[Tuple[int, int]] = set()
        self.house_levels: Dict[Tuple[int, int], int] = {}
        # New multi-tile buildings and decorative facilities keyed by top-left anchor.
        self.city_objects: Dict[Tuple[int, int], Dict[str, object]] = {}
        self.logging_progress: Dict[Tuple[int, int], float] = {}
        self.selected_building_type = "house"
        self.selected_structure_anchor: Optional[Tuple[int, int]] = None
        self.build_palette_open = False
        self.build_palette_anchor: Optional[Tuple[int, int]] = None
        self.build_palette_dragging = False
        self.build_palette_hover_index: Optional[int] = None
        self.build_palette_pressed_index: Optional[int] = None
        # (x, y) -> (current stratum 1..4, elapsed in-game minutes in that stratum).
        # Layer 4 means the three available strata have been exhausted.
        self.mines: Dict[Tuple[int, int], Tuple[int, float]] = {}
        self.expand_level = 0
        self.money = 100000
        self.population = 0
        self.wood = 0
        self.stone = 0
        self.day = 1
        self.game_minutes = 8 * 60
        self.last_clock_tick = time.time()

        self.zoom_index = 2
        self.zoom = ZOOM_LEVELS[self.zoom_index]
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.tool = "move"
        self.remove_mode = "clear"
        self.restore_mode = "terrain"
        self.worker_x = MAP_W // 2
        self.worker_y = MAP_H // 2
        self.worker_facing = (1, 0)
        self.worker_path: List[Tuple[int, int]] = []
        self.worker_move_progress = 0.0
        self.worker_moved = False
        self.worker_action = "idle"
        self.worker_action_timer = 0.0
        self.worker_action_elapsed = 0.0
        self.worker_action_hit_played = False
        self.worker_pending_action: Optional[Tuple[str, int, int]] = None
        self.work_queue: List[Tuple[str, int, int]] = []
        self.work_path_active = False
        self.dragging = False  # Middle-button camera panning.
        self.last_mouse = (0, 0)
        self.touch_input_active = False
        self.active_finger_id: Optional[int] = None
        self.touch_fingers: Dict[int, Tuple[int, int]] = {}
        self.touch_gesture_mode: Optional[str] = None
        self.touch_last_midpoint = (0, 0)
        self.touch_last_distance = 0.0
        self.tool_dragging = False
        self.tool_drag_start_tile: Optional[Tuple[int, int]] = None
        self.tool_drag_last_tile: Optional[Tuple[int, int]] = None
        self.tool_drag_start_pos = (0, 0)
        self.tool_drag_moved = False
        self.tool_drag_visited: Set[Tuple[int, int]] = set()
        self.modal_seed = False
        self.seed_text = ""
        self.save_dialog_mode: Optional[str] = None
        self.save_dialog_selected = 1
        self.save_dialog_confirm = False
        self.autosave_elapsed = 0.0
        self.last_load_success = False
        self.settings_open = False
        self.help_open = False
        self.sandbox_mode = False
        self.sound_enabled = True
        self.window_scale = 2
        self.notice = "새로운 도시를 시작해 보세요!"
        self.notice_until = time.time() + 4
        self.tutorial_step = 0
        self.tutorial_done = False
        self.tutorial_removed = 0
        self.tutorial_roads = 0
        self.tutorial_house_built = False
        self.tutorial_started_at = time.time()

        self.generate_world(self.seed)
        self.center_camera()

    # ------------------------------------------------------------------
    # Fonts / UI helpers
    # ------------------------------------------------------------------
    def _find_font(self) -> Optional[str]:
        # Ship the same Korean-capable font with desktop and browser builds.
        bundled_font = BASE_DIR / "assets" / "fonts" / "NotoSansKR[wght].ttf"
        if bundled_font.is_file():
            return str(bundled_font)
        names = ["malgungothic", "nanumgothic", "noto sans cjk kr", "arial", "dejavusans"]
        for name in names:
            path = pygame.font.match_font(name)
            if path:
                return path
        return None

    def font(self, size: int) -> pygame.font.Font:
        if size not in self.font_cache:
            self.font_cache[size] = pygame.font.Font(self.font_path, size)
        return self.font_cache[size]

    def text(self, surface: pygame.Surface, value: str, x: int, y: int,
             size: int = 12, color: Tuple[int, int, int] = C["text"],
             center: bool = False) -> None:
        img = self.font(size).render(str(value), False, color)
        rect = img.get_rect()
        if center:
            rect.center = (x, y)
        else:
            rect.topleft = (x, y)
        surface.blit(img, rect)

    def notify(self, message: str, seconds: float = 2.8) -> None:
        self.notice = message
        self.notice_until = time.time() + seconds

    def select_tool(self, tool: str) -> None:
        """Change the active interaction mode from mouse or function keys."""
        if tool not in TOOL_KEYS:
            return
        changed = self.tool != tool
        self.tool = tool
        if changed:
            self.close_build_palette()
            self.selected_structure_anchor = None
            if tool != "road":
                self.selected_road_tile = None
        if changed:
            mode_name = TOOL_NAMES[TOOL_KEYS.index(tool)].split(" ", 1)[1]
            if tool == "remove":
                self.notify(
                    f"제거 모드 · {REMOVE_MODE_LABELS[self.remove_mode]}",
                    1.2
                )
            else:
                self.notify(f"{mode_name} 모드", 1.2)

    def active_action_tool(self) -> str:
        """Resolve the selected sub-action inside a consolidated parent mode."""
        if self.tool == "remove":
            return self.remove_mode
        if self.tool == "restore":
            return {"terrain": "restore", "tree": "restore_tree", "rock": "restore_rock"}.get(self.restore_mode, "restore")
        return self.tool

    def cycle_restore_mode(self, direction: int) -> None:
        modes = [mode for mode, _label in RESTORE_MODE_OPTIONS]
        current = modes.index(self.restore_mode)
        self.restore_mode = modes[(current + direction) % len(modes)]
        if self.tool == "restore":
            self.notify(f"복원 대상: {RESTORE_MODE_LABELS[self.restore_mode]}", 1.6)

    def set_remove_mode(self, mode: str) -> None:
        if mode not in REMOVE_MODE_LABELS:
            return
        if self.remove_mode == mode:
            return
        self.remove_mode = mode
        if self.tool == "remove":
            self.notify(f"제거 대상: {REMOVE_MODE_LABELS[mode]}", 1.6)

    def cycle_remove_mode(self, direction: int) -> None:
        modes = [mode for mode, _label in REMOVE_MODE_OPTIONS]
        current = modes.index(self.remove_mode)
        self.set_remove_mode(modes[(current + direction) % len(modes)])

    def init_worker_sounds(self) -> None:
        """Create small procedural work sounds; audio failure never blocks startup."""
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            mixer_info = pygame.mixer.get_init()
            if mixer_info is None:
                return
            sample_rate, sample_format, channels = mixer_info
            if sample_format != -16:
                return

            specifications = {
                "chop": (145.0, 72.0, 0.22, 0.48, 0.46),
                "mine": (980.0, 410.0, 0.24, 0.40, 0.24),
                "build": (235.0, 105.0, 0.17, 0.46, 0.34),
            }
            for index, (name, spec) in enumerate(specifications.items()):
                self.worker_sounds[name] = self.make_worker_sound(
                    sample_rate, channels, *spec, seed=1201 + index
                )
        except (pygame.error, OSError, ValueError):
            self.worker_sounds = {}

    def make_worker_sound(
        self,
        sample_rate: int,
        channels: int,
        start_frequency: float,
        end_frequency: float,
        duration: float,
        volume: float,
        noise_amount: float,
        seed: int = 1,
    ) -> pygame.mixer.Sound:
        """Build a short decaying impact sound in the active mixer format."""
        rng = random.Random(seed)
        sample_count = max(1, int(sample_rate * duration))
        samples = array("h")
        phase = 0.0
        for index in range(sample_count):
            progress = index / sample_count
            frequency = start_frequency + (end_frequency - start_frequency) * progress
            phase += (2.0 * math.pi * frequency) / sample_rate
            envelope = math.exp(-7.5 * progress)
            tone = (math.sin(phase) * 0.82 + math.sin(phase * 2.03) * 0.18)
            noise = (rng.random() * 2.0 - 1.0) * noise_amount * math.exp(-18.0 * progress)
            value = int(clamp((tone * envelope * volume + noise) * 26000, -32767, 32767))
            for _channel in range(channels):
                samples.append(value)
        return pygame.mixer.Sound(buffer=samples.tobytes())

    def play_worker_action_sound(self, action: str) -> None:
        if not self.sound_enabled:
            return
        sound = self.worker_sounds.get(action)
        if sound is not None:
            try:
                sound.play()
            except pygame.error:
                # The visual action still works if the mixer becomes unavailable.
                pass

    def start_worker_action(self, action: str, target_x: int, target_y: int) -> None:
        """Face the work target and begin a timed wind-up, impact and recovery."""
        wx, wy = self.worker_grid_position()
        dx, dy = target_x - wx, target_y - wy
        if abs(dx) >= abs(dy):
            self.worker_facing = (1 if dx >= 0 else -1, 0)
        else:
            self.worker_facing = (0, 1 if dy >= 0 else -1)
        self.worker_action = action
        self.worker_action_elapsed = 0.0
        self.worker_action_timer = WORK_ACTION_DURATION
        self.worker_action_hit_played = False

    def button(self, rect: pygame.Rect, label: str, active: bool = False,
               small: bool = False) -> None:
        fill = C["gold"] if active else C["panel2"]
        edge = (255, 222, 137) if active else (88, 104, 103)
        pygame.draw.rect(self.canvas, edge, rect)
        inner = rect.inflate(-2, -2)
        pygame.draw.rect(self.canvas, fill, inner)
        color = (42, 48, 43) if active else C["text"]
        self.text(self.canvas, label, rect.centerx, rect.centery,
                  9 if small else 10, color, center=True)

    # ------------------------------------------------------------------
    # World generation
    # ------------------------------------------------------------------
    def generate_world(self, seed: int) -> None:
        self.seed = int(seed)
        self.rng = random.Random(self.seed)
        self.terrain = [[TileInfo("grass", self.rng.randrange(3)) for _ in range(MAP_H)]
                        for _ in range(MAP_W)]
        self.trees.clear()
        self.rocks.clear()
        self.roads.clear()
        self.road_directions.clear()
        self.road_direction = "x"
        self.selected_road_tile = None
        self.map_rotation = 0
        self.camera_follow_worker = False
        self.underground_view = False
        self.underground_layer = 1
        self.underground_mined.clear()
        self.mines.clear()
        self.tool_dragging = False
        self.tool_drag_start_tile = None
        self.tool_drag_last_tile = None
        self.tool_drag_moved = False
        self.tool_drag_visited.clear()
        self.houses.clear()
        self.house_levels.clear()
        self.city_objects.clear()
        self.logging_progress.clear()
        self.selected_building_type = "house"
        self.selected_structure_anchor = None
        self.build_palette_open = False
        self.build_palette_anchor = None
        self.build_palette_dragging = False
        self.build_palette_hover_index = None
        self.build_palette_pressed_index = None
        self.expand_level = 0
        self.money = 100000
        self.population = 0
        self.wood = 0
        self.stone = 0
        self.day = 1
        self.game_minutes = 8 * 60
        self.tool = "move"
        self.worker_x = MAP_W // 2
        self.worker_y = MAP_H // 2
        self.worker_facing = (1, 0)
        self.worker_path = []
        self.worker_move_progress = 0.0
        self.worker_moved = False
        self.worker_action = "idle"
        self.worker_action_timer = 0.0
        self.worker_action_elapsed = 0.0
        self.worker_action_hit_played = False
        self.worker_pending_action = None
        self.work_queue = []
        self.work_path_active = False
        self.tutorial_step = 0
        self.tutorial_done = False
        self.tutorial_removed = 0
        self.tutorial_roads = 0
        self.tutorial_house_built = False

        # A gently winding river runs along one side of the map.
        river_x = MAP_W - 9
        river_path: List[int] = []
        for y in range(MAP_H):
            if y % 4 == 0 and self.rng.random() < 0.72:
                river_x += self.rng.choice([-1, 0, 0, 1])
            river_x = int(clamp(river_x, MAP_W - 13, MAP_W - 5))
            river_path.append(river_x)
            width = 1 if y % 7 in (0, 1, 2, 3, 4) else 2
            for dx in range(-width, width + 1):
                xx = river_x + dx
                if 0 <= xx < MAP_W:
                    self.terrain[xx][y].terrain = "water"

        # Mountain clusters are kept away from the initial settlement area.
        center = (MAP_W // 2, MAP_H // 2)
        for _ in range(9):
            for attempt in range(40):
                cx = self.rng.randrange(3, MAP_W - 3)
                cy = self.rng.randrange(3, MAP_H - 3)
                if abs(cx - center[0]) + abs(cy - center[1]) > 13 and cx < MAP_W - 14:
                    break
            radius = self.rng.randint(2, 5)
            for x in range(max(0, cx - radius - 1), min(MAP_W, cx + radius + 2)):
                for y in range(max(0, cy - radius - 1), min(MAP_H, cy + radius + 2)):
                    dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
                    if dist < radius + self.rng.uniform(-0.3, 0.9):
                        if self.terrain[x][y].terrain != "water":
                            # Hills contain several walkable elevation steps.
                            level = int(clamp(math.ceil((radius - dist + 0.8) / 1.15), 1, 4))
                            self.terrain[x][y].terrain = "mountain"
                            self.terrain[x][y].height = max(self.terrain[x][y].height, level)

        # Preserve a broad starter clearing but leave some trees around it.
        sx, sy = center
        for x in range(sx - 2, sx + 3):
            for y in range(sy - 2, sy + 3):
                self.terrain[x][y].terrain = "grass"
                self.terrain[x][y].height = 0

        # Trees use several clusters to create forests and scattered woodland.
        forest_centers = []
        for _ in range(18):
            fx = self.rng.randrange(MAP_W)
            fy = self.rng.randrange(MAP_H)
            if abs(fx - sx) + abs(fy - sy) > 6:
                forest_centers.append((fx, fy, self.rng.randint(2, 5)))

        for x in range(MAP_W):
            for y in range(MAP_H):
                if self.terrain[x][y].terrain != "grass":
                    continue
                if abs(x - sx) <= 2 and abs(y - sy) <= 2:
                    continue
                chance = 0.045
                for fx, fy, rad in forest_centers:
                    if abs(x - fx) + abs(y - fy) < rad * 2:
                        chance = max(chance, 0.30)
                if abs(x - sx) + abs(y - sy) <= 7:
                    chance = max(chance, 0.20)
                if self.rng.random() < chance:
                    self.trees.add((x, y))
                elif self.rng.random() < 0.018:
                    self.rocks.add((x, y))

        # Ensure the tutorial always has trees to clear near the starting area.
        candidates = [(sx - 4, sy), (sx + 4, sy), (sx, sy - 4), (sx, sy + 4),
                      (sx - 4, sy + 2), (sx + 4, sy - 2)]
        forced_trees = 0
        for pos in candidates:
            x, y = pos
            if 0 <= x < MAP_W and 0 <= y < MAP_H and self.terrain[x][y].terrain != "water":
                self.terrain[x][y].terrain = "grass"
                self.terrain[x][y].height = 0
                self.rocks.discard(pos)
                self.trees.add(pos)
                forced_trees += 1
                if forced_trees >= 2:
                    break

        # Guarantee two visible stone sources close to the starter clearing.
        # Clear access lanes so randomized trees or hills cannot trap the worker.
        starter_rocks = ((sx, sy + 5), (sx, sy - 5))
        for rock_x, rock_y in starter_rocks:
            step = 1 if rock_y > sy else -1
            for path_y in range(sy + step, rock_y, step):
                path_tile = (sx, path_y)
                self.terrain[sx][path_y].terrain = "grass"
                self.terrain[sx][path_y].height = 0
                self.trees.discard(path_tile)
                self.rocks.discard(path_tile)
            self.terrain[rock_x][rock_y].terrain = "grass"
            self.terrain[rock_x][rock_y].height = 0
            self.trees.discard((rock_x, rock_y))
            self.rocks.add((rock_x, rock_y))

        self.notify(f"새 지형 생성 완료 · 시드 {self.seed}", 3.5)

    def center_camera(self) -> None:
        cx = MAP_W // 2
        cy = MAP_H // 2
        rx, ry = self.rotate_grid_position(cx, cy)
        world_x = (rx - ry) * (TILE_W * self.zoom / 2)
        world_y = (rx + ry) * (TILE_H * self.zoom / 2)
        self.camera_x = VIEW_RECT.centerx - world_x
        self.camera_y = VIEW_RECT.centery - world_y

    def center_camera_on_worker(self) -> None:
        """Keep the moving worker centered when camera-follow mode is enabled."""
        wx, wy = self.worker_grid_position()
        rx, ry = self.rotate_grid_float(wx, wy)
        height = self.terrain[self.worker_x][self.worker_y].height
        if self.worker_path:
            nx, ny = self.worker_path[0]
            next_height = self.terrain[nx][ny].height
            height += (next_height - height) * clamp(self.worker_move_progress, 0.0, 1.0)
        tw, th = TILE_W * self.zoom, TILE_H * self.zoom
        self.camera_x = VIEW_RECT.centerx - (rx - ry) * tw / 2
        self.camera_y = (
            VIEW_RECT.centery - (rx + ry) * th / 2
            + height * ELEVATION_STEP * self.zoom
        )

    def rotate_map(self, turns: int) -> None:
        """Rotate the entire isometric map while preserving the current focal point."""
        focus_tile = (MAP_W // 2, MAP_H // 2)
        before_x, before_y = self.tile_to_screen(*focus_tile)
        self.map_rotation = (self.map_rotation + turns) % 4
        if self.camera_follow_worker:
            self.center_camera_on_worker()
        else:
            after_x, after_y = self.tile_to_screen(*focus_tile)
            self.camera_x += before_x - after_x
            self.camera_y += before_y - after_y
        self.notify(f"지도 회전: {self.map_rotation * 90}도", 1.8)

    def unlocked_bounds(self) -> Tuple[int, int, int, int]:
        radii = [6, 10, 14, 18, 22]
        radius = radii[min(self.expand_level, len(radii) - 1)]
        cx, cy = MAP_W // 2, MAP_H // 2
        return cx - radius, cy - radius, cx + radius, cy + radius

    def is_unlocked(self, x: int, y: int) -> bool:
        x0, y0, x1, y1 = self.unlocked_bounds()
        return x0 <= x <= x1 and y0 <= y <= y1

    # ------------------------------------------------------------------
    # Isometric transform and tile picking
    # ------------------------------------------------------------------
    def rotate_grid_position(self, x: int, y: int) -> Tuple[int, int]:
        """Map world tile coordinates into the currently rotated grid."""
        rotation = self.map_rotation % 4
        if rotation == 1:
            return MAP_W - 1 - y, x
        if rotation == 2:
            return MAP_W - 1 - x, MAP_H - 1 - y
        if rotation == 3:
            return y, MAP_H - 1 - x
        return x, y

    def unrotate_grid_position(self, rx: int, ry: int) -> Tuple[int, int]:
        """Convert rotated grid coordinates back to saved world coordinates."""
        rotation = self.map_rotation % 4
        if rotation == 1:
            return ry, MAP_W - 1 - rx
        if rotation == 2:
            return MAP_W - 1 - rx, MAP_H - 1 - ry
        if rotation == 3:
            return MAP_H - 1 - ry, rx
        return rx, ry

    def rotate_grid_float(self, x: float, y: float) -> Tuple[float, float]:
        """Rotate interpolated worker coordinates without rounding."""
        rotation = self.map_rotation % 4
        if rotation == 1:
            return MAP_W - 1 - y, x
        if rotation == 2:
            return MAP_W - 1 - x, MAP_H - 1 - y
        if rotation == 3:
            return y, MAP_H - 1 - x
        return x, y

    def screen_neighbor(self, x: int, y: int, dx: int, dy: int) -> Tuple[int, int]:
        """Return a neighboring world tile in a direction on the rotated screen."""
        rx, ry = self.rotate_grid_position(x, y)
        nrx, nry = rx + dx, ry + dy
        if not (0 <= nrx < MAP_W and 0 <= nry < MAP_H):
            return -1, -1
        return self.unrotate_grid_position(nrx, nry)

    def tile_to_screen(self, x: int, y: int) -> Tuple[float, float]:
        tw = TILE_W * self.zoom
        th = TILE_H * self.zoom
        rx, ry = self.rotate_grid_position(x, y)
        height = self.terrain[x][y].height if self.terrain else 0
        return ((rx - ry) * tw / 2 + self.camera_x,
                (rx + ry) * th / 2 + self.camera_y
                - height * ELEVATION_STEP * self.zoom)

    def screen_to_tile(self, sx: float, sy: float) -> Optional[Tuple[int, int]]:
        tw = TILE_W * self.zoom
        th = TILE_H * self.zoom
        if tw <= 0 or th <= 0:
            return None
        dx = sx - self.camera_x
        dy = sy - self.camera_y
        a = dx / (tw / 2)
        b = dy / (th / 2)
        xf = (a + b) / 2
        yf = (b - a) / 2
        candidates = []
        # Candidate search takes place in the rotated grid, then returns to
        # the original saved tile coordinates.
        for rx in range(math.floor(xf) - 6, math.floor(xf) + 7):
            for ry in range(math.floor(yf) - 6, math.floor(yf) + 7):
                if not (0 <= rx < MAP_W and 0 <= ry < MAP_H):
                    continue
                x, y = self.unrotate_grid_position(rx, ry)
                if not (0 <= x < MAP_W and 0 <= y < MAP_H):
                    continue
                cx, cy = self.tile_to_screen(x, y)
                nx = abs(sx - cx) / (tw / 2)
                ny = abs(sy - cy) / (th / 2)
                if nx + ny <= 1.03:
                    candidates.append((-self.terrain[x][y].height, nx + ny,
                                       -(rx + ry), x, y))
        if not candidates:
            return None
        candidates.sort()
        _, _, _, x, y = candidates[0]
        return x, y

    # ------------------------------------------------------------------
    # Building / economy
    # ------------------------------------------------------------------
    def worker_can_stand(self, x: int, y: int) -> bool:
        """Return whether the worker can occupy land or a completed bridge tile."""
        if not (0 <= x < MAP_W and 0 <= y < MAP_H) or not self.is_unlocked(x, y):
            return False
        terrain = self.terrain[x][y].terrain
        if terrain not in ("grass", "mountain") and not (
            terrain == "water" and (x, y) in self.roads
        ):
            return False
        if ((x, y) in self.trees or (x, y) in self.rocks
                or (x, y) in self.houses or (x, y) in self.mines
                or self.is_city_object_occupied(x, y)):
            return False
        return True

    def can_step_worker(self, start: Tuple[int, int], end: Tuple[int, int]) -> bool:
        """Allow walking on terraces but limit each step to one height level."""
        if not self.worker_can_stand(*end):
            return False
        sx, sy = start
        ex, ey = end
        if not (0 <= sx < MAP_W and 0 <= sy < MAP_H):
            return False
        return abs(self.terrain[sx][sy].height - self.terrain[ex][ey].height) <= 1

    def find_worker_path(self, goal: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
        """Find a four-direction path with BFS. Trees, rocks, houses and terrain block movement."""
        start = (self.worker_x, self.worker_y)
        if goal == start:
            return []
        if not self.worker_can_stand(*goal):
            return None

        frontier = [start]
        came_from: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {start: None}
        head = 0
        while head < len(frontier):
            current = frontier[head]
            head += 1
            if current == goal:
                break

            x, y = current
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (x + dx, y + dy)
                if nxt in came_from or not self.can_step_worker(current, nxt):
                    continue
                came_from[nxt] = current
                frontier.append(nxt)

        if goal not in came_from:
            return None

        path: List[Tuple[int, int]] = []
        current = goal
        while current != start:
            path.append(current)
            previous = came_from[current]
            if previous is None:
                return None
            current = previous
        path.reverse()
        return path

    def set_worker_destination(self, x: int, y: int) -> None:
        """Set a click-to-move destination. This is only called in move mode."""
        if self.worker_pending_action is not None or self.worker_action_timer > 0:
            self.notify("작업 동작이 끝난 뒤 이동할 수 있어요.", 2)
            return
        goal = (x, y)
        if goal == (self.worker_x, self.worker_y) and not self.worker_path:
            return
        if not self.worker_can_stand(x, y):
            self.notify("그곳에는 이동할 수 없어요. 다른 빈 타일을 선택해 주세요.", 2)
            return

        # When a new destination is chosen mid-step, settle at the nearer tile
        # before calculating the new route so the character never teleports.
        if self.worker_path:
            if self.worker_move_progress >= 0.5:
                self.worker_x, self.worker_y = self.worker_path[0]
            self.worker_path.clear()
            self.worker_move_progress = 0.0
        self.work_path_active = False

        path = self.find_worker_path(goal)
        if path is None:
            self.notify("그곳까지 이동할 수 없어요. 길이 막혀 있는지 확인해 주세요.", 2)
            return
        if not path:
            return

        self.worker_path = path
        nx, ny = path[0]
        self.worker_facing = (nx - self.worker_x, ny - self.worker_y)
        self.worker_moved = True

    def update_worker(self, dt: float) -> None:
        """Advance the worker smoothly along the current tile path."""
        if not self.worker_path:
            self.worker_move_progress = 0.0
            return

        self.worker_move_progress += dt / 0.18
        while self.worker_path and self.worker_move_progress >= 1.0:
            next_x, next_y = self.worker_path.pop(0)
            self.worker_facing = (next_x - self.worker_x, next_y - self.worker_y)
            self.worker_x, self.worker_y = next_x, next_y
            self.worker_move_progress -= 1.0
        if not self.worker_path:
            self.worker_move_progress = 0.0

    def footprint_for(self, kind: str, x: int, y: int) -> Set[Tuple[int, int]]:
        """Return every tile occupied by a building/facility footprint."""
        if kind == "house" or kind == "mine":
            width, height = 1, 1
        else:
            spec = CITY_OBJECT_DEFS.get(kind)
            if spec is None:
                return set()
            width, height = spec["w"], spec["h"]
        return {
            (x + dx, y + dy)
            for dx in range(width)
            for dy in range(height)
        }

    def city_object_at(
        self, x: int, y: int
    ) -> Optional[Tuple[Tuple[int, int], str, int]]:
        """Find the anchor and type when a clicked tile belongs to a city object."""
        pos = (x, y)
        if pos in self.houses:
            return pos, "house", self.house_levels.get(pos, 1)
        if pos in self.mines:
            return pos, "mine", 1
        for anchor, data in self.city_objects.items():
            kind = data.get("type")
            if kind in CITY_OBJECT_DEFS and pos in self.footprint_for(kind, *anchor):
                return anchor, kind, max(1, int(data.get("level", 1)))
        return None

    def is_city_object_occupied(self, x: int, y: int) -> bool:
        return self.city_object_at(x, y) is not None

    def footprint_has_road(self, footprint: Set[Tuple[int, int]]) -> bool:
        """Check all footprint edges for built or already planned road access."""
        for tx, ty in footprint:
            if self.has_adjacent_road(tx, ty):
                return True
            if any(
                tool == "road" and abs(rx - tx) + abs(ry - ty) == 1
                for tool, rx, ry in self.work_queue
            ):
                return True
        return False

    def queued_building_overlap(self, kind: str, x: int, y: int) -> bool:
        """Prevent small buildings from being reserved inside a larger planned footprint."""
        footprint = self.footprint_for(kind, x, y)
        for queued_tool, qx, qy in self.work_queue:
            if queued_tool in ("house", "mine") or queued_tool in CITY_OBJECT_DEFS:
                if footprint & self.footprint_for(queued_tool, qx, qy):
                    return True
        return False

    def can_build_city_object(
        self, kind: str, x: int, y: int, allow_worker: bool = False,
        ignore_order: Optional[Tuple[str, int, int]] = None,
        require_forest: bool = True,
        require_road: bool = True,
    ) -> bool:
        """Validate an entire multi-tile footprint, not just its anchor tile."""
        spec = CITY_OBJECT_DEFS.get(kind)
        if spec is None:
            return False
        footprint = self.footprint_for(kind, x, y)
        if not footprint:
            return False
        heights: Set[int] = set()
        for tx, ty in footprint:
            if not (0 <= tx < MAP_W and 0 <= ty < MAP_H) or not self.is_unlocked(tx, ty):
                return False
            tile = self.terrain[tx][ty]
            if tile.terrain not in ("grass", "mountain"):
                return False
            heights.add(tile.height)
            if ((tx, ty) in self.trees or (tx, ty) in self.rocks
                    or (tx, ty) in self.roads or (tx, ty) in self.houses
                    or (tx, ty) in self.mines or self.is_city_object_occupied(tx, ty)):
                return False
            if (tx, ty) == (self.worker_x, self.worker_y) and not allow_worker:
                return False
        # Multi-tile buildings may span elevation layers; each occupied tile
        # keeps its own height and is still checked for blockers.

        # Prevent two planned structures from reserving overlapping ground.
        for queued_tool, qx, qy in self.work_queue:
            if ignore_order == (queued_tool, qx, qy):
                continue
            if queued_tool in ("house", "mine") or queued_tool in CITY_OBJECT_DEFS:
                if footprint & self.footprint_for(queued_tool, qx, qy):
                    return False

        if spec["road"] and require_road and not self.footprint_has_road(footprint):
            return False
        if kind == "logging" and require_forest:
            nearby_trees = {
                tree for tree in self.trees
                if min(abs(tree[0] - tx) + abs(tree[1] - ty) for tx, ty in footprint) <= 5
            }
            if not nearby_trees:
                return False
        return True

    def cycle_building_type(self, direction: int) -> None:
        current = BUILDING_CYCLE.index(self.selected_building_type)
        self.selected_building_type = BUILDING_CYCLE[
            (current + direction) % len(BUILDING_CYCLE)
        ]
        label = (
            "주택" if self.selected_building_type == "house"
            else "채굴장" if self.selected_building_type == "mine"
            else CITY_OBJECT_DEFS[self.selected_building_type]["label"]
        )
        self.notify(f"건설 종류: {label}", 1.8)

    def build_palette_geometry(self) -> Tuple[pygame.Rect, List[pygame.Rect]]:
        """Return an anchored 3x3 building palette clamped inside the map view."""
        rows = math.ceil(len(BUILD_MENU_ITEMS) / 3)
        width, height = 246, 24 + rows * 30 + max(0, rows - 1) * 4 + 18
        anchor = self.build_palette_anchor or (self.worker_x, self.worker_y)
        ax, ay = self.tile_to_screen(*anchor)
        px = round(ax + 18)
        if px + width > LOGICAL_W - 4:
            px = round(ax - width - 18)
        px = int(clamp(px, 4, LOGICAL_W - width - 4))
        py = int(clamp(round(ay - height / 2), TOP_H + 4, BOTTOM_Y - height - 4))
        panel = pygame.Rect(px, py, width, height)
        cells: List[pygame.Rect] = []
        cell_w, cell_h, gap = 72, 30, 4
        for index in range(len(BUILD_MENU_ITEMS)):
            col, row = index % 3, index // 3
            cells.append(pygame.Rect(
                px + 8 + col * (cell_w + gap),
                py + 24 + row * (cell_h + gap),
                cell_w, cell_h
            ))
        return panel, cells

    def build_palette_hit_test(self, pos: Tuple[int, int]) -> Optional[int]:
        if not self.build_palette_open:
            return None
        _panel, cells = self.build_palette_geometry()
        for index, rect in enumerate(cells):
            if rect.collidepoint(pos):
                return index
        return None

    def open_build_palette(self, anchor: Tuple[int, int]) -> None:
        """Click a tile to open the palette; holding and releasing on an option selects it."""
        found = self.city_object_at(*anchor)
        if found is not None:
            self.selected_structure_anchor = found[0]
            self.notify("건물을 선택했어요. G 키로 업그레이드할 수 있어요.", 2.2)
            return
        self.selected_structure_anchor = None
        self.build_palette_anchor = anchor
        self.build_palette_open = True
        self.build_palette_dragging = True
        self.build_palette_pressed_index = None
        self.build_palette_hover_index = None

    def close_build_palette(self) -> None:
        self.build_palette_open = False
        self.build_palette_anchor = None
        self.build_palette_dragging = False
        self.build_palette_hover_index = None
        self.build_palette_pressed_index = None

    def choose_building_from_palette(self, index: int) -> None:
        if not self.build_palette_open or self.build_palette_anchor is None:
            return
        if not 0 <= index < len(BUILD_MENU_ITEMS):
            return
        kind = BUILD_MENU_ITEMS[index][0]
        anchor = self.build_palette_anchor
        self.close_build_palette()
        self.selected_building_type = kind
        self.toggle_work_order(kind, *anchor)

    def draw_build_palette(self) -> None:
        """Render the floating building selector with live costs and hover feedback."""
        if not self.build_palette_open:
            return
        panel, cells = self.build_palette_geometry()
        pygame.draw.rect(self.canvas, (24, 32, 37), panel)
        pygame.draw.rect(self.canvas, C["gold"], panel, 2)
        self.text(
            self.canvas, "건설 종류 선택 · 원하는 항목 위에서 놓기",
            panel.centerx, panel.y + 12, 9, C["gold"], center=True
        )

        for index, (_kind, label, size) in enumerate(BUILD_MENU_ITEMS):
            rect = cells[index]
            active = index == self.build_palette_hover_index
            fill = (112, 132, 103) if active else C["panel2"]
            edge = C["white"] if active else (91, 112, 105)
            pygame.draw.rect(self.canvas, edge, rect)
            pygame.draw.rect(self.canvas, fill, rect.inflate(-2, -2))
            text_color = (35, 43, 38) if active else C["text"]
            sub_color = (35, 43, 38) if active else C["muted"]
            self.text(self.canvas, label, rect.centerx, rect.y + 8,
                      9, text_color, center=True)
            self.text(self.canvas, size, rect.centerx, rect.y + 21,
                      7, sub_color, center=True)

        if self.build_palette_hover_index is None:
            footer = "취소: ESC · 빈 곳 클릭"
            footer_color = C["muted"]
        else:
            kind = BUILD_MENU_ITEMS[self.build_palette_hover_index][0]
            money, wood, stone = self.order_costs(
                kind, *(self.build_palette_anchor or (self.worker_x, self.worker_y))
            )
            valid, reason = self.can_reserve_work_order(
                kind, *(self.build_palette_anchor or (self.worker_x, self.worker_y))
            )
            if valid:
                footer = f"₩{money:,} · 목재 {wood} · 석재 {stone}"
                footer_color = C["green"]
            else:
                footer = reason
                footer_color = C["red"]
        self.text(
            self.canvas, footer, panel.centerx, panel.bottom - 7,
            7, footer_color, center=True
        )

    def upgrade_selected_structure(self) -> None:
        """Upgrade a selected home or city building up to level three."""
        anchor = self.selected_structure_anchor
        if anchor is None:
            self.notify("먼저 F4 건설 모드에서 기존 건물을 클릭해 선택하세요.", 2.5)
            return
        found = self.city_object_at(*anchor)
        if found is None:
            self.selected_structure_anchor = None
            self.notify("선택한 건물을 찾을 수 없어요.", 2)
            return
        _anchor, kind, level = found
        if kind not in UPGRADABLE_OBJECTS:
            self.notify("이 시설은 업그레이드할 수 없어요.", 2.2)
            return
        if level >= 3:
            self.notify("이미 최대 단계예요.", 2)
            return

        if kind == "house":
            base_money, base_wood, base_stone = 2500, 2, 1
        else:
            spec = CITY_OBJECT_DEFS[kind]
            base_money = int(spec["money"])
            base_wood = int(spec["wood"])
            base_stone = int(spec["stone"])
        money_cost = base_money * level // 2
        wood_cost = base_wood + level
        stone_cost = base_stone + level
        reserved_wood, reserved_stone = self.reserved_material_costs()
        if not self.sandbox_mode and self.money - self.reserved_build_cost() < money_cost:
            self.notify(f"업그레이드 자금이 부족해요. 필요 자금 ₩{money_cost:,}", 2.5)
            return
        if (self.wood - reserved_wood < wood_cost
                or self.stone - reserved_stone < stone_cost):
            self.notify(
                f"업그레이드 재료가 부족해요. 목재 {wood_cost} · 석재 {stone_cost}", 2.5
            )
            return

        self.money -= money_cost
        self.wood -= wood_cost
        self.stone -= stone_cost
        new_level = level + 1
        if kind == "house":
            self.house_levels[anchor] = new_level
            self.population += 2
        else:
            self.city_objects[anchor]["level"] = new_level
        name = "주택" if kind == "house" else CITY_OBJECT_DEFS[kind]["label"]
        extra = " · 주민 +2" if kind == "house" else ""
        self.notify(
            f"{name} 업그레이드 완료 · Lv.{new_level}{extra} · -₩{money_cost:,}", 3
        )

    def can_build_on(self, x: int, y: int, allow_worker: bool = False) -> bool:
        if not (0 <= x < MAP_W and 0 <= y < MAP_H) or not self.is_unlocked(x, y):
            return False
        if self.terrain[x][y].terrain not in ("grass", "mountain"):
            return False
        if (x, y) in self.trees or (x, y) in self.rocks:
            return False
        if (x, y) in self.roads or (x, y) in self.houses or (x, y) in self.mines:
            return False
        if self.is_city_object_occupied(x, y):
            return False
        if (x, y) == (self.worker_x, self.worker_y) and not allow_worker:
            return False
        return True

    def can_build_mine_on(
        self, x: int, y: int, allow_worker: bool = False
    ) -> bool:
        """A mine needs a clear grass tile beside a built or planned road."""
        return (
            self.can_build_on(x, y, allow_worker=allow_worker)
            and self.has_planned_adjacent_road(x, y)
        )

    def can_restore_terrain(
        self, x: int, y: int, allow_worker: bool = False
    ) -> bool:
        """Raise empty land by one level; never overwrite water or city objects."""
        if not (0 <= x < MAP_W and 0 <= y < MAP_H) or not self.is_unlocked(x, y):
            return False
        tile = self.terrain[x][y]
        if tile.terrain not in ("grass", "mountain") or tile.height >= 4:
            return False
        if ((x, y) in self.trees or (x, y) in self.rocks
                or (x, y) in self.roads or (x, y) in self.houses
                or (x, y) in self.mines or self.is_city_object_occupied(x, y)):
            return False
        if (x, y) == (self.worker_x, self.worker_y) and not allow_worker:
            return False
        return True

    def can_build_road_on(self, x: int, y: int) -> bool:
        """Allow a bridge segment to extend from an existing or queued road."""
        if not (0 <= x < MAP_W and 0 <= y < MAP_H) or not self.is_unlocked(x, y):
            return False
        if (x, y) in self.trees or (x, y) in self.rocks or (x, y) in self.roads:
            return False
        if (x, y) in self.houses or (x, y) in self.mines or self.is_city_object_occupied(x, y):
            return False
        if self.terrain[x][y].terrain == "water":
            return self.has_planned_adjacent_road(x, y)
        return self.can_build_on(x, y)

    def road_build_cost(self, x: int, y: int) -> Tuple[int, int, int]:
        """Return money, wood and stone costs for a road or a water bridge tile."""
        if self.terrain[x][y].terrain == "water":
            return BRIDGE_MONEY_COST, BRIDGE_WOOD_COST, BRIDGE_STONE_COST
        return ROAD_MONEY_COST, ROAD_WOOD_COST, 0

    def can_dig_terrain(self, x: int, y: int) -> bool:
        """Only exposed, unlocked mountain tiles can be excavated."""
        if not (0 <= x < MAP_W and 0 <= y < MAP_H) or not self.is_unlocked(x, y):
            return False
        if (self.terrain[x][y].terrain != "mountain"
                and self.terrain[x][y].height <= 0):
            return False
        if (x, y) in self.trees or (x, y) in self.rocks or (x, y) in self.roads or (x, y) in self.houses:
            return False
        if (x, y) in self.mines or self.is_city_object_occupied(x, y):
            return False
        return True

    def worker_grid_position(self) -> Tuple[float, float]:
        """Current continuous grid coordinates, including an in-progress step."""
        wx, wy = float(self.worker_x), float(self.worker_y)
        if self.worker_path:
            nx, ny = self.worker_path[0]
            t = clamp(self.worker_move_progress, 0.0, 1.0)
            wx += (nx - wx) * t
            wy += (ny - wy) * t
        return wx, wy

    def worker_can_reach(self, x: int, y: int) -> bool:
        """Actions are limited to a small Manhattan radius around the character."""
        wx, wy = self.worker_grid_position()
        return abs(x - wx) + abs(y - wy) <= ACTION_RANGE

    def infer_road_axis(self, x: int, y: int) -> str:
        """Infer a new road's default marking from its connected neighbors."""
        x_links = int((x - 1, y) in self.roads) + int((x + 1, y) in self.roads)
        y_links = int((x, y - 1) in self.roads) + int((x, y + 1) in self.roads)
        return "y" if y_links > x_links else "x"

    def order_costs(self, tool: str, x: int, y: int) -> Tuple[int, int, int]:
        """Return reserved money/wood/stone costs for any construction order."""
        if tool == "road":
            return self.road_build_cost(x, y)
        if tool == "house":
            return HOUSE_MONEY_COST, HOUSE_WOOD_COST, HOUSE_STONE_COST
        if tool == "mine":
            return MINE_MONEY_COST, MINE_WOOD_COST, MINE_STONE_COST
        spec = CITY_OBJECT_DEFS.get(tool)
        if spec:
            return spec["money"], spec["wood"], spec["stone"]
        if tool == "restore":
            return 0, 0, TERRAIN_RESTORE_STONE_COST
        if tool == "restore_tree":
            return RESTORE_TREE_MONEY_COST, 0, 0
        if tool == "restore_rock":
            return RESTORE_ROCK_MONEY_COST, 0, 0
        return 0, 0, 0

    def reserved_build_cost(self) -> int:
        """Money already committed to queued construction orders."""
        return sum(self.order_costs(tool, x, y)[0] for tool, x, y in self.work_queue)

    def reserved_material_costs(self) -> Tuple[int, int]:
        """Wood and stone already committed to queued construction/terraforming."""
        reserved_wood = 0
        reserved_stone = 0
        for tool, x, y in self.work_queue:
            _money, wood_cost, stone_cost = self.order_costs(tool, x, y)
            reserved_wood += wood_cost
            reserved_stone += stone_cost
        return reserved_wood, reserved_stone

    def has_planned_adjacent_road(self, x: int, y: int) -> bool:
        """Check built roads and road orders placed earlier in the queue."""
        if self.has_adjacent_road(x, y):
            return True
        return any(
            tool == "road" and abs(rx - x) + abs(ry - y) == 1
            for tool, rx, ry in self.work_queue
        )

    def underground_vein_amount(self, x: int, y: int, layer: int) -> int:
        """Return the seed-stable stone deposit size for an underground stratum."""
        if not (0 <= x < MAP_W and 0 <= y < MAP_H and 1 <= layer <= 3):
            return 0
        roll = (self.seed * 31 + x * 73 + y * 47 + layer * 109) % 53
        if roll < 2:
            return 8
        if roll < 5:
            return 4
        return 0

    def can_mine_underground_vein(self, x: int, y: int, layer: int) -> bool:
        return (
            self.is_unlocked(x, y)
            and (layer, x, y) not in self.underground_mined
            and self.underground_vein_amount(x, y, layer) > 0
        )

    def mine_underground_vein(self, x: int, y: int, layer: int) -> bool:
        if not self.can_mine_underground_vein(x, y, layer):
            self.notify("이 지층에는 채굴할 광맥이 없거나 이미 채굴했어요.", 2.2)
            return False
        amount = self.underground_vein_amount(x, y, layer)
        self.underground_mined.add((layer, x, y))
        self.stone += amount
        self.notify(f"지하 {layer}층 광맥 채굴 완료 · 석재 +{amount}", 3)
        return True

    def can_reserve_work_order(self, tool: str, x: int, y: int) -> Tuple[bool, str]:
        if not self.is_unlocked(x, y):
            return False, "아직 개척하지 않은 땅이에요. 먼저 땅을 확장하세요."

        if tool == "clear":
            if (x, y) not in self.trees and (x, y) not in self.rocks:
                return False, "자연 제거 대상인 나무나 바위가 없어요."
            return True, ""

        if tool == "demolish":
            if (x, y) not in self.roads and self.city_object_at(x, y) is None:
                return False, "인공 철거 대상인 도로·건물·시설이 없어요."
            return True, ""

        if tool == "dig":
            if not self.can_dig_terrain(x, y):
                return False, "굴착은 개척 구역 안의 산 타일에만 예약할 수 있어요."
            return True, ""

        if tool == "restore":
            if not self.can_restore_terrain(
                x, y, allow_worker=(x, y) == (self.worker_x, self.worker_y)
            ):
                return False, "지형 복원은 빈 육지의 높이가 4단계보다 낮을 때 가능해요."
            _reserved_wood, reserved_stone = self.reserved_material_costs()
            if self.stone - reserved_stone < TERRAIN_RESTORE_STONE_COST:
                return False, f"지형 복원에는 석재 {TERRAIN_RESTORE_STONE_COST}개가 필요해요."
            return True, ""

        if tool in ("restore_tree", "restore_rock"):
            if (self.terrain[x][y].terrain != "grass"
                    or (x, y) in self.trees or (x, y) in self.rocks
                    or (x, y) in self.roads or (x, y) in self.houses
                    or (x, y) in self.mines or self.is_city_object_occupied(x, y)
                    or (x, y) == (self.worker_x, self.worker_y)):
                return False, "나무와 바위는 비어 있는 잔디 타일에만 복원할 수 있어요."
        else:
            allow_worker = (x, y) == (self.worker_x, self.worker_y)
            if tool == "road":
                if not self.can_build_road_on(x, y):
                    return False, "도로는 빈 땅 또는 기존 도로에서 이어지는 물 위에만 놓을 수 있어요."
            elif tool == "house":
                if not self.can_build_on(x, y, allow_worker=allow_worker):
                    return False, "주택은 비어 있는 육지 타일에만 지을 수 있어요."
                if self.queued_building_overlap("house", x, y):
                    return False, "다른 건설 예약이 이 칸을 사용하고 있어요."
                if not self.has_planned_adjacent_road(x, y):
                    return False, "주택은 이미 있는 도로나 먼저 예약한 도로 옆에 지어야 해요."
            elif tool == "mine":
                if not self.can_build_mine_on(x, y, allow_worker=allow_worker):
                    return False, "채굴장은 도로 옆의 빈 육지 타일에만 건설할 수 있어요."
                if self.queued_building_overlap("mine", x, y):
                    return False, "다른 건설 예약이 이 칸을 사용하고 있어요."
            elif tool in CITY_OBJECT_DEFS:
                if not self.can_build_city_object(tool, x, y, allow_worker=allow_worker):
                    spec = CITY_OBJECT_DEFS[tool]
                    if spec["road"]:
                        return False, (
                            f"{spec['label']}은 {spec['w']}×{spec['h']}칸의 빈 육지가 필요하고 "
                            "도로와 인접해야 해요."
                        )
                    return False, (
                        f"{spec['label']}은 {spec['w']}×{spec['h']}칸의 빈 육지가 필요해요."
                    )
            else:
                return False, "예약할 수 없는 작업 종류예요."

        available_money = self.money - self.reserved_build_cost()
        reserved_wood, reserved_stone = self.reserved_material_costs()
        available_wood = self.wood - reserved_wood
        available_stone = self.stone - reserved_stone
        money_cost, wood_cost, stone_cost = self.order_costs(tool, x, y)

        if not self.sandbox_mode and available_money < money_cost:
            return False, f"건설 자금이 부족해요. 필요 자금: ₩{money_cost:,}"
        if available_wood < wood_cost or available_stone < stone_cost:
            return False, f"필요 재료: 목재 {wood_cost}개 · 석재 {stone_cost}개"
        return True, ""

    def toggle_work_order(self, tool: str, x: int, y: int) -> None:
        """Queue or cancel demolition, construction, digging or terrain restoration."""
        if tool not in ("clear", "demolish", "road", "house", "dig", "mine", "restore", "restore_tree", "restore_rock", *CITY_OBJECT_DEFS.keys()):
            return

        existing_index = next(
            (i for i, order in enumerate(self.work_queue)
             if order[1] == x and order[2] == y),
            None
        )
        if existing_index is not None:
            existing = self.work_queue[existing_index]
            if existing[0] != tool:
                self.notify("이 타일에는 이미 다른 작업이 예약되어 있어요.", 2.2)
                return
            self.work_queue.pop(existing_index)
            if tool == "road" and (x, y) not in self.roads:
                self.road_directions.pop((x, y), None)
            if existing_index == 0 and self.worker_pending_action == existing:
                self.worker_pending_action = None
                self.worker_action = "idle"
                self.worker_action_timer = 0.0
                self.worker_action_elapsed = 0.0
                self.worker_action_hit_played = False
                self.work_path_active = False
            elif existing_index == 0 and self.work_path_active:
                if self.worker_path and self.worker_move_progress >= 0.5:
                    self.worker_x, self.worker_y = self.worker_path[0]
                self.worker_path.clear()
                self.worker_move_progress = 0.0
                self.work_path_active = False
            self.notify(f"작업 예약을 취소했어요. 남은 예약 {len(self.work_queue)}개", 2.2)
            return

        if len(self.work_queue) >= MAX_WORK_QUEUE:
            self.notify(f"작업 예약은 최대 {MAX_WORK_QUEUE}개까지 가능해요.", 2.5)
            return
        valid, reason = self.can_reserve_work_order(tool, x, y)
        if not valid:
            self.notify(reason, 2.8)
            return

        self.work_queue.append((tool, x, y))
        if tool == "road":
            self.road_directions[(x, y)] = self.infer_road_axis(x, y)
        labels = {
            "clear": "자연 제거", "demolish": "인공 철거",
            "road": "도로 건설", "house": "주택 건설",
            "dig": "지형 굴착", "mine": "채굴장 건설", "restore": "지형 복원",
            "restore_tree": "나무 복원", "restore_rock": "바위 복원",
            **{kind: f"{spec['label']} 건설" for kind, spec in CITY_OBJECT_DEFS.items()},
        }
        self.notify(
            f"{labels[tool]} 예약 {len(self.work_queue)}개 · 클릭한 순서대로 작업합니다.",
            2.5
        )

    def find_worker_path_to_work_target(
        self, target: Tuple[int, int]
    ) -> Optional[List[Tuple[int, int]]]:
        """Find a path beside a resource or dig site, with a short-range fallback."""
        tx, ty = target
        start = (self.worker_x, self.worker_y)
        adjacent_positions = {
            (tx + dx, ty + dy)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if self.worker_can_stand(tx + dx, ty + dy)
        }
        adjacent_path = self.find_path_to_any_position(start, adjacent_positions)
        if adjacent_path is not None:
            return adjacent_path

        fallback_positions = {
            (tx + dx, ty + dy)
            for dx in range(-ACTION_RANGE, ACTION_RANGE + 1)
            for dy in range(-ACTION_RANGE, ACTION_RANGE + 1)
            if 1 < abs(dx) + abs(dy) <= ACTION_RANGE
            and self.worker_can_stand(tx + dx, ty + dy)
        }
        return self.find_path_to_any_position(start, fallback_positions)

    def find_worker_path_to_action_target(
        self,
        target: Tuple[int, int],
        footprint: Optional[Set[Tuple[int, int]]] = None,
    ) -> Optional[List[Tuple[int, int]]]:
        """Find a legal work position beside every tile of a multi-tile target."""
        tx, ty = target
        blocked_tiles = footprint or {target}
        positions: Set[Tuple[int, int]] = set()
        for fx, fy in blocked_tiles:
            for dx in range(-ACTION_RANGE, ACTION_RANGE + 1):
                for dy in range(-ACTION_RANGE, ACTION_RANGE + 1):
                    candidate = (fx + dx, fy + dy)
                    if (
                        1 <= abs(dx) + abs(dy) <= ACTION_RANGE
                        and candidate not in blocked_tiles
                        and self.worker_can_stand(*candidate)
                    ):
                        positions.add(candidate)
        return self.find_path_to_any_position(
            (self.worker_x, self.worker_y), positions, blocked=blocked_tiles
        )

    def find_path_to_any_position(
        self,
        start: Tuple[int, int],
        goals: Set[Tuple[int, int]],
        blocked: Optional[Set[Tuple[int, int]]] = None,
    ) -> Optional[List[Tuple[int, int]]]:
        """Shared breadth-first path search for multiple possible work positions."""
        if not goals:
            return None
        if start in goals:
            return []
        blocked_tiles = blocked or set()

        frontier = [start]
        came_from: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {start: None}
        head = 0
        goal: Optional[Tuple[int, int]] = None
        while head < len(frontier):
            current = frontier[head]
            head += 1
            if current in goals:
                goal = current
                break
            x, y = current
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (x + dx, y + dy)
                if (nxt in came_from or nxt in blocked_tiles
                        or not self.can_step_worker(current, nxt)):
                    continue
                came_from[nxt] = current
                frontier.append(nxt)

        if goal is None:
            return None
        path: List[Tuple[int, int]] = []
        current = goal
        while current != start:
            path.append(current)
            previous = came_from[current]
            if previous is None:
                return None
            current = previous
        path.reverse()
        return path

    def remove_resource_at(self, x: int, y: int, start_animation: bool = True) -> bool:
        """Remove natural resources only: trees and rocks."""
        target = (x, y)
        if target in self.trees:
            self.trees.remove(target)
            if start_animation:
                self.start_worker_action("chop", x, y)
            self.wood += 2
            self.tutorial_removed += 1
            self.notify("나무를 제거했어요! 목재 +2")
            self.check_tutorial()
            return True
        if target in self.rocks:
            self.rocks.remove(target)
            if start_animation:
                self.start_worker_action("mine", x, y)
            self.stone += 2
            self.notify("바위를 제거했어요! 석재 +2")
            return True
        return False

    def demolish_structure_at(
        self, x: int, y: int, start_animation: bool = True
    ) -> bool:
        """Demolish the complete artificial object, including every footprint tile."""
        target = (x, y)
        if target in self.roads:
            self.roads.remove(target)
            self.road_directions.pop(target, None)
            if self.selected_road_tile == target:
                self.selected_road_tile = None
            self.notify("도로/다리를 철거했어요. 자원은 반환되지 않아요.")
        else:
            found = self.city_object_at(x, y)
            if found is None:
                return False
            anchor, kind, _level = found
            if kind == "house":
                house_level = self.house_levels.pop(anchor, 1)
                self.houses.discard(anchor)
                self.population = max(0, self.population - (4 + 2 * (house_level - 1)))
                self.notify("주택을 철거했어요. 주민이 도시를 떠났어요.")
            elif kind == "mine":
                self.mines.pop(anchor, None)
                self.notify("채굴장을 철거했어요. 진행 중이던 채굴은 중단됐어요.")
            elif anchor in self.city_objects:
                del self.city_objects[anchor]
                self.logging_progress.pop(anchor, None)
                if self.selected_structure_anchor == anchor:
                    self.selected_structure_anchor = None
                name = CITY_OBJECT_DEFS[kind]["label"]
                self.notify(f"{name}을 철거했어요. 자원은 반환되지 않아요.")
            else:
                return False

        if start_animation:
            self.start_worker_action("mine", x, y)
        return True

    def dig_terrain_at(self, x: int, y: int) -> bool:
        """Flatten one mountain tile and award stone at the mining impact frame."""
        if not self.can_dig_terrain(x, y):
            self.notify("굴착할 수 없는 지형이에요.", 2)
            return False
        tile = self.terrain[x][y]
        tile.height = max(0, tile.height - 1)
        if tile.height == 0:
            tile.terrain = "grass"
        tile.variation = self.rng.randrange(3)
        self.stone += DIG_STONE_REWARD
        self.notify(
            f"지형을 한 층 굴착했어요! 남은 높이 {tile.height} · 석재 +{DIG_STONE_REWARD}"
        )
        return True

    def restore_terrain_at(self, x: int, y: int) -> bool:
        """Rebuild one elevation step on empty land using stored stone."""
        if not self.can_restore_terrain(x, y):
            self.notify("이 타일에는 지형을 복원할 수 없어요.", 2)
            return False
        if self.stone < TERRAIN_RESTORE_STONE_COST:
            self.notify("지형 복원에 필요한 석재가 부족해요.", 2)
            return False
        self.stone -= TERRAIN_RESTORE_STONE_COST
        tile = self.terrain[x][y]
        tile.height = min(4, tile.height + 1)
        tile.terrain = "mountain"
        tile.variation = self.rng.randrange(3)
        self.notify(
            f"지형을 한 층 복원했어요! 높이 {tile.height}/4 · 석재 -{TERRAIN_RESTORE_STONE_COST}"
        )
        return True

    def perform_build_order(self, tool: str, x: int, y: int, start_animation: bool = True) -> bool:
        """Build roads, housing, mines, typed city buildings or decorative facilities."""
        if tool == "road":
            if not self.can_build_road_on(x, y):
                self.notify("예약한 도로 위치를 더 이상 사용할 수 없어 작업을 건너뛰었어요.", 2.8)
                return False
            money_cost, wood_cost, stone_cost = self.road_build_cost(x, y)
            if ((not self.sandbox_mode and self.money < money_cost)
                    or self.wood < wood_cost or self.stone < stone_cost):
                self.notify("도로 또는 다리 건설에 필요한 자원이 부족해 예약을 건너뛰었어요.", 2.8)
                return False
            self.money -= money_cost
            self.wood -= wood_cost
            self.stone -= stone_cost
            self.roads.add((x, y))
            self.road_directions.setdefault((x, y), self.infer_road_axis(x, y))
            if start_animation:
                self.start_worker_action("build", x, y)
            if not self.tutorial_done and self.terrain[x][y].terrain != "water":
                self.tutorial_roads += 1
            structure_name = "다리" if self.terrain[x][y].terrain == "water" else "도로"
            self.notify(
                f"{structure_name} 건설 완료 · -₩{money_cost:,} · 목재 -{wood_cost}"
                + (f" · 석재 -{stone_cost}" if stone_cost else "")
            )
            self.check_tutorial()
            return True

        if tool == "house":
            if not self.can_build_on(x, y):
                self.notify("예약한 주택 위치를 더 이상 사용할 수 없어 작업을 건너뛰었어요.", 2.8)
                return False
            if not self.has_adjacent_road(x, y):
                self.notify("예약한 집 옆에 도로가 없어 건설을 건너뛰었어요.", 2.8)
                return False
            if ((not self.sandbox_mode and self.money < HOUSE_MONEY_COST)
                    or self.wood < HOUSE_WOOD_COST or self.stone < HOUSE_STONE_COST):
                self.notify("주택 건설에 필요한 자금 또는 자원이 부족해 예약을 건너뛰었어요.", 2.8)
                return False
            self.money -= HOUSE_MONEY_COST
            self.wood -= HOUSE_WOOD_COST
            self.stone -= HOUSE_STONE_COST
            self.houses.add((x, y))
            self.house_levels[(x, y)] = 1
            if start_animation:
                self.start_worker_action("build", x, y)
            self.population += 4
            self.tutorial_house_built = True
            self.notify(
                f"주택 완공! 주민 4명 입주 · -₩{HOUSE_MONEY_COST:,} · "
                f"목재 -{HOUSE_WOOD_COST} · 석재 -{HOUSE_STONE_COST}", 3.5
            )
            self.check_tutorial()
            return True

        if tool == "mine":
            if not self.can_build_mine_on(x, y):
                self.notify("채굴장은 도로 옆의 빈 잔디 타일에만 건설할 수 있어요.", 2.8)
                return False
            if ((not self.sandbox_mode and self.money < MINE_MONEY_COST)
                    or self.wood < MINE_WOOD_COST or self.stone < MINE_STONE_COST):
                self.notify("채굴장 건설에 필요한 자금 또는 자원이 부족해요.", 2.8)
                return False
            self.money -= MINE_MONEY_COST
            self.wood -= MINE_WOOD_COST
            self.stone -= MINE_STONE_COST
            self.mines[(x, y)] = (1, 0.0)
            if start_animation:
                self.start_worker_action("build", x, y)
            self.notify(
                f"채굴장 완공! 지하 1층부터 자동 채굴 · -₩{MINE_MONEY_COST:,} · "
                f"목재 -{MINE_WOOD_COST} · 석재 -{MINE_STONE_COST}", 3.5
            )
            return True

        spec = CITY_OBJECT_DEFS.get(tool)
        if spec is not None:
            if not self.can_build_city_object(tool, x, y):
                self.notify("예약한 건물/시설의 점유 공간을 사용할 수 없어 작업을 건너뛰었어요.", 2.8)
                return False
            money_cost, wood_cost, stone_cost = self.order_costs(tool, x, y)
            if ((not self.sandbox_mode and self.money < money_cost)
                    or self.wood < wood_cost or self.stone < stone_cost):
                self.notify("건설에 필요한 자금 또는 재료가 부족해 예약을 건너뛰었어요.", 2.8)
                return False
            self.money -= money_cost
            self.wood -= wood_cost
            self.stone -= stone_cost
            self.city_objects[(x, y)] = {"type": tool, "level": 1}
            if tool == "logging":
                self.logging_progress[(x, y)] = 0.0
            if start_animation:
                self.start_worker_action("build", x, y)
            self.notify(
                f"{spec['label']} 건설 완료 · {spec['w']}×{spec['h']}칸 · "
                f"-₩{money_cost:,} · 목재 -{wood_cost} · 석재 -{stone_cost}", 3.2
            )
            return True
        return False

    def update_work_queue(self) -> None:
        """Execute queued work in order and keep multi-tile footprints clear."""
        while self.work_queue:
            tool, x, y = self.work_queue[0]
            if tool == "clear":
                valid = (x, y) in self.trees or (x, y) in self.rocks
            elif tool == "demolish":
                valid = (x, y) in self.roads or self.city_object_at(x, y) is not None
            elif tool == "road":
                valid = self.can_build_road_on(x, y)
            elif tool == "house":
                valid = (
                    self.can_build_on(x, y, allow_worker=True)
                    and self.has_planned_adjacent_road(x, y)
                )
            elif tool == "mine":
                valid = self.can_build_mine_on(x, y, allow_worker=True)
            elif tool in CITY_OBJECT_DEFS:
                valid = self.can_build_city_object(
                    tool, x, y, allow_worker=True, ignore_order=(tool, x, y)
                )
            elif tool == "dig":
                valid = self.can_dig_terrain(x, y)
            elif tool == "restore":
                valid = self.can_restore_terrain(x, y, allow_worker=True)
            elif tool in ("restore_tree", "restore_rock"):
                valid = (
                    self.terrain[x][y].terrain == "grass"
                    and (x, y) not in self.trees and (x, y) not in self.rocks
                    and (x, y) not in self.roads and (x, y) not in self.houses
                    and (x, y) not in self.mines and not self.is_city_object_occupied(x, y)
                    and self.money >= self.order_costs(tool, x, y)[0]
                )
            else:
                valid = False

            if valid:
                break
            self.work_queue.pop(0)
            if tool == "road" and (x, y) not in self.roads:
                self.road_directions.pop((x, y), None)
            self.work_path_active = False
            self.notify("사용할 수 없게 된 작업 예약을 건너뛰었어요.", 2.2)

        if (not self.work_queue or self.worker_path
                or self.worker_action_timer > 0
                or self.worker_pending_action is not None):
            return

        tool, x, y = self.work_queue[0]
        target = (x, y)
        if tool in ("clear", "dig", "restore_tree", "restore_rock"):
            path = self.find_worker_path_to_work_target(target)
        else:
            footprint = (
                self.footprint_for(tool, x, y)
                if tool in CITY_OBJECT_DEFS or tool in ("house", "mine")
                else (
                    self.footprint_for(self.city_object_at(x, y)[1], *self.city_object_at(x, y)[0])
                    if tool == "demolish" and self.city_object_at(x, y) is not None
                    else {target}
                )
            )
            path = self.find_worker_path_to_action_target(target, footprint)

        if path is None:
            self.work_queue.pop(0)
            if tool == "road" and (x, y) not in self.roads:
                self.road_directions.pop((x, y), None)
            self.work_path_active = False
            self.notify("작업 위치까지 이동할 수 없어 예약을 건너뛰었어요.", 2.8)
            return
        if path:
            self.worker_path = path
            self.worker_move_progress = 0.0
            self.worker_moved = True
            self.work_path_active = True
            nx, ny = path[0]
            self.worker_facing = (nx - self.worker_x, ny - self.worker_y)
            return

        self.work_path_active = False
        if tool == "clear":
            action = "chop" if (x, y) in self.trees else "mine"
        elif tool in ("demolish", "dig"):
            action = "mine"
        else:
            action = "build"
        self.worker_pending_action = (tool, x, y)
        self.start_worker_action(action, x, y)

    def complete_pending_work_action(self) -> None:
        """Apply the queued result exactly at the animation's impact frame."""
        pending = self.worker_pending_action
        if pending is None:
            return
        if not self.work_queue or self.work_queue[0] != pending:
            self.worker_pending_action = None
            return

        tool, x, y = pending
        self.worker_pending_action = None
        self.work_queue.pop(0)
        self.work_path_active = False
        if tool == "clear":
            self.remove_resource_at(x, y, start_animation=False)
        elif tool == "demolish":
            self.demolish_structure_at(x, y, start_animation=False)
        elif tool == "dig":
            self.dig_terrain_at(x, y)
        elif tool == "restore":
            self.restore_terrain_at(x, y)
        elif tool == "restore_tree":
            if (self.terrain[x][y].terrain == "grass"
                    and (self.sandbox_mode or self.money >= RESTORE_TREE_MONEY_COST)):
                self.trees.add((x, y))
                if not self.sandbox_mode:
                    self.money -= RESTORE_TREE_MONEY_COST
                self.notify(f"나무를 복원했어요 · -₩{RESTORE_TREE_MONEY_COST:,}")
        elif tool == "restore_rock":
            if (self.terrain[x][y].terrain == "grass"
                    and (self.sandbox_mode or self.money >= RESTORE_ROCK_MONEY_COST)):
                self.rocks.add((x, y))
                if not self.sandbox_mode:
                    self.money -= RESTORE_ROCK_MONEY_COST
                self.notify(f"바위를 복원했어요 · -₩{RESTORE_ROCK_MONEY_COST:,}")
        else:
            built = self.perform_build_order(tool, x, y, start_animation=False)
            if not built and tool == "road":
                self.road_directions.pop((x, y), None)

    def has_adjacent_road(self, x: int, y: int) -> bool:
        return any((x + dx, y + dy) in self.roads
                   for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)])

    def act_on_tile(self, x: int, y: int) -> None:
        """Compatibility entry point: all non-movement tools queue actions."""
        action_tool = self.active_action_tool()
        if action_tool in ("clear", "demolish", "road", "house", "dig", "mine", "restore", "restore_tree", "restore_rock"):
            self.toggle_work_order(action_tool, x, y)

    def check_tutorial(self) -> None:
        if self.tutorial_done:
            return
        if self.tutorial_step == 1 and self.tutorial_removed >= 2:
            self.tutorial_step = 2
            self.tool = "road"
            self.notify("도로 3칸을 배치하세요. 도로는 목재 1개, 집은 목재와 석재가 필요해요.", 4)
        elif self.tutorial_step == 2 and self.tutorial_roads >= 3:
            self.tutorial_step = 3
            self.tool = "house"
            self.notify("도로가 준비됐어요. 집에는 목재 1개와 석재 1개가 필요해요.", 4)
        elif self.tutorial_step == 3 and self.tutorial_house_built:
            self.tutorial_step = 4
            self.tutorial_done = True
            self.tool = "move"
            self.notify("튜토리얼 완료! 이제 자유롭게 도시를 만들어 보세요.", 6)

    def expand_land(self) -> None:
        costs = [5000, 15000, 35000, 75000]
        if self.expand_level >= len(costs):
            self.notify("지도 전체를 개척했어요. 더 이상 확장할 땅이 없어요.", 2.8)
            return
        cost = costs[self.expand_level]
        if not self.sandbox_mode and self.money - self.reserved_build_cost() < cost:
            self.notify(f"예약된 건설 비용을 제외하면 확장 자금이 부족해요. 필요 자금: ₩{cost:,}")
            return
        self.money -= cost
        self.expand_level += 1
        radius = [10, 14, 18, 22][self.expand_level - 1]
        self.notify(
            f"도시 영역 확장 완료 · 반경 {radius}타일 · -₩{cost:,}", 3
        )

    def save_slot_path(self, slot: int, autosave: bool = False) -> Optional[Path]:
        if IS_WEB:
            return None
        return SAVE_DIR / ("city_autosave.json" if autosave else f"city_slot_{slot}.json")

    def save_slot_key(self, slot: int = 1, autosave: bool = False) -> str:
        return WEB_SAVE_KEY + ("-autosave" if autosave else f"-slot-{slot}")

    def read_save_text(self, slot: int = 1, autosave: bool = False) -> str:
        if IS_WEB:
            try:
                from platform import window
                saved_text = window.localStorage.getItem(self.save_slot_key(slot, autosave))
                if saved_text is None and slot == 1 and not autosave:
                    saved_text = window.localStorage.getItem(WEB_SAVE_KEY)
            except Exception as storage_error:
                raise OSError("브라우저 저장 공간에 접근할 수 없어요.") from storage_error
            if saved_text is None:
                raise FileNotFoundError
            return str(saved_text)

        path = self.save_slot_path(slot, autosave)
        if path is None:
            raise FileNotFoundError
        if not path.exists() and slot == 1 and not autosave and SAVE_FILE.exists():
            path = SAVE_FILE
        return path.read_text(encoding="utf-8")

    def save_slot_info(self, slot: int, autosave: bool = False) -> Tuple[bool, str]:
        try:
            data = json.loads(self.read_save_text(slot, autosave))
            if not isinstance(data, dict) or type(data.get("seed")) is not int:
                return True, "손상된 저장 데이터"
            return True, f"DAY {data.get('day', '?')} · {data.get('saved_at', '이전 버전 저장')}"
        except FileNotFoundError:
            return False, "빈 저장 데이터"
        except (OSError, ValueError, TypeError):
            return True, "읽을 수 없는 저장 파일"

    def open_save_dialog(self, mode: str) -> None:
        if mode not in ("save", "load"):
            return
        self.save_dialog_mode = mode
        self.save_dialog_selected = 1
        self.save_dialog_confirm = False

    def handle_save_dialog_click(self, pos: Tuple[int, int]) -> None:
        x, y = pos
        mode = self.save_dialog_mode
        if mode is None:
            return
        if self.save_dialog_confirm:
            if 190 <= x <= 315 and 286 <= y <= 316:
                self.save_game(self.save_dialog_selected)
                self.save_dialog_mode = None
                self.save_dialog_confirm = False
                return
            if 325 <= x <= 450 and 286 <= y <= 316:
                self.save_dialog_confirm = False
                return
            return
        for slot, top in enumerate((72, 108, 144), start=1):
            if 160 <= x <= 480 and top <= y <= top + 30:
                exists, _description = self.save_slot_info(slot)
                self.save_dialog_selected = slot
                if mode == "load":
                    if exists:
                        self.load_game(slot)
                        self.save_dialog_mode = None
                    else:
                        self.notify(f"슬롯 {slot}은 비어 있어요.", 2)
                elif exists:
                    self.save_dialog_confirm = True
                else:
                    self.save_game(slot)
                    self.save_dialog_mode = None
                return
        if mode == "load" and 160 <= x <= 480 and 180 <= y <= 210:
            self.load_game(autosave=True)
            self.save_dialog_mode = None
            return
        if 160 <= x <= 315 and 220 <= y <= 250:
            self.export_save_json(self.save_dialog_selected)
            return
        if 325 <= x <= 480 and 220 <= y <= 250:
            self.import_save_json(self.save_dialog_selected)
            return
        if 325 <= x <= 450 and 286 <= y <= 316:
            self.save_dialog_mode = None
            self.save_dialog_confirm = False

    def save_game(self, slot: int = 1, autosave: bool = False) -> None:
        if not autosave and (type(slot) is not int or not 1 <= slot <= 3):
            self.notify("저장 슬롯은 1~3 중에서 선택해 주세요.", 2.5)
            return
        data = {
            "version": 14,
            "sandbox_mode": self.sandbox_mode,
            "sound_enabled": self.sound_enabled,
            "window_scale": self.window_scale,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "seed": self.seed,
            "underground_mined": [list(p) for p in sorted(self.underground_mined)],
            "mine_sites": [[x, y, layer, progress] for (x, y), (layer, progress) in sorted(self.mines.items())],
            "map_rotation": self.map_rotation,
            "camera_follow_worker": self.camera_follow_worker,
            "underground_view": self.underground_view,
            "underground_layer": self.underground_layer,
            "trees": [list(p) for p in sorted(self.trees)],
            "rocks": [list(p) for p in sorted(self.rocks)],
            "roads": [list(p) for p in sorted(self.roads)],
            "road_direction": self.road_direction,
            "road_directions": [[x, y, axis] for (x, y), axis in sorted(self.road_directions.items())],
            "terrain_heights": [[self.terrain[x][y].height for y in range(MAP_H)] for x in range(MAP_W)],
            "houses": [list(p) for p in sorted(self.houses)],
            "house_levels": [[x, y, level] for (x, y), level in sorted(self.house_levels.items())],
            "city_objects": [[x, y, item.get("type"), item.get("level", 1)] for (x, y), item in sorted(self.city_objects.items())],
            "logging_progress": [[x, y, progress] for (x, y), progress in sorted(self.logging_progress.items())],
            "expand_level": self.expand_level,
            "money": self.money,
            "population": self.population,
            "wood": self.wood,
            "stone": self.stone,
            "day": self.day,
            "game_minutes": self.game_minutes,
            "worker": [self.worker_x, self.worker_y],
            "worker_facing": list(self.worker_facing),
            "work_orders": [{"tool": tool, "x": x, "y": y} for tool, x, y in self.work_queue],
            "tutorial_step": self.tutorial_step,
            "tutorial_done": self.tutorial_done,
            "tutorial_removed": self.tutorial_removed,
            "tutorial_roads": self.tutorial_roads,
            "tutorial_house_built": self.tutorial_house_built,
            "restore_mode": self.restore_mode,
        }
        temporary_file = None
        try:
            serialized = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
            if IS_WEB:
                try:
                    from platform import window
                    window.localStorage.setItem(self.save_slot_key(slot, autosave), serialized)
                    if not autosave and slot == 1:
                        window.localStorage.setItem(WEB_SAVE_KEY, serialized)
                except Exception as storage_error:
                    raise OSError("브라우저 저장 공간에 접근할 수 없어요.") from storage_error
            else:
                path = self.save_slot_path(slot, autosave)
                if path is None:
                    raise OSError("저장 위치를 확인할 수 없어요.")
                temporary_file = path.with_suffix(path.suffix + ".tmp")
                SAVE_DIR.mkdir(parents=True, exist_ok=True)
                temporary_file.write_text(serialized, encoding="utf-8")
                os.replace(temporary_file, path)
            if autosave:
                self.autosave_elapsed = 0.0
            else:
                self.notify(f"슬롯 {slot}에 도시를 저장했어요.", 3)
        except (OSError, TypeError, ValueError) as exc:
            if temporary_file is not None:
                try:
                    temporary_file.unlink(missing_ok=True)
                except OSError:
                    pass
            if not autosave:
                self.notify(f"저장 실패 · 기존 저장 데이터는 유지했어요: {exc}", 4)

    def load_game(
        self, slot: int = 1, autosave: bool = False,
        save_text_override: Optional[str] = None
    ) -> None:
        state_fields = (
            "seed", "rng", "terrain", "trees", "rocks", "roads",
            "road_directions", "road_direction", "selected_road_tile",
            "map_rotation", "camera_follow_worker", "underground_view",
            "underground_layer", "underground_mined", "houses", "house_levels",
            "city_objects", "logging_progress", "mines", "expand_level",
            "selected_building_type", "selected_structure_anchor",
            "build_palette_open", "build_palette_anchor", "build_palette_dragging",
            "build_palette_hover_index", "build_palette_pressed_index",
            "money", "population", "wood", "stone", "day", "game_minutes",
            "worker_x", "worker_y", "worker_facing", "worker_path",
            "worker_move_progress", "worker_moved", "worker_action",
            "worker_action_timer", "worker_action_elapsed",
            "worker_action_hit_played", "worker_pending_action", "work_queue",
            "work_path_active", "tool", "remove_mode", "restore_mode", "camera_x", "camera_y",
            "tutorial_step", "tutorial_done", "tutorial_removed",
            "tutorial_roads", "tutorial_house_built",
            "sandbox_mode", "sound_enabled", "window_scale",
        )
        previous_state = {
            name: copy.deepcopy(getattr(self, name)) for name in state_fields
        }
        self.last_load_success = False
        try:
            raw_save = (
                save_text_override if save_text_override is not None
                else self.read_save_text(slot, autosave)
            )
            data = json.loads(raw_save)
            if not isinstance(data, dict):
                raise ValueError("저장 파일의 최상위 데이터가 올바르지 않아요.")
            saved_version = data.get("version", 1)
            if type(saved_version) is not int or saved_version > 14:
                raise ValueError("이 저장 파일은 현재 게임 버전보다 새 버전에서 만들어졌어요.")
            saved_seed = data.get("seed")
            if type(saved_seed) is not int:
                raise ValueError("저장 파일의 지도 시드가 올바르지 않아요.")
            self.generate_world(saved_seed)
            saved_rotation = data.get("map_rotation", 0)
            self.map_rotation = saved_rotation % 4 if type(saved_rotation) is int else 0
            self.camera_follow_worker = bool(data.get("camera_follow_worker", False))
            self.underground_view = bool(data.get("underground_view", False))
            saved_layer = data.get("underground_layer", 1)
            self.underground_layer = int(clamp(saved_layer, 1, 3)) if type(saved_layer) is int else 1
            self.underground_mined = set()
            saved_mined = data.get("underground_mined", [])
            if isinstance(saved_mined, list):
                for entry in saved_mined:
                    if (isinstance(entry, list) and len(entry) == 3
                            and all(type(value) is int for value in entry)
                            and 1 <= entry[0] <= 3
                            and 0 <= entry[1] < MAP_W and 0 <= entry[2] < MAP_H):
                        self.underground_mined.add(tuple(entry))
            saved_heights = data.get("terrain_heights")
            if isinstance(saved_heights, list) and len(saved_heights) == MAP_W:
                for x, column in enumerate(saved_heights):
                    if not isinstance(column, list) or len(column) != MAP_H:
                        continue
                    for y, raw_height in enumerate(column):
                        if type(raw_height) is int:
                            height = int(clamp(raw_height, 0, 4))
                            self.terrain[x][y].height = height
                            if height > 0 and self.terrain[x][y].terrain != "water":
                                self.terrain[x][y].terrain = "mountain"
                            elif height == 0 and self.terrain[x][y].terrain == "mountain":
                                self.terrain[x][y].terrain = "grass"
            self.trees = {
                pos for pos in valid_tile_set(data.get("trees", []))
                if self.terrain[pos[0]][pos[1]].terrain != "water"
            }
            self.rocks = {
                pos for pos in valid_tile_set(data.get("rocks", []))
                if self.terrain[pos[0]][pos[1]].terrain != "water"
            }
            self.roads = {
                pos for pos in valid_tile_set(data.get("roads", []))
                if pos not in self.trees and pos not in self.rocks
            }
            self.road_direction = data.get("road_direction", "x")
            if self.road_direction not in ("x", "y"):
                self.road_direction = "x"
            self.road_directions = {}
            saved_road_directions = data.get("road_directions", [])
            if isinstance(saved_road_directions, list):
                for entry in saved_road_directions:
                    if (isinstance(entry, list) and len(entry) == 3
                            and type(entry[0]) is int and type(entry[1]) is int
                            and 0 <= entry[0] < MAP_W and 0 <= entry[1] < MAP_H
                            and (entry[0], entry[1]) in self.roads
                            and entry[2] in ("x", "y")):
                        self.road_directions[(entry[0], entry[1])] = entry[2]
            self.houses = {
                pos for pos in valid_tile_set(data.get("houses", []))
                if self.is_unlocked(*pos)
                and self.terrain[pos[0]][pos[1]].terrain in ("grass", "mountain")
                and pos not in self.trees and pos not in self.rocks
                and pos not in self.roads
            }
            self.house_levels = {}
            saved_house_levels = data.get("house_levels", [])
            if isinstance(saved_house_levels, list):
                for entry in saved_house_levels:
                    if (isinstance(entry, list) and len(entry) == 3
                            and type(entry[0]) is int and type(entry[1]) is int
                            and type(entry[2]) is int and 0 <= entry[2] <= 3
                            and (entry[0], entry[1]) in self.houses):
                        self.house_levels[(entry[0], entry[1])] = max(1, entry[2])
            self.city_objects = {}
            self.mines = {}
            saved_mines = data.get("mine_sites", [])
            if isinstance(saved_mines, list):
                for entry in saved_mines:
                    if not (
                        isinstance(entry, list) and len(entry) == 4
                        and type(entry[0]) is int and type(entry[1]) is int
                        and type(entry[2]) is int
                        and isinstance(entry[3], (int, float)) and not isinstance(entry[3], bool)
                        and 0 <= entry[0] < MAP_W and 0 <= entry[1] < MAP_H
                        and 1 <= entry[2] <= 4 and 0 <= entry[3] < MINE_LAYER_DURATION_MINUTES
                    ):
                        continue
                    pos = (entry[0], entry[1])
                    if (self.is_unlocked(*pos) and self.terrain[pos[0]][pos[1]].terrain in ("grass", "mountain")
                            and pos not in self.roads and pos not in self.houses
                            and pos not in self.trees and pos not in self.rocks):
                        self.mines[pos] = (entry[2], float(entry[3]))
            self.expand_level = safe_saved_int(data.get("expand_level", 0), 0, 0, 4)
            saved_city_objects = data.get("city_objects", [])
            if isinstance(saved_city_objects, list):
                for entry in saved_city_objects:
                    if (not isinstance(entry, list) or len(entry) != 4
                            or type(entry[0]) is not int or type(entry[1]) is not int
                            or entry[2] not in CITY_OBJECT_DEFS or type(entry[3]) is not int):
                        continue
                    x, y, kind, level = entry
                    if self.can_build_city_object(
                        kind, x, y, require_forest=False, require_road=False
                    ):
                        self.city_objects[(x, y)] = {
                            "type": kind, "level": int(clamp(level, 1, 3))
                        }
            self.logging_progress = {}
            saved_logging_progress = data.get("logging_progress", [])
            if isinstance(saved_logging_progress, list):
                for entry in saved_logging_progress:
                    if (isinstance(entry, list) and len(entry) == 3
                            and type(entry[0]) is int and type(entry[1]) is int
                            and isinstance(entry[2], (int, float)) and not isinstance(entry[2], bool)
                            and (entry[0], entry[1]) in self.city_objects
                            and self.city_objects[(entry[0], entry[1])].get("type") == "logging"
                            and 0 <= entry[2] <= LUMBER_CAMP_DURATION_MINUTES):
                        self.logging_progress[(entry[0], entry[1])] = float(entry[2])
            for anchor, object_data in self.city_objects.items():
                if object_data.get("type") == "logging":
                    self.logging_progress.setdefault(anchor, 0.0)
            self.money = safe_saved_int(data.get("money", 100000), 100000, -1000000000, 1000000000)
            self.population = safe_saved_int(data.get("population", 0), 0, 0, 1000000)
            self.wood = safe_saved_int(data.get("wood", 0), 0, 0, 1000000000)
            self.stone = safe_saved_int(data.get("stone", 0), 0, 0, 1000000000)
            self.day = safe_saved_int(data.get("day", 1), 1, 1, 1000000000)
            self.game_minutes = safe_saved_int(data.get("game_minutes", 480), 480, 0, 1439)
            worker_pos = data.get("worker", [MAP_W // 2, MAP_H // 2])
            if (isinstance(worker_pos, list) and len(worker_pos) == 2
                    and all(type(v) is int for v in worker_pos)
                    and self.worker_can_stand(worker_pos[0], worker_pos[1])):
                self.worker_x, self.worker_y = worker_pos
            facing = data.get("worker_facing", [1, 0])
            if (isinstance(facing, list) and len(facing) == 2
                    and tuple(facing) in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                self.worker_facing = tuple(facing)

            # Migrate old clear-only queues and load the new typed work orders.
            self.work_queue = []
            self.work_path_active = False
            saved_orders = data.get("work_orders")
            if not isinstance(saved_orders, list):
                legacy_queue = data.get("removal_queue", data.get("work_queue", []))
                saved_orders = [
                    {"tool": "clear", "x": pos[0], "y": pos[1]}
                    for pos in legacy_queue
                    if isinstance(pos, list) and len(pos) == 2
                ]
            if isinstance(saved_orders, list):
                for order in saved_orders[:MAX_WORK_QUEUE]:
                    if not isinstance(order, dict):
                        continue
                    tool = order.get("tool")
                    x, y = order.get("x"), order.get("y")
                    if (tool == "clear" and type(x) is int and type(y) is int
                            and ((x, y) in self.roads or (x, y) in self.houses or (x, y) in self.mines)):
                        tool = "demolish"
                    if (tool not in ("clear", "demolish", "road", "house", "dig", "mine", "restore", "restore_tree", "restore_rock", *CITY_OBJECT_DEFS.keys())
                            or type(x) is not int or type(y) is not int
                            or not (0 <= x < MAP_W and 0 <= y < MAP_H)
                            or not self.is_unlocked(x, y)):
                        continue
                    if any(ox == x and oy == y for _tool, ox, oy in self.work_queue):
                        continue
                    if tool == "clear" and (x, y) not in self.trees and (x, y) not in self.rocks:
                        continue
                    if tool == "demolish" and (x, y) not in self.roads and self.city_object_at(x, y) is None:
                        continue
                    if tool == "dig" and not self.can_dig_terrain(x, y):
                        continue
                    if tool.startswith("vein") and not self.can_mine_underground_vein(x, y, int(tool[4:])):
                        continue
                    if tool == "road" and not self.can_build_road_on(x, y):
                        continue
                    if tool == "house" and not self.can_build_on(x, y, allow_worker=True):
                        continue
                    if tool == "house" and not self.has_planned_adjacent_road(x, y):
                        continue
                    if tool == "mine" and not self.can_build_mine_on(x, y, allow_worker=True):
                        continue
                    if tool in CITY_OBJECT_DEFS and not self.can_build_city_object(
                            tool, x, y, allow_worker=True):
                        continue
                    if tool == "restore" and not self.can_restore_terrain(x, y, allow_worker=True):
                        continue
                    if tool in ("restore_tree", "restore_rock") and (
                        self.terrain[x][y].terrain != "grass"
                        or (x, y) in self.trees or (x, y) in self.rocks
                        or (x, y) in self.roads or (x, y) in self.houses
                        or (x, y) in self.mines or self.is_city_object_occupied(x, y)
                    ):
                        continue
                    self.work_queue.append((tool, x, y))
                    if tool == "road":
                        self.road_directions.setdefault((x, y), self.infer_road_axis(x, y))

            self.tutorial_step = safe_saved_int(data.get("tutorial_step", 0), 0, 0, 20)
            self.tutorial_done = bool(data.get("tutorial_done", False))
            self.tutorial_removed = safe_saved_int(data.get("tutorial_removed", 0), 0, 0, 1000000)
            self.tutorial_roads = safe_saved_int(data.get("tutorial_roads", 0), 0, 0, 1000000)
            self.tutorial_house_built = bool(data.get("tutorial_house_built", False))
            self.sandbox_mode = bool(data.get("sandbox_mode", False))
            self.sound_enabled = bool(data.get("sound_enabled", True))
            saved_scale = data.get("window_scale", self.window_scale)
            self.window_scale = saved_scale if saved_scale in (1, 2, 3) else 2
            self.window = pygame.display.set_mode(
                (LOGICAL_W * self.window_scale, LOGICAL_H * self.window_scale)
            )
            saved_restore_mode = data.get("restore_mode", "terrain")
            self.restore_mode = saved_restore_mode if saved_restore_mode in ("terrain", "tree", "rock") else "terrain"
            self.center_camera()
            if self.camera_follow_worker:
                self.center_camera_on_worker()
            self.last_load_success = True
            self.notify(
                f"{'자동 저장' if autosave else f'슬롯 {slot}'} 도시를 불러왔어요.",
                3,
            )
        except FileNotFoundError:
            self.notify(
                "자동 저장 데이터가 없어요." if autosave
                else f"슬롯 {slot}에는 저장 데이터가 없어요.",
                3,
            )
        except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
            for name, value in previous_state.items():
                setattr(self, name, value)
            self.notify(
                f"불러오기 실패 · 현재 도시는 유지했어요. 저장 파일이 손상됐거나 "
                f"버전이 다를 수 있어요. 다른 슬롯/자동 저장을 확인하세요. ({exc})",
                5,
            )

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def diamond(self, cx: float, cy: float, tw: float, th: float) -> List[Tuple[int, int]]:
        return [(round(cx), round(cy - th / 2)),
                (round(cx + tw / 2), round(cy)),
                (round(cx), round(cy + th / 2)),
                (round(cx - tw / 2), round(cy))]

    def draw_tile(self, x: int, y: int) -> None:
        cx, cy = self.tile_to_screen(x, y)
        tw, th = TILE_W * self.zoom, TILE_H * self.zoom
        terrain = self.terrain[x][y].terrain
        if terrain == "water":
            color = C["water"]
        elif terrain == "mountain":
            height_colors = [
                (112, 165, 91), (125, 164, 99),
                (139, 158, 105), (153, 151, 109)
            ]
            color = height_colors[int(clamp(self.terrain[x][y].height, 1, 4)) - 1]
        else:
            variation = self.terrain[x][y].variation
            color = [C["grass_a"], C["grass_b"], C["grass_c"]][variation]
        pts = self.diamond(cx, cy, tw, th)
        pygame.draw.polygon(self.canvas, color, pts)
        pygame.draw.polygon(self.canvas, C["grass_edge"] if terrain != "water" else C["water_dark"], pts, 1)

        # A thin sand lip follows only the land tiles that actually touch water.
        if terrain == "grass":
            top = (round(cx), round(cy - th / 2))
            right = (round(cx + tw / 2), round(cy))
            bottom = (round(cx), round(cy + th / 2))
            left = (round(cx - tw / 2), round(cy))
            shoreline_sides = (
                (self.screen_neighbor(x, y, 1, 0), [right, bottom,
                              (round(cx + tw * 0.16), round(cy + th * 0.34)),
                              (round(cx + tw * 0.34), round(cy + th * 0.16))]),
                (self.screen_neighbor(x, y, -1, 0), [top, left,
                              (round(cx - tw * 0.34), round(cy - th * 0.16)),
                              (round(cx - tw * 0.16), round(cy - th * 0.34))]),
                (self.screen_neighbor(x, y, 0, 1), [left, bottom,
                              (round(cx - tw * 0.34), round(cy + th * 0.16)),
                              (round(cx - tw * 0.16), round(cy + th * 0.34))]),
                (self.screen_neighbor(x, y, 0, -1), [top, right,
                              (round(cx + tw * 0.34), round(cy - th * 0.16)),
                              (round(cx + tw * 0.16), round(cy - th * 0.34))]),
            )
            for (nx, ny), shore_points in shoreline_sides:
                if (0 <= nx < MAP_W and 0 <= ny < MAP_H
                        and self.terrain[nx][ny].terrain == "water"):
                    pygame.draw.polygon(self.canvas, (190, 177, 126), shore_points)
                    pygame.draw.lines(self.canvas, (151, 155, 111), True,
                                      shore_points[:2], max(1, round(self.zoom)))

        # Tiny low-contrast pixel flecks make open ground feel less flat.
        if terrain == "grass" and self.zoom >= 0.82:
            if (x * 7 + y * 11) % 19 == 0:
                pygame.draw.rect(self.canvas, (133, 183, 101),
                                 (round(cx - 2 * self.zoom), round(cy - 1 * self.zoom),
                                  max(1, round(2 * self.zoom)), max(1, round(1 * self.zoom))))
        elif terrain == "water":
            if (x + y) % 4 == 0:
                pygame.draw.line(self.canvas, C["water_light"],
                                 (round(cx - 4 * self.zoom), round(cy)),
                                 (round(cx + 3 * self.zoom), round(cy)), max(1, round(self.zoom)))
        elif terrain == "mountain":
            # Contour marks identify the top of a stepped elevation terrace.
            offset = max(2, round(3 * self.zoom))
            pygame.draw.line(
                self.canvas, (173, 187, 126),
                (round(cx - 5 * self.zoom), round(cy - offset)),
                (round(cx + 2 * self.zoom), round(cy - offset)),
                max(1, round(self.zoom))
            )
            pygame.draw.line(
                self.canvas, (91, 119, 73),
                (round(cx - 2 * self.zoom), round(cy + offset)),
                (round(cx + 5 * self.zoom), round(cy + offset)),
                max(1, round(self.zoom))
            )

    def draw_underground_tile(self, x: int, y: int) -> None:
        """Render the selected geological stratum as a survey view."""
        cx, cy = self.tile_to_screen(x, y)
        tw, th = TILE_W * self.zoom, TILE_H * self.zoom
        layer = max(1, min(3, self.underground_layer))
        palettes = {
            1: ((132, 103, 73), (116, 88, 63), (96, 74, 57)),
            2: ((105, 111, 105), (86, 94, 94), (69, 78, 83)),
            3: ((75, 87, 98), (62, 73, 86), (49, 60, 75)),
        }
        band_colors = palettes[layer]
        points = self.diamond(cx, cy, tw, th)
        pygame.draw.polygon(self.canvas, band_colors[0], points)
        for index, color in enumerate(band_colors[1:], start=1):
            fraction = index / 3.0
            offset_y = (fraction - 0.5) * th
            line_half = tw * 0.5 * (1.0 - abs(fraction - 0.5) * 2.0)
            pygame.draw.line(
                self.canvas, color,
                (round(cx - line_half), round(cy + offset_y)),
                (round(cx + line_half), round(cy + offset_y)),
                max(1, round(2.0 * self.zoom))
            )

        # Geological marks are decorative survey contours, not mineable deposits.
        mark = (self.seed * 31 + x * 73 + y * 47 + layer * 109) % 17
        if mark in (0, 1, 2):
            offset = (mark - 1) * 2 * self.zoom
            pygame.draw.line(
                self.canvas, band_colors[2],
                (round(cx - 5 * self.zoom), round(cy + offset)),
                (round(cx + 5 * self.zoom), round(cy + offset)),
                max(1, round(self.zoom))
            )
        pygame.draw.polygon(self.canvas, (48, 56, 61), points, 1)

    def draw_elevation_cliff_faces(
        self, x: int, y: int, worker_gx: float, worker_gy: float
    ) -> None:
        """Draw only this tile's exposed cliff faces before foreground tiles."""
        height = self.terrain[x][y].height
        if height <= 0:
            return

        layer = self.cliff_layer
        tw, th = TILE_W * self.zoom, TILE_H * self.zoom
        cx, cy = self.tile_to_screen(x, y)
        if (cx < -100 or cx > LOGICAL_W + 100
                or cy < TOP_H - 130 or cy > BOTTOM_Y + 100):
            return

        right = (round(cx + tw / 2), round(cy))
        bottom = (round(cx), round(cy + th / 2))
        left = (round(cx - tw / 2), round(cy))

        for nx, ny, edge_a, edge_b, base_color in (
            (*self.screen_neighbor(x, y, 1, 0), right, bottom, (77, 87, 78)),
            (*self.screen_neighbor(x, y, 0, 1), left, bottom, (61, 72, 69)),
        ):
            if (not (0 <= nx < MAP_W and 0 <= ny < MAP_H)
                    or not self.is_unlocked(nx, ny)):
                continue

            # Water is a shoreline, not a solid lower ground tile. Do not
            # cover it with an opaque soil wall.
            if self.terrain[nx][ny].terrain == "water":
                continue

            drop = height - self.terrain[nx][ny].height
            if drop <= 0:
                continue

            wall_drop = round(drop * ELEVATION_STEP * self.zoom)
            tile_rx, tile_ry = self.rotate_grid_position(x, y)
            neighbor_rx, neighbor_ry = self.rotate_grid_position(nx, ny)
            worker_rx, worker_ry = self.rotate_grid_float(worker_gx, worker_gy)
            near_worker = (
                abs(neighbor_rx - worker_rx) + abs(neighbor_ry - worker_ry) <= 4
                and (tile_rx + tile_ry) > (worker_rx + worker_ry)
            )
            alpha = 125 if near_worker else 255
            color = (*base_color, alpha)
            lower_a = (edge_a[0], edge_a[1] + wall_drop)
            lower_b = (edge_b[0], edge_b[1] + wall_drop)

            bounds = pygame.Rect(
                min(edge_a[0], edge_b[0], lower_a[0], lower_b[0]),
                min(edge_a[1], edge_b[1], lower_a[1], lower_b[1]),
                max(edge_a[0], edge_b[0], lower_a[0], lower_b[0])
                - min(edge_a[0], edge_b[0], lower_a[0], lower_b[0]) + 1,
                max(edge_a[1], edge_b[1], lower_a[1], lower_b[1])
                - min(edge_a[1], edge_b[1], lower_a[1], lower_b[1]) + 1,
            ).clip(VIEW_RECT)
            if bounds.width <= 0 or bounds.height <= 0:
                continue

            # Clear this small buffer region, draw one face, and composite it
            # immediately. A later foreground tile can then cover the part
            # that belongs to its own top surface.
            layer.fill((0, 0, 0, 0), bounds)
            layer.set_clip(bounds)
            pygame.draw.polygon(
                layer, color, [edge_a, edge_b, lower_b, lower_a]
            )
            pygame.draw.line(
                layer, (38, 48, 45, alpha), lower_a, lower_b,
                max(1, round(self.zoom))
            )
            layer.set_clip(None)
            self.canvas.blit(layer, bounds.topleft, bounds)

    def draw_tree(self, x: int, y: int) -> None:
        cx, cy = self.tile_to_screen(x, y)
        z = self.zoom
        # Trunk
        pygame.draw.rect(self.canvas, C["trunk"],
                         (round(cx - 2 * z), round(cy - 12 * z), max(2, round(4 * z)), max(4, round(9 * z))))
        # Layered square foliage, intentionally crisp rather than smoothed.
        blocks = [(-8, -22, 16, 10, C["tree_dark"]),
                  (-6, -29, 12, 10, C["tree_mid"]),
                  (-3, -34, 6, 7, C["tree_light"]),
                  (-11, -19, 5, 5, C["tree_mid"]),
                  (6, -20, 5, 5, C["tree_dark"])]
        for bx, by, bw, bh, color in blocks:
            pygame.draw.rect(self.canvas, color,
                             (round(cx + bx * z), round(cy + by * z),
                              max(1, round(bw * z)), max(1, round(bh * z))))
        pygame.draw.rect(self.canvas, (112, 189, 88),
                         (round(cx - 2 * z), round(cy - 29 * z), max(1, round(4 * z)), max(1, round(3 * z))))

    def draw_rock(self, x: int, y: int) -> None:
        cx, cy = self.tile_to_screen(x, y)
        z = self.zoom
        pts = [(round(cx - 6*z), round(cy - 2*z)), (round(cx - 3*z), round(cy - 9*z)),
               (round(cx + 4*z), round(cy - 10*z)), (round(cx + 7*z), round(cy - 3*z)),
               (round(cx + 3*z), round(cy + 1*z)), (round(cx - 4*z), round(cy + 1*z))]
        pygame.draw.polygon(self.canvas, C["rock"], pts)
        pygame.draw.line(self.canvas, (177, 181, 167), pts[1], pts[2], max(1, round(z)))

    def draw_road(self, x: int, y: int) -> None:
        """Draw an inset road surface that expands to meet neighboring road tiles."""
        cx, cy = self.tile_to_screen(x, y)
        z = self.zoom
        tw, th = TILE_W * z, TILE_H * z

        # A road tile is an inset diamond on the grass. When another road is
        # present across one side, that side's inset is removed so both tiles
        # meet exactly at their shared edge.
        side_specs = (
            ("east", self.screen_neighbor(x, y, 1, 0), 1.0, 1.0, tw * 0.25, th * 0.25),
            ("west", self.screen_neighbor(x, y, -1, 0), -1.0, -1.0, -tw * 0.25, -th * 0.25),
            ("south", self.screen_neighbor(x, y, 0, 1), -1.0, 1.0, -tw * 0.25, th * 0.25),
            ("north", self.screen_neighbor(x, y, 0, -1), 1.0, -1.0, tw * 0.25, -th * 0.25),
        )
        connected = {
            name: (neighbor in self.roads and self.is_unlocked(*neighbor))
            for name, neighbor, _a, _b, _dx, _dy in side_specs
        }

        def road_polygon(limits: Dict[str, float]) -> List[Tuple[int, int]]:
            # Clip the tile diamond in normalized isometric coordinates.
            # Each side is described by A*u + B*v <= limit.
            polygon: List[Tuple[float, float]] = [
                (0.0, -1.0), (1.0, 0.0), (0.0, 1.0), (-1.0, 0.0)
            ]
            planes = (
                ("east", 1.0, 1.0),
                ("west", -1.0, -1.0),
                ("south", -1.0, 1.0),
                ("north", 1.0, -1.0),
            )
            for side, a_coeff, b_coeff in planes:
                limit = limits[side]
                if not polygon:
                    break
                clipped: List[Tuple[float, float]] = []
                previous = polygon[-1]
                previous_value = a_coeff * previous[0] + b_coeff * previous[1] - limit
                previous_inside = previous_value <= 1e-9

                for current in polygon:
                    current_value = a_coeff * current[0] + b_coeff * current[1] - limit
                    current_inside = current_value <= 1e-9
                    if previous_inside != current_inside:
                        denominator = previous_value - current_value
                        t = previous_value / denominator if abs(denominator) > 1e-12 else 0.0
                        clipped.append((
                            previous[0] + (current[0] - previous[0]) * t,
                            previous[1] + (current[1] - previous[1]) * t,
                        ))
                    if current_inside:
                        clipped.append(current)
                    previous = current
                    previous_value = current_value
                    previous_inside = current_inside
                polygon = clipped

            return [
                (round(cx + u * tw * 0.5), round(cy + v * th * 0.5))
                for u, v in polygon
            ]

        # Unconnected sides retain a narrow strip of grass. Connected sides
        # reach the tile edge; the inner fill uses the same edge to avoid seams.
        outer_limits = {
            side: (1.0 if connected[side] else 0.80)
            for side in connected
        }
        inner_limits = {
            side: (outer_limits[side] if connected[side] else outer_limits[side] - 0.035)
            for side in connected
        }

        outer = road_polygon(outer_limits)
        inner = road_polygon(inner_limits)
        is_bridge = self.terrain[x][y].terrain == "water"
        outer_color = (77, 54, 39) if is_bridge else C["road_edge"]
        inner_color = (137, 99, 59) if is_bridge else C["road"]
        if len(outer) >= 3:
            pygame.draw.polygon(self.canvas, outer_color, outer)
        if len(inner) >= 3:
            pygame.draw.polygon(self.canvas, inner_color, inner)

        # The stored axis always determines this tile's main lane. Connected
        # neighbors add sharp branches but cannot override the rotated direction.
        center = (round(cx), round(cy))
        dash_length = max(2.0, 4.0 * z)
        dash_gap = max(1.5, 2.8 * z)
        line_width = max(1, round(1.4 * z))
        road_axis = self.road_directions.get((x, y), "x")
        if self.map_rotation % 2:
            road_axis = "y" if road_axis == "x" else "x"
        vectors = {
            name: (dx, dy)
            for name, _neighbor, _a, _b, dx, dy in side_specs
        }
        axis_sides = ("east", "west") if road_axis == "x" else ("south", "north")

        if self.terrain[x][y].terrain == "water":
            # A road placed on water is rendered as a timber bridge deck.
            plank_color = (96, 65, 43)
            plank_light = (177, 133, 80)
            ax, ay = vectors[axis_sides[0]]
            axis_length = max(1.0, math.hypot(ax, ay))
            ax, ay = ax / axis_length, ay / axis_length
            across_sides = ("south", "north") if road_axis == "x" else ("east", "west")
            bx, by = vectors[across_sides[0]]
            across_length = max(1.0, math.hypot(bx, by))
            bx, by = bx / across_length, by / across_length
            for offset in (-0.34, -0.17, 0.0, 0.17, 0.34):
                px = cx + ax * offset * axis_length * 2.0
                py = cy + ay * offset * axis_length * 2.0
                p1 = (round(px - bx * across_length * 0.66),
                      round(py - by * across_length * 0.66))
                p2 = (round(px + bx * across_length * 0.66),
                      round(py + by * across_length * 0.66))
                pygame.draw.line(self.canvas, plank_color, p1, p2,
                                 max(1, round(1.8 * z)))
                pygame.draw.line(self.canvas, plank_light,
                                 (p1[0], p1[1] - max(1, round(z))),
                                 (p2[0], p2[1] - max(1, round(z))), 1)
        else:
            def draw_dashed_lane(start_point, end_point):
                dx = end_point[0] - start_point[0]
                dy = end_point[1] - start_point[1]
                length = math.hypot(dx, dy)
                if length <= 0:
                    return
                ux, uy = dx / length, dy / length
                offset = 0.0
                while offset < length:
                    end_offset = min(length, offset + dash_length)
                    p1 = (round(start_point[0] + ux * offset),
                          round(start_point[1] + uy * offset))
                    p2 = (round(start_point[0] + ux * end_offset),
                          round(start_point[1] + uy * end_offset))
                    pygame.draw.line(self.canvas, C["road_center"], p1, p2, line_width)
                    offset += dash_length + dash_gap

            # The full main axis is drawn even when both ends are connected.
            main_a = vectors[axis_sides[0]]
            main_b = vectors[axis_sides[1]]
            draw_dashed_lane(
                (cx + main_a[0], cy + main_a[1]),
                (cx + main_b[0], cy + main_b[1])
            )
            for name, neighbor, _a, _b, dx, dy in side_specs:
                if connected[name] and neighbor in self.roads and name not in axis_sides:
                    draw_dashed_lane(center, (cx + dx, cy + dy))

        # The selected installed tile shows its stored orientation. Rotating
        # it changes this marker while the road network keeps its square joins.
        if self.selected_road_tile == (x, y):
            stored_axis = self.road_directions.get((x, y), "x")
            if self.map_rotation % 2:
                stored_axis = "y" if stored_axis == "x" else "x"
            axis_mark = "↘" if stored_axis == "x" else "↙"
            self.text(self.canvas, axis_mark, center[0], center[1], 8, C["white"], center=True)
            selected_outline = self.diamond(cx, cy, tw, th)
            pygame.draw.polygon(
                self.canvas, C["gold"], selected_outline,
                max(1, round(2 * z))
            )

    def draw_house(self, x: int, y: int, level: int = 1) -> None:
        """Draw the authored house sprite for the selected upgrade level."""
        cx, cy = self.tile_to_screen(x, y)
        z = self.zoom
        level = int(clamp(level, 1, 3))
        sprite = self.house_sprites.get(level)
        if sprite is not None:
            cache_key = (level, self.zoom_index)
            scaled = self.house_sprite_cache.get(cache_key)
            if scaled is None:
                size = (
                    max(1, round(sprite.get_width() * z)),
                    max(1, round(sprite.get_height() * z)),
                )
                # pygame.transform.scale keeps the pixel-art edges crisp.
                scaled = pygame.transform.scale(sprite, size)
                self.house_sprite_cache[cache_key] = scaled

            # The sprite's bottom-center sits on the bottom point of its 1x1
            # isometric footprint (33x17 tile guide, 33x30 house canvas).
            draw_x = round(cx - scaled.get_width() / 2)
            draw_y = round(cy + (TILE_H * z / 2) - scaled.get_height())
            self.canvas.blit(scaled, (draw_x, draw_y))
            return

        # Fallback for source checkouts that do not yet contain house PNGs.
        self._draw_house_procedural(x, y, level)

    def _draw_house_procedural(self, x: int, y: int, level: int = 1) -> None:
        """Fallback procedural house used when a sprite asset is unavailable."""
        cx, cy = self.tile_to_screen(x, y)
        z = self.zoom
        level = int(clamp(level, 1, 3))
        base_y = cy - z
        wall_height = (10 + (level - 1) * 7) * z

        foundation = self.diamond(cx, base_y + 7*z, 18*z, 8*z)
        pygame.draw.polygon(self.canvas, (91, 91, 76), foundation)
        pygame.draw.polygon(self.canvas, (55, 64, 56), foundation, max(1, round(z)))

        left_top = (round(cx - 8*z), round(base_y - wall_height*0.42))
        back_top = (round(cx), round(base_y - wall_height*0.82))
        right_top = (round(cx + 8*z), round(base_y - wall_height*0.42))
        front_top = (round(cx), round(base_y))
        left_bottom = (round(cx - 8*z), round(base_y + 5*z))
        front_bottom = (round(cx), round(base_y + 10*z))
        right_bottom = (round(cx + 8*z), round(base_y + 5*z))
        pygame.draw.polygon(
            self.canvas, (206, 172, 119),
            [left_top, front_top, front_bottom, left_bottom]
        )
        pygame.draw.polygon(
            self.canvas, (157, 119, 82),
            [front_top, right_top, right_bottom, front_bottom]
        )
        pygame.draw.line(self.canvas, (239, 207, 151), left_top, front_top, max(1, round(z)))

        roof_base = base_y - wall_height*0.82
        roof_peak = (round(cx), round(roof_base - 15*z))
        roof_left = (round(cx - 11*z), round(roof_base - 2*z))
        roof_front = (round(cx), round(roof_base + 5*z))
        roof_right = (round(cx + 11*z), round(roof_base - 2*z))
        pygame.draw.polygon(self.canvas, (151, 54, 47), [roof_peak, roof_left, roof_front])
        pygame.draw.polygon(self.canvas, (105, 39, 42), [roof_peak, roof_front, roof_right])
        pygame.draw.line(self.canvas, (224, 111, 70), roof_peak, roof_left, max(1, round(z)))
        pygame.draw.line(self.canvas, (185, 78, 57), roof_left, roof_front, max(1, round(z)))
        pygame.draw.line(self.canvas, (76, 39, 39), roof_peak, roof_right, max(1, round(z)))

        chimney_x = round(cx - 6*z)
        chimney_y = round(roof_base - 11*z)
        pygame.draw.rect(
            self.canvas, (105, 67, 56),
            (chimney_x, chimney_y, max(3, round(4*z)), max(10, round(12*z)))
        )
        pygame.draw.rect(
            self.canvas, (166, 91, 70),
            (chimney_x - max(1, round(z)), chimney_y,
             max(4, round(6*z)), max(2, round(2*z)))
        )

        door_w, door_h = max(3, round(4*z)), max(6, round(7*z))
        pygame.draw.rect(
            self.canvas, (77, 48, 37),
            (round(cx + z), round(base_y + z), door_w, door_h)
        )
        pygame.draw.rect(
            self.canvas, (230, 184, 91),
            (round(cx + z), round(base_y + z), max(1, round(z)), max(2, round(2*z)))
        )
        window_w, window_h = max(3, round(4*z)), max(4, round(5*z))
        for wx, wy in ((cx - 7*z, base_y - 4*z), (cx + 4*z, base_y - 3*z)):
            rect = pygame.Rect(round(wx), round(wy), window_w, window_h)
            pygame.draw.rect(self.canvas, (47, 91, 111), rect)
            pygame.draw.rect(self.canvas, (136, 202, 204), rect, max(1, round(z)))
            pygame.draw.line(
                self.canvas, (190, 225, 207),
                (rect.centerx, rect.y + 1), (rect.centerx, rect.bottom - 1), 1
            )
        pygame.draw.polygon(
            self.canvas, (126, 94, 63),
            [(round(cx - 3*z), round(base_y + 10*z)),
             (round(cx + 4*z), round(base_y + 10*z)),
             (round(cx + 3*z), round(base_y + 12*z)),
             (round(cx - 2*z), round(base_y + 12*z))]
        )

        if level >= 2:
            upper_y = round(base_y - 10*z)
            for wx in (cx - 6*z, cx + 2*z):
                rect = pygame.Rect(round(wx), upper_y, window_w, window_h)
                pygame.draw.rect(self.canvas, (48, 92, 116), rect)
                pygame.draw.rect(self.canvas, (171, 213, 208), rect, max(1, round(z)))
            pygame.draw.line(
                self.canvas, (110, 76, 54),
                (round(cx - 8*z), round(base_y - z)),
                (round(cx - z), round(base_y - z)), max(1, round(z))
            )
        if level >= 3:
            roof_trim_y = round(roof_base - 2*z)
            pygame.draw.line(
                self.canvas, (239, 197, 127),
                (round(cx - 8*z), roof_trim_y),
                (round(cx + 8*z), roof_trim_y), max(1, round(z))
            )
            pygame.draw.rect(
                self.canvas, (77, 111, 130),
                (round(cx - 2*z), round(roof_base - 8*z),
                 max(4, round(5*z)), max(4, round(5*z)))
            )

    def draw_city_object(self, x: int, y: int, kind: str, level: int = 1) -> None:
        """Draw recognizable pixel-art city structures with distinct rooflines."""
        spec = CITY_OBJECT_DEFS[kind]
        width, height = int(spec["w"]), int(spec["h"])
        z = self.zoom
        tw, th = TILE_W*z, TILE_H*z
        footprint = self.footprint_for(kind, x, y)
        centers = [self.tile_to_screen(tx, ty) for tx, ty in footprint]
        cx = sum(point[0] for point in centers) / len(centers)
        ground_y = sum(point[1] for point in centers) / len(centers)
        half_w = (width + height) * tw / 4
        half_h = (width + height) * th / 4
        ground = [
            (round(cx), round(ground_y-half_h)),
            (round(cx+half_w), round(ground_y)),
            (round(cx), round(ground_y+half_h)),
            (round(cx-half_w), round(ground_y)),
        ]
        line = max(1, round(z))
        thick = max(2, round(2*z))

        if kind == "park":
            pygame.draw.polygon(self.canvas, (69, 137, 75), ground)
            pygame.draw.polygon(self.canvas, (39, 89, 56), ground, line)
            pygame.draw.line(
                self.canvas, (197, 177, 132),
                (round(cx-half_w*0.58), round(ground_y)),
                (round(cx+half_w*0.58), round(ground_y)), thick
            )
            pygame.draw.line(
                self.canvas, (218, 195, 146),
                (round(cx), round(ground_y-half_h*0.52)),
                (round(cx), round(ground_y+half_h*0.48)), line
            )
            pond = pygame.Rect(
                round(cx+half_w*0.12), round(ground_y-half_h*0.42),
                max(7, round(half_w*0.36)), max(4, round(half_h*0.38))
            )
            pygame.draw.ellipse(self.canvas, (207, 194, 133), pond.inflate(line*2, line*2))
            pygame.draw.ellipse(self.canvas, (54, 139, 166), pond)
            pygame.draw.line(
                self.canvas, (130, 208, 214),
                (pond.x+line, pond.y+line), (pond.right-line, pond.y+line), line
            )
            for tx, ty in (
                (cx-half_w*0.34, ground_y-half_h*0.20),
                (cx+half_w*0.30, ground_y+half_h*0.17),
            ):
                pygame.draw.rect(
                    self.canvas, (101, 68, 43),
                    (round(tx-z), round(ty-z), max(2, round(3*z)), max(5, round(6*z)))
                )
                pygame.draw.rect(
                    self.canvas, (39, 101, 58),
                    (round(tx-5*z), round(ty-10*z), max(8, round(10*z)), max(7, round(8*z)))
                )
                pygame.draw.rect(
                    self.canvas, (84, 157, 73),
                    (round(tx-3*z), round(ty-14*z), max(5, round(7*z)), max(6, round(6*z)))
                )
                pygame.draw.rect(
                    self.canvas, (147, 190, 91),
                    (round(tx-z), round(ty-13*z), max(2, round(2*z)), max(2, round(2*z)))
                )
            pygame.draw.rect(
                self.canvas, (113, 76, 48),
                (round(cx-half_w*0.34), round(ground_y+half_h*0.22),
                 max(7, round(9*z)), max(2, round(2*z)))
            )
            pygame.draw.circle(
                self.canvas, (238, 205, 105),
                (round(cx-half_w*0.08), round(ground_y-half_h*0.20)), max(1, round(2*z))
            )
            pygame.draw.circle(
                self.canvas, (213, 125, 122),
                (round(cx-half_w*0.02), round(ground_y-half_h*0.12)), max(1, round(2*z))
            )
            return

        if kind == "lamp":
            pygame.draw.polygon(self.canvas, (90, 96, 86), ground)
            pygame.draw.polygon(self.canvas, (49, 61, 57), ground, line)
            base = (round(cx), round(ground_y-z))
            pole_top = (round(cx-z), round(ground_y-29*z))
            arm_end = (round(cx+7*z), round(ground_y-29*z))
            pygame.draw.line(self.canvas, (49, 57, 57), base, pole_top, thick)
            pygame.draw.line(self.canvas, (49, 57, 57), pole_top, arm_end, thick)
            pygame.draw.line(
                self.canvas, (143, 151, 133),
                (pole_top[0]+1, pole_top[1]), arm_end, line
            )
            glow = pygame.Rect(
                round(cx+3*z), round(ground_y-31*z),
                max(7, round(8*z)), max(5, round(6*z))
            )
            pygame.draw.rect(self.canvas, (244, 202, 91), glow.inflate(line*2, line*2))
            pygame.draw.rect(self.canvas, (255, 239, 167), glow)
            pygame.draw.rect(self.canvas, (255, 255, 216), glow, line)
            return

        if kind == "power":
            pygame.draw.polygon(self.canvas, (101, 111, 105), ground)
            pygame.draw.polygon(self.canvas, (48, 61, 61), ground, line)
            block = pygame.Rect(round(cx-half_w*0.43), round(ground_y-half_h*0.68), max(16, round(half_w*0.86)), max(14, round(half_h*0.70)))
            pygame.draw.rect(self.canvas, (82, 91, 91), block)
            pygame.draw.rect(self.canvas, (160, 165, 148), block, line)
            chimney = pygame.Rect(round(cx+half_w*0.18), round(ground_y-half_h*1.35), max(6,round(8*z)), max(22,round(25*z)))
            pygame.draw.rect(self.canvas, (78, 84, 82), chimney)
            pygame.draw.rect(self.canvas, (194, 105, 74), (chimney.x, chimney.y+round(8*z), chimney.width, max(3,round(4*z))))
            for offset in (-0.20, 0.12):
                pygame.draw.rect(self.canvas, (232, 198, 102), (round(cx+half_w*offset), round(ground_y-half_h*0.45), max(4,round(5*z)), max(5,round(7*z))))
            return

        if kind == "water":
            pygame.draw.polygon(self.canvas, (91, 135, 156), ground)
            pygame.draw.polygon(self.canvas, (44, 76, 93), ground, line)
            tower = pygame.Rect(round(cx-half_w*0.22), round(ground_y-half_h*1.25), max(12,round(half_w*0.44)), max(18,round(half_h*1.2)))
            pygame.draw.rect(self.canvas, (91, 148, 171), tower)
            pygame.draw.rect(self.canvas, (37, 83, 107), tower, line)
            cap = pygame.Rect(tower.x-line, tower.y-line, tower.width+line*2, max(5,round(7*z)))
            pygame.draw.rect(self.canvas, (177, 201, 194), cap)
            pygame.draw.rect(self.canvas, (52, 99, 118), cap, line)
            pygame.draw.line(self.canvas, (211, 226, 204), (tower.x+line, tower.centery), (tower.right-line, tower.centery), line)
            pygame.draw.rect(self.canvas, (217, 229, 205), (round(cx-2*z), tower.bottom, max(3,round(4*z)), max(6,round(8*z))))
            return

        if kind == "decor_tree":
            pygame.draw.polygon(self.canvas, (88, 133, 70), ground)
            pygame.draw.polygon(self.canvas, (48, 91, 56), ground, line)
            pygame.draw.rect(
                self.canvas, (104, 71, 45),
                (round(cx-2*z), round(ground_y-18*z), max(3, round(4*z)), max(16, round(17*z)))
            )
            pygame.draw.rect(
                self.canvas, (64, 48, 39),
                (round(cx-3*z), round(ground_y-3*z), max(5, round(6*z)), max(2, round(3*z)))
            )
            for ox, oy, w, h, color in (
                (-8,-28,16,10,(35,99,57)), (-6,-35,13,11,(65,137,68)),
                (-3,-41,8,9,(104,169,76)), (-11,-24,6,6,(54,119,62)),
                (6,-25,6,6,(45,108,59)),
            ):
                pygame.draw.rect(
                    self.canvas, color,
                    (round(cx+ox*z), round(ground_y+oy*z),
                     max(2, round(w*z)), max(2, round(h*z)))
                )
            pygame.draw.rect(
                self.canvas, (154, 197, 91),
                (round(cx-2*z), round(ground_y-34*z), max(2, round(3*z)), max(2, round(3*z)))
            )
            return

        level = int(clamp(level, 1, 3))
        height_px = (25 + (level-1)*7)*z + (3*z if kind == "industrial" else 0)
        top = [
            (ground[0][0], round(ground[0][1]-height_px)),
            (ground[1][0], round(ground[1][1]-height_px)),
            (ground[2][0], round(ground[2][1]-height_px)),
            (ground[3][0], round(ground[3][1]-height_px)),
        ]
        front_left = [ground[3], ground[2], top[2], top[3]]
        front_right = [ground[2], ground[1], top[1], top[2]]
        palettes = {
            "commercial": ((221,190,130),(153,112,75),(72,151,179)),
            "industrial": ((150,158,147),(91,101,99),(111,174,184)),
            "public": ((216,207,174),(144,148,132),(87,152,173)),
            "logging": ((178,139,87),(120,84,53),(183,142,82)),
        }
        top_color, side_color, window_color = palettes[kind]
        dark_side = tuple(max(0,c-24) for c in side_color)
        pygame.draw.polygon(self.canvas, dark_side, front_right)
        pygame.draw.polygon(self.canvas, side_color, front_left)
        pygame.draw.polygon(self.canvas, top_color, top)
        pygame.draw.polygon(self.canvas, (55,62,56), top, line)
        pygame.draw.line(
            self.canvas, tuple(min(255,c+35) for c in side_color),
            top[3], top[2], line
        )

        facade_y = round(ground_y-height_px*0.57)
        window_w, window_h = max(3, round(4*z)), max(4, round(6*z))
        window_count = max(2, width+1)
        for index in range(window_count):
            wx = round(cx-half_w*0.34 + index*(half_w*0.68/max(1,window_count-1)))
            rect = pygame.Rect(wx, facade_y, window_w, window_h)
            pygame.draw.rect(self.canvas, (39,66,75), rect.inflate(line,line))
            pygame.draw.rect(self.canvas, window_color, rect)
            pygame.draw.line(
                self.canvas, (188,220,207),
                (rect.x+line, rect.y+line), (rect.x+line, rect.bottom-line), 1
            )

        if kind == "commercial":
            sign = pygame.Rect(
                round(cx-half_w*0.34), round(ground_y-height_px*0.91),
                max(12,round(half_w*0.68)), max(4,round(5*z))
            )
            pygame.draw.rect(self.canvas, (61,77,77), sign.inflate(line,line))
            pygame.draw.rect(self.canvas, (232,194,107), sign)
            pygame.draw.rect(
                self.canvas, (179,77,68),
                (sign.x+line, sign.y+line, max(3,sign.width//3), max(2,sign.height-line*2))
            )
            awning = pygame.Rect(
                round(cx-half_w*0.36), round(ground_y-height_px*0.30),
                max(10,round(half_w*0.72)), max(3,round(4*z))
            )
            pygame.draw.rect(self.canvas, (172,68,62), awning)
            stripe_w=max(2,awning.width//6)
            for stripe in range(0,awning.width,stripe_w*2):
                pygame.draw.rect(
                    self.canvas,(238,214,157),
                    (awning.x+stripe,awning.y,min(stripe_w,awning.right-(awning.x+stripe)),awning.height)
                )
            pygame.draw.rect(
                self.canvas,(47,80,91),
                (round(cx-3*z),round(ground_y-height_px*0.23),
                 max(6,round(7*z)),max(8,round(9*z)))
            )
            pygame.draw.rect(
                self.canvas,(88,63,45),
                (round(cx-4*z),round(ground_y-height_px*0.23),
                 max(8,round(9*z)),max(2,round(2*z)))
            )

        elif kind == "industrial":
            for index in range(3):
                vx=round(cx-half_w*0.30+index*half_w*0.23)
                vy=round(ground_y-height_px-4*z)
                pygame.draw.rect(
                    self.canvas,(102,115,110),
                    (vx,vy,max(5,round(7*z)),max(3,round(4*z)))
                )
                pygame.draw.line(self.canvas,(207,190,143),(vx,vy),(vx+max(5,round(7*z)),vy),line)
            chimney_x=round(cx+half_w*0.23)
            chimney_y=round(ground_y-height_px-21*z)
            pygame.draw.rect(
                self.canvas,(82,88,82),
                (chimney_x,chimney_y,max(5,round(6*z)),max(22,round(24*z)))
            )
            pygame.draw.rect(
                self.canvas,(182,91,66),
                (chimney_x,chimney_y+round(8*z),max(5,round(6*z)),max(3,round(4*z)))
            )
            pygame.draw.rect(
                self.canvas,(57,63,60),
                (round(cx-half_w*0.10),round(ground_y-height_px*0.28),
                 max(9,round(15*z)),max(8,round(11*z)))
            )
            for stripe in range(1,4):
                sx=round(cx-half_w*0.10+stripe*3*z)
                pygame.draw.line(
                    self.canvas,(147,159,151),
                    (sx,round(ground_y-height_px*0.28)),
                    (sx,round(ground_y-height_px*0.28+10*z)),line
                )
            pygame.draw.line(
                self.canvas,(218,176,103),
                (round(cx-half_w*0.42),round(ground_y-height_px*0.10)),
                (round(cx+half_w*0.34),round(ground_y-height_px*0.10)),thick
            )

        elif kind == "public":
            pediment = [
                (round(cx-half_w*0.28),round(ground_y-height_px-2*z)),
                (round(cx),round(ground_y-height_px-13*z)),
                (round(cx+half_w*0.28),round(ground_y-height_px-2*z)),
            ]
            pygame.draw.polygon(self.canvas,(235,220,174),pediment)
            pygame.draw.polygon(self.canvas,(122,131,119),pediment,line)
            col_y=round(ground_y-height_px*0.43)
            for offset in (-0.24,-0.08,0.08,0.24):
                px=round(cx+half_w*offset)
                pygame.draw.rect(
                    self.canvas,(232,221,181),
                    (px,col_y,max(2,round(3*z)),max(8,round(12*z)))
                )
                pygame.draw.rect(
                    self.canvas,(117,124,111),
                    (px-line,col_y,max(3,round(4*z)),line)
                )
            pygame.draw.rect(
                self.canvas,(139,79,60),
                (round(cx-4*z),round(ground_y-height_px*0.28),
                 max(7,round(8*z)),max(10,round(12*z)))
            )
            pygame.draw.rect(
                self.canvas,(210,188,113),
                (round(cx-3*z),round(ground_y-height_px*0.28),
                 max(2,round(2*z)),max(4,round(5*z)))
            )
            pygame.draw.circle(
                self.canvas,(211,181,110),
                (round(cx),round(ground_y-height_px-5*z)),max(2,round(3*z))
            )
            pygame.draw.line(
                self.canvas,(76,76,67),
                (round(cx),round(ground_y-height_px-2*z)),
                (round(cx),round(ground_y-height_px-7*z)),line
            )
            for step in range(3):
                sy=round(ground_y+(step+1)*2*z)
                pygame.draw.line(
                    self.canvas,(214,203,169),
                    (round(cx-(5+step*2)*z),sy),
                    (round(cx+(5+step*2)*z),sy),line
                )

        elif kind == "logging":
            roof_ridge = [
                (round(cx-half_w*0.35),round(ground_y-height_px*0.84)),
                (round(cx),round(ground_y-height_px-8*z)),
                (round(cx+half_w*0.35),round(ground_y-height_px*0.84)),
            ]
            pygame.draw.polygon(self.canvas,(119,73,45),roof_ridge)
            pygame.draw.line(self.canvas,(218,166,94),roof_ridge[0],roof_ridge[1],thick)
            pygame.draw.line(self.canvas,(158,104,60),roof_ridge[1],roof_ridge[2],thick)
            shed=pygame.Rect(
                round(cx-half_w*0.20),round(ground_y-height_px*0.50),
                max(9,round(half_w*0.38)),max(7,round(11*z))
            )
            pygame.draw.rect(self.canvas,(92,62,43),shed)
            pygame.draw.rect(self.canvas,(196,150,86),shed,line)
            for row in range(2):
                log_y=round(ground_y-height_px*0.20+row*3*z)
                for col in range(3):
                    log_x=round(cx+half_w*0.10+col*3*z)
                    log_rect=pygame.Rect(log_x,log_y,max(5,round(6*z)),max(2,round(2*z)))
                    pygame.draw.rect(self.canvas,(113,72,42),log_rect)
                    pygame.draw.circle(
                        self.canvas,(225,184,112),
                        (log_rect.right-1,log_rect.centery),max(1,round(z))
                    )
            saw_center=(round(cx-half_w*0.27),round(ground_y-height_px*0.25))
            pygame.draw.circle(self.canvas,(81,94,93),saw_center,max(3,round(4*z)))
            pygame.draw.circle(self.canvas,(205,205,173),saw_center,max(2,round(3*z)),line)
            pygame.draw.circle(self.canvas,(77,83,77),saw_center,max(1,round(z)))

            progress=self.logging_progress.get((x,y),0.0)
            bar=pygame.Rect(
                round(cx-10*z),round(ground_y-height_px-16*z),
                max(10,round(20*z)),max(3,round(4*z))
            )
            pygame.draw.rect(self.canvas,(37,43,42),bar)
            fill_w=round(bar.width*clamp(progress/LUMBER_CAMP_DURATION_MINUTES,0.0,1.0))
            if fill_w:
                pygame.draw.rect(self.canvas,(124,187,106),(bar.x,bar.y,fill_w,bar.height))
            pygame.draw.rect(self.canvas,(224,219,188),bar,line)

    def draw_mine(self, x: int, y: int) -> None:
        """Draw a small mine derrick with a layer/progress indicator."""
        cx, cy = self.tile_to_screen(x, y)
        z = self.zoom
        layer, progress = self.mines.get((x, y), (4, 0.0))
        base_y = cy - 2 * z

        # Stone foundation.
        foundation = self.diamond(cx, base_y + 5 * z, 17 * z, 8 * z)
        pygame.draw.polygon(self.canvas, (76, 78, 73), foundation)
        pygame.draw.polygon(self.canvas, (42, 54, 55), foundation, max(1, round(z)))

        # Timber/steel headframe and cross braces.
        left_foot = (round(cx - 6 * z), round(base_y + 3 * z))
        right_foot = (round(cx + 6 * z), round(base_y + 3 * z))
        left_top = (round(cx - 3 * z), round(base_y - 20 * z))
        right_top = (round(cx + 3 * z), round(base_y - 20 * z))
        crown = (round(cx), round(base_y - 24 * z))
        beam = (105, 91, 69)
        beam_light = (174, 145, 96)
        pygame.draw.line(self.canvas, beam, left_foot, left_top, max(2, round(3 * z)))
        pygame.draw.line(self.canvas, beam, right_foot, right_top, max(2, round(3 * z)))
        pygame.draw.line(self.canvas, beam_light, left_top, crown, max(2, round(2 * z)))
        pygame.draw.line(self.canvas, beam_light, crown, right_top, max(2, round(2 * z)))
        pygame.draw.line(self.canvas, (70, 65, 55), left_top, right_foot, max(1, round(z)))
        pygame.draw.line(self.canvas, (70, 65, 55), right_top, left_foot, max(1, round(z)))
        pygame.draw.line(
            self.canvas, (45, 51, 53),
            (round(cx), round(base_y - 22 * z)),
            (round(cx), round(base_y + 3 * z)), max(1, round(z))
        )
        pygame.draw.circle(
            self.canvas, (205, 183, 126), crown,
            max(2, round(3 * z))
        )
        # Pulley housing and hanging ore bucket make the headframe readable.
        pulley = pygame.Rect(
            round(cx - 3*z), round(base_y - 25*z),
            max(6, round(7*z)), max(4, round(5*z))
        )
        pygame.draw.rect(self.canvas, (62, 67, 64), pulley)
        pygame.draw.rect(self.canvas, (210, 184, 126), pulley, max(1, round(z)))
        pygame.draw.circle(
            self.canvas, (220, 196, 137),
            (pulley.centerx, pulley.centery), max(2, round(2*z))
        )
        bucket_x = round(cx + 1*z)
        pygame.draw.line(
            self.canvas, (48, 53, 52),
            (bucket_x, round(base_y - 19*z)),
            (bucket_x, round(base_y - 1*z)), max(1, round(z))
        )
        pygame.draw.rect(
            self.canvas, (113, 88, 60),
            (bucket_x - max(2, round(2*z)), round(base_y - 4*z),
             max(5, round(6*z)), max(4, round(5*z)))
        )
        pygame.draw.rect(
            self.canvas, (194, 157, 98),
            (bucket_x - max(2, round(2*z)), round(base_y - 4*z),
             max(5, round(6*z)), max(1, round(z)))
        )

        # Dark shaft entrance and a tiny ore cart sit beside the derrick.
        entry = pygame.Rect(
            round(cx - 12*z), round(base_y - 2*z),
            max(6, round(7*z)), max(6, round(7*z))
        )
        pygame.draw.rect(self.canvas, (42, 44, 43), entry)
        pygame.draw.rect(
            self.canvas, (121, 91, 60),
            (entry.x, entry.y, entry.width, max(2, round(2*z)))
        )
        cart = pygame.Rect(
            round(cx + 7*z), round(base_y + 1*z),
            max(7, round(9*z)), max(4, round(5*z))
        )
        pygame.draw.rect(self.canvas, (73, 81, 78), cart)
        cart_top = [
            (cart.x, cart.y),
            (cart.x + max(2, round(2*z)), cart.y - max(2, round(2*z))),
            (cart.right, cart.y - max(2, round(2*z))),
            (cart.right, cart.y),
        ]
        pygame.draw.polygon(self.canvas, (120, 126, 115), cart_top)
        for wheel_x in (cart.x + max(1, round(2*z)), cart.right - max(2, round(2*z))):
            pygame.draw.circle(
                self.canvas, (44, 48, 46),
                (wheel_x, cart.bottom), max(1, round(2*z))
            )
        for ore_x, ore_y in (
            (cart.x + round(2*z), cart.y - round(2*z)),
            (cart.x + round(5*z), cart.y - round(3*z)),
        ):
            pygame.draw.rect(
                self.canvas, (139, 143, 133),
                (ore_x, ore_y, max(2, round(3*z)), max(2, round(3*z)))
            )

        # Progress bar: each completed bar moves the site to the next stratum.
        bar = pygame.Rect(
            round(cx - 9 * z), round(base_y - 31 * z),
            max(8, round(18 * z)), max(2, round(3 * z))
        )
        pygame.draw.rect(self.canvas, (35, 43, 49), bar)
        if layer <= 3:
            fill_w = round(bar.width * clamp(progress / MINE_LAYER_DURATION_MINUTES, 0.0, 1.0))
            if fill_w:
                pygame.draw.rect(self.canvas, (125, 190, 121), (bar.x, bar.y, fill_w, bar.height))
        pygame.draw.rect(self.canvas, (224, 219, 188), bar, 1)
        layer_label = "완료" if layer > 3 else f"{layer}층"
        self.text(self.canvas, layer_label, round(cx), round(base_y - 36 * z),
                  max(7, round(8 * z)), (247, 231, 185), center=True)

    def worker_screen_position(self) -> Tuple[float, float]:
        """Return the worker's interpolated screen position, including map rotation."""
        current = self.tile_to_screen(self.worker_x, self.worker_y)
        if not self.worker_path:
            return current
        next_point = self.tile_to_screen(*self.worker_path[0])
        progress = clamp(self.worker_move_progress, 0.0, 1.0)
        return (
            current[0] + (next_point[0] - current[0]) * progress,
            current[1] + (next_point[1] - current[1]) * progress,
        )

    def draw_worker(self) -> None:
        """Draw the worker with four facing directions and timed work frames."""
        cx, cy = self.worker_screen_position()
        z = self.zoom * WORKER_SIZE
        moving = bool(self.worker_path)
        phase = time.time() * 14.0
        walk_swing = math.sin(phase)
        stride = walk_swing * 2.0 * z if moving else 0.0
        bob = abs(walk_swing) * 1.15 * z if moving else 0.0

        facing_x, facing_y = self.worker_facing
        rotation = self.map_rotation % 4
        if rotation == 1:
            facing_x, facing_y = -facing_y, facing_x
        elif rotation == 2:
            facing_x, facing_y = -facing_x, -facing_y
        elif rotation == 3:
            facing_x, facing_y = facing_y, -facing_x
        screen_direction = facing_x - facing_y
        screen_side = 1 if screen_direction >= 0 else -1
        facing_front = (facing_x + facing_y) > 0
        # The four grid directions become front-left/front-right/back-left/back-right
        # in the isometric view.
        body_offset = screen_side * 0.45 * z
        body_y = cy - 12.0 * z + bob
        foot_y = round(cy + 1.0 * z + bob)

        pygame.draw.ellipse(
            self.canvas, (44, 57, 48),
            (round(cx - 5*z), round(cy - 1*z), max(3, round(10*z)), max(2, round(4*z)))
        )

        # Walking legs alternate; their screen-side order follows the facing.
        near_stride = stride * screen_side
        pygame.draw.rect(
            self.canvas, (54, 49, 48),
            (round(cx - 2.5*z - near_stride), foot_y - round(4*z),
             max(2, round(3*z)), max(3, round(4*z)))
        )
        pygame.draw.rect(
            self.canvas, (69, 59, 53),
            (round(cx + 0.5*z + near_stride), foot_y - round(4*z),
             max(2, round(3*z)), max(3, round(4*z)))
        )

        # Side-facing views are narrower; the torso shifts toward the leading side.
        body_width = max(5, round((7.0 if abs(screen_direction) else 8.0) * z))
        body_rect = pygame.Rect(
            round(cx - body_width / 2 + body_offset),
            round(body_y),
            body_width,
            max(6, round(8*z))
        )
        pygame.draw.rect(self.canvas, (35, 75, 105), body_rect)
        pygame.draw.rect(
            self.canvas, (61, 111, 139),
            (body_rect.x, body_rect.y, body_rect.width, max(2, round(2*z)))
        )
        if not facing_front:
            # Back view: a dark collar/back seam replaces facial details.
            pygame.draw.rect(
                self.canvas, (29, 58, 76),
                (round(cx - 2*z + body_offset), round(body_y + 2*z),
                 max(3, round(4*z)), max(2, round(2*z)))
            )

        working = self.worker_action_timer > 0
        action_progress = clamp(
            self.worker_action_elapsed / WORK_ACTION_DURATION, 0.0, 1.0
        ) if working else 0.0

        # The non-working arm swings while walking. The working arm is drawn
        # separately below and replaces its resting counterpart.
        arm_swing = walk_swing * 1.4 * z if moving and not working else 0.0
        shoulder_y = body_y + 1.2*z
        left_arm_x = cx - 5.0*z + body_offset
        right_arm_x = cx + 3.0*z + body_offset
        active_arm_x = right_arm_x if screen_side > 0 else left_arm_x
        resting_arm_x = left_arm_x if screen_side > 0 else right_arm_x

        pygame.draw.rect(
            self.canvas, (213, 157, 111),
            (round(resting_arm_x), round(shoulder_y + arm_swing),
             max(2, round(3*z)), max(4, round(5*z)))
        )

        if not working:
            pygame.draw.rect(
                self.canvas, (213, 157, 111),
                (round(active_arm_x), round(shoulder_y - arm_swing),
                 max(2, round(3*z)), max(4, round(5*z)))
            )
        else:
            # Wind-up (0-0.36), impact stroke (0.36-0.60), recovery (0.60-1).
            if action_progress < 0.36:
                t = action_progress / 0.36
                hand_y_offset = -8.0 - 7.0 * t
                hand_x_offset = 4.0 + 1.5 * t
            elif action_progress < 0.60:
                t = (action_progress - 0.36) / 0.24
                hand_y_offset = -15.0 + 9.0 * t
                hand_x_offset = 5.5 - 1.5 * t
            else:
                t = (action_progress - 0.60) / 0.40
                hand_y_offset = -6.0 - 2.0 * t
                hand_x_offset = 4.0

            shoulder = (
                round(cx + screen_side * 2.7*z + body_offset),
                round(shoulder_y)
            )
            hand = (
                round(cx + screen_side * hand_x_offset*z + body_offset),
                round(cy + hand_y_offset*z + bob)
            )
            pygame.draw.line(
                self.canvas, (213, 157, 111), shoulder, hand,
                max(1, round(2.4*z))
            )

            tool_tip = (
                hand[0] + round(screen_side * 3.0*z),
                hand[1] - round((4.0 if action_progress < 0.48 else 1.5)*z)
            )
            pygame.draw.line(
                self.canvas, (112, 73, 42), hand, tool_tip,
                max(1, round(2*z))
            )
            if self.worker_action in ("chop", "mine"):
                head_rect = pygame.Rect(
                    tool_tip[0] - round(2*z),
                    tool_tip[1] - round(1.5*z),
                    max(3, round(5*z)),
                    max(2, round(3*z))
                )
                pygame.draw.rect(
                    self.canvas,
                    (185, 190, 184) if self.worker_action == "mine" else (132, 139, 145),
                    head_rect
                )
                if self.worker_action == "chop":
                    pygame.draw.rect(
                        self.canvas, (94, 105, 110),
                        (head_rect.x, head_rect.y, max(2, round(2*z)), head_rect.height)
                    )
            else:
                pygame.draw.rect(
                    self.canvas, (185, 190, 184),
                    (tool_tip[0] - round(2.5*z), tool_tip[1] - round(1*z),
                     max(4, round(6*z)), max(2, round(2*z)))
                )

            # A brief pixel spark marks the exact strike window.
            if 0.43 <= action_progress <= 0.62:
                spark_x, spark_y = tool_tip[0], tool_tip[1] + round(2*z)
                pygame.draw.line(
                    self.canvas, C["gold"],
                    (spark_x - round(3*z), spark_y),
                    (spark_x + round(3*z), spark_y),
                    max(1, round(z))
                )
                pygame.draw.line(
                    self.canvas, C["white"],
                    (spark_x, spark_y - round(3*z)),
                    (spark_x, spark_y + round(3*z)),
                    max(1, round(z))
                )

        # Helmet and head change details according to the four-way facing.
        head_x = cx + body_offset * 0.55
        head_rect = pygame.Rect(
            round(head_x - 3.0*z), round(cy - 18.0*z + bob),
            max(4, round(6*z)), max(5, round(6*z))
        )
        pygame.draw.rect(self.canvas, (229, 185, 143), head_rect)
        if facing_front:
            # Front-facing worker: eyes and a tiny nose appear on the leading side.
            eye_y = head_rect.y + max(2, round(3*z))
            pygame.draw.rect(
                self.canvas, (61, 52, 47),
                (head_rect.centerx - max(2, round(1.5*z)), eye_y, max(1, round(z)), max(1, round(z)))
            )
            pygame.draw.rect(
                self.canvas, (61, 52, 47),
                (head_rect.centerx + max(1, round(1.0*z)), eye_y, max(1, round(z)), max(1, round(z)))
            )
            pygame.draw.rect(
                self.canvas, (195, 121, 92),
                (round(head_x + screen_side*2.2*z), round(head_rect.centery),
                 max(1, round(z)), max(1, round(z)))
            )
        else:
            # Back-facing worker: no eyes; show the back rim of the safety helmet.
            pygame.draw.rect(
                self.canvas, (171, 119, 69),
                (round(head_x - 2*z), round(head_rect.bottom - 2*z),
                 max(4, round(4*z)), max(1, round(z)))
            )

        helmet_y = round(cy - 20.0*z + bob)
        pygame.draw.rect(
            self.canvas, (228, 174, 55),
            (round(head_x - 4*z), helmet_y, max(6, round(8*z)), max(2, round(3*z)))
        )
        pygame.draw.rect(
            self.canvas, (245, 205, 95),
            (round(head_x - 1*z), helmet_y, max(2, round(2*z)), max(1, round(2*z)))
        )

    def draw_resident_walkers(self) -> None:
        """Show tiny moving residents on built roads as a lightweight traffic simulation."""
        if self.underground_view or self.population <= 0 or not self.roads:
            return
        road_tiles = sorted(
            self.roads,
            key=lambda pos: (
                self.rotate_grid_position(*pos)[0] +
                self.rotate_grid_position(*pos)[1],
                self.rotate_grid_position(*pos)[0],
            )
        )
        count = min(12, max(1, self.population // 2), len(road_tiles))
        travel_phase = self.game_minutes * 0.035 + self.day * 0.71
        for index in range(count):
            phase = (travel_phase + index * 0.61803398875) % 1.0
            tile_index = int(phase * len(road_tiles))
            local_phase = (phase * len(road_tiles)) % 1.0
            x, y = road_tiles[tile_index]
            cx, cy = self.tile_to_screen(x, y)
            axis = self.road_directions.get((x, y), self.infer_road_axis(x, y))
            offset = (local_phase - 0.5) * TILE_W * self.zoom * 0.42
            if axis == "x":
                cx += offset
            else:
                cy += offset * 0.5
            px, py = round(cx), round(cy - 3 * self.zoom)
            scale = max(1, round(self.zoom))
            shirt = (235, 190, 105) if index % 2 == 0 else (116, 177, 199)
            pygame.draw.rect(
                self.canvas, (42, 48, 47),
                (px - scale, py - 2 * scale, 3 * scale, 5 * scale)
            )
            pygame.draw.rect(
                self.canvas, shirt,
                (px - scale, py, 3 * scale, 3 * scale)
            )
            pygame.draw.rect(
                self.canvas, (230, 190, 145),
                (px, py - 3 * scale, 2 * scale, 2 * scale)
            )

    def draw_time_of_day(self) -> None:
        """Tint the playfield at night and illuminate placed street lamps."""
        if self.underground_view:
            return
        hour = self.game_minutes / 60.0
        if 5.0 <= hour < 7.0:
            night = (7.0 - hour) / 2.0
        elif 17.0 <= hour < 20.0:
            night = (hour - 17.0) / 3.0
        elif hour >= 20.0 or hour < 5.0:
            night = 1.0
        else:
            night = 0.0
        if night <= 0.01:
            return
        shade = pygame.Surface((LOGICAL_W, LOGICAL_H), pygame.SRCALPHA)
        shade.fill((13, 22, 49, round(105 * night)))
        self.canvas.blit(shade, (0, 0))
        if night < 0.12:
            return
        glow_layer = pygame.Surface((LOGICAL_W, LOGICAL_H), pygame.SRCALPHA)
        for (x, y), data in self.city_objects.items():
            if data.get("type") != "lamp" or not self.is_unlocked(x, y):
                continue
            cx, cy = self.tile_to_screen(x, y)
            if not VIEW_RECT.collidepoint(round(cx), round(cy)):
                continue
            radius = max(5, round(25 * self.zoom))
            pygame.draw.circle(
                glow_layer, (255, 205, 103, round(36 * night)),
                (round(cx), round(cy - 15 * self.zoom)), radius
            )
            pygame.draw.circle(
                glow_layer, (255, 229, 159, round(24 * night)),
                (round(cx), round(cy - 15 * self.zoom)), max(3, radius // 2)
            )
        self.canvas.blit(glow_layer, (0, 0))

    def draw_world(self) -> None:
        self.canvas.fill(C["sky"])
        self.canvas.set_clip(VIEW_RECT)

        # Unclaimed land is a true void, not a dimmed continuation of the terrain.
        # The dark background makes the edge of the owned island easy to read.
        pygame.draw.rect(self.canvas, (28, 39, 55), VIEW_RECT)

        wall_color_a = (91, 63, 48)
        wall_color_b = (62, 47, 43)

        # Draw top faces and their cliff walls in ground-depth order. Each wall
        # is composited before the next foreground tile is drawn.
        worker_gx, worker_gy = self.worker_grid_position()
        for depth in range(MAP_W + MAP_H - 1):
            for rx in range(MAP_W):
                ry = depth - rx
                if not (0 <= ry < MAP_H):
                    continue
                x, y = self.unrotate_grid_position(rx, ry)
                if not self.is_unlocked(x, y):
                    continue

                cx, cy = self.tile_to_screen(x, y)
                if cx < -80 or cx > LOGICAL_W + 80 or cy < TOP_H - 100 or cy > BOTTOM_Y + 50:
                    continue

                if self.underground_view:
                    self.draw_underground_tile(x, y)
                    continue

                self.draw_tile(x, y)
                self.draw_elevation_cliff_faces(x, y, worker_gx, worker_gy)
                wall_depth = max(
                    4, round((8 + self.terrain[x][y].height * ELEVATION_STEP) * self.zoom)
                )
                tw, th = TILE_W * self.zoom, TILE_H * self.zoom
                right = (round(cx + tw / 2), round(cy))
                bottom = (round(cx), round(cy + th / 2))
                left = (round(cx - tw / 2), round(cy))

                # Screen-right and screen-down neighbors remain correct after rotation.
                right_neighbor = self.screen_neighbor(x, y, 1, 0)
                down_neighbor = self.screen_neighbor(x, y, 0, 1)
                if not self.is_unlocked(*right_neighbor):
                    pygame.draw.polygon(
                        self.canvas, wall_color_a,
                        [right, bottom,
                         (bottom[0], bottom[1] + wall_depth),
                         (right[0], right[1] + wall_depth)]
                    )
                    pygame.draw.line(
                        self.canvas, wall_color_b,
                        (bottom[0], bottom[1] + wall_depth),
                        (right[0], right[1] + wall_depth), 1
                    )

                if not self.is_unlocked(*down_neighbor):
                    pygame.draw.polygon(
                        self.canvas, wall_color_b,
                        [left, bottom,
                         (bottom[0], bottom[1] + wall_depth),
                         (left[0], left[1] + wall_depth)]
                    )
                    pygame.draw.line(
                        self.canvas, wall_color_a,
                        (left[0], left[1] + wall_depth),
                        (bottom[0], bottom[1] + wall_depth), 1
                    )

        if not self.underground_view:
            # Roads sit above the terrain tops; each tile's center markings use
            # its real orthogonal neighbor mask.
            for x, y in self.roads:
                if self.is_unlocked(x, y):
                    cx, cy = self.tile_to_screen(x, y)
                    if -80 <= cx <= LOGICAL_W + 80 and TOP_H - 40 <= cy <= BOTTOM_Y + 40:
                        self.draw_road(x, y)
            self.draw_resident_walkers()
            self.draw_worker_path_preview()

            depth_items: List[Tuple[float, float, int, int, int, str]] = []
            for x in range(MAP_W):
                for y in range(MAP_H):
                    if not self.is_unlocked(x, y):
                        continue
                    if (x, y) in self.trees:
                        rx, ry = self.rotate_grid_position(x, y)
                        depth_items.append(((rx + ry) * TILE_H / 2 - self.terrain[x][y].height * ELEVATION_STEP, rx, 0, x, y, "tree"))
                    if (x, y) in self.rocks:
                        rx, ry = self.rotate_grid_position(x, y)
                        depth_items.append(((rx + ry) * TILE_H / 2 - self.terrain[x][y].height * ELEVATION_STEP, rx, 1, x, y, "rock"))
                    if (x, y) in self.houses:
                        rx, ry = self.rotate_grid_position(x, y)
                        depth_items.append(((rx + ry) * TILE_H / 2 - self.terrain[x][y].height * ELEVATION_STEP, rx, 2, x, y, "house"))
                    if (x, y) in self.mines:
                        rx, ry = self.rotate_grid_position(x, y)
                        depth_items.append(((rx + ry) * TILE_H / 2 - self.terrain[x][y].height * ELEVATION_STEP, rx, 3, x, y, "mine"))
                    if (x, y) in self.city_objects:
                        rx, ry = self.rotate_grid_position(x, y)
                        object_type = self.city_objects[(x, y)].get("type")
                        if object_type in CITY_OBJECT_DEFS:
                            footprint = self.footprint_for(object_type, x, y)
                            depth = max(
                                sum(self.rotate_grid_position(tx, ty))
                                for tx, ty in footprint
                            ) * TILE_H / 2
                            depth_items.append((depth, rx, 4, x, y, "city_object"))

            worker_gx, worker_gy = self.worker_grid_position()
            worker_height = self.terrain[self.worker_x][self.worker_y].height
            if self.worker_path:
                nx, ny = self.worker_path[0]
                worker_height += (
                    self.terrain[nx][ny].height - worker_height
                ) * clamp(self.worker_move_progress, 0.0, 1.0)
            worker_rx, worker_ry = self.rotate_grid_float(worker_gx, worker_gy)
            depth_items.append(((worker_rx + worker_ry) * TILE_H / 2
                                - worker_height * ELEVATION_STEP,
                                worker_rx, 4, self.worker_x, self.worker_y, "worker"))
            depth_items.sort(key=lambda item: (item[0], item[1], item[2]))

            for _depth, _x_order, _kind_order, x, y, kind in depth_items:
                if kind == "tree":
                    self.draw_tree(x, y)
                elif kind == "rock":
                    self.draw_rock(x, y)
                elif kind == "house":
                    self.draw_house(x, y, self.house_levels.get((x, y), 1))
                elif kind == "mine":
                    self.draw_mine(x, y)
                elif kind == "city_object":
                    object_data = self.city_objects.get((x, y), {})
                    object_type = object_data.get("type")
                    if object_type in CITY_OBJECT_DEFS:
                        self.draw_city_object(
                            x, y, object_type, int(object_data.get("level", 1))
                        )
                elif kind == "worker":
                    self.draw_worker()

            if self.selected_structure_anchor is not None:
                selected = self.city_object_at(*self.selected_structure_anchor)
                if selected is not None:
                    selected_anchor, selected_kind, _selected_level = selected
                    for sx, sy in self.footprint_for(selected_kind, *selected_anchor):
                        scx, scy = self.tile_to_screen(sx, sy)
                        outline = self.diamond(
                            scx, scy, TILE_W*self.zoom*0.96, TILE_H*self.zoom*0.96
                        )
                        pygame.draw.polygon(
                            self.canvas, C["gold"], outline,
                            max(1, round(1.5*self.zoom))
                        )

            self.draw_work_queue()

        else:
            self.draw_work_queue(underground_only=True)
            # Keep the worker visible in the cutaway so underground jobs and
            # camera-follow movement remain understandable.
            self.draw_worker()
            self.text(
                self.canvas,
                f"지층 조사 화면 · {self.underground_layer}/3층 · 채굴은 지상의 채굴장이 자동 진행 · U: 지상 복귀 · [ ]: 층 변경",
                12, TOP_H + 5, 9, (224, 218, 187)
            )
            mx, my = self.logical_mouse(pygame.mouse.get_pos())
            if VIEW_RECT.collidepoint(mx, my):
                tile = self.screen_to_tile(mx, my)
                if tile:
                    vx, vy = tile
                    vcx, vcy = self.tile_to_screen(vx, vy)
                    vein_color = C["gold"]
                    pygame.draw.polygon(
                        self.canvas, vein_color,
                        self.diamond(vcx, vcy, TILE_W * self.zoom, TILE_H * self.zoom),
                        max(1, round(1.2 * self.zoom))
                    )

        if not self.underground_view:
            # Tile cursor / placement preview.
            mx, my = self.logical_mouse(pygame.mouse.get_pos())
            if VIEW_RECT.collidepoint(mx, my):
                tile = self.screen_to_tile(mx, my)
                if tile:
                    x, y = tile
                    cx, cy = self.tile_to_screen(x, y)
                    pts = self.diamond(cx, cy, TILE_W*self.zoom, TILE_H*self.zoom)
                    active_tool = self.active_action_tool()
                    if self.tool == "house":
                        if self.build_palette_open and self.build_palette_hover_index is not None:
                            preview_kind = BUILD_MENU_ITEMS[self.build_palette_hover_index][0]
                            preview_anchor = self.build_palette_anchor or (x, y)
                        else:
                            preview_kind = self.selected_building_type if not self.build_palette_open else "house"
                            preview_anchor = self.build_palette_anchor or (x, y)
                        preview_footprint = self.footprint_for(preview_kind, *preview_anchor)
                        allowed, _reason = self.can_reserve_work_order(
                            preview_kind, *preview_anchor
                        )
                        for fx, fy in preview_footprint:
                            if not (0 <= fx < MAP_W and 0 <= fy < MAP_H):
                                continue
                            fcx, fcy = self.tile_to_screen(fx, fy)
                            fpts = self.diamond(
                                fcx, fcy, TILE_W*self.zoom, TILE_H*self.zoom
                            )
                            pygame.draw.polygon(
                                self.canvas, C["green"] if allowed else C["red"],
                                fpts, max(1, round(1.4*self.zoom))
                            )
                    elif active_tool == "road":
                        allowed = self.can_build_road_on(x, y) or (x, y) in self.roads
                    elif active_tool == "clear":
                        allowed = (x, y) in self.trees or (x, y) in self.rocks
                    elif active_tool == "demolish":
                        allowed = (x, y) in self.roads or self.city_object_at(x, y) is not None
                    elif active_tool == "dig":
                        allowed = self.can_dig_terrain(x, y)
                    elif active_tool == "mine":
                        allowed = self.can_build_mine_on(
                            x, y, allow_worker=(x, y) == (self.worker_x, self.worker_y)
                        )
                    elif active_tool == "restore":
                        allowed = self.can_restore_terrain(
                            x, y, allow_worker=(x, y) == (self.worker_x, self.worker_y)
                        )
                    elif active_tool in ("restore_tree", "restore_rock"):
                        allowed = (
                            self.terrain[x][y].terrain == "grass"
                            and (x, y) not in self.trees and (x, y) not in self.rocks
                            and (x, y) not in self.roads and (x, y) not in self.houses
                            and (x, y) not in self.mines and not self.is_city_object_occupied(x, y)
                        )
                    else:
                        allowed = self.worker_can_stand(x, y)
                    if self.selected_road_tile == (x, y):
                        color = C["gold"]
                    elif any(order[1] == x and order[2] == y for order in self.work_queue):
                        color = C["gold"]
                    else:
                        color = C["green"] if allowed else C["red"]
                    pygame.draw.polygon(self.canvas, color, pts, max(1, round(1.2*self.zoom)))
                    if self.tool == "road" and allowed and (x, y) not in self.roads:
                        pygame.draw.circle(
                            self.canvas, C["road_center"],
                            (round(cx), round(cy)), max(2, round(2 * self.zoom))
                        )


        # Night lighting is applied after world objects but before the tutorial card.
        self.draw_time_of_day()
        # Tutorial card.
        self.draw_tutorial_card()
        self.canvas.set_clip(None)

    def draw_work_queue(self, underground_only: bool = False) -> None:
        """Mark queued surface work sites; the underground view has no tile jobs."""
        if underground_only:
            return
        order_colors = {
            "clear": C["green"],
            "demolish": C["red"],
            "road": (190, 198, 190),
            "house": (238, 151, 111),
            "mine": (193, 166, 111),
            "dig": (147, 158, 166),
            "restore": (114, 190, 139),
        }
        for index, (tool, x, y) in enumerate(self.work_queue, start=1):
            if not self.is_unlocked(x, y):
                continue
            color = order_colors.get(tool, C["gold"])
            cx, cy = self.tile_to_screen(x, y)
            marker = self.diamond(
                cx, cy, TILE_W * self.zoom * 0.94, TILE_H * self.zoom * 0.94
            )
            pygame.draw.polygon(
                self.canvas, color, marker, max(1, round(1.5 * self.zoom))
            )
            badge_x = round(cx + TILE_W * self.zoom * 0.20)
            badge_y = round(cy - TILE_H * self.zoom * 0.08)
            radius = max(4, round(5 * self.zoom))
            pygame.draw.circle(self.canvas, (35, 43, 49), (badge_x, badge_y), radius + 1)
            pygame.draw.circle(self.canvas, color, (badge_x, badge_y), radius)
            label = str(index) if index < 10 else "+"
            self.text(self.canvas, label, badge_x, badge_y, 7, (35, 43, 49), center=True)

    def draw_worker_path_preview(self) -> None:
        """Show the walkable route to the tile currently under the mouse."""
        if self.tool != "move" or self.dragging or self.modal_seed:
            return

        mx, my = self.logical_mouse(pygame.mouse.get_pos())
        if not VIEW_RECT.collidepoint(mx, my):
            return

        goal = self.screen_to_tile(mx, my)
        if goal is None:
            return

        path = self.find_worker_path(goal)
        if path is None or not path:
            return

        # Draw the route on the ground, before trees, rocks, houses and the
        # worker are rendered, so foreground objects naturally cover the path.
        previous = self.worker_screen_position()
        line_width = max(1, round(2 * self.zoom))
        dot_radius = max(2, round(2.2 * self.zoom))
        for tile in path:
            point = self.tile_to_screen(*tile)
            end = (round(point[0]), round(point[1]))
            pygame.draw.line(
                self.canvas, (34, 83, 55),
                (round(previous[0]), round(previous[1])), end,
                line_width + 2
            )
            pygame.draw.line(
                self.canvas, C["green"],
                (round(previous[0]), round(previous[1])), end,
                line_width
            )
            pygame.draw.circle(self.canvas, (34, 83, 55), end, dot_radius + 1)
            pygame.draw.circle(self.canvas, C["green"], end, dot_radius)
            previous = point

        # A brighter outline identifies the selected destination.
        gx, gy = self.tile_to_screen(*goal)
        destination = self.diamond(gx, gy, TILE_W * self.zoom, TILE_H * self.zoom)
        pygame.draw.polygon(
            self.canvas, C["white"], destination,
            max(1, round(1.5 * self.zoom))
        )

    def draw_tutorial_card(self) -> None:
        if self.tutorial_done:
            return
        box = pygame.Rect(8, 40, 218, 61)
        pygame.draw.rect(self.canvas, (27, 38, 43), box)
        pygame.draw.rect(self.canvas, C["gold"], box, 1)
        self.text(self.canvas, "첫 번째 도시 만들기", 15, 46, 11, C["gold"])
        tasks = [
            ("1. 캐릭터 이동하기", "[이동] 모드에서 빈 땅을 클릭해 보세요."),
            (f"2. 나무 제거하기 ({min(self.tutorial_removed,2)}/2)", "[제거] 도구로 나무 2개를 치우세요."),
            (f"3. 도로 배치하기 ({min(self.tutorial_roads,3)}/3)", "도로는 목재 1개, 집은 목재·석재가 필요해요."),
            ("4. 첫 번째 집 건설하기", "도로 옆에 집을 지으세요. 바위 1개를 제거해 석재를 얻으세요."),
        ]
        title, hint = tasks[min(self.tutorial_step, 3)]
        self.text(self.canvas, title, 15, 62, 10, C["white"])
        self.text(self.canvas, hint, 15, 78, 9, C["muted"])

    def draw_ui(self) -> None:
        # Top status bar.
        pygame.draw.rect(self.canvas, C["panel"], (0, 0, LOGICAL_W, TOP_H))
        pygame.draw.line(self.canvas, (111, 130, 122), (0, TOP_H-1), (LOGICAL_W, TOP_H-1), 1)
        self.text(self.canvas, "PIXEL CITY", 8, 5, 13, C["gold"])
        self.text(self.canvas, f"₩{self.money:,}", 132, 6, 11, C["white"])
        self.text(self.canvas, f"인구 {self.population}", 210, 7, 9, C["text"])
        self.text(self.canvas, f"일자리 {self.available_city_jobs()}", 270, 7, 8, C["muted"])
        self.text(self.canvas, f"목재 {self.wood}", 326, 7, 9, C["muted"])
        self.text(self.canvas, f"석재 {self.stone}", 378, 7, 9, C["muted"])
        tax_income, business_income, maintenance = self.calculate_daily_city_finances()
        daily_net = tax_income + business_income - maintenance
        income_color = C["green"] if daily_net >= 0 else C["red"]
        self.text(
            self.canvas, f"{daily_net:+,}원/일", 430, 7, 8, income_color
        )
        self.text(self.canvas, f"DAY {self.day}", 506, 7, 8, C["muted"])
        self.button(pygame.Rect(531, 5, 39, 21), "시드", small=True)
        self.button(pygame.Rect(573, 5, 29, 21), "저장", small=True)
        self.button(pygame.Rect(605, 5, 31, 21), "불러", small=True)

        # Compact toolbar: movement, clearing/demolition, construction and terrain tools.
        pygame.draw.rect(self.canvas, C["panel"], (0, BOTTOM_Y, LOGICAL_W, LOGICAL_H-BOTTOM_Y))
        pygame.draw.line(self.canvas, (111, 130, 122), (0, BOTTOM_Y), (LOGICAL_W, BOTTOM_Y), 1)
        tool_xs = [4, 50, 96, 142, 188]
        for i, (key, name) in enumerate(zip(TOOL_KEYS, TOOL_NAMES)):
            self.button(
                pygame.Rect(tool_xs[i], 294, 43, 23),
                name, self.tool == key, small=True
            )
        if self.tool == "remove":
            remove_xs = [234, 280, 326]
            for index, (mode, label) in enumerate(REMOVE_MODE_OPTIONS):
                self.button(
                    pygame.Rect(remove_xs[index], 294, 43, 23),
                    label, self.remove_mode == mode, small=True
                )
        elif self.tool == "restore":
            for index, (mode, label) in enumerate(RESTORE_MODE_OPTIONS):
                self.button(
                    pygame.Rect([234, 280, 326][index], 294, 43, 23),
                    label, self.restore_mode == mode, small=True
                )

        expansion_costs = [5000, 15000, 35000, 75000]
        cost_text = "최대" if self.expand_level >= len(expansion_costs) else f"₩{expansion_costs[self.expand_level]:,}"
        self.button(pygame.Rect(373, 294, 88, 23), "땅 확장", small=True)
        self.button(pygame.Rect(468, 294, 42, 23), "설정", small=True)
        self.button(pygame.Rect(515, 294, 42, 23), "도움", small=True)
        self.text(
            self.canvas, f"{cost_text} · {self.expand_level}/4",
            417, 326, 9, C["gold"], center=True
        )
        self.text(self.canvas, f"예약 {len(self.work_queue)}", 590, 326, 9, C["gold"], center=True)
        self.draw_virtual_keys()
        hint = TOOL_HINTS.get(self.tool, "")
        if self.tool == "remove":
            hint = (
                f"제거: {REMOVE_MODE_HINTS[self.remove_mode]} "
                "· [ ] 또는 하단 버튼으로 변경"
            )
        elif self.tool == "road":
            hint = "도로: 드래그 건설 · 기존 도로 클릭 후 R 회전 · 물 위로 연결하면 다리"
        elif self.tool == "house":
            hint = "건설: 빈 땅 클릭 → 건물 선택 → 건물 위에서 마우스를 놓아 예약 · G 업그레이드"
        elif self.tool == "restore":
            hint = f"복원: {RESTORE_MODE_LABELS[self.restore_mode]} · [ ] 또는 하단 버튼으로 변경"
        self.text(self.canvas, hint, 10, 327, 8, C["text"])
        city_status = self.calculate_city_service_status()
        self.text(
            self.canvas,
            f"전력 {int(city_status['power_output'])}/{int(city_status['power_demand'])} "
            f"물 {int(city_status['water_output'])}/{int(city_status['water_demand'])} "
            f"행복 {int(city_status['happiness'])} 환경 {int(city_status['environment'])} "
            f"교통 {int(city_status['traffic'])}",
            10, 344, 8, C["muted"]
        )

        if time.time() < self.notice_until:
            msg = self.notice
            w = min(480, max(180, self.font(10).size(msg)[0] + 18))
            rect = pygame.Rect((LOGICAL_W-w)//2, 266, w, 18)
            pygame.draw.rect(self.canvas, (34, 45, 47), rect)
            pygame.draw.rect(self.canvas, C["gold"], rect, 1)
            self.text(self.canvas, msg, rect.centerx, rect.centery, 9, C["white"], center=True)

        if self.modal_seed:
            self.draw_seed_modal()
        self.draw_build_palette()
        self.draw_save_dialog()
        self.draw_settings_modal()
        self.draw_help_modal()

    def export_save_json(self, slot: int = 1) -> None:
        """Export an existing manual save slot as a portable JSON file."""
        try:
            serialized = self.read_save_text(slot)
        except (OSError, FileNotFoundError) as exc:
            self.notify(f"슬롯 {slot} 저장 데이터를 찾을 수 없어요. 먼저 저장해 주세요. ({exc})", 3.5)
            return
        filename = f"pixel-city-tycoon-slot-{slot}.json"
        try:
            if IS_WEB:
                from platform import window
                blob = window.Blob.new([serialized], {"type": "application/json;charset=utf-8"})
                url = window.URL.createObjectURL(blob)
                anchor = window.document.createElement("a")
                anchor.href = url
                anchor.download = filename
                anchor.click()
                window.URL.revokeObjectURL(url)
            else:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                root.attributes("-topmost", True)
                path = filedialog.asksaveasfilename(
                    title="도시 저장 파일 내보내기",
                    defaultextension=".json",
                    initialfile=filename,
                    filetypes=[("JSON 저장 파일", "*.json"), ("모든 파일", "*.*")]
                )
                root.destroy()
                if not path:
                    return
                Path(path).write_text(serialized, encoding="utf-8")
            self.notify(f"슬롯 {slot} JSON 내보내기를 완료했어요.", 3)
        except Exception as exc:
            self.notify(f"JSON 내보내기 실패: {exc}", 4)

    def import_save_json(self, slot: int = 1) -> None:
        """Import a JSON save, validate it, then store it in the selected slot."""
        try:
            if IS_WEB:
                from platform import window
                serialized = window.prompt(
                    "가져올 JSON 저장 파일의 내용을 붙여넣으세요.\n"
                    "PC에서는 JSON 파일을 메모장으로 열어 전체 내용을 복사하면 됩니다."
                )
                if serialized is None or not str(serialized).strip():
                    return
                serialized = str(serialized)
            else:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                root.attributes("-topmost", True)
                path = filedialog.askopenfilename(
                    title="도시 JSON 저장 파일 가져오기",
                    filetypes=[("JSON 저장 파일", "*.json"), ("모든 파일", "*.*")]
                )
                root.destroy()
                if not path:
                    return
                serialized = Path(path).read_text(encoding="utf-8")
            self.load_game(slot=slot, save_text_override=serialized)
            if self.last_load_success:
                self.save_game(slot)
                self.notify(f"JSON 데이터를 슬롯 {slot}에 가져왔어요.", 3.5)
        except Exception as exc:
            self.notify(f"JSON 가져오기 실패: {exc}", 4)

    def handle_settings_click(self, pos: Tuple[int, int]) -> None:
        x, y = pos
        if 190 <= x <= 450 and 112 <= y <= 145:
            self.sandbox_mode = not self.sandbox_mode
            self.notify("샌드박스 경제 켜짐 · 자금 부족으로 건설이 막히지 않아요." if self.sandbox_mode else "일반 경제 모드로 전환했어요.", 3)
        elif 190 <= x <= 450 and 154 <= y <= 187:
            self.sound_enabled = not self.sound_enabled
            self.notify("효과음 켜짐" if self.sound_enabled else "효과음 꺼짐", 2)
        elif 190 <= x <= 450 and 196 <= y <= 229:
            self.window_scale = self.window_scale % 3 + 1
            self.window = pygame.display.set_mode(
                (LOGICAL_W * self.window_scale, LOGICAL_H * self.window_scale)
            )
            self.notify(f"화면 크기: {self.window_scale}배", 2)
        elif 325 <= x <= 450 and 250 <= y <= 282:
            self.settings_open = False

    def draw_settings_modal(self) -> None:
        if not self.settings_open:
            return
        shade = pygame.Surface((LOGICAL_W, LOGICAL_H), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 190))
        self.canvas.blit(shade, (0, 0))
        panel = pygame.Rect(142, 70, 356, 228)
        pygame.draw.rect(self.canvas, C["panel"], panel)
        pygame.draw.rect(self.canvas, C["gold"], panel, 2)
        self.text(self.canvas, "게임 설정", panel.centerx, 91, 14, C["gold"], center=True)
        rows = [
            (112, "샌드박스 경제", "켜짐" if self.sandbox_mode else "꺼짐"),
            (154, "효과음", "켜짐" if self.sound_enabled else "꺼짐"),
            (196, "화면 크기", f"{self.window_scale}배"),
        ]
        for top, label, value in rows:
            rect = pygame.Rect(190, top, 260, 34)
            pygame.draw.rect(self.canvas, C["panel2"], rect)
            pygame.draw.rect(self.canvas, (104, 122, 112), rect, 1)
            self.text(self.canvas, label, 202, top + 10, 10, C["text"])
            self.text(self.canvas, value, 435, top + 10, 10, C["gold"], center=True)
        self.text(self.canvas, "돈이 부족해도 건설할 수 있지만 목재와 석재는 소비됩니다.", panel.centerx, 240, 7, C["muted"], center=True)
        self.button(pygame.Rect(325, 250, 125, 32), "닫기", small=True)

    def draw_help_modal(self) -> None:
        if not self.help_open:
            return
        shade = pygame.Surface((LOGICAL_W, LOGICAL_H), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 195))
        self.canvas.blit(shade, (0, 0))
        panel = pygame.Rect(82, 35, 476, 290)
        pygame.draw.rect(self.canvas, C["panel"], panel)
        pygame.draw.rect(self.canvas, C["gold"], panel, 2)
        self.text(self.canvas, "조작법 / 게임 도움말", panel.centerx, 51, 14, C["gold"], center=True)
        help_lines = [
            "F1 이동 · F2 제거 · F3 도로 · F4 건설 · F8 복원",
            "1~5: 모드 선택 · [ / ]: 하위 작업/건물 종류 변경",
            "마우스 왼쪽 클릭: 선택 및 예약 · 드래그: 연속 작업 예약",
            "가운데 버튼 드래그 / WASD: 카메라 이동 · 휠: 확대/축소",
            "Q/E: 지도 회전 · C: 작업자 추적 · U: 지층 조사",
            "F3 도로 선택 후 R: 방향 회전 · F4 건물 선택 후 G: 업그레이드",
            "F5 저장 · F9 불러오기 · F10 설정 · F11 도움말 · JSON 저장/불러오기는 슬롯 창",
            "주택은 도로 옆에 건설해야 하며, 건설 예약은 자금과 재료를 확보합니다.",
            "채굴장과 벌목장은 시간이 지나면 각각 석재와 목재를 생산합니다.",
            "발전소·급수탑은 일정 범위의 주택에 전력·물을 공급하며 주민 증가에 필요합니다.",
            "행복도는 전력·물·일자리·공원·환경·교통 지표에 따라 달라집니다.",
            "저장/불러오기에서 수동 슬롯 3개와 자동 저장본을 관리할 수 있습니다.",
        ]
        for index, line in enumerate(help_lines):
            self.text(self.canvas, line, 105, 77 + index * 20, 8, C["text"])
        self.button(pygame.Rect(430, 288, 112, 27), "닫기 (ESC)", small=True)

    def draw_save_dialog(self) -> None:
        if self.save_dialog_mode is None:
            return
        shade = pygame.Surface((LOGICAL_W, LOGICAL_H), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 190))
        self.canvas.blit(shade, (0, 0))
        panel = pygame.Rect(142, 38, 356, 292)
        pygame.draw.rect(self.canvas, C["panel"], panel)
        pygame.draw.rect(self.canvas, C["gold"], panel, 2)
        title = "저장 슬롯 선택" if self.save_dialog_mode == "save" else "불러올 슬롯 선택"
        self.text(self.canvas, title, panel.centerx, 54, 13, C["gold"], center=True)
        for slot, top in enumerate((72, 108, 144), start=1):
            rect = pygame.Rect(160, top, 320, 30)
            active = slot == self.save_dialog_selected
            exists, description = self.save_slot_info(slot)
            fill = C["panel3"] if active else C["panel2"]
            pygame.draw.rect(self.canvas, fill, rect)
            pygame.draw.rect(self.canvas, C["gold"] if active else (88, 104, 103), rect, 1)
            self.text(self.canvas, f"슬롯 {slot}", rect.x + 10, rect.y + 5, 10, C["white"])
            color = C["muted"] if exists else (130, 145, 137)
            self.text(self.canvas, description, rect.x + 82, rect.y + 6, 8, color)
        if self.save_dialog_mode == "load":
            exists, description = self.save_slot_info(1, autosave=True)
            auto_rect = pygame.Rect(160, 180, 320, 30)
            pygame.draw.rect(self.canvas, C["panel2"], auto_rect)
            pygame.draw.rect(self.canvas, (88, 104, 103), auto_rect, 1)
            self.text(self.canvas, "자동 저장", auto_rect.x + 10, auto_rect.y + 5, 10, C["gold"])
            self.text(
                self.canvas, description if exists else "아직 자동 저장 데이터가 없어요.",
                auto_rect.x + 82, auto_rect.y + 6, 8, C["muted"]
            )
        if self.save_dialog_confirm:
            self.text(
                self.canvas, f"슬롯 {self.save_dialog_selected}의 저장 데이터를 덮어쓸까요?",
                panel.centerx, 264, 9, C["white"], center=True
            )
            self.button(pygame.Rect(190, 286, 125, 30), "덮어쓰기", True, small=True)
            self.button(pygame.Rect(325, 286, 125, 30), "취소", small=True)
        else:
            self.button(pygame.Rect(325, 286, 125, 30), "닫기", small=True)
        self.button(pygame.Rect(160, 220, 155, 30), "JSON 내보내기", small=True)
        self.button(pygame.Rect(325, 220, 155, 30), "JSON 가져오기", small=True)

    def draw_seed_modal(self) -> None:
        shade = pygame.Surface((LOGICAL_W, LOGICAL_H), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 170))
        self.canvas.blit(shade, (0, 0))
        box = pygame.Rect(170, 125, 300, 110)
        pygame.draw.rect(self.canvas, C["panel"], box)
        pygame.draw.rect(self.canvas, C["gold"], box, 2)
        self.text(self.canvas, "새로운 지형 만들기", 320, 143, 14, C["gold"], center=True)
        self.text(self.canvas, "숫자 시드를 입력하세요. 빈칸이면 랜덤 생성", 320, 165, 9, C["text"], center=True)
        pygame.draw.rect(self.canvas, C["panel2"], (205, 180, 230, 22))
        pygame.draw.rect(self.canvas, C["muted"], (205, 180, 230, 22), 1)
        self.text(self.canvas, self.seed_text + "_", 214, 184, 11, C["white"])
        self.text(self.canvas, "ENTER: 생성   ESC: 취소", 320, 215, 9, C["muted"], center=True)

    # ------------------------------------------------------------------
    # Input and game loop
    # ------------------------------------------------------------------
    def logical_mouse(self, pos: Tuple[int, int]) -> Tuple[int, int]:
        scale_x = self.window.get_width() / LOGICAL_W
        scale_y = self.window.get_height() / LOGICAL_H
        return int(pos[0] / scale_x), int(pos[1] / scale_y)

    def virtual_key_buttons(self) -> List[Tuple[pygame.Rect, int, str]]:
        """Return context-sensitive on-screen keycaps after touch input is detected."""
        if not self.touch_input_active or self.modal_seed:
            return []

        keys: List[Tuple[str, int]] = [("Q", pygame.K_q), ("E", pygame.K_e)]
        road_selected = (
            self.tool == "road"
            and self.selected_road_tile is not None
            and self.selected_road_tile in self.roads
        )
        upgrade_available = False
        if self.tool == "house" and self.selected_structure_anchor is not None:
            found = self.city_object_at(*self.selected_structure_anchor)
            upgrade_available = bool(
                found is not None
                and found[1] in UPGRADABLE_OBJECTS
                and found[2] < 3
            )

        if road_selected:
            keys.extend([("C", pygame.K_c), ("U", pygame.K_u), ("R", pygame.K_r)])
        elif upgrade_available:
            keys.extend([("C", pygame.K_c), ("U", pygame.K_u), ("G", pygame.K_g)])
        elif self.tool in ("remove", "house", "restore") or self.underground_view:
            keys.extend([
                ("[", pygame.K_LEFTBRACKET), ("]", pygame.K_RIGHTBRACKET),
                ("C", pygame.K_c), ("U", pygame.K_u)
            ])
        else:
            keys.extend([("C", pygame.K_c), ("U", pygame.K_u)])

        width, height, gap = 25, 23, 2
        start_x = LOGICAL_W - 8 - len(keys) * width - (len(keys) - 1) * gap
        return [
            (pygame.Rect(start_x + index * (width + gap), 294, width, height), key, label)
            for index, (label, key) in enumerate(keys)
        ]

    def draw_virtual_keys(self) -> None:
        """Draw small keycaps for the shortcuts currently useful on a touch device."""
        for rect, _key, label in self.virtual_key_buttons():
            pygame.draw.rect(self.canvas, (24, 32, 37), rect)
            pygame.draw.rect(self.canvas, C["gold"], rect, 1)
            self.text(self.canvas, label, rect.centerx, rect.centery, 10, C["gold"], center=True)

    def virtual_key_at(self, pos: Tuple[int, int]) -> Optional[int]:
        for rect, key, _label in self.virtual_key_buttons():
            if rect.collidepoint(pos):
                return key
        return None

    def queue_virtual_key(self, key: int) -> None:
        """Send a virtual key through pygame's normal KEYDOWN handling path."""
        pygame.event.post(pygame.event.Event(
            pygame.KEYDOWN, key=key, mod=pygame.KMOD_NONE, unicode=""
        ))

    def update_multi_touch_gesture(self) -> None:
        """Pan with two fingers and zoom when their separation changes."""
        if len(self.touch_fingers) < 2:
            return
        first, second = list(self.touch_fingers.values())[:2]
        midpoint = (
            (first[0] + second[0]) // 2,
            (first[1] + second[1]) // 2,
        )
        distance = math.hypot(second[0] - first[0], second[1] - first[1])
        if self.touch_gesture_mode != "camera":
            self.touch_gesture_mode = "camera"
            self.touch_last_midpoint = midpoint
            self.touch_last_distance = distance
            return
        dx = midpoint[0] - self.touch_last_midpoint[0]
        dy = midpoint[1] - self.touch_last_midpoint[1]
        if distance > self.touch_last_distance * 1.10:
            self.change_zoom(1, midpoint)
            self.touch_last_distance = distance
        elif distance < self.touch_last_distance * 0.90:
            self.change_zoom(-1, midpoint)
            self.touch_last_distance = distance
        self.camera_x += dx
        self.camera_y += dy
        if dx or dy:
            self.camera_follow_worker = False
        self.touch_last_midpoint = midpoint

    def handle_touch_down(self, pos: Tuple[int, int]) -> None:
        """Route a touch press through the same tile and UI handlers as a mouse press."""
        if self.save_dialog_mode is not None:
            self.handle_click(pos)
            return
        if self.modal_seed:
            return
        hit = self.build_palette_hit_test(pos)
        if self.build_palette_open and hit is not None:
            self.build_palette_dragging = True
            self.build_palette_pressed_index = hit
            self.build_palette_hover_index = hit
            return
        if self.build_palette_open:
            panel, _cells = self.build_palette_geometry()
            if panel.collidepoint(pos):
                return
            self.close_build_palette()
        if VIEW_RECT.collidepoint(*pos):
            if self.tool == "house" and not self.underground_view:
                tile = self.screen_to_tile(*pos)
                if tile is not None:
                    self.open_build_palette(tile)
            else:
                self.begin_tool_drag(pos)
        else:
            self.handle_click(pos)

    def handle_touch_motion(self, pos: Tuple[int, int]) -> None:
        if self.build_palette_open:
            self.build_palette_hover_index = self.build_palette_hit_test(pos)
        if self.tool_dragging:
            self.update_tool_drag(pos)

    def handle_touch_up(self, pos: Tuple[int, int]) -> None:
        if self.build_palette_dragging:
            hit = self.build_palette_hit_test(pos)
            if hit is not None:
                self.choose_building_from_palette(hit)
            else:
                self.build_palette_dragging = False
                self.build_palette_pressed_index = None
                self.build_palette_hover_index = None
        elif self.tool_dragging:
            self.finish_tool_drag(pos)

    def handle_click(self, pos: Tuple[int, int]) -> None:
        x, y = pos
        if self.settings_open:
            self.handle_settings_click(pos)
            return
        if self.help_open:
            self.help_open = False
            return
        if self.save_dialog_mode is not None:
            self.handle_save_dialog_click(pos)
            return
        if self.modal_seed:
            return
        virtual_key = self.virtual_key_at(pos)
        if virtual_key is not None:
            self.queue_virtual_key(virtual_key)
            return
        if y <= TOP_H:
            if 531 <= x <= 570 and 4 <= y <= 27:
                self.modal_seed = True
                self.seed_text = ""
            elif 573 <= x <= 602 and 4 <= y <= 27:
                self.open_save_dialog("save")
            elif 605 <= x <= 638 and 4 <= y <= 27:
                self.open_save_dialog("load")
            return
        if y >= BOTTOM_Y:
            if 294 <= y <= 317:
                tool_xs = [4, 50, 96, 142, 188]
                for i, tx in enumerate(tool_xs):
                    if tx <= x <= tx + 43:
                        self.select_tool(TOOL_KEYS[i])
                        return
                if self.tool == "remove":
                    remove_xs = [234, 280, 326]
                    for index, tx in enumerate(remove_xs):
                        if tx <= x <= tx + 43:
                            self.set_remove_mode(REMOVE_MODE_OPTIONS[index][0])
                            return
                elif self.tool == "restore":
                    for index, tx in enumerate((234, 280, 326)):
                        if tx <= x <= tx + 43:
                            self.restore_mode = RESTORE_MODE_OPTIONS[index][0]
                            self.notify(f"복원 대상: {RESTORE_MODE_LABELS[self.restore_mode]}", 1.6)
                            return
            if 373 <= x <= 461 and 294 <= y <= 317:
                self.expand_land()
                return
            if 468 <= x <= 510 and 294 <= y <= 317:
                self.settings_open = True
                return
            if 515 <= x <= 557 and 294 <= y <= 317:
                self.help_open = True
                return
            return
        if VIEW_RECT.collidepoint(x, y):
            tile = self.screen_to_tile(x, y)
            if tile:
                self.apply_single_tile_click(tile)

    def apply_single_tile_click(self, tile: Tuple[int, int]) -> None:
        x, y = tile
        if self.underground_view:
            if self.tool == "move":
                self.set_worker_destination(x, y)
            else:
                self.notify("지층 조사는 보기 전용이에요. 채굴은 지상의 채굴장이 자동으로 진행해요.", 2.5)
            return
        if self.tool == "house":
            self.open_build_palette((x, y))
            return
        if self.tool == "road" and (x, y) in self.roads:
            self.selected_road_tile = (x, y)
            self.notify("도로 타일을 선택했어요. R 키로 중앙선 방향을 90도 회전해요.", 2.5)
            return
        if self.selected_road_tile != (x, y):
            self.selected_road_tile = None
        if self.tool == "move":
            self.set_worker_destination(x, y)
        else:
            self.toggle_work_order(self.active_action_tool(), x, y)

    def queue_drag_order(self, tool: str, x: int, y: int) -> None:
        """Queue one drag-painted surface tile without toggling existing orders."""
        if self.underground_view or tool == "move":
            return
        if any(order[1] == x and order[2] == y for order in self.work_queue):
            return
        if len(self.work_queue) >= MAX_WORK_QUEUE:
            return
        valid, _reason = self.can_reserve_work_order(tool, x, y)
        if not valid:
            return
        self.work_queue.append((tool, x, y))
        if tool == "road":
            self.road_directions[(x, y)] = self.infer_road_axis(x, y)

    def paint_drag_segment(
        self, start: Tuple[int, int], end: Tuple[int, int]
    ) -> None:
        """Sample every grid tile crossed by a quick mouse drag."""
        x0, y0 = start
        x1, y1 = end
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        error = dx - dy
        while True:
            tile = (x0, y0)
            if tile not in self.tool_drag_visited:
                self.tool_drag_visited.add(tile)
                active_tool = self.active_action_tool()
                if self.tool == "move":
                    self.tool_drag_last_tile = tile
                elif self.tool == "road" and tile in self.roads:
                    self.selected_road_tile = tile
                elif active_tool in ("clear", "demolish", "road", "house", "dig", "mine", "restore", "restore_tree", "restore_rock"):
                    self.queue_drag_order(active_tool, x0, y0)
            if x0 == x1 and y0 == y1:
                break
            twice_error = 2 * error
            if twice_error > -dy:
                error -= dy
                x0 += sx
            if twice_error < dx:
                error += dx
                y0 += sy

    def begin_tool_drag(self, pos: Tuple[int, int]) -> None:
        tile = self.screen_to_tile(*pos)
        if tile is None:
            return
        self.tool_dragging = True
        self.tool_drag_start_tile = tile
        self.tool_drag_last_tile = tile
        self.tool_drag_start_pos = pos
        self.tool_drag_moved = False
        self.tool_drag_visited = set()

    def update_tool_drag(self, pos: Tuple[int, int]) -> None:
        if not self.tool_dragging:
            return
        dx = pos[0] - self.tool_drag_start_pos[0]
        dy = pos[1] - self.tool_drag_start_pos[1]
        if dx * dx + dy * dy >= 25:
            self.tool_drag_moved = True
        if not self.tool_drag_moved or not VIEW_RECT.collidepoint(*pos):
            return
        tile = self.screen_to_tile(*pos)
        if tile is None:
            return
        previous = self.tool_drag_last_tile or self.tool_drag_start_tile
        if previous is not None:
            self.paint_drag_segment(previous, tile)
        self.tool_drag_last_tile = tile

    def finish_tool_drag(self, pos: Tuple[int, int]) -> None:
        if not self.tool_dragging:
            return
        self.update_tool_drag(pos)
        start_tile = self.tool_drag_start_tile
        moved = self.tool_drag_moved
        final_tile = self.tool_drag_last_tile
        if start_tile is not None:
            if not moved:
                self.apply_single_tile_click(start_tile)
            elif self.tool == "move":
                if final_tile is not None:
                    self.set_worker_destination(*final_tile)
            else:
                self.notify(f"드래그 작업 예약 완료 · 현재 예약 {len(self.work_queue)}개", 2.2)
        self.tool_dragging = False
        self.tool_drag_start_tile = None
        self.tool_drag_last_tile = None
        self.tool_drag_moved = False
        self.tool_drag_visited.clear()

    def toggle_road_direction(self) -> None:
        """Rotate a selected, already-installed road tile while in road mode."""
        if self.tool != "road":
            self.notify("F3 도로 모드에서 기존 도로를 선택한 뒤 R을 누르세요.", 2.3)
            return
        tile = self.selected_road_tile
        if tile is None or tile not in self.roads:
            self.notify("방향을 바꿀 기존 도로 타일을 먼저 클릭해 선택하세요.", 2.5)
            return
        self.road_directions[tile] = (
            "y" if self.road_directions.get(tile, "x") == "x" else "x"
        )
        axis = "↙" if self.road_directions[tile] == "y" else "↘"
        self.notify(f"선택한 도로 방향을 {axis} 축으로 90도 회전했어요.", 2.2)

    def change_zoom(self, direction: int, mouse_logical: Tuple[int, int]) -> None:
        old_zoom = self.zoom
        new_idx = int(clamp(self.zoom_index + direction, 0, len(ZOOM_LEVELS) - 1))
        if new_idx == self.zoom_index:
            return
        mx, my = mouse_logical
        # Preserve the point under the cursor, including the selected tile's elevation.
        tile = self.screen_to_tile(mx, my)
        anchor_height = (
            self.terrain[tile[0]][tile[1]].height if tile is not None else 0
        )
        anchor_rx, anchor_ry = (
            self.rotate_grid_position(tile[0], tile[1]) if tile is not None else (0.0, 0.0)
        )
        self.zoom_index = new_idx
        self.zoom = ZOOM_LEVELS[self.zoom_index]
        new_tw, new_th = TILE_W * self.zoom, TILE_H * self.zoom
        self.camera_x = mx - (anchor_rx - anchor_ry) * new_tw / 2
        self.camera_y = (
            my - (anchor_rx + anchor_ry) * new_th / 2
            + anchor_height * ELEVATION_STEP * self.zoom
        )
    
    def process_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if self.settings_open:
                    if event.key == pygame.K_ESCAPE:
                        self.settings_open = False
                elif self.help_open:
                    if event.key in (pygame.K_ESCAPE, pygame.K_F11):
                        self.help_open = False
                elif self.save_dialog_mode is not None:
                    if event.key == pygame.K_ESCAPE:
                        self.save_dialog_mode = None
                        self.save_dialog_confirm = False
                elif self.modal_seed:
                    if event.key == pygame.K_ESCAPE:
                        self.modal_seed = False
                    elif event.key == pygame.K_RETURN:
                        value = self.seed_text.strip()
                        if value:
                            try:
                                seed = int(value) % 2147483647
                            except ValueError:
                                seed = sum((i + 1) * ord(ch) for i, ch in enumerate(value)) % 2147483647
                        else:
                            seed = random.randint(100000, 999999999)
                        self.generate_world(seed)
                        self.center_camera()
                        self.modal_seed = False
                    elif event.key == pygame.K_BACKSPACE:
                        self.seed_text = self.seed_text[:-1]
                    elif event.unicode and event.unicode.isprintable() and len(self.seed_text) < 14:
                        self.seed_text += event.unicode
                else:
                    if event.key == pygame.K_F10:
                        self.settings_open = True
                    elif event.key == pygame.K_F11:
                        self.help_open = True
                    elif event.key == pygame.K_ESCAPE:
                        if self.build_palette_open:
                            self.close_build_palette()
                        else:
                            self.running = False
                    elif event.key == pygame.K_g:
                        self.upgrade_selected_structure()
                    elif event.key == pygame.K_F1:
                        self.select_tool("move")
                    elif event.key == pygame.K_F2:
                        self.select_tool("remove")
                    elif event.key == pygame.K_F3:
                        self.select_tool("road")
                    elif event.key == pygame.K_F4:
                        self.select_tool("house")
                    elif event.key == pygame.K_F8:
                        self.select_tool("restore")
                    elif event.key == pygame.K_r and self.tool == "road":
                        self.toggle_road_direction()
                    elif event.key == pygame.K_q:
                        self.rotate_map(-1)
                    elif event.key == pygame.K_e:
                        self.rotate_map(1)
                    elif event.key == pygame.K_c:
                        self.camera_follow_worker = not self.camera_follow_worker
                        if self.camera_follow_worker:
                            self.center_camera_on_worker()
                        self.notify(
                            "작업자 카메라 추적 켜짐" if self.camera_follow_worker
                            else "작업자 카메라 추적 꺼짐", 2
                        )
                    elif event.key == pygame.K_u:
                        self.underground_view = not self.underground_view
                        self.notify(
                            "지층 조사 보기 · 채굴장은 자동으로 지층을 채굴해요."
                            if self.underground_view else "지상 보기", 2
                        )
                    elif event.key == pygame.K_LEFTBRACKET:
                        if self.underground_view:
                            self.underground_layer = max(1, self.underground_layer - 1)
                            self.notify(f"지하 지층 {self.underground_layer}/3", 1.5)
                        elif self.tool == "remove":
                            self.cycle_remove_mode(-1)
                        elif self.tool == "house":
                            self.cycle_building_type(-1)
                        elif self.tool == "restore":
                            self.cycle_restore_mode(-1)
                    elif event.key == pygame.K_RIGHTBRACKET:
                        if self.underground_view:
                            self.underground_layer = min(3, self.underground_layer + 1)
                            self.notify(f"지하 지층 {self.underground_layer}/3", 1.5)
                        elif self.tool == "remove":
                            self.cycle_remove_mode(1)
                        elif self.tool == "house":
                            self.cycle_building_type(1)
                        elif self.tool == "restore":
                            self.cycle_restore_mode(1)
                    elif event.key == pygame.K_1:
                        self.select_tool("move")
                    elif event.key == pygame.K_2:
                        self.select_tool("remove")
                    elif event.key == pygame.K_3:
                        self.select_tool("road")
                    elif event.key == pygame.K_4:
                        self.select_tool("house")
                    elif event.key == pygame.K_5:
                        self.select_tool("restore")
                    elif event.key == pygame.K_F5:
                        self.save_game()
                    elif event.key == pygame.K_F9:
                        self.load_game()
            elif event.type == pygame.FINGERDOWN:
                self.touch_input_active = True
                logical = (
                    int(clamp(event.x * LOGICAL_W, 0, LOGICAL_W - 1)),
                    int(clamp(event.y * LOGICAL_H, 0, LOGICAL_H - 1)),
                )
                self.touch_fingers[event.finger_id] = logical
                if len(self.touch_fingers) == 1:
                    self.active_finger_id = event.finger_id
                    if self.virtual_key_at(logical) is not None:
                        self.handle_click(logical)
                    else:
                        self.handle_touch_down(logical)
                elif len(self.touch_fingers) == 2:
                    # A second finger converts the gesture into camera control.
                    self.active_finger_id = None
                    self.tool_dragging = False
                    self.tool_drag_start_tile = None
                    self.tool_drag_last_tile = None
                    self.tool_drag_visited.clear()
                    self.build_palette_dragging = False
                    self.build_palette_pressed_index = None
                    self.update_multi_touch_gesture()
            elif event.type == pygame.FINGERMOTION:
                if event.finger_id in self.touch_fingers:
                    logical = (
                        int(clamp(event.x * LOGICAL_W, 0, LOGICAL_W - 1)),
                        int(clamp(event.y * LOGICAL_H, 0, LOGICAL_H - 1)),
                    )
                    self.touch_fingers[event.finger_id] = logical
                    if len(self.touch_fingers) >= 2:
                        self.update_multi_touch_gesture()
                    elif self.active_finger_id == event.finger_id:
                        self.handle_touch_motion(logical)
            elif event.type == pygame.FINGERUP:
                if event.finger_id in self.touch_fingers:
                    logical = (
                        int(clamp(event.x * LOGICAL_W, 0, LOGICAL_W - 1)),
                        int(clamp(event.y * LOGICAL_H, 0, LOGICAL_H - 1)),
                    )
                    if len(self.touch_fingers) == 1 and self.active_finger_id == event.finger_id:
                        self.handle_touch_up(logical)
                    self.touch_fingers.pop(event.finger_id, None)
                    self.active_finger_id = None
                    if len(self.touch_fingers) < 2:
                        self.touch_gesture_mode = None
                        self.touch_last_distance = 0.0
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if getattr(event, "touch", False):
                    continue
                logical = self.logical_mouse(event.pos)
                if self.modal_seed:
                    continue
                if self.save_dialog_mode is not None:
                    if event.button == 1:
                        self.handle_click(logical)
                    continue
                if event.button == 1:
                    if self.build_palette_open:
                        hit = self.build_palette_hit_test(logical)
                        if hit is not None:
                            self.build_palette_dragging = True
                            self.build_palette_pressed_index = hit
                            self.build_palette_hover_index = hit
                            continue
                        panel, _cells = self.build_palette_geometry()
                        if panel.collidepoint(logical):
                            continue
                        self.close_build_palette()
                    if VIEW_RECT.collidepoint(*logical):
                        if self.tool == "house" and not self.underground_view:
                            tile = self.screen_to_tile(*logical)
                            if tile is not None:
                                self.open_build_palette(tile)
                        else:
                            self.begin_tool_drag(logical)
                    else:
                        self.handle_click(logical)
                elif event.button == 2:
                    self.dragging = True
                    self.camera_follow_worker = False
                    self.last_mouse = logical
                elif event.button == 4:
                    if VIEW_RECT.collidepoint(*logical):
                        self.change_zoom(1, logical)
                elif event.button == 5:
                    if VIEW_RECT.collidepoint(*logical):
                        self.change_zoom(-1, logical)
            elif event.type == pygame.MOUSEBUTTONUP:
                if getattr(event, "touch", False):
                    continue
                logical = self.logical_mouse(event.pos)
                if event.button == 1 and self.build_palette_dragging:
                    hit = self.build_palette_hit_test(logical)
                    if hit is not None:
                        self.choose_building_from_palette(hit)
                    else:
                        self.build_palette_dragging = False
                        self.build_palette_pressed_index = None
                        self.build_palette_hover_index = None
                elif event.button == 1 and self.tool_dragging:
                    self.finish_tool_drag(logical)
                elif event.button == 2:
                    self.dragging = False
            elif event.type == pygame.MOUSEMOTION:
                if getattr(event, "touch", False):
                    continue
                logical = self.logical_mouse(event.pos)
                if self.build_palette_open:
                    self.build_palette_hover_index = self.build_palette_hit_test(logical)
                if self.tool_dragging:
                    self.update_tool_drag(logical)
                if self.dragging:
                    dx = logical[0] - self.last_mouse[0]
                    dy = logical[1] - self.last_mouse[1]
                    self.camera_x += dx
                    self.camera_y += dy
                    self.last_mouse = logical
            elif event.type == pygame.MOUSEWHEEL:
                logical = self.logical_mouse(pygame.mouse.get_pos())
                if VIEW_RECT.collidepoint(*logical):
                    self.change_zoom(1 if event.y > 0 else -1, logical)

    def update_mines(self, game_minutes_elapsed: float) -> None:
        """Each mine extracts one stratum at a time, independent of surface tiles."""
        if game_minutes_elapsed <= 0:
            return
        completed_layers = 0
        finished_mines = 0
        for position, (layer, progress) in list(self.mines.items()):
            if layer > 3:
                continue
            progress += game_minutes_elapsed
            while progress >= MINE_LAYER_DURATION_MINUTES and layer <= 3:
                progress -= MINE_LAYER_DURATION_MINUTES
                self.stone += MINE_STONE_PER_LAYER
                completed_layers += 1
                layer += 1
                if layer > 3:
                    progress = 0.0
                    finished_mines += 1
            self.mines[position] = (layer, progress)
        if completed_layers:
            suffix = f" · 채굴 완료 {finished_mines}곳" if finished_mines else ""
            self.notify(
                f"채굴장 지층 채굴 완료 · 석재 +{completed_layers * MINE_STONE_PER_LAYER}{suffix}",
                3.2
            )

    def update_logging_camps(self, game_minutes_elapsed: float) -> None:
        """Turn a nearby forest tree into stored wood at each completed work cycle."""
        if game_minutes_elapsed <= 0:
            return
        produced = 0
        for anchor, data in list(self.city_objects.items()):
            if data.get("type") != "logging":
                continue
            progress = self.logging_progress.get(anchor, 0.0) + game_minutes_elapsed
            footprint = self.footprint_for("logging", *anchor)
            while progress >= LUMBER_CAMP_DURATION_MINUTES:
                nearby = [
                    tree for tree in self.trees
                    if min(abs(tree[0] - tx) + abs(tree[1] - ty) for tx, ty in footprint) <= 5
                ]
                if not nearby:
                    progress = LUMBER_CAMP_DURATION_MINUTES
                    break
                target = min(
                    nearby,
                    key=lambda tree: (
                        min(abs(tree[0] - tx) + abs(tree[1] - ty) for tx, ty in footprint),
                        tree[1], tree[0]
                    )
                )
                self.trees.remove(target)
                self.wood += LUMBER_CAMP_WOOD_PER_CYCLE
                progress -= LUMBER_CAMP_DURATION_MINUTES
                produced += LUMBER_CAMP_WOOD_PER_CYCLE
            self.logging_progress[anchor] = progress
        if produced:
            self.notify(f"벌목장 생산 완료 · 목재 +{produced}", 3)

    def calculate_city_service_status(self) -> Dict[str, float]:
        """Calculate housing, job, utility coverage, environment and traffic indicators."""
        houses = list(self.houses)
        population = max(0, self.population)
        housing_capacity = sum(
            4 + 2 * (self.house_levels.get(pos, 1) - 1) for pos in houses
        )
        power_plants = [
            (pos, data) for pos, data in self.city_objects.items()
            if data.get("type") == "power"
        ]
        water_plants = [
            (pos, data) for pos, data in self.city_objects.items()
            if data.get("type") == "water"
        ]
        power_output = sum(
            int(CITY_OBJECT_DEFS["power"]["power_output"]) *
            max(1, int(data.get("level", 1))) for _pos, data in power_plants
        )
        water_output = sum(
            int(CITY_OBJECT_DEFS["water"]["water_output"]) *
            max(1, int(data.get("level", 1))) for _pos, data in water_plants
        )
        power_demand = math.ceil(population / 4)
        water_demand = math.ceil(population / 4)
        pollution = 0
        park_count = 0
        commercial_count = 0
        for data in self.city_objects.values():
            kind = data.get("type")
            spec = CITY_OBJECT_DEFS.get(kind)
            if spec is None:
                continue
            level = max(1, int(data.get("level", 1)))
            power_demand += int(spec.get("power_use", 0)) * level
            water_demand += int(spec.get("water_use", 0)) * level
            pollution += int(spec.get("pollution", 0)) * level
            if kind == "park":
                park_count += 1
            elif kind == "commercial":
                commercial_count += 1

        def coverage(plants: List[Tuple[Tuple[int, int], dict]]) -> float:
            if not houses:
                return 1.0
            if not plants:
                return 0.0
            covered = 0
            for hx, hy in houses:
                if any(
                    abs(hx - px) + abs(hy - py) <= int(
                        CITY_OBJECT_DEFS[data["type"]].get("service_range", 0)
                    )
                    for (px, py), data in plants
                ):
                    covered += 1
            return covered / len(houses)

        power_coverage = coverage(power_plants)
        water_coverage = coverage(water_plants)
        power_ratio = 1.0 if power_demand == 0 else min(1.0, power_output / power_demand)
        water_ratio = 1.0 if water_demand == 0 else min(1.0, water_output / water_demand)
        jobs = self.available_city_jobs()
        job_ratio = 1.0 if population == 0 else min(1.0, jobs / population)
        tree_bonus = min(20, len(self.trees) // 3)
        environment = int(clamp(100 - pollution + park_count * 5 + tree_bonus, 0, 100))
        traffic = int(clamp(population * 4 / max(1, len(self.roads)), 0, 100))
        happiness = int(clamp(
            35 + power_ratio * power_coverage * 20
            + water_ratio * water_coverage * 20
            + job_ratio * 10 + environment * 0.10
            + min(5, park_count * 2) - traffic * 0.15,
            0, 100
        ))
        return {
            "housing_capacity": float(housing_capacity),
            "housing_demand": float(max(0, population + 1 - housing_capacity)),
            "power_output": float(power_output),
            "power_demand": float(power_demand),
            "power_coverage": power_coverage,
            "water_output": float(water_output),
            "water_demand": float(water_demand),
            "water_coverage": water_coverage,
            "jobs": float(jobs),
            "job_demand": float(max(0, population - jobs)),
            "commercial_demand": float(max(0, math.ceil(population / 8) - commercial_count)),
            "environment": float(environment),
            "traffic": float(traffic),
            "happiness": float(happiness),
        }

    def update_city_population(self) -> int:
        """Grow or gently shrink the city according to housing, services and jobs."""
        status = self.calculate_city_service_status()
        if (
            status["housing_capacity"] > self.population
            and status["power_demand"] <= status["power_output"]
            and status["water_demand"] <= status["water_output"]
            and status["power_coverage"] >= 1.0
            and status["water_coverage"] >= 1.0
            and status["jobs"] > 0
            and status["jobs"] >= self.population
            and status["happiness"] >= 60
        ):
            growth = min(2, int(status["housing_capacity"] - self.population))
            self.population += growth
            return growth
        if status["happiness"] < 20 and self.population > 0:
            self.population -= 1
            return -1
        return 0

    def calculate_daily_city_finances(self) -> Tuple[int, int, int]:
        """Return tax income, business income, and maintenance due for one game day."""
        tax_income = self.population * DAILY_INCOME_PER_RESIDENT
        business_income = 0
        maintenance = 0
        for (x, y) in self.houses:
            maintenance += 5 * self.house_levels.get((x, y), 1)
        for data in self.city_objects.values():
            kind = data.get("type")
            if kind not in CITY_OBJECT_DEFS:
                continue
            level = max(1, int(data.get("level", 1)))
            spec = CITY_OBJECT_DEFS[kind]
            business_income += int(spec["income"]) * level
            maintenance += int(spec["maintenance"]) * level
        return tax_income, business_income, maintenance

    def available_city_jobs(self) -> int:
        """Total job capacity provided by commercial, industrial and public buildings."""
        jobs = 0
        for data in self.city_objects.values():
            kind = data.get("type")
            if kind in CITY_OBJECT_DEFS:
                jobs += int(CITY_OBJECT_DEFS[kind]["jobs"]) * max(1, int(data.get("level", 1)))
        return jobs

    def city_building_footprints(self) -> List[Tuple[str, Set[Tuple[int, int]], int, int]]:
        """Return service demand for every home and occupied city facility."""
        buildings: List[Tuple[str, Set[Tuple[int, int]], int, int]] = []
        for anchor in self.houses:
            level = self.house_levels.get(anchor, 1)
            buildings.append(("house", {anchor}, 2 + level, 2 + level))
        for anchor, data in self.city_objects.items():
            kind = data.get("type")
            spec = CITY_OBJECT_DEFS.get(kind)
            if spec is None or kind in ("power", "water"):
                continue
            level = max(1, int(data.get("level", 1)))
            buildings.append((
                str(kind), self.footprint_for(str(kind), *anchor),
                int(spec.get("power_use", 2)) * level,
                int(spec.get("water_use", 2)) * level,
            ))
        return buildings

    @staticmethod
    def footprint_distance(first: Set[Tuple[int, int]], second: Set[Tuple[int, int]]) -> int:
        if not first or not second:
            return 10 ** 6
        return min(abs(ax - bx) + abs(ay - by)
                   for ax, ay in first for bx, by in second)

    def calculate_city_metrics(self) -> Dict[str, int]:
        """Calculate housing, jobs, utility coverage, environment and traffic."""
        housing = sum(4 + 2 * (self.house_levels.get(pos, 1) - 1) for pos in self.houses)
        job_capacity = self.available_city_jobs()
        job_demand = math.ceil(self.population * 0.60)
        power_sources = []
        water_sources = []
        power_capacity = 0
        water_capacity = 0
        parks = 0
        industry_count = 0
        pollution = 0
        for anchor, data in self.city_objects.items():
            kind = data.get("type")
            spec = CITY_OBJECT_DEFS.get(kind)
            if spec is None:
                continue
            level = max(1, int(data.get("level", 1)))
            footprint = self.footprint_for(str(kind), *anchor)
            if kind == "power":
                power_capacity += int(spec.get("power_output", 0)) * level
                power_sources.append((footprint, int(spec.get("service_range", 9))))
            elif kind == "water":
                water_capacity += int(spec.get("water_output", 0)) * level
                water_sources.append((footprint, int(spec.get("service_range", 9))))
            elif kind == "park":
                parks += 1
            elif kind == "industrial":
                industry_count += 1
            pollution += int(spec.get("pollution", 0)) * level

        buildings = self.city_building_footprints()
        resident_demand = math.ceil(self.population / 3)
        power_demand = resident_demand + sum(item[2] for item in buildings)
        water_demand = resident_demand + sum(item[3] for item in buildings)
        covered_power = 0
        covered_water = 0
        for _kind, footprint, power_use, water_use in buildings:
            if any(self.footprint_distance(footprint, source) <= radius
                   for source, radius in power_sources):
                covered_power += power_use
            if any(self.footprint_distance(footprint, source) <= radius
                   for source, radius in water_sources):
                covered_water += water_use

        power_supply = 100 if power_demand == 0 else min(100, power_capacity * 100 // power_demand)
        water_supply = 100 if water_demand == 0 else min(100, water_capacity * 100 // water_demand)
        building_power_demand = max(1, power_demand - resident_demand)
        building_water_demand = max(1, water_demand - resident_demand)
        power_range = 100 if power_demand == 0 else min(100, covered_power * 100 // building_power_demand)
        water_range = 100 if water_demand == 0 else min(100, covered_water * 100 // building_water_demand)
        power_ratio = min(power_supply, power_range)
        water_ratio = min(water_supply, water_range)

        sx, sy = MAP_W // 2, MAP_H // 2
        nearby_trees = sum(1 for x, y in self.trees if abs(x - sx) + abs(y - sy) <= 12)
        environment = int(clamp(
            55 + min(nearby_trees, 24) * 1.5 + parks * 8
            - industry_count * 9 - pollution * 0.35, 0, 100
        ))
        road_capacity = len(self.roads) * 3
        traffic_demand = self.population + job_demand
        congestion = 0 if traffic_demand == 0 else (
            100 if road_capacity == 0 else int(clamp(traffic_demand * 100 / road_capacity, 0, 100))
        )
        housing_ratio = 100 if self.population == 0 else min(100, housing * 100 // max(1, self.population))
        employment_ratio = 100 if job_demand == 0 else min(100, job_capacity * 100 // job_demand)
        park_access = min(100, parks * 30)
        happiness = round(
            housing_ratio * 0.20 + employment_ratio * 0.14
            + power_ratio * 0.18 + water_ratio * 0.18
            + environment * 0.15 + (100 - congestion) * 0.10
            + park_access * 0.05
        )
        return {
            "housing": housing, "jobs": job_capacity, "job_demand": job_demand,
            "power": power_capacity, "power_demand": power_demand, "power_ratio": power_ratio,
            "water": water_capacity, "water_demand": water_demand, "water_ratio": water_ratio,
            "environment": environment, "congestion": congestion,
            "happiness": int(clamp(happiness, 0, 100)),
        }

    def update_city_population(self) -> int:
        """Move residents in/out once per day based on housing and city services."""
        metrics = self.calculate_city_metrics()
        vacant_homes = max(0, metrics["housing"] - self.population)
        job_vacancies = max(0, metrics["jobs"] - metrics["job_demand"])
        change = 0
        if metrics["happiness"] >= 62 and vacant_homes > 0 and job_vacancies > 0:
            change = min(2, vacant_homes, max(1, job_vacancies))
        elif metrics["happiness"] < 28 and self.population > 0:
            change = -1
        if change:
            self.population = max(0, self.population + change)
        return change

    def update_citizen_traffic(self, dt: float) -> None:
        """Move a representative group of residents along road tiles."""
        roads = sorted(self.roads)
        if not roads or self.population <= 0:
            self.citizens = []
            return
        desired = min(12, self.population // 3)
        while len(self.citizens) < desired:
            position = roads[self.citizen_rng.randrange(len(roads))]
            self.citizens.append({
                "from": position, "to": position, "previous": None, "elapsed": 0.0
            })
        self.citizens = self.citizens[:desired]
        for citizen in self.citizens:
            current = citizen["to"]
            if current not in self.roads:
                current = roads[self.citizen_rng.randrange(len(roads))]
                citizen.update({"from": current, "to": current, "previous": None, "elapsed": 0.0})
            citizen["elapsed"] = float(citizen.get("elapsed", 0.0)) + max(0.0, dt)
            while citizen["elapsed"] >= 1.25:
                current = citizen["to"]
                neighbors = [
                    (current[0] + dx, current[1] + dy)
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                    if (current[0] + dx, current[1] + dy) in self.roads
                ]
                previous = citizen.get("previous")
                choices = [pos for pos in neighbors if pos != previous] or neighbors
                if not choices:
                    citizen.update({"from": current, "to": current, "previous": None, "elapsed": 0.0})
                    break
                next_tile = choices[self.citizen_rng.randrange(len(choices))]
                citizen["from"] = current
                citizen["to"] = next_tile
                citizen["previous"] = current
                citizen["elapsed"] = float(citizen["elapsed"]) - 1.25

    def draw_citizen_traffic(self) -> None:
        """Render small pedestrian markers moving along roads."""
        for index, citizen in enumerate(self.citizens):
            start, end = citizen["from"], citizen["to"]
            progress = clamp(float(citizen.get("elapsed", 0.0)) / 1.25, 0.0, 1.0)
            sx, sy = self.tile_to_screen(*start)
            ex, ey = self.tile_to_screen(*end)
            cx = sx + (ex - sx) * progress
            cy = sy + (ey - sy) * progress
            pygame.draw.ellipse(
                self.canvas, (35, 43, 40),
                pygame.Rect(round(cx-3*self.zoom), round(cy+1*self.zoom),
                            max(4, round(6*self.zoom)), max(2, round(3*self.zoom)))
            )
            shirt = ((219, 185, 119), (115, 174, 181), (185, 139, 151))[index % 3]
            pygame.draw.rect(
                self.canvas, shirt,
                (round(cx-2*self.zoom), round(cy-5*self.zoom),
                 max(3, round(4*self.zoom)), max(5, round(6*self.zoom)))
            )
            pygame.draw.circle(
                self.canvas, (232, 194, 151),
                (round(cx), round(cy-6*self.zoom)), max(2, round(2*self.zoom))
            )

    def draw_city_metrics_panel(self) -> None:
        metrics = self.calculate_city_metrics()
        panel = pygame.Rect(422, 36, 209, 48)
        pygame.draw.rect(self.canvas, (28, 39, 43), panel)
        pygame.draw.rect(self.canvas, (89, 106, 100), panel, 1)
        happiness_color = C["green"] if metrics["happiness"] >= 65 else (
            C["gold"] if metrics["happiness"] >= 40 else C["red"]
        )
        self.text(self.canvas, f"행복 {metrics['happiness']}%", 430, 41, 9, happiness_color)
        self.text(self.canvas, f"전력 {metrics['power_ratio']}%  물 {metrics['water_ratio']}%", 430, 56, 8, C["text"])
        self.text(self.canvas, f"환경 {metrics['environment']}  교통혼잡 {metrics['congestion']}%", 430, 69, 8, C["muted"])

    def draw_lighting_overlay(self) -> None:
        """Tint the world view based on the in-game clock."""
        hour = self.game_minutes / 60.0
        tint = None
        if hour >= 21 or hour < 5:
            tint = (22, 34, 66, 112)
        elif hour >= 18:
            tint = (104, 70, 45, round((hour - 18) / 3 * 66))
        elif hour < 7:
            tint = (92, 74, 60, round((7 - hour) / 2 * 52))
        if tint is None:
            return
        overlay = pygame.Surface((LOGICAL_W, VIEW_RECT.height), pygame.SRCALPHA)
        overlay.fill(tint)
        self.canvas.blit(overlay, (0, TOP_H))

    def update(self, dt: float) -> None:
        if self.save_dialog_mode is not None or self.settings_open or self.help_open:
            return
        self.update_worker(dt)
        if not self.modal_seed:
            keys = pygame.key.get_pressed()
            camera_dx = int(keys[pygame.K_d]) - int(keys[pygame.K_a])
            camera_dy = int(keys[pygame.K_s]) - int(keys[pygame.K_w])
            if camera_dx or camera_dy:
                if self.camera_follow_worker:
                    self.camera_follow_worker = False
                    self.notify("수동 카메라 이동으로 추적을 껐어요.", 1.8)
                length = math.hypot(camera_dx, camera_dy)
                self.camera_x -= (camera_dx / length) * CAMERA_SPEED * dt
                self.camera_y -= (camera_dy / length) * CAMERA_SPEED * dt
            elif self.camera_follow_worker:
                self.center_camera_on_worker()
        self.autosave_elapsed += max(0.0, dt)
        if self.autosave_elapsed >= 180.0:
            self.save_game(autosave=True)

        if self.worker_action_timer > 0:
            self.worker_action_elapsed = min(
                WORK_ACTION_DURATION,
                self.worker_action_elapsed + max(0.0, dt)
            )
            self.worker_action_timer = max(
                0.0, WORK_ACTION_DURATION - self.worker_action_elapsed
            )
            hit_time = WORK_ACTION_HIT_TIMES.get(
                self.worker_action, WORK_ACTION_DURATION * 0.55
            )
            if (not self.worker_action_hit_played
                    and self.worker_action_elapsed >= hit_time):
                self.worker_action_hit_played = True
                self.play_worker_action_sound(self.worker_action)
                self.complete_pending_work_action()
            if self.worker_action_timer == 0.0:
                self.worker_action = "idle"
                self.worker_action_elapsed = 0.0
                self.worker_action_hit_played = False
        self.update_work_queue()
        # Accelerated clock: six in-game minutes pass per real second.
        # Cap one frame's contribution so resuming a minimized/stalled window
        # cannot instantly consume many in-game hours or exhaust a forest.
        game_elapsed_minutes = clamp(dt, 0.0, 0.25) * 6
        self.game_minutes += game_elapsed_minutes
        self.update_mines(game_elapsed_minutes)
        self.update_logging_camps(game_elapsed_minutes)
        while self.game_minutes >= 24 * 60:
            self.game_minutes -= 24 * 60
            self.day += 1
            tax_income, business_income, maintenance = self.calculate_daily_city_finances()
            net_income = tax_income + business_income - maintenance
            self.money += net_income
            population_change = self.update_city_population()
            change_text = (
                f" · 주민 {'+' if population_change > 0 else ''}{population_change}"
                if population_change else ""
            )
            self.notify(
                f"DAY {self.day} · 세금 +₩{tax_income:,} · 사업 +₩{business_income:,} "
                f"· 유지비 -₩{maintenance:,} · 순수익 {net_income:+,}원{change_text}",
                3.4
            )
        # The first tutorial task is completed by giving the character a destination.
        if not self.tutorial_done and self.tutorial_step == 0 and self.worker_moved and not self.worker_path:
            self.tutorial_step = 1
            self.remove_mode = "clear"
            self.select_tool("remove")
            self.notify("좋아요! 이제 제거 모드로 나무 2개를 치워 건설 공간을 만드세요.", 4)

    def draw(self) -> None:
        self.draw_world()
        self.draw_ui()
        # Pixel-perfect upscale: no smoothing.
        scaled = pygame.transform.scale(self.canvas, self.window.get_size())
        self.window.blit(scaled, (0, 0))
        pygame.display.flip()

    def run(self) -> None:
        """Synchronous desktop loop used by the Windows EXE build."""
        while self.running:
            dt = min(self.clock.tick(60) / 1000.0, 0.25)
            self.process_events()
            self.update(dt)
            self.draw()
        pygame.quit()

    async def run_web(self) -> None:
        """Async browser loop; yielding each frame keeps the WASM page responsive."""
        previous_frame = time.perf_counter()
        while self.running:
            now = time.perf_counter()
            dt = min(max(now - previous_frame, 0.0), 0.25)
            previous_frame = now
            self.process_events()
            self.update(dt)
            self.draw()
            await asyncio.sleep(0)
        pygame.quit()


def main() -> None:
    try:
        game = CityGame()
        if IS_WEB:
            asyncio.run(game.run_web())
        else:
            game.run()
    except Exception as exc:
        # Keep a useful error message visible when launched from a terminal.
        print(f"{APP_NAME} failed to start: {exc}")
        raise


if __name__ == "__main__":
    main()
