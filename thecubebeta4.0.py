"""
Advanced Pygame + Pymunk Simulation with GUI:
- Main menu: Start / Quit
- Customization panel: choose shape size, color, and mode (Future / Next Only)
- Alternating shapes spawn (circle/rectangle)
- Shapes fall, rotate, stack realistically
- Drag shapes with mouse
- Reset button
- Score counter with stacking bonus
"""

import sys
import random
import pygame
import pymunk
import pymunk.pygame_util

# ---------------------------
# Configuration
# ---------------------------
WIDTH, HEIGHT = 1000, 700
FPS = 60
GRAVITY = 900

BUTTON_W, BUTTON_H = 120, 40
BUTTON_MARGIN = 12

CIRCLE_MIN_R, CIRCLE_MAX_R = 12, 36
BOX_MIN_W, BOX_MAX_W = 30, 90
BOX_MIN_H, BOX_MAX_H = 20, 70

STACK_BONUS_HEIGHT = HEIGHT // 2  # Top half of screen

# Colors
WHITE = (255, 255, 255)
GRAY = (200, 200, 200)
DARK_GRAY = (50, 50, 50)
BLACK = (36, 40, 44)

PRESET_COLORS = [
    (255, 50, 50), (50, 255, 50), (50, 50, 255),
    (255, 255, 50), (255, 50, 255), (50, 255, 255)
]

SIZE_OPTIONS = {
    "Small": 0.5,
    "Medium": 1.0,
    "Large": 1.5
}

# ---------------------------
# Setup
# ---------------------------
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("the cube beta 4.0.0")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 20)
big_font = pygame.font.SysFont("Arial", 28, bold=True)

draw_options = pymunk.pygame_util.DrawOptions(screen)

# Pymunk space
space = pymunk.Space()
space.gravity = (0, GRAVITY)
static_body = space.static_body

# Ground and walls
ground_y = HEIGHT - 50
ground = pymunk.Segment(static_body, (0, ground_y), (WIDTH, ground_y), 5)
ground.friction = 1.0
ground.elasticity = 0.2
space.add(ground)

left_wall = pymunk.Segment(static_body, (0, 0), (0, HEIGHT), 5)
right_wall = pymunk.Segment(static_body, (WIDTH, 0), (WIDTH, HEIGHT), 5)
left_wall.friction = right_wall.friction = 1.0
left_wall.elasticity = right_wall.elasticity = 0.2
space.add(left_wall, right_wall)

# ---------------------------
# Global State
# ---------------------------
shapes = []
score = 0
spawn_circle_next = True

# Customization
custom_size_multiplier = 1.0
custom_color = random.choice(PRESET_COLORS)
mode_future = True  # True: Future applies to all; False: next-only
apply_next_custom = False  # for Next Only mode

dragging_body = None
mouse_grabbed_constraint = None

# GUI buttons
button_reset = pygame.Rect(WIDTH - BUTTON_W - BUTTON_MARGIN, BUTTON_MARGIN, BUTTON_W, BUTTON_H)
button_size_options = []
button_color_options = []

