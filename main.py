from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
import sqlite3
import requests
import uuid
import random

app = FastAPI()

# --- CONFIGURATION ---
DB_FILE = "league.db"

# Setup DB (Stores URLs instead of files now)
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bots (
                id TEXT PRIMARY KEY, 
                name TEXT, 
                url TEXT,  -- The API Address
                elo INTEGER DEFAULT 1200, 
                wins INTEGER DEFAULT 0, 
                losses INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                id TEXT PRIMARY KEY, 
                p1_id TEXT, 
                p2_id TEXT, 
                winner_id TEXT, 
                moves TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
init_db()

# --- THE GAME ENGINE (The Referee) ---
def play_match(p1_url, p2_url):
    board = [[0]*7 for _ in range(6)] # 6 rows, 7 cols
    moves = []
    
    players = [
        {"id": 1, "url": p1_url},
        {"id": 2, "url": p2_url}
    ]
    
    # Game Loop (Max 42 moves)
    for _ in range(42):
        current_player = players[len(moves) % 2]
        
        # 1. ASK THE BOT FOR A MOVE
        try:
            payload = {
                "board": board,
                "you_are": current_player["id"] # 1 or 2
            }
            # Timeout is critical! Don't let them stall forever.
            response = requests.post(f"{current_player['url']}/move", json=payload, timeout=2.0)
            col = response.json().get("column")
        except Exception as e:
            print(f"Bot {current_player['id']} crashed or timed out: {e}")
            return (2 if current_player["id"] == 1 else 1), moves # Opponent wins

        # 2. VALIDATE MOVE
        if col is None or not (0 <= col < 7) or board[0][col] != 0:
            print(f"Bot {current_player['id']} made illegal move: {col}")
            return (2 if current_player["id"] == 1 else 1), moves # Opponent wins
            
        # 3. UPDATE BOARD
        moves.append(col)
        for r in range(5, -1, -1):
            if board[r][col] == 0:
                board[r][col] = current_player["id"]
                break
        
        # 4. CHECK WIN (Simplified vertical check for brevity - add full logic later)
        # (You should add full connect-4 logic here)
    
    return 0, moves # Draw

# --- WEB ROUTES ---

@app.get("/")
def home():
    with sqlite3.connect(DB_FILE) as conn:
        bots = conn.execute("SELECT id, name, url, elo FROM bots ORDER BY elo DESC").fetchall()
        matches = conn.execute("SELECT id, winner_id, moves FROM matches ORDER BY timestamp DESC LIMIT 5").fetchall()
    
    bot_list = "".join([f"<li><b>{b[1]}</b> ({b[3]}) <br><small>{b[2]}</small></li>" for b in bots])
    
    return HTMLResponse(f"""
    <h1>🏆 The API Arena</h1>
    <div style="display:flex; gap:20px;">
        <div style="border:1px solid #ccc; padding:20px;">
            <h3>1. Register a Bot</h3>
            <form action="/register" method="post">
                <input type="text" name="name" placeholder="Bot Name" required>
                <input type="url" name="url" placeholder="https://my-bot.onrender.com" required>
                <button>Register</button>
            </form>
            <ul>{bot_list}</ul>
        </div>
        
        <div style="border:1px solid #ccc; padding:20px;">
            <h3>2. Run Match</h3>
            <form action="/fight" method="post">
                <button style="font-size:20px; padding:10px; cursor:pointer">⚔️ FIGHT RANDOM PAIR ⚔️</button>
            </form>
        </div>
    </div>
    """)

@app.post("/register")
def register(name: str = Form(...), url: str = Form(...)):
    # Remove trailing slash to avoid double //
    url = url.rstrip("/")
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT INTO bots (id, name, url) VALUES (?, ?, ?)", 
                    (str(uuid.uuid4()), name, url))
    return HTMLResponse("<script>window.location.href='/'</script>")

@app.post("/fight")
def fight():
    with sqlite3.connect(DB_FILE) as conn:
        bots = conn.execute("SELECT id, url, name FROM bots").fetchall()
    
    if len(bots) < 2:
        return HTMLResponse("Need at least 2 bots! <a href='/'>Back</a>")
    
    # Pick 2 random fighters
    p1, p2 = random.sample(bots, 2)
    
    # --- RUN THE MATCH (Synchronous for now, easy to understand) ---
    winner_local_id, moves = play_match(p1[1], p2[1])
    
    winner_id = p1[0] if winner_local_id == 1 else (p2[0] if winner_local_id == 2 else None)
    winner_name = p1[2] if winner_local_id == 1 else (p2[2] if winner_local_id == 2 else "Draw")
    
    # Save Result
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT INTO matches (id, p1_id, p2_id, winner_id, moves) VALUES (?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), p1[0], p2[0], winner_id, str(moves)))
        
    return HTMLResponse(f"<h1>Match Over!</h1><p>Winner: {winner_name}</p><p>Moves: {moves}</p><a href='/'>Back</a>")