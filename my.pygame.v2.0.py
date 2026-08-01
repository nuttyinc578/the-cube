import pygame
import pymunk
import pymunk.pygame_util
import sys

# Initialize Pygame
pygame.init()
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("the cube v2.0")

clock = pygame.time.Clock()
draw_options = pymunk.pygame_util.DrawOptions(screen)

# Physics space
space = pymunk.Space()
space.gravity = (0, 900)  # Gravity pulls down

# Ground
static_body = space.static_body
ground = pymunk.Segment(static_body, (0, HEIGHT - 50), (WIDTH, HEIGHT - 50), 5)
ground.elasticity = 0.8
space.add(ground)

# Shapes list
shapes = []

def create_circle(position):
    mass = 1
    radius = 20
    moment = pymunk.moment_for_circle(mass, 0, radius)
    body = pymunk.Body(mass, moment)
    body.position = position
    shape = pymunk.Circle(body, radius)
    shape.elasticity = 0.8
    shape.friction = 0.5
    space.add(body, shape)
    shapes.append(shape)

dragging_shape = None
mouse_joint = None

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        elif event.type == pygame.MOUSEBUTTONDOWN:
            pos = pymunk.pygame_util.from_pygame(event.pos, screen)
            # Check if clicked on shape
            hit = space.point_query_nearest(pos, 5, pymunk.ShapeFilter())
            if hit:
                dragging_shape = hit.shape.body
                mouse_joint = pymunk.PivotJoint(space.static_body, dragging_shape, pos)
                mouse_joint.max_force = 5000
                space.add(mouse_joint)
            else:
                create_circle(pos)
        elif event.type == pygame.MOUSEBUTTONUP:
            if mouse_joint:
                space.remove(mouse_joint)
                mouse_joint = None
                dragging_shape = None
        elif event.type == pygame.MOUSEMOTION and mouse_joint:
            mouse_joint.anchor_a = pymunk.pygame_util.from_pygame(event.pos, screen)

    # Clear screen
    screen.fill((30, 30, 30))

    # Update physics
    space.step(1/60)

    # Draw
    space.debug_draw(draw_options)
    pygame.display.flip()
    clock.tick(60)

