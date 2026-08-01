"""
2D Shape Simulation Game with Singleplayer, Online Multiplayer, and Settings
Single Python File
Dependencies: pygame, pymunk
"""

import pygame, pymunk, pymunk.pygame_util, random, sys, json, socket, threading, pickle, math

# ------------------- Config -------------------
WIDTH, HEIGHT = 1000, 700
FPS = 60
SETTINGS_FILE = "settings.json"

# ------------------- Default Settings -------------------
default_settings = {
    "background_theme": "dark",  # dark, light, gradient
    "gravity": 900,
    "difficulty": "medium",  # small, medium, large
    "graphics_shadows": True
}

# ------------------- Initialize -------------------
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("2D Shape Simulation Game")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 20)
big_font = pygame.font.SysFont("Arial", 28, bold=True)
draw_options = pymunk.pygame_util.DrawOptions(screen)

# ------------------- Global State -------------------
settings = default_settings.copy()
try:
    with open(SETTINGS_FILE, "r") as f:
        settings.update(json.load(f))
except Exception:
    pass

# Physics space
space = pymunk.Space()
space.gravity = (0, settings["gravity"])

# --- Static world boundaries ---
static_body = space.static_body

ground = pymunk.Segment(static_body, (0, HEIGHT - 50), (WIDTH, HEIGHT - 50), 5)
ground.friction = 1.0
ground.elasticity = 0.2

left_wall = pymunk.Segment(static_body, (0, 0), (0, HEIGHT), 5)
left_wall.friction = 1.0
left_wall.elasticity = 0.2

right_wall = pymunk.Segment(static_body, (WIDTH, 0), (WIDTH, HEIGHT), 5)
right_wall.friction = 1.0
right_wall.elasticity = 0.2

space.add(ground, left_wall, right_wall)

# Simulation state
shapes = []  # list of tuples (body, shape, player_id)
score = 0
spawn_circle_next = True
dragging_body = None
mouse_grabbed_constraint = None

# GUI buttons
BUTTON_W, BUTTON_H = 140, 40
BUTTON_MARGIN = 12
button_reset = pygame.Rect(WIDTH - BUTTON_W - BUTTON_MARGIN, BUTTON_MARGIN, BUTTON_W, BUTTON_H)

# Multiplayer network state
network_socket = None  # will hold the connected socket (client or accepted conn)
server_listen_socket = None  # if we're the server, this is the listening socket
network_thread = None
multiplayer_running = False
player_id = 1  # 1 or 2
peer_addr = None
peer_port = 50007
network_shapes = []

# ------------------- Helper Functions -------------------
def save_settings():
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f)
    except Exception:
        pass

def load_settings():
    global settings
    try:
        with open(SETTINGS_FILE, "r") as f:
            settings.update(json.load(f))
    except Exception:
        pass

def reset_simulation():
    global shapes, score
    for body, shape, _ in list(shapes):
        try:
            space.remove(body, shape)
        except Exception:
            pass
    shapes = []
    score = 0

def increment_score(pos):
    global score
    # pos might be Vec2d or tuple
    try:
        y = pos[1]
    except Exception:
        y = float(pos.y)
    score += 1
    if y < HEIGHT // 2:
        score += 1

# ------------------- Shape Creation -------------------
def create_circle(pos, player=None, from_network=False):
    """
    pos: pymunk Vec2d or (x,y)
    player: id or None
    from_network: if True, do NOT re-send to network
    """
    global shapes
    r = {"small": 12, "medium": 24, "large": 36}[settings["difficulty"]]
    mass = 1.0
    moment = pymunk.moment_for_circle(mass, 0, r)
    body = pymunk.Body(mass, moment)
    # ensure pos is tuple-like
    if hasattr(pos, "x") and hasattr(pos, "y"):
        body.position = (pos.x, pos.y)
    else:
        body.position = (float(pos[0]), float(pos[1]))
    shape = pymunk.Circle(body, r)
    shape.friction = 0.8
    shape.elasticity = 0.2
    shape.color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255), 255)
    space.add(body, shape)
    shapes.append((body, shape, player))
    increment_score(body.position)
    if not from_network:
        send_shape_to_peer("circle", (body.position.x, body.position.y), r, player)

