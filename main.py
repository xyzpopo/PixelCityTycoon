"""Pixel City Tycoon - Prototype 0.1
A small isometric city-builder prototype using Pygame and procedural pixel-style art.
"""
from __future__ import annotations

import json
import math
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

TOOL_NAMES = ["이동", "제거", "도로", "집"]
TOOL_KEYS = ["move", "clear", "road", "house"]
TOOL_HINTS = {
    "move": "이동 모드: 목적지를 클릭하면 캐릭터가 길을 따라 걸어갑니다.",
    "clear": "제거 모드: 나무나 바위를 클릭해 자원을 얻으세요.",
    "road": "도로 모드: 빈 잔디 타일을 클릭해 도로를 건설하세요.",
    "house": "집 모드: 도로 옆 빈 땅을 클릭해 집을 건설하세요.",
}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def tile_key(x: int, y: int) -> str:
    return f"{x},{y}"


@dataclass
class TileInfo:
    terrain: str = "grass"
    variation: int = 0


class CityGame:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption(APP_NAME + " - Prototype 0.1")
        self.window = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        self.canvas = pygame.Surface((LOGICAL_W, LOGICAL_H))
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
        self.houses: Set[Tuple[int, int]] = set()
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
        self.dragging = False
        self.last_mouse = (0, 0)
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
                            self.terrain[x][y].terrain = "mountain"

        # Preserve a broad starter clearing but leave some trees around it.
        sx, sy = center
        for x in range(sx - 2, sx + 3):
            for y in range(sy - 2, sy + 3):
                self.terrain[x][y].terrain = "grass"

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
                self.rocks.discard(pos)
                self.trees.add(pos)
                forced_trees += 1
                if forced_trees >= 2:
                    break

        self.notify(f"새 지형 생성 완료 · 시드 {self.seed}", 3.5)

    def center_camera(self) -> None:
        cx = MAP_W // 2
        cy = MAP_H // 2
        world_x = (cx - cy) * (TILE_W * self.zoom / 2)
        world_y = (cx + cy) * (TILE_H * self.zoom / 2)
        self.camera_x = VIEW_RECT.centerx - world_x
        self.camera_y = VIEW_RECT.centery - world_y

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
    def tile_to_screen(self, x: int, y: int) -> Tuple[float, float]:
        tw = TILE_W * self.zoom
        th = TILE_H * self.zoom
        return ((x - y) * tw / 2 + self.camera_x,
                (x + y) * th / 2 + self.camera_y)

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
        for x in range(math.floor(xf) - 1, math.floor(xf) + 2):
            for y in range(math.floor(yf) - 1, math.floor(yf) + 2):
                if 0 <= x < MAP_W and 0 <= y < MAP_H:
                    cx, cy = self.tile_to_screen(x, y)
                    nx = abs(sx - cx) / (tw / 2)
                    ny = abs(sy - cy) / (th / 2)
                    if nx + ny <= 1.03:
                        candidates.append((nx + ny, x + y, x, y))
        if not candidates:
            return None
        candidates.sort()
        _, _, x, y = candidates[0]
        return x, y

    # ------------------------------------------------------------------
    # Building / economy
    # ------------------------------------------------------------------
    def worker_can_stand(self, x: int, y: int) -> bool:
        """Return whether the worker can occupy a tile."""
        if not (0 <= x < MAP_W and 0 <= y < MAP_H) or not self.is_unlocked(x, y):
            return False
        if self.terrain[x][y].terrain != "grass":
            return False
        if (x, y) in self.trees or (x, y) in self.rocks or (x, y) in self.houses:
            return False
        return True

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
                if nxt in came_from or not self.worker_can_stand(*nxt):
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

        path = self.find_worker_path(goal)
        if path is None:
            self.notify("그곳까지 이동할 수 없어요. 길이 막혀 있는지 확인해 주세요.", 2)
            return
        if not path:
            return

        self.worker_path = path
        self.worker_moved = True

    def update_worker(self, dt: float) -> None:
        """Advance the worker smoothly along the current tile path."""
        if not self.worker_path:
            self.worker_move_progress = 0.0
            return

        self.worker_move_progress += dt / 0.18
        while self.worker_path and self.worker_move_progress >= 1.0:
            self.worker_x, self.worker_y = self.worker_path.pop(0)
            self.worker_move_progress -= 1.0
            if self.worker_path:
                nx, ny = self.worker_path[0]
                self.worker_facing = (nx - self.worker_x, ny - self.worker_y)
        if not self.worker_path:
            self.worker_move_progress = 0.0

    def can_build_on(self, x: int, y: int) -> bool:
        if not (0 <= x < MAP_W and 0 <= y < MAP_H) or not self.is_unlocked(x, y):
            return False
        if self.terrain[x][y].terrain != "grass":
            return False
        if (x, y) in self.trees or (x, y) in self.rocks:
            return False
        if (x, y) in self.roads or (x, y) in self.houses:
            return False
        if (x, y) == (self.worker_x, self.worker_y):
            return False
        return True

    def has_adjacent_road(self, x: int, y: int) -> bool:
        return any((x + dx, y + dy) in self.roads
                   for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)])

    def act_on_tile(self, x: int, y: int) -> None:
        if not self.is_unlocked(x, y):
            self.notify("아직 개척하지 않은 땅이에요. [확장]을 이용하세요.")
            return
        if self.tool == "clear":
            if (x, y) in self.trees:
                self.trees.remove((x, y))
                self.wood += 2
                self.tutorial_removed += 1
                self.notify("나무를 제거했어요! 목재 +2")
                self.check_tutorial()
            elif (x, y) in self.rocks:
                self.rocks.remove((x, y))
                self.stone += 2
                self.notify("바위를 제거했어요! 석재 +2")
            else:
                self.notify("이 타일에는 제거할 장애물이 없어요.")
        elif self.tool == "road":
            if not self.can_build_on(x, y):
                self.notify("도로는 비어 있는 잔디 위에만 놓을 수 있어요.")
                return
            if self.money < 100:
                self.notify("자금이 부족해요.")
                return
            self.money -= 100
            self.roads.add((x, y))
            if not self.tutorial_done:
                self.tutorial_roads += 1
            self.notify("도로를 건설했어요. -₩100")
            self.check_tutorial()
        elif self.tool == "house":
            if not self.can_build_on(x, y):
                self.notify("집은 비어 있는 잔디 위에 지을 수 있어요.")
                return
            if not self.has_adjacent_road(x, y):
                self.notify("집은 도로와 한 칸 이상 인접해야 해요.")
                return
            if self.money < 3000:
                self.notify("자금이 부족해요.")
                return
            self.money -= 3000
            self.houses.add((x, y))
            self.population += 4
            self.tutorial_house_built = True
            self.notify("첫 주택 완공! 주민 4명이 입주했어요.", 3.5)
            self.check_tutorial()

    def check_tutorial(self) -> None:
        if self.tutorial_done:
            return
        if self.tutorial_step == 1 and self.tutorial_removed >= 2:
            self.tutorial_step = 2
            self.tool = "road"
            self.notify("좋아요! 이제 도로 타일 3개를 배치하세요.", 4)
        elif self.tutorial_step == 2 and self.tutorial_roads >= 3:
            self.tutorial_step = 3
            self.tool = "house"
            self.notify("도로가 준비됐어요. 도로 옆에 집을 지어보세요.", 4)
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
        if self.money < cost:
            self.notify(f"확장 비용이 부족해요. 필요 자금: ₩{cost:,}")
            return
        self.money -= cost
        self.expand_level += 1
        self.notify(f"새로운 땅을 개척했어요! -₩{cost:,}", 3)

    # ------------------------------------------------------------------
    # Save / load
    # ------------------------------------------------------------------
    def save_game(self) -> None:
        data = {
            "version": 3,
            "seed": self.seed,
            "trees": [list(p) for p in sorted(self.trees)],
            "rocks": [list(p) for p in sorted(self.rocks)],
            "roads": [list(p) for p in sorted(self.roads)],
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
            self.trees = {tuple(p) for p in data.get("trees", [])}
            self.rocks = {tuple(p) for p in data.get("rocks", [])}
            self.roads = {tuple(p) for p in data.get("roads", [])}
            self.houses = {tuple(p) for p in data.get("houses", [])}
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
            self.tutorial_step = int(data.get("tutorial_step", 0))
            self.tutorial_done = bool(data.get("tutorial_done", False))
            self.tutorial_removed = int(data.get("tutorial_removed", 0))
            self.tutorial_roads = int(data.get("tutorial_roads", 0))
            self.tutorial_house_built = bool(data.get("tutorial_house_built", False))
            self.center_camera()
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
            color = C["grass_b"]
        else:
            variation = self.terrain[x][y].variation
            color = [C["grass_a"], C["grass_b"], C["grass_c"]][variation]
        pts = self.diamond(cx, cy, tw, th)
        pygame.draw.polygon(self.canvas, color, pts)
        pygame.draw.polygon(self.canvas, C["grass_edge"] if terrain != "water" else C["water_dark"], pts, 1)

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
            h = (7 + ((x * 13 + y * 7) % 5)) * self.zoom
            top = [(round(cx), round(cy - h - th / 2)),
                   (round(cx + tw / 2), round(cy - h)),
                   (round(cx), round(cy - h + th / 2)),
                   (round(cx - tw / 2), round(cy - h))]
            pygame.draw.polygon(self.canvas, C["mountain_dark"],
                                [(round(cx - tw / 2), round(cy - h)),
                                 (round(cx), round(cy - h + th / 2)),
                                 (round(cx), round(cy + th / 2)),
                                 (round(cx - tw / 2), round(cy))])
            pygame.draw.polygon(self.canvas, C["mountain_side"],
                                [(round(cx), round(cy - h + th / 2)),
                                 (round(cx + tw / 2), round(cy - h)),
                                 (round(cx + tw / 2), round(cy)),
                                 (round(cx), round(cy + th / 2))])
            pygame.draw.polygon(self.canvas, C["mountain_top"], top)
            pygame.draw.line(self.canvas, C["mountain_light"], top[0], top[3], max(1, round(self.zoom)))

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
        cx, cy = self.tile_to_screen(x, y)
        tw, th = TILE_W * self.zoom, TILE_H * self.zoom
        inset = 2 * self.zoom
        pts = self.diamond(cx, cy, tw - inset * 2, th - inset)
        pygame.draw.polygon(self.canvas, C["road_edge"], pts)
        inner = self.diamond(cx, cy - self.zoom, tw - inset * 2.5, th - inset * 1.7)
        pygame.draw.polygon(self.canvas, C["road"], inner)
        if (x + y) % 3 == 0:
            pygame.draw.rect(self.canvas, C["road_light"],
                             (round(cx - 2*self.zoom), round(cy - self.zoom),
                              max(1, round(4*self.zoom)), max(1, round(self.zoom))))

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

    def worker_screen_position(self) -> Tuple[float, float]:
        """Return the worker's interpolated world position during a step."""
        wx, wy = float(self.worker_x), float(self.worker_y)
        if self.worker_path:
            nx, ny = self.worker_path[0]
            t = clamp(self.worker_move_progress, 0.0, 1.0)
            wx += (nx - wx) * t
            wy += (ny - wy) * t
        tw, th = TILE_W * self.zoom, TILE_H * self.zoom
        return ((wx - wy) * tw / 2 + self.camera_x,
                (wx + wy) * th / 2 + self.camera_y)

    def draw_worker(self) -> None:
        """Draw a pixel worker with a two-frame walking motion."""
        cx, cy = self.worker_screen_position()
        z = self.zoom
        moving = bool(self.worker_path)
        phase = time.time() * 18.0
        stride = math.sin(phase) * 2.0 * z if moving else 0.0
        bob = abs(math.sin(phase)) * 1.25 * z if moving else 0.0
        foot_y = round(cy + 1 * z + bob)

        # Ground shadow.
        pygame.draw.ellipse(
            self.canvas, (44, 57, 48),
            (round(cx - 5*z), round(cy - 1*z), max(3, round(10*z)), max(2, round(4*z)))
        )
        # Alternating legs and swinging arms create the walking animation.
        pygame.draw.rect(self.canvas, (54, 49, 48),
                         (round(cx - 3*z - stride), foot_y - round(4*z), max(2, round(3*z)), max(3, round(4*z))))
        pygame.draw.rect(self.canvas, (54, 49, 48),
                         (round(cx + 1*z + stride), foot_y - round(4*z), max(2, round(3*z)), max(3, round(4*z))))
        pygame.draw.rect(self.canvas, (44, 91, 125),
                         (round(cx - 4*z), round(cy - 12*z + bob), max(5, round(8*z)), max(6, round(8*z))))
        pygame.draw.rect(self.canvas, (213, 157, 111),
                         (round(cx - 6*z - stride*0.35), round(cy - 11*z + bob), max(2, round(3*z)), max(5, round(5*z))))
        pygame.draw.rect(self.canvas, (213, 157, 111),
                         (round(cx + 3*z + stride*0.35), round(cy - 11*z + bob), max(2, round(3*z)), max(5, round(5*z))))
        # Face and yellow safety helmet.
        pygame.draw.rect(self.canvas, (229, 185, 143),
                         (round(cx - 3*z), round(cy - 18*z + bob), max(4, round(6*z)), max(5, round(6*z))))
        pygame.draw.rect(self.canvas, (228, 174, 55),
                         (round(cx - 4*z), round(cy - 20*z + bob), max(6, round(8*z)), max(2, round(3*z))))
        pygame.draw.rect(self.canvas, (245, 205, 95),
                         (round(cx - 1*z), round(cy - 20*z + bob), max(2, round(2*z)), max(1, round(2*z))))

    def draw_world(self) -> None:
        self.canvas.fill(C["sky"])
        self.canvas.set_clip(VIEW_RECT)

        # Unclaimed land is a true void, not a dimmed continuation of the terrain.
        # The dark background makes the edge of the owned island easy to read.
        pygame.draw.rect(self.canvas, (28, 39, 55), VIEW_RECT)

        wall_depth = max(4, round(8 * self.zoom))
        wall_color_a = (91, 63, 48)
        wall_color_b = (62, 47, 43)

        # Draw only unlocked tiles, back-to-front. The exposed southern edges
        # receive a small soil wall so the map reads as a raised land platform.
        for depth in range(MAP_W + MAP_H - 1):
            for x in range(MAP_W):
                y = depth - x
                if not (0 <= y < MAP_H) or not self.is_unlocked(x, y):
                    continue

                cx, cy = self.tile_to_screen(x, y)
                if cx < -80 or cx > LOGICAL_W + 80 or cy < TOP_H - 100 or cy > BOTTOM_Y + 50:
                    continue

                self.draw_tile(x, y)
                tw, th = TILE_W * self.zoom, TILE_H * self.zoom
                right = (round(cx + tw / 2), round(cy))
                bottom = (round(cx), round(cy + th / 2))
                left = (round(cx - tw / 2), round(cy))

                # The edge shared with (x+1, y) is the right-bottom edge.
                if not self.is_unlocked(x + 1, y):
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

                # The edge shared with (x, y+1) is the left-bottom edge.
                if not self.is_unlocked(x, y + 1):
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

                # Keep each building/object attached to its tile's depth order.
                if (x, y) in self.roads:
                    self.draw_road(x, y)
                if (x, y) in self.trees:
                    self.draw_tree(x, y)
                if (x, y) in self.rocks:
                    self.draw_rock(x, y)
                if (x, y) in self.houses:
                    self.draw_house(x, y)
                if (x, y) == (self.worker_x, self.worker_y):
                    self.draw_worker()

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
                    allowed = self.can_build_on(x, y) and self.has_adjacent_road(x, y)
                elif self.tool == "road":
                    allowed = self.can_build_on(x, y)
                elif self.tool == "clear":
                    allowed = (x, y) in self.trees or (x, y) in self.rocks
                else:
                    allowed = self.worker_can_stand(x, y)
                color = C["green"] if allowed else C["red"]
                pygame.draw.polygon(self.canvas, color, pts, max(1, round(1.2*self.zoom)))

        # Tutorial card.
        self.draw_tutorial_card()
        self.canvas.set_clip(None)

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
            (f"3. 도로 배치하기 ({min(self.tutorial_roads,3)}/3)", "[도로] 도구로 도로 3칸을 놓으세요."),
            ("4. 첫 번째 집 건설하기", "도로 옆에 [집]을 지으세요."),
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
        self.text(self.canvas, f"목재 {self.wood}", 314, 7, 9, C["muted"])
        self.text(self.canvas, f"DAY {self.day}", 385, 7, 9, C["muted"])
        self.text(self.canvas, f"시드 {self.seed}", 432, 7, 9, C["muted"])
        self.button(pygame.Rect(531, 5, 39, 21), "시드", small=True)
        self.button(pygame.Rect(573, 5, 29, 21), "저장", small=True)
        self.button(pygame.Rect(605, 5, 31, 21), "불러", small=True)

        # Bottom tool bar.
        pygame.draw.rect(self.canvas, C["panel"], (0, BOTTOM_Y, LOGICAL_W, LOGICAL_H-BOTTOM_Y))
        pygame.draw.line(self.canvas, (111, 130, 122), (0, BOTTOM_Y), (LOGICAL_W, BOTTOM_Y), 1)
        xs = [8, 94, 180, 266]
        for i, (key, name) in enumerate(zip(TOOL_KEYS, TOOL_NAMES)):
            self.button(pygame.Rect(xs[i], 294, 80, 23), name, self.tool == key)
        # Expansion is a separate utility button and does not replace the tool mode.
        cost_text = "최대" if self.expand_level >= 3 else f"₩{[5000,15000,35000][self.expand_level]:,}"
        self.button(pygame.Rect(408, 294, 86, 23), "땅 확장", small=True)
        self.text(self.canvas, cost_text, 451, 326, 9, C["gold"], center=True)
        self.text(self.canvas, f"석재 {self.stone}", 550, 326, 9, C["muted"], center=True)
        hint = TOOL_HINTS.get(self.tool, "")
        self.text(self.canvas, hint, 10, 327, 9, C["text"])

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
                tool_xs = [8, 94, 180, 266]
                for i, tx in enumerate(tool_xs):
                    if tx <= x <= tx + 80:
                        self.tool = TOOL_KEYS[i]
                        return
            if 408 <= x <= 494 and 294 <= y <= 317:
                self.expand_land()
                return
            return
        if VIEW_RECT.collidepoint(x, y):
            tile = self.screen_to_tile(x, y)
            if tile:
                if self.tool == "move":
                    self.set_worker_destination(*tile)
                else:
                    self.act_on_tile(*tile)

    def change_zoom(self, direction: int, mouse_logical: Tuple[int, int]) -> None:
        old_zoom = self.zoom
        new_idx = int(clamp(self.zoom_index + direction, 0, len(ZOOM_LEVELS) - 1))
        if new_idx == self.zoom_index:
            return
        mx, my = mouse_logical
        # Keep the tile under the cursor in approximately the same screen position.
        old_tw, old_th = TILE_W * old_zoom, TILE_H * old_zoom
        dx, dy = mx - self.camera_x, my - self.camera_y
        a, b = dx / (old_tw / 2), dy / (old_th / 2)
        tx, ty = (a+b)/2, (b-a)/2
        self.zoom_index = new_idx
        self.zoom = ZOOM_LEVELS[self.zoom_index]
        new_tw, new_th = TILE_W * self.zoom, TILE_H * self.zoom
        self.camera_x = mx - (tx-ty) * new_tw / 2
        self.camera_y = my - (tx+ty) * new_th / 2
    
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
                    elif event.key == pygame.K_1:
                        self.tool = "move"
                    elif event.key == pygame.K_2:
                        self.tool = "clear"
                    elif event.key == pygame.K_3:
                        self.tool = "road"
                    elif event.key == pygame.K_4:
                        self.tool = "house"
                    elif event.key == pygame.K_F5:
                        self.save_game()
                    elif event.key == pygame.K_F9:
                        self.load_game()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                logical = self.logical_mouse(event.pos)
                if self.modal_seed:
                    continue
                if event.button == 1:
                    self.handle_click(logical)
                elif event.button == 2:
                    self.dragging = True
                    self.last_mouse = logical
                elif event.button == 4:
                    if VIEW_RECT.collidepoint(*logical):
                        self.change_zoom(1, logical)
                elif event.button == 5:
                    if VIEW_RECT.collidepoint(*logical):
                        self.change_zoom(-1, logical)
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 2:
                    self.dragging = False
            elif event.type == pygame.MOUSEMOTION and self.dragging:
                logical = self.logical_mouse(event.pos)
                dx = logical[0] - self.last_mouse[0]
                dy = logical[1] - self.last_mouse[1]
                self.camera_x += dx
                self.camera_y += dy
                self.last_mouse = logical
            elif event.type == pygame.MOUSEWHEEL:
                logical = self.logical_mouse(pygame.mouse.get_pos())
                if VIEW_RECT.collidepoint(*logical):
                    self.change_zoom(1 if event.y > 0 else -1, logical)

    def update(self, dt: float) -> None:
        self.update_worker(dt)
        # Accelerated clock: six in-game minutes pass per real second.
        now = time.time()
        elapsed = now - self.last_clock_tick
        self.last_clock_tick = now
        self.game_minutes += elapsed * 6
        while self.game_minutes >= 24 * 60:
            self.game_minutes -= 24 * 60
            self.day += 1
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
