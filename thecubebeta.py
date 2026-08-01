"""
Pygame + Pymunk demo:
- Click anywhere to spawn a shape (alternates between circle and rectangle).
- Drag shapes by clicking on them.
- Shapes fall, rotate, and stack realistically.
- On-screen GUI button "Reset" clears all shapes (keeps ground).
- Score displayed top-left (increments per created shape).
"""

import sys
import random
import math
import pygame
import pymunk
import pymunk.pygame_util

# ---------------------------
# Configuration
# ---------------------------
WIDTH, HEIGHT = 1000, 700
FPS = 60
GRAVITY = 900  # pixels/s^2 downward

BUTTON_W, BUTTON_H = 120, 40
BUTTON_MARGIN = 12

CIRCLE_MIN_R, CIRCLE_MAX_R = 12, 36
BOX_MIN_W, BOX_MAX_W = 30, 90
BOX_MIN_H, BOX_MAX_H = 20, 70

# ---------------------------
# Setup Pygame & Pymunk
# ---------------------------
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("the cube beta")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 20)
big_font = pygame.font.SysFont("Arial", 28, bold=True)

# Pymunk space
space = pymunk.Space()
space.gravity = (0, GRAVITY)
draw_options = pymunk.pygame_util.DrawOptions(screen)

# Convert helpers
from_pygame = pymunk.pygame_util.from_pygame
to_pygame = pymunk.pygame_util.to_pygame

# ---------------------------
# Ground and walls (static)
# ---------------------------
static_body = space.static_body
ground_y = HEIGHT - 50
ground = pymunk.Segment(static_body, (0, ground_y), (WIDTH, ground_y), 5)
ground.friction = 1.0
ground.elasticity = 0.2
space.add(ground)

# optional side walls so shapes cannot escape horizontally
left_wall = pymunk.Segment(static_body, (0, 0), (0, HEIGHT), 5)
right_wall = pymunk.Segment(static_body, (WIDTH, 0), (WIDTH, HEIGHT), 5)
left_wall.friction = right_wall.friction = 1.0
left_wall.elasticity = right_wall.elasticity = 0.2
space.add(left_wall, right_wall)

# ---------------------------
# State
# ---------------------------
shapes = []  # list of pymunk shapes (we'll only track dynamic shapes here)
score = 0
spawn_circle_next = True  # alternate between circle and box

dragging_body = None
mouse_joint = None
mouse_grabbed_constraint = None

# GUI button rect (top-right)
button_rect = pygame.Rect(WIDTH - BUTTON_W - BUTTON_MARGIN, BUTTON_MARGIN, BUTTON_W, BUTTON_H)

# ---------------------------
# Helper functions to create shapes
# ---------------------------
def create_circle(world_pos, radius=None, mass=1.0):
    global shapes
    if radius is None:
        radius = random.randint(CIRCLE_MIN_R, CIRCLE_MAX_R)
    mass = mass
    moment = pymunk.moment_for_circle(mass, 0, radius)
    body = pymunk.Body(mass, moment)
    body.position = world_pos
    shape = pymunk.Circle(body, radius)
    shape.friction = 0.8
    shape.elasticity = 0.2
    shape.color = tuple(random.randint(40, 255) for _ in range(3)) + (255,)
    space.add(body, shape)
    shapes.append((body, shape))
    return body, shape

def create_box(world_pos, size=None, mass=1.0):
    global shapes
    if size is None:
        w = random.randint(BOX_MIN_W, BOX_MAX_W)
        h = random.randint(BOX_MIN_H, BOX_MAX_H)
        size = (w, h)
    w, h = size
    mass = mass
    moment = pymunk.moment_for_box(mass, (w, h))
    body = pymunk.Body(mass, moment)
    body.position = world_pos
    # Create poly as box centered on origin
    verts = [(-w/2, -h/2), (w/2, -h/2), (w/2, h/2), (-w/2, h/2)]
    shape = pymunk.Poly(body, verts)
    shape.friction = 0.9
    shape.elasticity = 0.1
    shape.color = tuple(random.randint(40, 255) for _ in range(3)) + (255,)
    space.add(body, shape)
    shapes.append((body, shape))
    return body, shape

def reset_simulation():
    global shapes, score
    # Remove dynamic shapes from space
    for body, shape in list(shapes):
        try:
            space.remove(shape)
        except Exception:
            pass
        try:
            space.remove(body)
        except Exception:
            pass
    shapes = []
    score = 0