def create_box(pos, player=None, from_network=False):
    global shapes
    w, h = {"small": (20, 20), "medium": (40, 40), "large": (80, 60)}[settings["difficulty"]]
    mass = 1.0
    moment = pymunk.moment_for_box(mass, (w, h))
    body = pymunk.Body(mass, moment)
    if hasattr(pos, "x") and hasattr(pos, "y"):
        body.position = (pos.x, pos.y)
    else:
        body.position = (float(pos[0]), float(pos[1]))
    verts = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    shape = pymunk.Poly(body, verts)
    shape.friction = 0.9
    shape.elasticity = 0.1
    shape.color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255), 255)
    space.add(body, shape)
    shapes.append((body, shape, player))
    increment_score(body.position)
    if not from_network:
        send_shape_to_peer("box", (body.position.x, body.position.y), (w, h), player)

# ------------------- Dragging -------------------
def start_drag(pos):
    global dragging_body, mouse_grabbed_constraint
    # pos should be world coords (Vec2d)
    nearest = space.point_query_nearest(pos, 5, pymunk.ShapeFilter())
    if nearest and nearest.shape and nearest.shape.body.body_type == pymunk.Body.DYNAMIC:
        dragging_body = nearest.shape.body
        # create a single kinematic mouse body that follows the cursor
        mouse_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        mouse_body.position = pos
        # pivot joint with local anchor
        local_anchor = dragging_body.world_to_local(pos)
        joint = pymunk.PivotJoint(mouse_body, dragging_body, (0, 0), local_anchor)
        joint.max_force = 1e6
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
        try:
            space.remove(joint)
        except Exception:
            pass
        try:
            space.remove(mouse_body)
        except Exception:
            pass
    dragging_body = None
    mouse_grabbed_constraint = None

# ------------------- Networking -------------------
def start_server():
    """
    Start listening for a single client. This call spawns a blocking accept() in a separate thread.
    """
    global network_socket, server_listen_socket, multiplayer_running, player_id, peer_addr, network_thread
    try:
        server_listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_listen_socket.bind(('', peer_port))
        server_listen_socket.listen(1)
    except Exception as e:
        print("Failed to start server listen socket:", e)
        return

    def accept_thread():
        global network_socket, multiplayer_running, player_id, peer_addr
        print("Waiting for client...")
        try:
            conn, addr = server_listen_socket.accept()
        except Exception as e:
            print("Accept failed:", e)
            return
        peer_addr = addr
        network_socket = conn  # set to the connected socket so send_shape_to_peer works
        player_id = 1
        print(f"Client connected: {addr}")
        multiplayer_running = True
        threading.Thread(target=network_listener, args=(conn,), daemon=True).start()

    network_thread = threading.Thread(target=accept_thread, daemon=True)
    network_thread.start()

def start_client(host_ip):
    global network_socket, multiplayer_running, player_id, network_thread
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host_ip, peer_port))
    except Exception as e:
        print("Failed to connect to host:", e)
        return
    network_socket = sock
    player_id = 2
    multiplayer_running = True
    network_thread = threading.Thread(target=network_listener, args=(network_socket,), daemon=True)
    network_thread.start()

def network_listener(conn):
    global network_shapes, multiplayer_running
    # continuous receive; handle partial reads by reading into buffer and unpickling when possible
    buf = b""
    while multiplayer_running:
        try:
            data = conn.recv(4096)
            if not data:
                # connection closed
                print("Peer closed connection.")
                multiplayer_running = False
                break
            buf += data
            # Try to unpickle as many objects as possible from the buffer.
            # Since pickle streams don't have a clean delimiter, we'll attempt a single loads each time.
            try:
                obj = pickle.loads(buf)
                network_shapes.append(obj)
                buf = b""
            except Exception:
                # partial data - wait for more
                continue
        except Exception:
            # ignore transient errors and continue
            continue

def send_shape_to_peer(shape_type, pos, size, player):
    global network_socket, multiplayer_running
    if not multiplayer_running or not network_socket:
        return
    try:
        obj = {"type": shape_type, "pos": pos, "size": size, "player": player}
        network_socket.sendall(pickle.dumps(obj))
    except Exception:
        pass

def update_network_shapes():
    global network_shapes
    while network_shapes:
        obj = network_shapes.pop(0)
        # create shapes coming from network without re-sending
        try:
            if obj.get("type") == "circle":
                create_circle(obj["pos"], obj.get("player"), from_network=True)
            else:
                create_box(obj["pos"], obj.get("player"), from_network=True)
        except Exception:
            pass

