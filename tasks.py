from celery import Celery
import sqlite3
import subprocess
import os
import json
import uuid

# SETUP CELERY
# We point to the Docker Redis container we just started
celery_app = Celery('tasks', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')

BOTS_DIR = "bots"
DB_FILE = "leaderboard.db"

@celery_app.task
def run_match_task(bot1_id, bot2_id):
    bot1_path = os.path.abspath(os.path.join(BOTS_DIR, f"{bot1_id}.py"))
    bot2_path = os.path.abspath(os.path.join(BOTS_DIR, f"{bot2_id}.py"))

    def start_bot(path):
        return subprocess.Popen(
            ["python", "-u", path],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            cwd=os.path.dirname(path) # Run from the bot's folder
        )

    print(f"--- STARTING MATCH: {bot1_id} vs {bot2_id} ---")
    
    p1 = start_bot(bot1_path)
    p2 = start_bot(bot2_path)
    
    board = [0] * 42
    turn = 1 
    winner = 0
    moves = []
    
    try:
        for _ in range(42): 
            if 0 not in board: break

            current_proc = p1 if turn == 1 else p2
            
            # Send Board
            board_str = "".join(map(str, board))
            current_proc.stdin.write(board_str + "\n")
            current_proc.stdin.flush()
            
            # Get Move
            move_str = current_proc.stdout.readline()
            if not move_str: break
            
            try:
                col = int(move_str.strip())
            except ValueError: break

            # Apply Move
            row_to_fill = -1
            for r in range(5, -1, -1):
                idx = r * 7 + col
                if board[idx] == 0:
                    row_to_fill = idx
                    break
            
            if row_to_fill == -1: break 
            
            board[row_to_fill] = turn
            moves.append(col)
            
            # Check Win (Simplified)
            def check_win(p):
                # Horizontal
                for r in range(6):
                    for c in range(4):
                        if all(board[r*7 + c + i] == p for i in range(4)): return True
                # Vertical
                for r in range(3):
                    for c in range(7):
                        if all(board[(r+i)*7 + c] == p for i in range(4)): return True
                # Diag 1
                for r in range(3):
                    for c in range(4):
                        if all(board[(r+i)*7 + c + i] == p for i in range(4)): return True
                # Diag 2
                for r in range(3):
                    for c in range(3, 7):
                        if all(board[(r+i)*7 + c - i] == p for i in range(4)): return True
                return False

            if check_win(turn):
                winner = turn
                break
                
            turn = 3 - turn 

    except Exception as e:
        print(f"Match Error: {e}")
    finally:
        p1.terminate()
        p2.terminate()
        
    # SAVE RESULT
    match_id = str(uuid.uuid4())
    winner_id = bot1_id if winner == 1 else bot2_id if winner == 2 else None
    moves_json = json.dumps(moves)
    
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT INTO matches (id, bot1_id, bot2_id, winner_id, moves) VALUES (?,?,?,?,?)",
                     (match_id, bot1_id, bot2_id, winner_id, moves_json))
        
        if winner == 1:
            conn.execute("UPDATE bots SET elo=elo+10, wins=wins+1 WHERE id=?", (bot1_id,))
            conn.execute("UPDATE bots SET elo=elo-10, losses=losses+1 WHERE id=?", (bot2_id,))
        elif winner == 2:
            conn.execute("UPDATE bots SET elo=elo-10, losses=losses+1 WHERE id=?", (bot1_id,))
            conn.execute("UPDATE bots SET elo=elo+10, wins=wins+1 WHERE id=?", (bot2_id,))
            
    print(f"--- MATCH FINISHED. Winner: {winner} ---")
    return match_id