"""Pixel City Tycoon - Prototype 0.1
A small isometric city-builder prototype using Pygame and procedural pixel-style art.
"""
from __future__ import annotations

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
    "F1 이동", "F2 자연", "F3 도로", "F4 집",
    "F6 굴착", "F7 채굴", "F8 복원", "F10 인공"
]
TOOL_KEYS = [
    "move", "clear", "road", "house", "dig", "mine", "restore", "demolish"
]
TOOL_HINTS = {
    "move": "이동: 빈 땅을 클릭해 작업자를 이동합니다.",
    "clear": "자연 제거: 나무·바위만 제거 · 목재/석재 획득",
    "demolish": "인공 철거: 도로·다리·주택·채굴장 제거",
    "road": "도로: 드래그 건설 · 물 위로 연결하면 다리 · R 회전",
    "house": "집: 도로 옆 건설 · ₩3,000 + 목재 1 + 석재 1",
    "dig": "굴착: 산을 한 층 낮추고 석재 획득",
    "mine": "채굴장: 도로 옆 설치 · 지층별 6시간 자동 채굴",
    "restore": "지형 복원: 빈 땅을 한 층 높임 · 석재 2",
}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def tile_key(x: int, y: int) -> str:
    return f"{x},{y}"


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
        self.tool_dragging = False
        self.tool_drag_start_tile: Optional[Tuple[int, int]] = None
        self.tool_drag_last_tile: Optional[Tuple[int, int]] = None
        self.tool_drag_start_pos = (0, 0)
        self.tool_drag_moved = False
        self.tool_drag_visited: Set[Tuple[int, int]] = set()
        self.modal_seed = False
        self.seed_text = ""
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
            mode_name = TOOL_NAMES[TOOL_KEYS.index(tool)].split(" ", 1)[1]
            self.notify(f"{mode_name} 모드", 1.2)

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

        # Keep one stone source reachable in every new starter settlement.
        # A short clear strip ensures at least one adjacent work position is open.
        starter_rock = (sx, sy + 5)
        for path_y in range(sy + 1, sy + 5):
            path_tile = (sx, path_y)
            self.terrain[path_tile[0]][path_tile[1]].terrain = "grass"
            self.trees.discard(path_tile)
            self.rocks.discard(path_tile)
        self.terrain[starter_rock[0]][starter_rock[1]].terrain = "grass"
        self.terrain[starter_rock[0]][starter_rock[1]].height = 0
        self.trees.discard(starter_rock)
        self.rocks.add(starter_rock)

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
        radii = [6, 10, 14, 18]
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
                or (x, y) in self.houses or (x, y) in self.mines):
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

    def can_build_on(self, x: int, y: int, allow_worker: bool = False) -> bool:
        if not (0 <= x < MAP_W and 0 <= y < MAP_H) or not self.is_unlocked(x, y):
            return False
        if self.terrain[x][y].terrain != "grass":
            return False
        if (x, y) in self.trees or (x, y) in self.rocks:
            return False
        if (x, y) in self.roads or (x, y) in self.houses or (x, y) in self.mines:
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
                or (x, y) in self.mines):
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
        if (x, y) in self.houses or (x, y) in self.mines:
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

    def reserved_build_cost(self) -> int:
        """Money already committed to queued construction orders."""
        total = 0
        for tool, x, y in self.work_queue:
            if tool == "road":
                total += self.road_build_cost(x, y)[0]
            elif tool == "house":
                total += HOUSE_MONEY_COST
            elif tool == "mine":
                total += MINE_MONEY_COST
        return total

    def reserved_material_costs(self) -> Tuple[int, int]:
        """Wood and stone already committed to queued construction/terraforming."""
        reserved_wood = 0
        reserved_stone = 0
        for tool, x, y in self.work_queue:
            if tool == "road":
                _, wood_cost, stone_cost = self.road_build_cost(x, y)
                reserved_wood += wood_cost
                reserved_stone += stone_cost
            elif tool == "house":
                reserved_wood += HOUSE_WOOD_COST
                reserved_stone += HOUSE_STONE_COST
            elif tool == "mine":
                reserved_wood += MINE_WOOD_COST
                reserved_stone += MINE_STONE_COST
            elif tool == "restore":
                reserved_stone += TERRAIN_RESTORE_STONE_COST
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
            if (x, y) not in self.roads and (x, y) not in self.houses and (x, y) not in self.mines:
                return False, "인공 철거 대상인 도로·주택·채굴장이 없어요."
            return True, ""

        if tool == "dig":
            if not self.can_dig_terrain(x, y):
                return False, "굴착은 개척 구역 안의 산 타일에만 예약할 수 있어요."
            return True, ""

        if tool == "restore":
            if not self.can_restore_terrain(
                x, y, allow_worker=(x, y) == (self.worker_x, self.worker_y)
            ):
                return False, "복원은 빈 육지의 높이가 4단계보다 낮을 때만 가능해요."
            _reserved_wood, reserved_stone = self.reserved_material_costs()
            if self.stone - reserved_stone < TERRAIN_RESTORE_STONE_COST:
                return False, f"지형 복원에는 석재 {TERRAIN_RESTORE_STONE_COST}개가 필요해요."
            return True, ""

        if tool not in ("road", "house", "mine"):
            return False, "예약할 수 없는 작업 종류예요."

        allow_worker = (x, y) == (self.worker_x, self.worker_y)
        if tool == "road":
            if not self.can_build_road_on(x, y):
                return False, "도로는 빈 땅 또는 기존 도로에서 이어지는 물 위에만 놓을 수 있어요."
        elif tool == "house":
            if not self.can_build_on(x, y, allow_worker=allow_worker):
                return False, "건설 예약은 비어 있는 잔디 타일에만 할 수 있어요."
        elif not self.can_build_mine_on(x, y, allow_worker=allow_worker):
            return False, "채굴장은 도로 옆의 빈 잔디 타일에만 건설할 수 있어요."

        available_money = self.money - self.reserved_build_cost()
        reserved_wood, reserved_stone = self.reserved_material_costs()
        available_wood = self.wood - reserved_wood
        available_stone = self.stone - reserved_stone

        if tool == "road":
            money_cost, wood_cost, stone_cost = self.road_build_cost(x, y)
        elif tool == "house":
            money_cost, wood_cost, stone_cost = (
                HOUSE_MONEY_COST, HOUSE_WOOD_COST, HOUSE_STONE_COST
            )
        else:
            money_cost, wood_cost, stone_cost = (
                MINE_MONEY_COST, MINE_WOOD_COST, MINE_STONE_COST
            )

        if available_money < money_cost:
            return False, f"건설 자금이 부족해요. 필요 자금: ₩{money_cost:,}"
        if available_wood < wood_cost or available_stone < stone_cost:
            return False, f"필요 재료: 목재 {wood_cost}개 · 석재 {stone_cost}개"
        return True, ""

    def toggle_work_order(self, tool: str, x: int, y: int) -> None:
        """Queue or cancel demolition, construction, digging or terrain restoration."""
        if tool not in ("clear", "demolish", "road", "house", "dig", "mine", "restore"):
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
        self, target: Tuple[int, int]
    ) -> Optional[List[Tuple[int, int]]]:
        """Find a path to a legal standing tile within normal construction range."""
        tx, ty = target
        positions = {
            (tx + dx, ty + dy)
            for dx in range(-ACTION_RANGE, ACTION_RANGE + 1)
            for dy in range(-ACTION_RANGE, ACTION_RANGE + 1)
            if 1 <= abs(dx) + abs(dy) <= ACTION_RANGE
            and self.worker_can_stand(tx + dx, ty + dy)
        }
        return self.find_path_to_any_position(
            (self.worker_x, self.worker_y), positions, blocked={target}
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
        """Demolish artificial structures only; demolition refunds no resources."""
        target = (x, y)
        if target in self.roads:
            self.roads.remove(target)
            self.road_directions.pop(target, None)
            if self.selected_road_tile == target:
                self.selected_road_tile = None
            self.notify("도로/다리를 철거했어요. 자원은 반환되지 않아요.")
        elif target in self.houses:
            self.houses.remove(target)
            self.population = max(0, self.population - 4)
            self.notify("주택을 철거했어요. 주민 4명이 도시를 떠났어요.")
        elif target in self.mines:
            del self.mines[target]
            self.notify("채굴장을 철거했어요. 진행 중이던 채굴은 중단됐어요.")
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
        """Apply a queued road, house or mine construction after the worker arrives."""
        if tool == "road":
            if not self.can_build_road_on(x, y):
                self.notify("예약한 도로 위치를 더 이상 사용할 수 없어 작업을 건너뛰었어요.", 2.8)
                return False
            money_cost, wood_cost, stone_cost = self.road_build_cost(x, y)
            if self.money < money_cost or self.wood < wood_cost or self.stone < stone_cost:
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
            if (self.money < HOUSE_MONEY_COST or self.wood < HOUSE_WOOD_COST
                    or self.stone < HOUSE_STONE_COST):
                self.notify("주택 건설에 필요한 자금 또는 자원이 부족해 예약을 건너뛰었어요.", 2.8)
                return False
            self.money -= HOUSE_MONEY_COST
            self.wood -= HOUSE_WOOD_COST
            self.stone -= HOUSE_STONE_COST
            self.houses.add((x, y))
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
            if (self.money < MINE_MONEY_COST or self.wood < MINE_WOOD_COST
                    or self.stone < MINE_STONE_COST):
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
        return False

    def update_work_queue(self) -> None:
        """Execute queued jobs in order, automatically moving the worker first."""
        while self.work_queue:
            tool, x, y = self.work_queue[0]
            if tool == "clear":
                valid = (x, y) in self.trees or (x, y) in self.rocks
            elif tool == "demolish":
                valid = (x, y) in self.roads or (x, y) in self.houses or (x, y) in self.mines
            elif tool == "road":
                valid = self.can_build_road_on(x, y)
            elif tool == "house":
                valid = (
                    self.can_build_on(x, y, allow_worker=True)
                    and self.has_planned_adjacent_road(x, y)
                )
            elif tool == "mine":
                valid = self.can_build_mine_on(x, y, allow_worker=True)
            elif tool == "dig":
                valid = self.can_dig_terrain(x, y)
            elif tool == "restore":
                valid = self.can_restore_terrain(x, y, allow_worker=True)
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
        if tool in ("clear", "dig"):
            path = self.find_worker_path_to_work_target(target)
        else:
            path = self.find_worker_path_to_action_target(target)

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
        elif tool == "demolish":
            action = "mine"
        elif tool == "dig":
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
        else:
            built = self.perform_build_order(tool, x, y, start_animation=False)
            if not built and tool == "road":
                self.road_directions.pop((x, y), None)

    def has_adjacent_road(self, x: int, y: int) -> bool:
        return any((x + dx, y + dy) in self.roads
                   for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)])

    def act_on_tile(self, x: int, y: int) -> None:
        """Compatibility entry point: all non-movement tools queue actions."""
        if self.tool in ("clear", "demolish", "road", "house", "dig", "mine", "restore"):
            self.toggle_work_order(self.tool, x, y)

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
        costs = [5000, 15000, 35000]
        if self.expand_level >= 3:
            self.notify("현재 프로토타입에서 확장할 수 있는 최대 크기예요.")
            return
        cost = costs[self.expand_level]
        if self.money - self.reserved_build_cost() < cost:
            self.notify(f"예약된 건설 비용을 제외하면 확장 자금이 부족해요. 필요 자금: ₩{cost:,}")
            return
        self.money -= cost
        self.expand_level += 1
        self.notify(f"새로운 땅을 개척했어요! -₩{cost:,}", 3)

    # ------------------------------------------------------------------
    # Save / load
    # ------------------------------------------------------------------
    def save_game(self) -> None:
        data = {
            "version": 10,
            "seed": self.seed,
            "underground_mined": [list(p) for p in sorted(self.underground_mined)],
            "mine_sites": [
                [x, y, layer, progress]
                for (x, y), (layer, progress) in sorted(self.mines.items())
            ],
            "map_rotation": self.map_rotation,
            "camera_follow_worker": self.camera_follow_worker,
            "underground_view": self.underground_view,
            "underground_layer": self.underground_layer,
            "trees": [list(p) for p in sorted(self.trees)],
            "rocks": [list(p) for p in sorted(self.rocks)],
            "roads": [list(p) for p in sorted(self.roads)],
            "road_direction": self.road_direction,
            "road_directions": [
                [x, y, axis] for (x, y), axis in sorted(self.road_directions.items())
            ],
            "terrain_heights": [
                [self.terrain[x][y].height for y in range(MAP_H)]
                for x in range(MAP_W)
            ],
            "houses": [list(p) for p in sorted(self.houses)],
            "expand_level": self.expand_level,
            "money": self.money,
            "population": self.population,
            "wood": self.wood,
            "stone": self.stone,
            "day": self.day,
            "game_minutes": self.game_minutes,
            "worker": [self.worker_x, self.worker_y],
            "worker_facing": list(self.worker_facing),
            "work_orders": [{"tool": tool, "x": x, "y": y}
                            for tool, x, y in self.work_queue],
            "tutorial_step": self.tutorial_step,
            "tutorial_done": self.tutorial_done,
            "tutorial_removed": self.tutorial_removed,
            "tutorial_roads": self.tutorial_roads,
            "tutorial_house_built": self.tutorial_house_built,
        }
        try:
            SAVE_DIR.mkdir(parents=True, exist_ok=True)
            SAVE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            self.notify("도시를 저장했어요.", 3)
        except OSError as exc:
            self.notify(f"저장 실패: {exc}", 4)

    def load_game(self) -> None:
        try:
            data = json.loads(SAVE_FILE.read_text(encoding="utf-8"))
            self.generate_world(int(data["seed"]))
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
            self.trees = {tuple(p) for p in data.get("trees", [])}
            self.rocks = {tuple(p) for p in data.get("rocks", [])}
            self.roads = {tuple(p) for p in data.get("roads", [])}
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
                            and entry[2] in ("x", "y")):
                        self.road_directions[(entry[0], entry[1])] = entry[2]
            self.houses = {tuple(p) for p in data.get("houses", [])}
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
                    if (self.is_unlocked(*pos) and self.terrain[pos[0]][pos[1]].terrain == "grass"
                            and pos not in self.roads and pos not in self.houses
                            and pos not in self.trees and pos not in self.rocks):
                        self.mines[pos] = (entry[2], float(entry[3]))
            self.expand_level = int(data.get("expand_level", 0))
            self.money = int(data.get("money", 100000))
            self.population = int(data.get("population", 0))
            self.wood = int(data.get("wood", 0))
            self.stone = int(data.get("stone", 0))
            self.day = int(data.get("day", 1))
            self.game_minutes = int(data.get("game_minutes", 480))
            worker_pos = data.get("worker", [MAP_W // 2, MAP_H // 2])
            if (isinstance(worker_pos, list) and len(worker_pos) == 2
                    and all(isinstance(v, int) for v in worker_pos)
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
                    if (tool not in ("clear", "demolish", "road", "house", "dig", "mine", "restore")
                            or type(x) is not int or type(y) is not int
                            or not (0 <= x < MAP_W and 0 <= y < MAP_H)
                            or not self.is_unlocked(x, y)):
                        continue
                    if any(ox == x and oy == y for _tool, ox, oy in self.work_queue):
                        continue
                    if tool == "clear" and (x, y) not in self.trees and (x, y) not in self.rocks:
                        continue
                    if tool == "demolish" and (x, y) not in self.roads and (x, y) not in self.houses and (x, y) not in self.mines:
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
                    if tool == "restore" and not self.can_restore_terrain(x, y, allow_worker=True):
                        continue
                    self.work_queue.append((tool, x, y))
                    if tool == "road":
                        self.road_directions.setdefault((x, y), self.infer_road_axis(x, y))

            self.tutorial_step = int(data.get("tutorial_step", 0))
            self.tutorial_done = bool(data.get("tutorial_done", False))
            self.tutorial_removed = int(data.get("tutorial_removed", 0))
            self.tutorial_roads = int(data.get("tutorial_roads", 0))
            self.tutorial_house_built = bool(data.get("tutorial_house_built", False))
            self.center_camera()
            if self.camera_follow_worker:
                self.center_camera_on_worker()
            self.notify("저장된 도시를 불러왔어요.", 3)
        except FileNotFoundError:
            self.notify("저장 파일이 없어요. 먼저 저장해 주세요.", 3)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.notify(f"불러오기 실패: {exc}", 4)

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

    def draw_house(self, x: int, y: int) -> None:
        cx, cy = self.tile_to_screen(x, y)
        z = self.zoom
        # Small isometric cabin with a red tiled roof.
        base_y = cy - 2*z
        left = (round(cx - 9*z), round(base_y - 7*z))
        back = (round(cx), round(base_y - 12*z))
        right = (round(cx + 9*z), round(base_y - 7*z))
        front = (round(cx), round(base_y - 2*z))
        left_bottom = (round(cx - 9*z), round(base_y + 5*z))
        front_bottom = (round(cx), round(base_y + 10*z))
        right_bottom = (round(cx + 9*z), round(base_y + 5*z))
        pygame.draw.polygon(self.canvas, (190, 153, 105), [left, front, front_bottom, left_bottom])
        pygame.draw.polygon(self.canvas, (142, 105, 76), [front, right, right_bottom, front_bottom])
        # Roof sides and ridge.
        roof_peak = (round(cx), round(base_y - 25*z))
        roof_left = (round(cx - 11*z), round(base_y - 12*z))
        roof_front = (round(cx), round(base_y - 5*z))
        roof_right = (round(cx + 11*z), round(base_y - 12*z))
        pygame.draw.polygon(self.canvas, (153, 57, 48), [roof_peak, roof_left, roof_front])
        pygame.draw.polygon(self.canvas, (119, 45, 44), [roof_peak, roof_front, roof_right])
        pygame.draw.line(self.canvas, (221, 106, 65), roof_peak, roof_left, max(1, round(z)))
        # Window and door.
        pygame.draw.rect(self.canvas, (75, 141, 164),
                         (round(cx - 6*z), round(base_y - 3*z), max(2, round(4*z)), max(4, round(5*z))))
        pygame.draw.rect(self.canvas, (85, 54, 38),
                         (round(cx + 1*z), round(base_y + 1*z), max(3, round(4*z)), max(8, round(7*z))))

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
                    self.draw_house(x, y)
                elif kind == "mine":
                    self.draw_mine(x, y)
                elif kind == "worker":
                    self.draw_worker()

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
            mouse = pygame.mouse.get_pos()
            mx, my = mouse[0] / WINDOW_SCALE, mouse[1] / WINDOW_SCALE
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
            mouse = pygame.mouse.get_pos()
            mx, my = mouse[0] / WINDOW_SCALE, mouse[1] / WINDOW_SCALE
            if VIEW_RECT.collidepoint(mx, my):
                tile = self.screen_to_tile(mx, my)
                if tile:
                    x, y = tile
                    cx, cy = self.tile_to_screen(x, y)
                    pts = self.diamond(cx, cy, TILE_W*self.zoom, TILE_H*self.zoom)
                    if self.tool == "house":
                        allowed = (
                            self.can_build_on(x, y, allow_worker=(x, y) == (self.worker_x, self.worker_y))
                            and self.has_planned_adjacent_road(x, y)
                        )
                    elif self.tool == "road":
                        allowed = self.can_build_road_on(x, y) or (x, y) in self.roads
                    elif self.tool == "clear":
                        allowed = (x, y) in self.trees or (x, y) in self.rocks
                    elif self.tool == "demolish":
                        allowed = (
                            (x, y) in self.roads
                            or (x, y) in self.houses
                            or (x, y) in self.mines
                        )
                    elif self.tool == "dig":
                        allowed = self.can_dig_terrain(x, y)
                    elif self.tool == "mine":
                        allowed = self.can_build_mine_on(
                            x, y, allow_worker=(x, y) == (self.worker_x, self.worker_y)
                        )
                    elif self.tool == "restore":
                        allowed = self.can_restore_terrain(
                            x, y, allow_worker=(x, y) == (self.worker_x, self.worker_y)
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

        mouse = pygame.mouse.get_pos()
        mx, my = mouse[0] / WINDOW_SCALE, mouse[1] / WINDOW_SCALE
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
            ("4. 첫 번째 집 건설하기", "도로 옆에 집을 지으세요. 바위는 [제거]로!"),
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
        self.text(self.canvas, f"인구 {self.population}", 230, 7, 10, C["text"])
        self.text(self.canvas, f"목재 {self.wood}", 302, 7, 9, C["muted"])
        self.text(self.canvas, f"석재 {self.stone}", 359, 7, 9, C["muted"])
        self.text(self.canvas, f"+₩{self.population * DAILY_INCOME_PER_RESIDENT:,}/일",
                  410, 7, 9, C["green"])
        self.text(self.canvas, f"DAY {self.day}", 490, 7, 9, C["muted"])
        self.button(pygame.Rect(531, 5, 39, 21), "시드", small=True)
        self.button(pygame.Rect(573, 5, 29, 21), "저장", small=True)
        self.button(pygame.Rect(605, 5, 31, 21), "불러", small=True)

        # Compact toolbar: movement, clearing/demolition, construction and terrain tools.
        pygame.draw.rect(self.canvas, C["panel"], (0, BOTTOM_Y, LOGICAL_W, LOGICAL_H-BOTTOM_Y))
        pygame.draw.line(self.canvas, (111, 130, 122), (0, BOTTOM_Y), (LOGICAL_W, BOTTOM_Y), 1)
        xs = [4, 50, 96, 142, 188, 234, 280, 326]
        for i, (key, name) in enumerate(zip(TOOL_KEYS, TOOL_NAMES)):
            self.button(pygame.Rect(xs[i], 294, 43, 23), name, self.tool == key, small=True)

        self.button(
            pygame.Rect(373, 294, 57, 23), "R 회전",
            self.tool == "road" and self.selected_road_tile is not None,
            small=True
        )
        cost_text = "최대" if self.expand_level >= 3 else f"₩{[5000,15000,35000][self.expand_level]:,}"
        self.button(pygame.Rect(434, 294, 80, 23), "땅 확장", small=True)
        self.text(self.canvas, cost_text, 474, 326, 9, C["gold"], center=True)
        self.text(self.canvas, f"예약 {len(self.work_queue)}", 590, 326, 9, C["gold"], center=True)
        hint = TOOL_HINTS.get(self.tool, "")
        self.text(self.canvas, hint, 10, 327, 8, C["text"])
        self.text(
            self.canvas,
            "Q/E 지도 회전   C 카메라 추적   U 지층 조사   [ ] 층 선택",
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
        return pos[0] // WINDOW_SCALE, pos[1] // WINDOW_SCALE

    def handle_click(self, pos: Tuple[int, int]) -> None:
        x, y = pos
        if self.modal_seed:
            return
        if y <= TOP_H:
            if 531 <= x <= 570 and 4 <= y <= 27:
                self.modal_seed = True
                self.seed_text = ""
            elif 573 <= x <= 602 and 4 <= y <= 27:
                self.save_game()
            elif 605 <= x <= 638 and 4 <= y <= 27:
                self.load_game()
            return
        if y >= BOTTOM_Y:
            if 294 <= y <= 317:
                tool_xs = [4, 50, 96, 142, 188, 234, 280, 326]
                for i, tx in enumerate(tool_xs):
                    if tx <= x <= tx + 43:
                        self.select_tool(TOOL_KEYS[i])
                        return
                if 373 <= x <= 430:
                    self.toggle_road_direction()
                    return
            if 434 <= x <= 514 and 294 <= y <= 317:
                self.expand_land()
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
        if self.tool == "road" and (x, y) in self.roads:
            self.selected_road_tile = (x, y)
            self.notify("설치된 도로를 선택했어요. R 또는 [R 회전]으로 방향을 바꿔요.", 2.5)
            return
        if self.selected_road_tile != (x, y):
            self.selected_road_tile = None
        if self.tool == "move":
            self.set_worker_destination(x, y)
        else:
            self.toggle_work_order(self.tool, x, y)

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
                if self.tool == "move":
                    self.tool_drag_last_tile = tile
                elif self.tool == "road" and tile in self.roads:
                    self.selected_road_tile = tile
                elif self.tool in ("clear", "demolish", "road", "house", "dig", "mine", "restore"):
                    self.queue_drag_order(self.tool, x0, y0)
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
        """Rotate a selected, already-installed road tile."""
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
                if self.modal_seed:
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
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_F1:
                        self.select_tool("move")
                    elif event.key == pygame.K_F2:
                        self.select_tool("clear")
                    elif event.key == pygame.K_F10:
                        self.select_tool("demolish")
                    elif event.key == pygame.K_F3:
                        self.select_tool("road")
                    elif event.key == pygame.K_F4:
                        self.select_tool("house")
                    elif event.key == pygame.K_F6:
                        self.select_tool("dig")
                    elif event.key == pygame.K_F7:
                        self.select_tool("mine")
                    elif event.key == pygame.K_F8:
                        self.select_tool("restore")
                    elif event.key == pygame.K_r:
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
                        self.underground_layer = max(1, self.underground_layer - 1)
                        if self.underground_view:
                            self.notify(f"지하 지층 {self.underground_layer}/3", 1.5)
                    elif event.key == pygame.K_RIGHTBRACKET:
                        self.underground_layer = min(3, self.underground_layer + 1)
                        if self.underground_view:
                            self.notify(f"지하 지층 {self.underground_layer}/3", 1.5)
                    elif event.key == pygame.K_1:
                        self.select_tool("move")
                    elif event.key == pygame.K_2:
                        self.select_tool("clear")
                    elif event.key == pygame.K_3:
                        self.select_tool("road")
                    elif event.key == pygame.K_4:
                        self.select_tool("house")
                    elif event.key == pygame.K_5:
                        self.select_tool("dig")
                    elif event.key == pygame.K_6:
                        self.select_tool("mine")
                    elif event.key == pygame.K_7:
                        self.select_tool("restore")
                    elif event.key == pygame.K_8:
                        self.select_tool("demolish")
                    elif event.key == pygame.K_F5:
                        self.save_game()
                    elif event.key == pygame.K_F9:
                        self.load_game()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                logical = self.logical_mouse(event.pos)
                if self.modal_seed:
                    continue
                if event.button == 1:
                    if VIEW_RECT.collidepoint(*logical):
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
                if event.button == 1 and self.tool_dragging:
                    self.finish_tool_drag(self.logical_mouse(event.pos))
                elif event.button == 2:
                    self.dragging = False
            elif event.type == pygame.MOUSEMOTION:
                logical = self.logical_mouse(event.pos)
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

    def update(self, dt: float) -> None:
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
        now = time.time()
        elapsed = now - self.last_clock_tick
        self.last_clock_tick = now
        game_elapsed_minutes = elapsed * 6
        self.game_minutes += game_elapsed_minutes
        self.update_mines(game_elapsed_minutes)
        while self.game_minutes >= 24 * 60:
            self.game_minutes -= 24 * 60
            self.day += 1
            daily_income = self.population * DAILY_INCOME_PER_RESIDENT
            if daily_income > 0:
                self.money += daily_income
                self.notify(f"DAY {self.day} · 주민 세금 수입 +₩{daily_income:,}", 2.4)
        # The first tutorial task is completed by giving the character a destination.
        if not self.tutorial_done and self.tutorial_step == 0 and self.worker_moved and not self.worker_path:
            self.tutorial_step = 1
            self.tool = "clear"
            self.notify("좋아요! 이제 나무 2개를 제거해 건설 공간을 만드세요.", 4)

    def draw(self) -> None:
        self.draw_world()
        self.draw_ui()
        # Pixel-perfect upscale: no smoothing.
        scaled = pygame.transform.scale(self.canvas, (WINDOW_W, WINDOW_H))
        self.window.blit(scaled, (0, 0))
        pygame.display.flip()

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            self.process_events()
            self.update(dt)
            self.draw()
        pygame.quit()


def main() -> None:
    try:
        game = CityGame()
        game.run()
    except Exception as exc:
        # Keep a useful error message visible when launched from a terminal.
        print(f"{APP_NAME} failed to start: {exc}")
        raise


if __name__ == "__main__":
    main()
