import random
import tkinter as tk

# Константы конфигурации
WIDTH, HEIGHT = 600, 560  # Увеличили высоту на 40 px под верхнюю панель с таймером
GRID = 40
FPS_DELAY = 30  # ~33 FPS
ROUND_TIME = 25.0  # Секунд на одну попытку

# Пресеты объектов: (ширина, цвет)
CAR_TYPES = [
    (45, "#E74C3C"),   # Спорткар
    (60, "#3498DB"),   # Седан
    (70, "#F1C40F"),   # Такси / Минивэн
    (105, "#E67E22"),  # Грузовик
    (55, "#9B59B6"),   # Хэтчбек
]

LOG_TYPES = [
    (80, "#A0522D"),   # Короткое бревно
    (115, "#8B4513"),  # Среднее бревно
    (150, "#6E3610"),  # Длинное бревно
]


class GameObject:
    """Базовый класс для всех игровых объектов на холсте."""

    def __init__(self, canvas, x, y, width, height, color, shape="rect"):
        self.canvas = canvas
        self.width = width
        self.height = height
        if shape == "oval":
            self.id = canvas.create_oval(
                x, y, x + width, y + height, fill=color, outline="#1e1e1e", width=2
            )
        else:
            self.id = canvas.create_rectangle(
                x, y, x + width, y + height, fill=color, outline="#1e1e1e", width=2
            )

    def get_bbox(self):
        return self.canvas.coords(self.id)

    def move(self, dx, dy):
        self.canvas.move(self.id, dx, dy)

    def delete(self):
        self.canvas.delete(self.id)

    def intersects(self, other):
        """AABB-коллизия с небольшим отступом (4 px) для честного хитбокса."""
        x1, y1, x2, y2 = self.get_bbox()
        ox1, oy1, ox2, oy2 = other.get_bbox()
        return not (x2 - 4 <= ox1 or x1 + 4 >= ox2 or y2 - 4 <= oy1 or y1 + 4 >= oy2)


class Obstacle(GameObject):
    """Движущийся объект (машина или бревно)."""

    def __init__(self, canvas, x, y, width, color, is_log=False):
        super().__init__(canvas, x, y + 4, width, GRID - 8, color)
        self.is_log = is_log