# ------------------- GUI -------------------
def draw_gui():
    global score
    # Reset button
    pygame.draw.rect(screen, (200, 200, 200), button_reset, border_radius=6)
    pygame.draw.rect(screen, (50, 50, 50), button_reset, 2, border_radius=6)
    txt = big_font.render("Reset", True, (0, 0, 0))
    screen.blit(
        txt,
        (button_reset.x + (BUTTON_W - txt.get_width()) // 2,
         button_reset.y + (BUTTON_H - txt.get_height()) // 2)
    )

    # Score
    score_text = font.render(f"Score: {score}", True, (255, 255, 255))
    screen.blit(score_text, (10, 10))

# ------------------- Main Menu -------------------
def main_menu():
    buttons = []
    start_btn = pygame.Rect(WIDTH // 2 - 120, HEIGHT // 2 - 80, 240, 50)
    multi_btn = pygame.Rect(WIDTH // 2 - 120, HEIGHT // 2 - 20, 240, 50)
    settings_btn = pygame.Rect(WIDTH // 2 - 120, HEIGHT // 2 + 40, 240, 50)
    quit_btn = pygame.Rect(WIDTH // 2 - 120, HEIGHT // 2 + 100, 240, 50)
    buttons = [("single", start_btn), ("multi", multi_btn), ("settings", settings_btn), ("quit", quit_btn)]
    running = True
    bg_offset = 0
    while running:
        mouse = pygame.mouse.get_pos()
        screen.fill((20, 30, 40))
        for i in range(0, HEIGHT, 20):
            color_val = (i + bg_offset) % 255
            pygame.draw.rect(screen, (color_val // 2, color_val // 3, color_val // 4), (0, i, WIDTH, 20))
        bg_offset = (bg_offset + 2) % 255
        for name, rect in buttons:
            color = (100, 100, 220) if rect.collidepoint(mouse) else (180, 180, 255)
            pygame.draw.rect(screen, color, rect, border_radius=10)
            pygame.draw.rect(screen, (0, 0, 0), rect, 3, border_radius=10)
            txt_text = {"single": "Singleplayer", "multi": "Multiplayer", "settings": "Settings", "quit": "Quit"}[name]
            screen.blit(big_font.render(txt_text, True, (0, 0, 0)), (rect.x + 20, rect.y + 10))
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                multiplayer_shutdown()
                pygame.quit(); sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for name, rect in buttons:
                    if rect.collidepoint(mouse):
                        if name == "single":
                            simulation_loop()
                        elif name == "multi":
                            multiplayer_menu()
                        elif name == "settings":
                            settings_menu()
                        elif name == "quit":
                            multiplayer_shutdown()
                            pygame.quit(); sys.exit()
        clock.tick(FPS)

# ------------------- Settings Menu -------------------
def settings_menu():
    running = True
    while running:
        mouse = pygame.mouse.get_pos()
        screen.fill((30, 30, 30))
        # Draw labels and options
        txt1 = big_font.render("Settings", True, (255, 255, 255))
        screen.blit(txt1, (WIDTH // 2 - txt1.get_width() // 2, 50))
        # Gravity slider
        grav_text = font.render(f"Gravity: {settings['gravity']}", True, (255, 255, 255))
        screen.blit(grav_text, (50, 150))
        grav_rect = pygame.Rect(200, 150, 400, 20)
        pygame.draw.rect(screen, (100, 100, 100), grav_rect)
        # clamp gravity to [0,2000]
        handle_x = int(grav_rect.x + grav_rect.width * (max(0, min(settings['gravity'], 2000)) / 2000.0))
        pygame.draw.rect(screen, (255, 0, 0), (handle_x - 10, 145, 20, 30))
        # Difficulty
        diff_text = font.render(f"Difficulty: {settings['difficulty']}", True, (255, 255, 255))
        screen.blit(diff_text, (50, 200))
        # Graphics options
        gfx_text = font.render(f"Graphics Shadows: {'On' if settings['graphics_shadows'] else 'Off'}", True,
                               (255, 255, 255))
        screen.blit(gfx_text, (50, 250))
        # Back button
        back_rect = pygame.Rect(50, 600, 120, 40)
        pygame.draw.rect(screen, (200, 200, 200), back_rect, border_radius=6)
        screen.blit(font.render("Back", True, (0, 0, 0)), (back_rect.x + 20, back_rect.y + 10))
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                multiplayer_shutdown()
                pygame.quit(); sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if back_rect.collidepoint(mouse):
                    save_settings()
                    return
                # Check gravity slider
                if grav_rect.collidepoint(mouse):
                    rel_x = mouse[0] - grav_rect.x
                    new_g = int(2000 * rel_x / grav_rect.width)
                    settings['gravity'] = max(0, min(new_g, 2000))
                    space.gravity = (0, settings['gravity'])
                # Cycling difficulty by clicking the difficulty area
                diff_area = pygame.Rect(50, 200, 300, 30)
                if diff_area.collidepoint(mouse):
                    # cycle difficulty small->medium->large
                    order = ["small", "medium", "large"]
                    idx = order.index(settings['difficulty'])
                    settings['difficulty'] = order[(idx + 1) % len(order)]
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    save_settings()
                    return
        clock.tick(FPS)

# ------------------- Multiplayer Menu -------------------
def multiplayer_menu():
    global player_id
    running = True
    host_btn = pygame.Rect(WIDTH // 2 - 120, HEIGHT // 2 - 60, 240, 50)
    join_btn = pygame.Rect(WIDTH // 2 - 120, HEIGHT // 2 + 20, 240, 50)
    while running:
        mouse = pygame.mouse.get_pos()
        screen.fill((20, 20, 50))
        pygame.draw.rect(screen, (180, 180, 255) if host_btn.collidepoint(mouse) else (100, 100, 220), host_btn,
                         border_radius=10)
        pygame.draw.rect(screen, (180, 180, 255) if join_btn.collidepoint(mouse) else (100, 100, 220), join_btn,
                         border_radius=10)
        screen.blit(big_font.render("Host", True, (0, 0, 0)), (host_btn.x + 70, host_btn.y + 10))
        screen.blit(big_font.render("Join", True, (0, 0, 0)), (join_btn.x + 70, join_btn.y + 10))
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                multiplayer_shutdown()
                pygame.quit(); sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if host_btn.collidepoint(mouse):
                    start_server()
                    # wait a moment for accept thread to run (non-blocking)
                    simulation_loop(multiplayer=True)
                    return
                elif join_btn.collidepoint(mouse):
                    # Prompt for IP in console
                    host_ip = input("Enter host IP: ")
                    start_client(host_ip)
                    simulation_loop(multiplayer=True)
                    return
        clock.tick(FPS)

# ------------------- Simulation Loop -------------------
def simulation_loop(multiplayer=False):
    global spawn_circle_next
    running = True
    while running:
        dt = 1.0 / FPS
        mouse_px = pygame.mouse.get_pos()
        # convert screen coords to pymunk world coords
        world_pos = pymunk.pygame_util.from_pygame(mouse_px, screen)
        update_network_shapes()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                multiplayer_shutdown()
                pygame.quit(); sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # use screen coords for UI hit-tests
                if button_reset.collidepoint(mouse_px):
                    reset_simulation()
                else:
                    start_drag(world_pos)
                    if not dragging_body:
                        if spawn_circle_next:
                            create_circle(world_pos, player_id if multiplayer else None)
                        else:
                            create_box(world_pos, player_id if multiplayer else None)
                        spawn_circle_next = not spawn_circle_next
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                end_drag()
            elif event.type == pygame.MOUSEMOTION:
                update_drag(world_pos)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    reset_simulation()
                if event.key == pygame.K_ESCAPE:
                    return
        space.step(dt)
        screen.fill((20, 20, 20) if settings["background_theme"] == "dark" else (200, 200, 200))
        space.debug_draw(draw_options)
        draw_gui()
        pygame.display.flip()
        clock.tick(FPS)

# ------------------- Multiplayer cleanup -------------------
def multiplayer_shutdown():
    global network_socket, server_listen_socket, multiplayer_running
    multiplayer_running = False
    try:
        if network_socket:
            network_socket.close()
    except Exception:
        pass
    try:
        if server_listen_socket:
            server_listen_socket.close()
    except Exception:
        pass
    network_socket = None

# ------------------- Entry -------------------
if __name__ == "__main__":
    main_menu()
