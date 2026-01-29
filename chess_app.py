import streamlit as st
import chess
import chess.pgn
import chess.svg
import chess.engine
import io
import shutil
import os
import time
from datetime import datetime

# --- Configuration & Styling ---
st.set_page_config(page_title="Chess Coach V3.0", layout="wide")

# 1. Find Stockfish
game_path = "/usr/games/stockfish"
if os.path.exists(game_path):
    STOCKFISH_PATH = game_path
else:
    STOCKFISH_PATH = shutil.which("stockfish")

# --- Session State Initialization ---
if "move_idx" not in st.session_state:
    st.session_state.move_idx = 0
if "analysis_data" not in st.session_state:
    st.session_state.analysis_data = {} 
if "blunders" not in st.session_state:
    st.session_state.blunders = []
if "app_mode" not in st.session_state:
    st.session_state.app_mode = "Analysis" # 'Analysis' or 'Play'
if "play_board" not in st.session_state:
    st.session_state.play_board = None
if "play_game_history" not in st.session_state:
    st.session_state.play_game_history = []

# --- Helper Functions ---
def get_engine_analysis(board, depth_limit):
    """Runs analysis of the specific board position"""
    if not STOCKFISH_PATH:
        return None, None
    
    with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
        result = engine.analyse(board, chess.engine.Limit(depth=depth_limit))
        score = result["score"].white()
        best_move = result.get("pv")[0] if result.get("pv") else None
        
        if score.is_mate():
            eval_val = 99.0 if score.mate() > 0 else -99.0
        else:
            eval_val = score.score() / 100.0
            
        return eval_val, best_move

def analyze_full_game(game, depth_limit):
    """Loops through the entire game and saves data"""
    board = game.board()
    moves = list(game.mainline_moves())
    data = {}
    blunders = []
    prev_eval = 0.0
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, move in enumerate(moves):
        status_text.text(f"Analyzing move {i+1} of {len(moves)}...")
        progress_bar.progress((i + 1) / len(moves))
        
        board.push(move)
        curr_eval, best_move_obj = get_engine_analysis(board, depth_limit)
        
        # Detect Blunder Logic
        diff = curr_eval - prev_eval
        is_blunder = False
        if i % 2 == 0: # White
            if diff < -1.5: is_blunder = True
        else: # Black
            if diff > 1.5: is_blunder = True

        if is_blunder:
            blunders.append(i + 1)
            
        data[i+1] = {
            "eval": curr_eval,
            "best_move": best_move_obj,
            "is_blunder": is_blunder
        }
        prev_eval = curr_eval
        
    status_text.empty()
    progress_bar.empty()
    return data, blunders

def make_engine_move(board, skill_level):
    """Makes a move for the computer with specific skill level (0-20)"""
    if not STOCKFISH_PATH: return
    
    with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
        # Configure Skill Level (0 is dumb, 20 is GM)
        engine.configure({"Skill Level": skill_level})
        # Limit time to keep it responsive
        result = engine.play(board, chess.engine.Limit(time=0.5))
        board.push(result.move)
        st.session_state.play_game_history.append(result.move)

# --- Sidebar ---
with st.sidebar:
    st.title("♟️ Chess Coach V3")
    
    # Mode Switcher
    mode = st.radio("App Mode", ["Analysis", "Play vs Stockfish"], 
                    key="mode_selection", 
                    on_change=lambda: st.session_state.update(app_mode=st.session_state.mode_selection))

    if st.session_state.app_mode == "Analysis":
        st.subheader("1. Load Game")
        upload_file = st.file_uploader("Upload PGN File", type=['pgn', 'txt'])
        paste_text = st.text_area("Or Paste Text:", height=100)
        
        # Determine source
        pgn_source = None
        if upload_file is not None:
            stringio = io.StringIO(upload_file.getvalue().decode("utf-8"))
            pgn_source = stringio
        elif paste_text:
            pgn_source = io.StringIO(paste_text)

        st.subheader("2. Settings")
        analysis_depth = st.slider("Analysis Depth", 10, 22, 12)
        
        if st.button("Reset / New Game"):
            st.session_state.move_idx = 0
            st.session_state.analysis_data = {}
            st.session_state.blunders = []
            st.rerun()

    else: # PLAY MODE SETTINGS
        st.subheader("Stockfish Settings")
        skill = st.slider("Stockfish Level (0-20)", 0, 20, 5, 
                          help="Level 0 is ~1000 ELO. Level 20 is ~3200 ELO.")
        user_side = st.selectbox("I want to play", ["White", "Black"])

# --- Main Application Logic ---

