import pygame, pymunk
import json, os, sys, random, threading, socket
import pygame, os, sys

click_sound = None
music = None

def resource_path(name):
    """Resolve bundled assets and the legacy folder's shared game assets."""
    bundled = getattr(sys, "_MEIPASS", None)
    candidates = []
    if bundled:
        candidates.append(os.path.join(bundled, name))
    candidates.extend((
        os.path.join(os.path.dirname(__file__), name),
        os.path.join(os.path.dirname(__file__), "..", name),
    ))
    return next((path for path in candidates if os.path.isfile(path)), name)

pygame.init()
pygame.mixer.init()

try:
    click_sound = pygame.mixer.Sound(resource_path("click.mp3"))
except:
    pass


# ---------------- INIT ----------------
pygame.init()
WIDTH, HEIGHT = 1000, 700
FPS = 60
current_shape = "box"  # "box" or "circle"

screen = None
clock = pygame.time.Clock()
font = pygame.font.SysFont("arial", 20)
big_font = pygame.font.SysFont("arial", 36, bold=True)

# ---------------- SETTINGS ----------------
SETTINGS_FILE = "settings.json"
DEFAULT_SETTINGS = {
    "theme": "christmas",
    "gravity": 900,
    "difficulty": "normal",
    "graphics": "high",
    "fullscreen": False
}

def save_settings(data):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()
    with open(SETTINGS_FILE, "r") as f:
        data = json.load(f)
    for k,v in DEFAULT_SETTINGS.items():
        if k not in data:
            data[k] = v
    save_settings(data)
    return data

settings = load_settings()

# ---------------- DISPLAY ----------------
def apply_display_mode():
    global screen
    flags = pygame.FULLSCREEN if settings.get("fullscreen", False) else 0
    screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)

apply_display_mode()
pygame.display.set_caption("The Cube Beta v5.1 Christmas")

# ---------------- COLORS ----------------
THEMES = {
    "dark": (25, 30, 40),
    "light": (220, 220, 230),
    "blue": (40, 60, 90),
    "christmas": (10, 20, 40)
}
WHITE = (240, 240, 240)
BLACK = (0,0,0)

# ---------------- SOUNDS ----------------
pygame.mixer.init()
try:
    click_sound = pygame.mixer.Sound(resource_path("click.mp3"))
    bg_music = pygame.mixer.Sound(resource_path("christmas_music.mp3"))
    bg_music.play(loops=-1)
except pygame.error:
    click_sound = None
    bg_music = None
    print("Warning: Sound files missing!")

def play_click():
    if click_sound is not None:
        click_sound.play()

# ---------------- SNOW ----------------
snowflakes = [[random.randint(0, WIDTH), random.randint(0, HEIGHT), random.randint(1,3)] for _ in range(120)]