class BonusFly(GameObject):
    """Бонусная муха: дает +50 очков и +5 секунд к таймеру."""

    def __init__(self, canvas):
        col = random.randint(1, (WIDTH // GRID) - 2)
        # Появляется на островке безопасности (ряд 7) или на дороге (ряды 8–12)
        row = random.choice([7, 8, 9, 10, 11, 12])
        x = col * GRID + 11
        y = row * GRID + 11
        super().__init__(canvas, x, y, 18, 18, "#FFD700", shape="oval")
        self.ttl = 260  # Исчезнет примерно через 8 секунд, если не подобрать


class Lane:
    """Полоса движения, отвечающая за случайную генерацию и удаление объектов."""

    def __init__(self, canvas, row, is_log):
        self.canvas = canvas
        self.row = row
        self.is_log = is_log
        self.obstacles = []

        self.direction = random.choice([-1, 1])
        self.base_speed = random.uniform(1.8, 3.6) if is_log else random.uniform(2.5, 5.2)
        self.spawn_timer = 0

    def get_current_speed(self, speed_mult):
        return self.base_speed * self.direction * speed_mult

    def update(self, speed_mult):
        velocity = self.get_current_speed(speed_mult)

        alive = []
        for obs in self.obstacles:
            obs.move(velocity, 0)
            x1, _, x2, _ = obs.get_bbox()
            if (self.direction > 0 and x1 > WIDTH + 40) or (self.direction < 0 and x2 < -40):
                obs.delete()
            else:
                alive.append(obs)
        self.obstacles = alive

        self.spawn_timer -= 1
        if self.spawn_timer <= 0:
            self._spawn_obstacle(abs(velocity))

    def _spawn_obstacle(self, abs_speed):
        if self.is_log:
            width, color = random.choice(LOG_TYPES)
            gap = random.randint(65, 145)
        else:
            width, color = random.choice(CAR_TYPES)
            gap = random.randint(90, 220)

        start_x = -width - 10 if self.direction > 0 else WIDTH + 10
        obs = Obstacle(self.canvas, start_x, self.row * GRID, width, color, self.is_log)
        self.obstacles.append(obs)
        self.spawn_timer = int((width + gap) / max(abs_speed, 0.5))

    def clear(self):
        for obs in self.obstacles:
            obs.delete()
        self.obstacles.clear()


class Frog(GameObject):
    """Игрок (лягушка), перемещающийся прыжками по сетке."""

    def __init__(self, canvas):
        self.start_x = (WIDTH // 2 // GRID) * GRID + 6
        self.start_y = HEIGHT - GRID + 6
        super().__init__(canvas, self.start_x, self.start_y, GRID - 12, GRID - 12, "#32CD32")

    def reset_position(self):
        self.canvas.coords(
            self.id,
            self.start_x,
            self.start_y,
            self.start_x + self.width,
            self.start_y + self.height,
        )

    def jump(self, dx, dy):
        x1, y1, x2, y2 = self.get_bbox()
        new_x1, new_y1 = x1 + dx * GRID, y1 + dy * GRID
        # Не даем запрыгнуть на верхнюю панель HUD (ряды 0 и 1)
        if 0 <= new_x1 <= WIDTH - self.width and GRID * 2 <= new_y1 <= HEIGHT - self.height:
            self.move(dx * GRID, dy * GRID)


class FroggerGame:
    """Главный контроллер игры."""

    def __init__(self, root):
        self.root = root
        self.root.title("Frogger — Динамическая версия")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg="#181818", highlightthickness=0)
        self.canvas.pack()

        self.score = 0
        self.high_score = 0
        self.lives = 3
        self.level = 1
        self.time_left = ROUND_TIME
        self.is_game_over = False
        self.lanes = []
        self.bonus_fly = None
        self.fly_spawn_cooldown = 120

        self._draw_background()
        self._init_hud()
        self._init_lanes()

        self.frog = Frog(self.canvas)

        # Единый обработчик клавиш (работает и на EN, и на RU раскладке)
        self.root.bind("<KeyPress>", self.on_key_press)

        self.game_loop()

    def _get_speed_mult(self):
        return 1.0 + (self.level - 1) * 0.15

    def _get_hud_str(self):
        return f"Ур: {self.level}  |  Очки: {self.score}  |  Рекорд: {self.high_score}  |  Жизни: {self.lives}"

    def _init_hud(self):
        """Создает текстовую панель и полоску таймера в верхней части экрана."""
        self.hud_text = self.canvas.create_text(
            15, 22, anchor="w", fill="white", font=("Arial", 12, "bold"), text=self._get_hud_str()
        )
        self.timer_label = self.canvas.create_text(
            15, 56, anchor="w", fill="#CCCCCC", font=("Arial", 10, "bold"), text="Время:"
        )
        # Фон полоски таймера
        self.canvas.create_rectangle(75, 48, WIDTH - 140, 64, fill="#333333", outline="#555555")
        # Заполнение полоски таймера
        self.timer_bar = self.canvas.create_rectangle(75, 48, WIDTH - 140, 64, fill="#2ECC71", outline="")
        self.canvas.create_text(
            WIDTH - 15, 56, anchor="e", fill="#999999", font=("Arial", 10), text="Пробел — рестарт"
        )

    def _update_timer_ui(self):
        ratio = max(0.0, min(1.0, self.time_left / ROUND_TIME))
        bar_max_width = (WIDTH - 140) - 75
        current_x2 = 75 + bar_max_width * ratio

        if ratio > 0.5:
            color = "#2ECC71"  # Зеленый
        elif ratio > 0.25:
            color = "#F1C40F"  # Желтый
        else:
            color = "#E74C3C"  # Красный

        self.canvas.coords(self.timer_bar, 75, 48, current_x2, 64)
        self.canvas.itemconfig(self.timer_bar, fill=color)

    def _draw_background(self):
        # Ряды 0–1: верхняя панель HUD
        self.canvas.create_rectangle(0, GRID * 2, WIDTH, GRID * 3, fill="#2E8B57", outline="")   # Финиш (ряд 2)
        self.canvas.create_rectangle(0, GRID * 3, WIDTH, GRID * 7, fill="#1E5F8A", outline="")   # Река (ряды 3–6)
        self.canvas.create_rectangle(0, GRID * 7, WIDTH, GRID * 8, fill="#8B7355", outline="")   # Островок (ряд 7)
        self.canvas.create_rectangle(0, GRID * 8, WIDTH, GRID * 13, fill="#333333", outline="")  # Дорога (ряды 8–12)
        self.canvas.create_rectangle(0, GRID * 13, WIDTH, GRID * 14, fill="#8B7355", outline="") # Старт (ряд 13)
        for row in range(9, 13):
            self.canvas.create_line(0, row * GRID, WIDTH, row * GRID, fill="#777777", dash=(10, 10))

    def _init_lanes(self):
        for lane in self.lanes:
            lane.clear()
        self.lanes.clear()

        for row in range(3, 7):
            self.lanes.append(Lane(self.canvas, row, is_log=True))
        for row in range(8, 13):
            self.lanes.append(Lane(self.canvas, row, is_log=False))

        for i in range(1, 4):
            self.lanes[i].direction = -self.lanes[i - 1].direction

        for _ in range(150):
            for lane in self.lanes:
                lane.update(1.0)

    def on_key_press(self, event):
        key = event.keysym
        char = event.char.lower()

        if key == "space":
            self.restart_game()
            return

        if self.is_game_over:
            return

        if key == "Up" or char in ("w", "ц"):
            self.frog.jump(0, -1)
        elif key == "Down" or char in ("s", "ы"):
            self.frog.jump(0, 1)
        elif key == "Left" or char in ("a", "ф"):
            self.frog.jump(-1, 0)
        elif key == "Right" or char in ("d", "в"):
            self.frog.jump(1, 0)

    def _update_bonus_fly(self):
        """Управляет появлением, исчезновением и сбором бонусной мухи."""
        if self.bonus_fly is None:
            self.fly_spawn_cooldown -= 1
            if self.fly_spawn_cooldown <= 0:
                self.bonus_fly = BonusFly(self.canvas)
                self.fly_spawn_cooldown = random.randint(150, 300)
        else:
            self.bonus_fly.ttl -= 1
            if self.frog.intersects(self.bonus_fly):
                self.score += 50
                self.high_score = max(self.high_score, self.score)
                self.time_left = min(ROUND_TIME, self.time_left + 5.0)
                self.canvas.itemconfig(self.hud_text, text=self._get_hud_str())
                self.bonus_fly.delete()
                self.bonus_fly = None
            elif self.bonus_fly.ttl <= 0:
                self.bonus_fly.delete()
                self.bonus_fly = None

    def lose_life(self, reason="Потеряна жизнь"):
        self.lives -= 1
        self.time_left = ROUND_TIME
        self.canvas.itemconfig(self.hud_text, text=self._get_hud_str())
        if self.lives <= 0:
            self.is_game_over = True
            self.canvas.create_rectangle(90, 220, 510, 350, fill="#111111", outline="white", width=2, tags="ui")
            self.canvas.create_text(
                WIDTH // 2, 265, fill="#E74C3C", font=("Arial", 22, "bold"), text="ИГРА ОКОНЧЕНА", tags="ui"
            )
            self.canvas.create_text(
                WIDTH // 2, 310, fill="white", font=("Arial", 13), text="Нажми ПРОБЕЛ для перезапуска", tags="ui"
            )
        else:
            self.frog.reset_position()

    def check_state(self):
        fx1, fy1, fx2, fy2 = self.frog.get_bbox()
        frog_center_y = (fy1 + fy2) / 2
        speed_mult = self._get_speed_mult()

        # 1. Финиш (ряд 2)
        if frog_center_y < GRID * 3:
            time_bonus = int(self.time_left * 5)
            self.score += 100 * self.level + time_bonus
            self.high_score = max(self.high_score, self.score)
            self.level += 1
            self.time_left = ROUND_TIME
            self.canvas.itemconfig(self.hud_text, text=self._get_hud_str())
            self.frog.reset_position()
            return

        # 2. Река (ряды 3–6)
        if GRID * 3 <= frog_center_y < GRID * 7:
            on_log = False
            for lane in self.lanes:
                if not lane.is_log:
                    continue
                for obs in lane.obstacles:
                    if self.frog.intersects(obs):
                        on_log = True
                        self.frog.move(lane.get_current_speed(speed_mult), 0)
                        break
                if on_log:
                    break

            fx1, _, fx2, _ = self.frog.get_bbox()
            if not on_log or fx1 < 0 or fx2 > WIDTH:
                self.lose_life()
            return

        # 3. Дорога (ряды 8–12)
        if GRID * 8 <= frog_center_y < GRID * 13:
            for lane in self.lanes:
                if lane.is_log:
                    continue
                for obs in lane.obstacles:
                    if self.frog.intersects(obs):
                        self.lose_life()
                        return

    def restart_game(self):
        self.canvas.delete("ui")
        if self.bonus_fly:
            self.bonus_fly.delete()
            self.bonus_fly = None
        self.score = 0
        self.lives = 3
        self.level = 1
        self.time_left = ROUND_TIME
        self.is_game_over = False
        self._init_lanes()
        self.canvas.itemconfig(self.hud_text, text=self._get_hud_str())
        self._update_timer_ui()
        self.frog.reset_position()

    def game_loop(self):
        if not self.is_game_over:
            # Обновление таймера
            self.time_left -= FPS_DELAY / 1000.0
            self._update_timer_ui()
            if self.time_left <= 0:
                self.lose_life()

            # Обновление трафика и бонусов
            speed_mult = self._get_speed_mult()
            for lane in self.lanes:
                lane.update(speed_mult)

            self._update_bonus_fly()
            if self.bonus_fly:
                self.canvas.tag_raise(self.bonus_fly.id)
            self.canvas.tag_raise(self.frog.id)
            self.check_state()

        self.root.after(FPS_DELAY, self.game_loop)


if __name__ == "__main__":
    root = tk.Tk()
    game = FroggerGame(root)
    root.mainloop()