# Main menu buttons
menu_start = pygame.Rect(WIDTH//2 - 100, HEIGHT//2 - 50, 200, 50)
menu_quit = pygame.Rect(WIDTH//2 - 100, HEIGHT//2 + 20, 200, 50)

# ---------------------------
# Helper Functions
# ---------------------------

def create_circle(pos, radius=None):
    global shapes, score, apply_next_custom
    r = radius or int(random.randint(CIRCLE_MIN_R, CIRCLE_MAX_R) * custom_size_multiplier)
    mass = 1.0
    moment = pymunk.moment_for_circle(mass, 0, r)
    body = pymunk.Body(mass, moment)
    body.position = pos
    shape = pymunk.Circle(body, r)
    shape.friction = 0.8
    shape.elasticity = 0.2
    if mode_future or apply_next_custom:
        shape.color = custom_color + (255,)
    else:
        shape.color = tuple(random.randint(40, 255) for _ in range(3)) + (255,)
    space.add(body, shape)
    shapes.append((body, shape))
    score_increment(pos)
    if not mode_future:
        apply_next_custom = False

def create_box(pos, size=None):
    global shapes, score, apply_next_custom
    w = random.randint(BOX_MIN_W, BOX_MAX_W)
    h = random.randint(BOX_MIN_H, BOX_MAX_H)
    w = int(w * custom_size_multiplier)
    h = int(h * custom_size_multiplier)
    mass = 1.0
    moment = pymunk.moment_for_box(mass, (w, h))
    body = pymunk.Body(mass, moment)
    body.position = pos
    verts = [(-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2)]
    shape = pymunk.Poly(body, verts)
    shape.friction = 0.9
    shape.elasticity = 0.1
    if mode_future or apply_next_custom:
        shape.color = custom_color + (255,)
    else:
        shape.color = tuple(random.randint(40, 255) for _ in range(3)) + (255,)
    space.add(body, shape)
    shapes.append((body, shape))
    score_increment(pos)
    if not mode_future:
        apply_next_custom = False

def score_increment(pos):
    global score
    score += 1
    # Stacking bonus if above threshold
    if pos[1] < STACK_BONUS_HEIGHT:
        score += 1  # 1 bonus per shape above threshold

def reset_simulation():
    global shapes, score
    for body, shape in shapes:
        try:
            space.remove(shape)
            space.remove(body)
        except:
            pass
    shapes = []
    score = 0

def start_drag(pos):
    global dragging_body, mouse_grabbed_constraint
    nearest = space.point_query_nearest(pos, 5, pymunk.ShapeFilter())
    if nearest and nearest.shape.body.body_type == pymunk.Body.DYNAMIC:
        dragging_body = nearest.shape.body
        mouse_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        mouse_body.position = pos
        joint = pymunk.PivotJoint(mouse_body, dragging_body, (0,0), dragging_body.world_to_local(pos))
        joint.max_force = 1e6
        joint.error_bias = (1 - 0.15) ** FPS
        space.add(mouse_body, joint)
        mouse_grabbed_constraint = (mouse_body, joint)

def update_drag(pos):
    if mouse_grabbed_constraint:
        mouse_body, _ = mouse_grabbed_constraint
        mouse_body.position = pos

def end_drag():
    global dragging_body, mouse_grabbed_constraint
    if mouse_grabbed_constraint:
        mouse_body, joint = mouse_grabbed_constraint
        try: space.remove(joint)
        except: pass
        try: space.remove(mouse_body)
        except: pass
    dragging_body = None
    mouse_grabbed_constraint = None

def draw_gui():
    # Reset button
    pygame.draw.rect(screen, GRAY, button_reset, border_radius=6)
    pygame.draw.rect(screen, DARK_GRAY, button_reset, 2, border_radius=6)
    txt = big_font.render("Reset", True, BLACK)
    screen.blit(txt, (button_reset.x + (BUTTON_W - txt.get_width())//2,
                      button_reset.y + (BUTTON_H - txt.get_height())//2))
    # Score
    score_text = font.render(f"Score: {score}", True, WHITE)
    screen.blit(score_text, (BUTTON_MARGIN, BUTTON_MARGIN))
    # Customization Panel
    y = BUTTON_MARGIN + 50
    size_text = font.render("Size:", True, WHITE)
    screen.blit(size_text, (BUTTON_MARGIN, y))
    x = BUTTON_MARGIN + 60
    for name, mult in SIZE_OPTIONS.items():
        rect = pygame.Rect(x, y, 60, 30)
        button_size_options.append((rect, name))
        pygame.draw.rect(screen, GRAY if custom_size_multiplier != mult else DARK_GRAY, rect)
        pygame.draw.rect(screen, BLACK, rect, 2)
        txt = font.render(name, True, WHITE)
        screen.blit(txt, (rect.x + 5, rect.y + 5))
        x += 70
    y += 40
    # Color selection
    color_text = font.render("Color:", True, WHITE)
    screen.blit(color_text, (BUTTON_MARGIN, y))
    x = BUTTON_MARGIN + 60
    for c in PRESET_COLORS:
        rect = pygame.Rect(x, y, 30, 30)
        button_color_options.append((rect, c))
        pygame.draw.rect(screen, c, rect)
        if custom_color == c:
            pygame.draw.rect(screen, WHITE, rect, 2)
        x += 40
    y += 40
    # Mode toggle
    mode_text = font.render("Mode: " + ("Future" if mode_future else "Next Only"), True, WHITE)
    screen.blit(mode_text, (BUTTON_MARGIN, y))

# ---------------------------
# Main Menu
# ---------------------------
def main_menu():
    running = True
    while running:
        screen.fill(BLACK)
        # Buttons
        pygame.draw.rect(screen, GRAY, menu_start)
        pygame.draw.rect(screen, DARK_GRAY, menu_start, 3)
        pygame.draw.rect(screen, GRAY, menu_quit)
        pygame.draw.rect(screen, DARK_GRAY, menu_quit, 3)
        screen.blit(big_font.render("play", True, BLACK), (menu_start.x+10, menu_start.y+10))
        screen.blit(big_font.render("Quit", True, BLACK), (menu_quit.x+70, menu_quit.y+10))
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if menu_start.collidepoint(event.pos):
                    running = False
                elif menu_quit.collidepoint(event.pos):
                    pygame.quit(); sys.exit()
        clock.tick(FPS)

# ---------------------------
# Main Loop
# ---------------------------
def main_loop():
    global spawn_circle_next, custom_size_multiplier, custom_color, mode_future, apply_next_custom
    running = True
    while running:
        dt = 1.0 / FPS
        mouse_pos = pygame.mouse.get_pos()
        world_pos = pymunk.pygame_util.from_pygame(mouse_pos, screen)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    # Check reset button
                    if button_reset.collidepoint(mouse_pos):
                        reset_simulation()
                        continue
                    # Check size buttons
                    for rect, name in button_size_options:
                        if rect.collidepoint(mouse_pos):
                            custom_size_multiplier = SIZE_OPTIONS[name]
                    # Check color buttons
                    for rect, c in button_color_options:
                        if rect.collidepoint(mouse_pos):
                            custom_color = c
                            if not mode_future:
                                apply_next_custom = True
                    # Check Mode toggle click (toggle)
                    # We'll use the mode text area approx
                    if pygame.Rect(BUTTON_MARGIN, BUTTON_MARGIN+130, 200, 30).collidepoint(mouse_pos):
                        mode_future = not mode_future
                    # Attempt to drag
                    nearest = space.point_query_nearest(world_pos, 2, pymunk.ShapeFilter())
                    if nearest and nearest.shape.body.body_type == pymunk.Body.DYNAMIC:
                        start_drag(world_pos)
                    else:
                        # Spawn new shape
                        if spawn_circle_next:
                            create_circle(world_pos)
                        else:
                            create_box(world_pos)
                        spawn_circle_next = not spawn_circle_next
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    end_drag()
            elif event.type == pygame.MOUSEMOTION:
                if mouse_grabbed_constraint:
                    update_drag(world_pos)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    reset_simulation()
        # Physics step
        space.step(dt)
        # Clear screen
        screen.fill(BLACK)
        # Draw Pymunk objects
        space.debug_draw(draw_options)
        # Draw GUI
        draw_gui()
        pygame.display.flip()
        clock.tick(FPS)
    pygame.quit(); sys.exit()

if __name__ == "__main__":
    main_menu()
    main_loop()