# ---------------- BUTTON ----------------
class Button:
    def __init__(self, rect, text, action):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.action = action

    def draw(self, mouse):
        color = (180,180,255) if self.rect.collidepoint(mouse) else (120,120,220)
        pygame.draw.rect(screen, color, self.rect, border_radius=8)
        pygame.draw.rect(screen, BLACK, self.rect, 2, border_radius=8)
        label = font.render(self.text, True, BLACK)
        screen.blit(label, (self.rect.centerx - label.get_width()//2,
                            self.rect.centery - label.get_height()//2))

    def click(self, mouse):
        if self.rect.collidepoint(mouse):
            play_click()
            self.action()

# ---------------- PHYSICS ----------------
def make_space():
    space = pymunk.Space()
    space.gravity = (0, settings["gravity"])
    floor = pymunk.Segment(space.static_body, (0, HEIGHT-40), (WIDTH, HEIGHT-40), 5)
    floor.friction = 1.0
    left_wall = pymunk.Segment(space.static_body, (0,0), (0, HEIGHT), 5)
    left_wall.friction = 1.0
    right_wall = pymunk.Segment(space.static_body, (WIDTH,0), (WIDTH, HEIGHT), 5)
    right_wall.friction = 1.0
    space.add(floor, left_wall, right_wall)
    return space

def spawn_shape(space, x, y, color):
    mass = 1 if settings["difficulty"]=="easy" else 2
    size = 40
    global current_shape
    if current_shape == "box":
        body = pymunk.Body(mass, pymunk.moment_for_box(mass, (size,size)))
        body.position = x, y
        shape = pymunk.Poly.create_box(body, (size,size))
    else:
        body = pymunk.Body(mass, pymunk.moment_for_circle(mass,0,size//2))
        body.position = x, y
        shape = pymunk.Circle(body, size//2)
    shape.color = color + (255,)
    shape.friction = 0.9
    space.add(body, shape)


def draw_space(screen, space):
    """Draw Pymunk shapes without the optional pymunk.pygame_util module."""
    for shape in space.shapes:
        color = tuple(getattr(shape, "color", (235, 235, 245, 255)))[:3]
        if isinstance(shape, pymunk.Circle):
            position = shape.body.local_to_world(shape.offset)
            pygame.draw.circle(screen, color, (round(position.x), round(position.y)), round(shape.radius))
        elif isinstance(shape, pymunk.Poly):
            points = [shape.body.local_to_world(vertex) for vertex in shape.get_vertices()]
            pygame.draw.polygon(screen, color, [(round(point.x), round(point.y)) for point in points])
        elif isinstance(shape, pymunk.Segment):
            start = shape.body.local_to_world(shape.a)
            end = shape.body.local_to_world(shape.b)
            pygame.draw.line(screen, color, (round(start.x), round(start.y)), (round(end.x), round(end.y)), max(1, round(shape.radius * 2)))

# ---------------- SIMULATION ----------------
def simulation(multiplayer=False, is_host=False, conn=None):
    space = make_space()
    running = True
    score = 0

    while running:
        mouse = pygame.mouse.get_pos()
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE: running = False
                if e.key == pygame.K_F11:
                    settings["fullscreen"] = not settings["fullscreen"]
                    apply_display_mode()
            if e.type == pygame.MOUSEBUTTONDOWN:
                if settings.get("theme")=="christmas":
                    color = random.choice([(255,0,0),(0,255,0)])
                else:
                    color = (random.randint(60,255), random.randint(60,255), random.randint(60,255))
                spawn_shape(space, mouse[0], mouse[1], color)
                play_click()

        space.step(1/FPS)
        screen.fill(THEMES[settings["theme"]])

        # Snowflakes
        for s in snowflakes:
            pygame.draw.circle(screen, (255,255,255), (s[0], s[1]), s[2])
            s[1] += 1
            if s[1] > HEIGHT: s[1]=0; s[0]=random.randint(0, WIDTH)

        draw_space(screen, space)

        # Score: shapes above height 500
        score = sum(1 for s in space.shapes if getattr(s.body,"position",(0,0))[1]<500)
        screen.blit(font.render(f"Score: {score}", True, WHITE), (10,10))

        # Reset button
        reset_rect = pygame.Rect(WIDTH-110,10,100,40)
        pygame.draw.rect(screen,(200,50,50),reset_rect,border_radius=8)
        screen.blit(font.render("RESET", True, WHITE), (reset_rect.x+20, reset_rect.y+10))
        if pygame.mouse.get_pressed()[0] and reset_rect.collidepoint(mouse):
            for s in space.shapes[:]:
                if hasattr(s,"body"): space.remove(s,s.body)

        pygame.display.flip()
        clock.tick(FPS)

# ---------------- SETTINGS MENU ----------------
def settings_menu():
    def theme():
        keys = list(THEMES.keys())
        settings["theme"]=keys[(keys.index(settings["theme"])+1)%len(keys)]
        play_click()
    def grav_up(): settings["gravity"]+=100; play_click()
    def grav_dn(): settings["gravity"]=max(100,settings["gravity"]-100); play_click()
    def toggle_fullscreen(): settings["fullscreen"]=not settings["fullscreen"]; apply_display_mode(); play_click()
    def toggle_shape(): global current_shape; current_shape="circle" if current_shape=="box" else "box"; play_click()
    def back(): save_settings(settings); main_menu()

    buttons=[
        Button((350,250,300,40),"Change Theme", theme),
        Button((350,300,300,40),"Gravity +", grav_up),
        Button((350,350,300,40),"Gravity -", grav_dn),
        Button((350,400,300,40),"Toggle Fullscreen", toggle_fullscreen),
        Button((350,430,300,40),"Toggle Shape", toggle_shape),
        Button((350,490,300,40),"Back", back)
    ]

    while True:
        mouse=pygame.mouse.get_pos()
        screen.fill(THEMES[settings["theme"]])
        y=180
        for k,v in settings.items():
            screen.blit(font.render(f"{k}: {v}", True, WHITE), (350,y)); y+=22
        for b in buttons: b.draw(mouse)
        pygame.display.flip()
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.MOUSEBUTTONDOWN:
                for b in buttons: b.click(mouse)
        clock.tick(60)

# ---------------- MAIN MENU ----------------
def main_menu():
    def single(): simulation()
    def settings_btn(): settings_menu()
    buttons=[
        Button((WIDTH//2-150,260,300,50),"Singleplayer", single),
        Button((WIDTH//2-150,470,300,50),"Settings", settings_btn),
        Button((WIDTH//2-150,540,300,50),"Quit", lambda: sys.exit())
    ]
    while True:
        mouse=pygame.mouse.get_pos()
        screen.fill(THEMES[settings["theme"]])
        # Snow
        for s in snowflakes:
            pygame.draw.circle(screen, (255,255,255), (s[0],s[1]), s[2])
            s[1]+=1
            if s[1]>HEIGHT: s[1]=0; s[0]=random.randint(0, WIDTH)
        # Title
        title=big_font.render("The Cube Beta v5.1 Christmas", True, WHITE)
        screen.blit(title, (WIDTH//2-title.get_width()//2,170))
        for b in buttons: b.draw(mouse)
        pygame.display.flip()
        for e in pygame.event.get():
            if e.type==pygame.QUIT: pygame.quit(); sys.exit()
            if e.type==pygame.MOUSEBUTTONDOWN:
                for b in buttons: b.click(mouse)
        clock.tick(60)

# ---------------- START ----------------
main_menu()
