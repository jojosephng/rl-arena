from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse
import sqlite3
import shutil
import os
import uuid
from tasks import run_match_task 

app = FastAPI()

# --- CONFIGURATION ---
BOTS_DIR = "bots"
DB_FILE = "leaderboard.db"
os.makedirs(BOTS_DIR, exist_ok=True)

# --- WEB ROUTES ---

@app.get("/")
async def get_dashboard():
    with sqlite3.connect(DB_FILE) as conn:
        # Get Leaderboard
        bots = conn.execute("SELECT id, name, elo, wins, losses FROM bots ORDER BY elo DESC").fetchall()
        # Get Recent Matches
        matches = conn.execute("""
            SELECT m.id, b1.name, b2.name, w.name 
            FROM matches m
            JOIN bots b1 ON m.bot1_id = b1.id
            JOIN bots b2 ON m.bot2_id = b2.id
            LEFT JOIN bots w ON m.winner_id = w.id
            ORDER BY m.timestamp DESC LIMIT 5
        """).fetchall()
    
    # 1. BUILD DROPDOWN OPTIONS (New!)
    bot_options = ""
    for b_id, b_name, elo, w, l in bots:
        bot_options += f'<option value="{b_id}">{b_name} ({elo})</option>'

    leaderboard_rows = ""
    for rank, (b_id, name, elo, w, l) in enumerate(bots, 1):
        leaderboard_rows += f"<tr><td>{rank}</td><td>{name}</td><td>{elo}</td><td>{w}W - {l}L</td></tr>"

    match_rows = ""
    for mid, p1, p2, winner in matches:
        w_text = winner if winner else "Draw"
        match_rows += f"""
        <tr>
            <td>{p1} vs {p2}</td>
            <td>{w_text}</td>
            <td><a href='/replay/{mid}'>📺 Watch</a></td>
        </tr>"""

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>RL League (Matchmaker)</title>
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f4f4f9; }}
            h1, h2 {{ text-align: center; color: #2c3e50; }}
            .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
            .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #6c5ce7; color: white; }}
            a {{ text-decoration: none; color: #0984e3; font-weight: bold; }}
            button {{ background: #00b894; color: white; border: none; padding: 10px 20px; cursor: pointer; border-radius: 4px; }}
            button:hover {{ background: #019e7e; }}
            .fight-btn {{ background: #d63031; width: 100%; font-size: 18px; padding: 15px; }}
            .fight-btn:hover {{ background: #b71c1c; }}
            select {{ padding: 10px; width: 45%; margin: 5px; font-size: 16px; }}
        </style>
    </head>
    <body>
        <h1>🏆 RL-Kaggle Arena</h1>
        
        <div class="card" style="text-align: center;">
            <h3>⚔️ Matchmaker ⚔️</h3>
            <form action="/fight" method="post">
                <select name="p1_id" required>
                    <option value="" disabled selected>Select Player 1</option>
                    {bot_options}
                </select>
                <span style="font-size: 24px; font-weight: bold;">VS</span>
                <select name="p2_id" required>
                    <option value="" disabled selected>Select Player 2</option>
                    {bot_options}
                </select>
                <br><br>
                <button type="submit" class="fight-btn">RUN MATCH</button>
            </form>
        </div>

        <div class="grid">
            <div class="card">
                <h3>📊 Leaderboard</h3>
                <table>
                    <tr><th>Rank</th><th>Name</th><th>ELO</th><th>Rec</th></tr>
                    {leaderboard_rows}
                </table>
            </div>
            
            <div class="card">
                <h3>📤 Upload Bot</h3>
                <form action="/upload" method="post" enctype="multipart/form-data">
                    <input type="text" name="name" placeholder="Bot Name" required style="width: 90%; padding: 8px; margin-bottom: 10px;">
                    <input type="file" name="file" accept=".py" required>
                    <button type="submit" style="width: 100%; margin-top: 10px;">Join League</button>
                </form>
                
                <h3>Recent Battles</h3>
                <table>
                    <tr><th>Match</th><th>Winner</th><th>Replay</th></tr>
                    {match_rows}
                </table>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.post("/upload")
async def upload_bot(name: str = Form(...), file: UploadFile = File(...)):
    bot_id = str(uuid.uuid4())
    save_path = os.path.join(BOTS_DIR, f"{bot_id}.py")
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT INTO bots (id, name) VALUES (?, ?)", (bot_id, name))
    return HTMLResponse(content=f"<script>window.location.href='/'</script>")

@app.post("/fight")
async def trigger_fight(p1_id: str = Form(...), p2_id: str = Form(...)):
    # 2. RECEIVE THE SELECTED IDS (New Logic!)
    with sqlite3.connect(DB_FILE) as conn:
        b1 = conn.execute("SELECT name FROM bots WHERE id=?", (p1_id,)).fetchone()
        b2 = conn.execute("SELECT name FROM bots WHERE id=?", (p2_id,)).fetchone()
    
    if not b1 or not b2:
        return HTMLResponse("<h1>Bot not found!</h1><a href='/'>Back</a>")

    # Send to Kitchen
    task = run_match_task.delay(p1_id, p2_id)
    
    return HTMLResponse(f"""
        <div style="font-family: sans-serif; text-align: center; padding: 50px;">
            <h1>👨‍🍳 Match Queued!</h1>
            <p>The kitchen has received order: <b>{b1[0]} vs {b2[0]}</b></p>
            <p>Ticket ID: <code>{task.id}</code></p>
            <br>
            <a href='/'>Return to Dashboard</a>
            <p>(Refresh in ~10 seconds to see the result)</p>
        </div>
    """)

@app.get("/replay/{match_id}")
async def get_replay(match_id: str):
    with sqlite3.connect(DB_FILE) as conn:
        match = conn.execute("""
            SELECT m.moves, b1.name, b2.name, w.name 
            FROM matches m
            JOIN bots b1 ON m.bot1_id = b1.id
            JOIN bots b2 ON m.bot2_id = b2.id
            LEFT JOIN bots w ON m.winner_id = w.id
            WHERE m.id = ?
        """, (match_id,)).fetchone()
    
    if not match: return HTMLResponse("Match not found (or still cooking!)")
    
    moves_json, p1_name, p2_name, winner_name = match
    winner_text = f"Winner: {winner_name}" if winner_name else "Draw"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Replay</title>
        <style>
            body {{ font-family: sans-serif; text-align: center; background: #2c3e50; color: white; }}
            .board {{ display: grid; grid-template-columns: repeat(7, 50px); gap: 8px; justify-content: center; margin: 20px auto; background: #34495e; padding: 15px; border-radius: 10px; width: fit-content; }}
            .cell {{ width: 50px; height: 50px; background: white; border-radius: 50%; }}
            .cell.p1 {{ background-color: #e74c3c; }}
            .cell.p2 {{ background-color: #f1c40f; }}
            button {{ padding: 10px 20px; font-size: 16px; cursor: pointer; }}
        </style>
    </head>
    <body>
        <h1>🔴 {p1_name} vs 🟡 {p2_name}</h1>
        <h3>{winner_text}</h3>
        <div class="board" id="board"></div>
        <button onclick="startReplay()">▶ Play Replay</button>
        <br><br>
        <a href="/" style="color: white">Back to League</a>

        <script>
            const moves = {moves_json};
            let board = Array(6).fill().map(() => Array(7).fill(0));
            let currentMove = 0;
            
            const boardDiv = document.getElementById('board');
            for (let r = 0; r < 6; r++) {{
                for (let c = 0; c < 7; c++) {{
                    let cell = document.createElement('div');
                    cell.className = 'cell';
                    cell.id = `cell-${{r}}-${{c}}`;
                    boardDiv.appendChild(cell);
                }}
            }}

            function dropPiece(col, player) {{
                for (let r = 5; r >= 0; r--) {{
                    if (board[r][col] === 0) {{
                        board[r][col] = player;
                        document.getElementById(`cell-${{r}}-${{col}}`).classList.add(player === 1 ? 'p1' : 'p2');
                        return;
                    }}
                }}
            }}

            function startReplay() {{
                board = Array(6).fill().map(() => Array(7).fill(0));
                document.querySelectorAll('.cell').forEach(c => c.className = 'cell');
                currentMove = 0;
                playNext();
            }}

            function playNext() {{
                if (currentMove >= moves.length) return;
                const player = (currentMove % 2) + 1;
                dropPiece(moves[currentMove], player);
                currentMove++;
                setTimeout(playNext, 500);
            }}
            setTimeout(startReplay, 500);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)