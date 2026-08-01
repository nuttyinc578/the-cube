import pygame
import sys
import random
import math

# Initialize Pygame
pygame.init()

# Screen dimensions
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("2D Shape Simulation")

# Clock for controlling FPS
clock = pygame.time.Clock()

# Shape class
class Circle:
    def __init__(self):
        self.radius = random.randint(10, 40)
        self.x = random.randint(self.radius, WIDTH - self.radius)
        self.y = random.randint(self.radius, HEIGHT - self.radius)
        self.dx = random.uniform(-5, 5)
        self.dy = random.uniform(-5, 5)
        self.color = (
            random.randint(50, 255),
            random.randint(50, 255),
            random.randint(50, 255)
        )

    def move(self):
        self.x += self.dx
        self.y += self.dy

        # Bounce off walls
        if self.x - self.radius <= 0 or self.x + self.radius >= WIDTH:
            self.dx = -self.dx
        if self.y - self.radius <= 0 or self.y + self.radius >= HEIGHT:
            self.dy = -self.dy

    def draw(self):
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.radius)

    def check_collision(self, other):
        # Check if this circle collides with another
        dist = math.hypot(self.x - other.x, self.y - other.y)
        if dist < self.radius + other.radius:
            # Simple elastic collision: swap velocities
            self.dx, other.dx = other.dx, self.dx
            self.dy, other.dy = other.dy, self.dy

# Create multiple circles
circles = [Circle() for _ in range(10)]

# Main loop
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

    # Move and handle collisions
    for i, circle in enumerate(circles):
        circle.move()
        for other in circles[i+1:]:
            circle.check_collision(other)

    # Draw everything
    screen.fill((0, 0, 0))  # Clear screen
    for circle in circles:
        circle.draw()
    pygame.display.flip()

    # Limit FPS
    clock.tick(60)