# ---------------------------
# Mouse dragging helpers
# ---------------------------
def start_drag(world_pos):
    global dragging_body, mouse_joint, mouse_grabbed_constraint
    # Query nearest shape to the mouse position
    nearest = space.point_query_nearest(world_pos, 5, pymunk.ShapeFilter())
    if nearest and nearest.shape.body.body_type == pymunk.Body.DYNAMIC:
        dragging_body = nearest.shape.body
        # Use a PivotJoint between a kinematic "mouse" body and the body to drag.
        mouse_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        mouse_body.position = world_pos
        mouse_joint = pymunk.PivotJoint(mouse_body, dragging_body, (0, 0), dragging_body.world_to_local(world_pos))
        mouse_joint.max_force = 1e6
        mouse_joint.error_bias = (1 - 0.15) ** FPS
        space.add(mouse_body, mouse_joint)
        # store the mouse kinematic body in the joint object so we can move it later and remove it later
        mouse_grabbed_constraint = (mouse_body, mouse_joint)

def update_drag(world_pos):
    if mouse_grabbed_constraint:
        mouse_body, _ = mouse_grabbed_constraint
        mouse_body.position = world_pos

def end_drag():
    global dragging_body, mouse_joint, mouse_grabbed_constraint
    if mouse_grabbed_constraint:
        mouse_body, joint = mouse_grabbed_constraint
        try:
            space.remove(joint)
        except Exception:
            pass
        try:
            space.remove(mouse_body)
        except Exception:
            pass
    dragging_body = None
    mouse_joint = None
    mouse_grabbed_constraint = None

# ---------------------------
# Draw GUI
# ---------------------------
def draw_gui():
    # Draw Reset button
    pygame.draw.rect(screen, (200, 200, 200), button_rect, border_radius=6)
    pygame.draw.rect(screen, (50, 50, 50), button_rect, 2, border_radius=6)
    txt = big_font.render("Reset", True, (20, 20, 20))
    tx = button_rect.x + (BUTTON_W - txt.get_width()) // 2
    ty = button_rect.y + (BUTTON_H - txt.get_height()) // 2
    screen.blit(txt, (tx, ty))

    # Score box background
    score_text = font.render(f"Score: {score}", True, (255, 255, 255))
    s_rect = score_text.get_rect(topleft=(BUTTON_MARGIN, BUTTON_MARGIN))
    bg = pygame.Rect(s_rect.x - 6, s_rect.y - 6, s_rect.width + 12, s_rect.height + 12)
    pygame.draw.rect(screen, (0, 0, 0, 120), bg)
    pygame.draw.rect(screen, (180, 180, 180), bg, 1)
    screen.blit(score_text, s_rect.topleft)

    # Instruction text
    inst1 = font.render("Click: spawn (alternates circle/box). Drag: hold mouse to move shape.", True, (230, 230, 230))
    inst2 = font.render("Click Reset to clear shapes.", True, (230, 230, 230))
    screen.blit(inst1, (BUTTON_MARGIN, HEIGHT - 60))
    screen.blit(inst2, (BUTTON_MARGIN, HEIGHT - 36))

# ---------------------------
# Main loop
# ---------------------------
def main():
    global spawn_circle_next, score

    running = True
    while running:
        dt = 1.0 / FPS
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                mouse_px = event.pos
                world_pos = from_pygame(mouse_px, screen)

                # Check GUI button click first (button on top-right)
                if button_rect.collidepoint(mouse_px):
                    # Reset simulation
                    reset_simulation()
                    continue

                # If left click: attempt to drag if clicking a body; else spawn new shape
                if event.button == 1:
                    nearest = space.point_query_nearest(world_pos, 2, pymunk.ShapeFilter())
                    if nearest and nearest.shape.body.body_type == pymunk.Body.DYNAMIC:
                        # start dragging existing body
                        start_drag(world_pos)
                    else:
                        # spawn new shape (alternate)
                        if spawn_circle_next:
                            create_circle(world_pos)
                        else:
                            create_box(world_pos)
                        spawn_circle_next = not spawn_circle_next
                        score += 1

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    end_drag()

            elif event.type == pygame.MOUSEMOTION:
                if mouse_grabbed_constraint:
                    world_pos = from_pygame(event.pos, screen)
                    update_drag(world_pos)

            elif event.type == pygame.KEYDOWN:
                # Also allow pressing 'r' to reset
                if event.key == pygame.K_r:
                    reset_simulation()

        # Step physics
        space.step(dt)

        # Clear screen
        screen.fill((36, 40, 44))

        # Draw Pymunk space (this uses pymunk's drawing, which converts coords for us)
        space.debug_draw(draw_options)

        # Draw GUI on top
        draw_gui()

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
