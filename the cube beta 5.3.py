import pygame, sys, os, json, requests

# ---------------- INIT ----------------
pygame.init()
WIDTH, HEIGHT = 1000, 700
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()
font = pygame.font.SysFont("arial", 22)
big = pygame.font.SysFont("arial", 40, bold=True)

# ---------------- ITCH.IO CONFIG ----------------
ITCH_API_KEY = "YOUR_ITCH_API_KEY"
GAME_ID = "your-game-id"

# ---------------- STATE ----------------
state = "login"
username = ""
key = ""
user_data = {}
premium = False

# ---------------- ITCH.IO OWNERSHIP CHECK ----------------
def check_itch_ownership():
    global premium
    try:
        headers = {"Authorization": f"Bearer {ITCH_API_KEY}"}
        r = requests.get(
            f"https://itch.io/api/1/{GAME_ID}/me/owned-keys",
            headers=headers,
            timeout=3
        )

        data = r.json()

        # if user owns game → unlock premium
        premium = data.get("owned", False)
        return premium

    except:
        # fallback offline mode
        return False

# ---------------- SAVE SYSTEM ----------------
def load_user(name):
    if os.path.exists(f"{name}.json"):
        return json.load(open(f"{name}.json"))
    return {"name": name, "score": 0}

def save_user(u):
    json.dump(u, open(f"{u['name']}.json","w"))

# ---------------- LOGIN ----------------
def login():
    global state, username, key, user_data, premium

    while state == "login":
        screen.fill((200,230,255))

        screen.blit(big.render("THE CUBE LOGIN",1,(0,0,0)),(330,120))

        screen.blit(font.render("Username: " + username,1,(0,0,0)),(350,250))
        screen.blit(font.render("Itch Key: " + key,1,(0,0,0)),(350,300))

        screen.blit(font.render("ENTER to login",1,(0,0,0)),(350,400))

        pygame.display.flip()

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_RETURN:
                    user_data = load_user(username)

                    # 🔐 REAL MONETIZATION CHECK
                    if check_itch_ownership():
                        premium = True

                    state = "game"

                elif e.key == pygame.K_BACKSPACE:
                    username = username[:-1]

                else:
                    username += e.unicode

        clock.tick(60)

# ---------------- GAME ----------------
def game():
    global state, user_data

    x, y = WIDTH//2, HEIGHT//2

    while state == "game":
        screen.fill((180,220,255))

        keys = pygame.key.get_pressed()

        if keys[pygame.K_LEFT]: x -= 5
        if keys[pygame.K_RIGHT]: x += 5
        if keys[pygame.K_UP]: y -= 5
        if keys[pygame.K_DOWN]: y += 5

        pygame.draw.circle(screen,(255,100,100),(x,y),20)

        # 💰 PREMIUM FEATURE LOCK
        if premium:
            screen.blit(font.render("PREMIUM ACTIVE",1,(0,150,0)),(10,10))
        else:
            screen.blit(font.render("FREE VERSION",1,(200,0,0)),(10,10))
            screen.blit(font.render("Buy on itch.io to unlock",1,(0,0,0)),(10,40))

        pygame.display.flip()

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                save_user(user_data)
                pygame.quit(); sys.exit()

            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    state = "login"

        clock.tick(60)

# ---------------- START ----------------
login()
game()