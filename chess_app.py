import streamlit as st
import chess
import chess.pgn
import chess.svg
import chess.engine
import io
import shutil
import os  # Critical for checking file paths

# --- Configuration ---
st.set_page_config(page_title="Chess Analyzer", layout="wide")

# 1. Define the specific location where Streamlit Cloud installs Stockfish
game_path = "/usr/games/stockfish"

# 2. Logic to find the engine
if os.path.exists(game_path):
    STOCKFISH_PATH = game_path
else:
    # Fallback for local testing (Mac/Windows)
    STOCKFISH_PATH = shutil.which("stockfish")

st.title("♟️ Chess PGN Analyzer")

# --- DEBUG SECTION (Remove this later if you want) ---
# This will show you exactly what is happening on the server
if STOCKFISH_PATH:
    st.success(f"Engine found at: {STOCKFISH_PATH}")
else:
    st.error(f"Engine still not found. Checked: {game_path}")
# ----------------------------------------------------

# --- Sidebar ---
with st.sidebar:
    st.header("Input Game")
    pgn_input = st.text_area("Paste PGN text:", height=200)
    
    st.header("Settings")
    depth = st.slider("Engine Depth", 10, 20, 15)
    orientation = st.selectbox("Flip Board", ["White at Bottom", "Black at Bottom"])

# --- Main Logic ---
if pgn_input:
    pgn = io.StringIO(pgn_input)
    try:
        game = chess.pgn.read_game(pgn)
        if game:
            board = game.board()
            moves = list(game.mainline_moves())
            
            # Navigation Slider
            move_idx = st.slider("Move Navigation", 0, len(moves), 0)
            
            # Update board to selected move
            for i in range(move_idx):
                board.push(moves[i])

            # Layout
            col1, col2 = st.columns([1, 1])
            
            with col1:
                # Draw Board
                is_white = (orientation == "White at Bottom")
                board_svg = chess.svg.board(board, size=400, lastmove=moves[move_idx-1] if move_idx > 0 else None, orientation=chess.WHITE if is_white else chess.BLACK)
                st.image(board_svg, use_column_width=False)
            
            with col2:
                # Analysis Button
                if st.button("Analyze Position"):
                    if STOCKFISH_PATH:
                        with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
                            info = engine.analyse(board, chess.engine.Limit(depth=depth))
                            score = info["score"].white()
                            
                            if score.is_mate():
                                st.metric("Evaluation", f"Mate in {score.mate()}")
                            else:
                                st.metric("Evaluation", f"{score.score() / 100:.2f}")
                                
                            # Contextual clue
                            if not score.is_mate():
                                val = score.score()
                                if val > 100: st.success("White is winning")
                                elif val < -100: st.error("Black is winning")
                                else: st.info("Game is even")
                    else:
                        st.error("Stockfish engine not found on server.")
        else:
            st.error("Invalid PGN format.")
    except Exception as e:
        st.error(f"Error: {e}")