if st.session_state.app_mode == "Analysis":
    # ---------------- ANALYSIS MODE ----------------
    if 'pgn_source' in locals() and pgn_source:
        try:
            game = chess.pgn.read_game(pgn_source)
        except:
            game = None
            st.error("Invalid PGN")

        if game:
            moves = list(game.mainline_moves())
            board = game.board()
            
            # Auto-Analyze Check
            if not st.session_state.analysis_data:
                st.info(f"Loaded {len(moves)} moves.")
                if st.button("🔍 Run Full Analysis"):
                    data, blunders = analyze_full_game(game, analysis_depth)
                    st.session_state.analysis_data = data
                    st.session_state.blunders = blunders
                    st.rerun()
            else:
                # VIEWING PHASE
                
                # --- Top Control Bar ---
                c1, c2, c3 = st.columns([1, 2, 1])
                with c1:
                    if st.button("Play this Position vs Stockfish"):
                        # Set up Play Mode state
                        current_board_state = game.board()
                        for k in range(st.session_state.move_idx):
                            current_board_state.push(moves[k])
                        st.session_state.play_board = current_board_state
                        st.session_state.play_game_history = []
                        st.session_state.app_mode = "Play vs Stockfish"
                        st.rerun()

                # --- Visual Logic ---
                # Check current move data
                current_data = st.session_state.analysis_data.get(st.session_state.move_idx)
                
                # Logic to handle "Better Move" toggle
                display_board = game.board()
                # Advance to current
                for k in range(st.session_state.move_idx):
                    display_board.push(moves[k])
                
                # If we are looking at a blunder, we might want to show the ALTERNATE reality
                show_alternate = False
                
                # Layout
                col_board, col_stats = st.columns([1.5, 1])
                
                with col_stats:
                    st.subheader(f"Move {st.session_state.move_idx}")
                    
                    # Navigation
                    b1, b2, b3 = st.columns(3)
                    if b1.button("◀ Prev") and st.session_state.move_idx > 0: 
                        st.session_state.move_idx -= 1
                        st.rerun()
                    if b2.button("Next ▶") and st.session_state.move_idx < len(moves): 
                        st.session_state.move_idx += 1
                        st.rerun()
                    if st.session_state.blunders:
                        next_b = [b for b in st.session_state.blunders if b > st.session_state.move_idx]
                        if next_b:
                            if b3.button("Next Blunder 🚨"):
                                st.session_state.move_idx = next_b[0]
                                st.rerun()

                    # Analysis Text
                    if current_data:
                        score = current_data['eval']
                        if current_data['is_blunder']:
                            st.error("🚨 BLUNDER")
                            
                            # Retrieve the better move that was calculated
                            # To show it, we need the board state BEFORE this move was made
                            prev_board = game.board()
                            for k in range(st.session_state.move_idx - 1):
                                prev_board.push(moves[k])
                            
                            # Ask engine for that better move again (fastest way to be sure) if not saved perfectly
                            # Or just use the one we saved
                            saved_best = current_data.get('best_move')
                            
                            st.markdown(f"You played: **{moves[st.session_state.move_idx-1]}**")
                            st.markdown(f"Better was: **{saved_best}**")
                            
                            # TOGGLE SWITCH
                            view_choice = st.radio("Visualize:", ["Actual Mistake", "Better Move"], horizontal=True)
                            if view_choice == "Better Move" and saved_best:
                                show_alternate = True
                                # Recalculate display board for the 'Better' path
                                display_board = prev_board # Step back
                                display_board.push(saved_best) # Push the good move
                        
                        st.metric("Eval", f"{score:.2f}")

                with col_board:
                    # Render Board
                    arrow = None
                    # If showing alternate, maybe highlight the move in green?
                    
                    board_svg = chess.svg.board(
                        display_board, 
                        size=500,
                        lastmove=display_board.peek() if display_board.move_stack else None
                    )
                    st.image(board_svg, use_column_width=False)


elif st.session_state.app_mode == "Play vs Stockfish":
    # ---------------- PLAY MODE ----------------
    if st.session_state.play_board is None:
        st.session_state.play_board = chess.Board() # Default if no game loaded
    
    board = st.session_state.play_board
    
    st.markdown("### Playing vs Stockfish")
    
    c1, c2 = st.columns([2, 1])
    
    with c1:
        # Check if it's engine's turn immediately
        engine_color = chess.WHITE if user_side == "Black" else chess.BLACK
        if board.turn == engine_color and not board.is_game_over():
            with st.spinner("Computer is thinking..."):
                make_engine_move(board, skill)
                st.rerun()

        # Render Board
        # Flip if user is Black
        orientation = chess.BLACK if user_side == "Black" else chess.WHITE
        board_svg = chess.svg.board(board, size=500, orientation=orientation)
        st.image(board_svg)
    
    with c2:
        # Move Input
        if not board.is_game_over():
            # Get legal moves for dropdown
            legal_moves = [board.san(m) for m in board.legal_moves]
            legal_moves.sort()
            
            # Using a form to prevent reload on every character type
            with st.form("move_form"):
                user_move = st.selectbox("Select your move:", [""] + legal_moves)
                submit = st.form_submit_button("Make Move")
                
                if submit and user_move:
                    try:
                        board.push_san(user_move)
                        st.session_state.play_game_history.append(board.peek())
                        st.rerun()
                    except ValueError:
                        st.error("Illegal move")
        else:
            st.success(f"Game Over! Result: {board.result()}")
        
        # Save Game Logic
        st.divider()
        if st.session_state.play_game_history:
            game_pgn = chess.pgn.Game.from_board(board)
            game_pgn.headers["Event"] = "User vs Stockfish"
            game_pgn.headers["Date"] = datetime.today().strftime('%Y.%m.%d')
            game_pgn.headers["White"] = "Player" if user_side=="White" else f"Stockfish Lvl {skill}"
            game_pgn.headers["Black"] = f"Stockfish Lvl {skill}" if user_side=="White" else "Player"
            
            exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=True)
            pgn_string = game_pgn.accept(exporter)
            
            st.download_button(
                label="💾 Download PGN",
                data=pgn_string,
                file_name=f"vs_stockfish_{datetime.now().strftime('%H%M')}.pgn",
                mime="text/plain"
            )
            
        if st.button("🔙 Back to Analysis"):
            st.session_state.app_mode = "Analysis"
            st.rerun()