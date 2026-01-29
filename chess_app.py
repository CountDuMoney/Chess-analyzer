import streamlit as st
import chess
import chess.pgn
import chess.svg
import chess.engine
import io
import shutil
import os

# --- Configuration & Styling ---
st.set_page_config(page_title="Chess Coach V2", layout="wide")

# 1. Find Stockfish (Robust Path Finding)
game_path = "/usr/games/stockfish"
if os.path.exists(game_path):
    STOCKFISH_PATH = game_path
else:
    STOCKFISH_PATH = shutil.which("stockfish")

# --- Session State Initialization ---
# This acts as the app's memory so it remembers analysis between clicks
if "move_idx" not in st.session_state:
    st.session_state.move_idx = 0
if "analysis_data" not in st.session_state:
    st.session_state.analysis_data = {} # Stores scores for each move
if "blunders" not in st.session_state:
    st.session_state.blunders = []      # List of move numbers that were bad

# --- Helper Functions ---
def get_engine_analysis(board, time_limit=0.1):
    """Runs a quick analysis of the specific board position"""
    if not STOCKFISH_PATH:
        return None, None
    
    with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
        result = engine.analyse(board, chess.engine.Limit(time=time_limit))
        score = result["score"].white()
        
        # Get the best move (what they SHOULD have done)
        best_move = result.get("pv")[0] if result.get("pv") else None
        
        # Standardize score to float
        if score.is_mate():
            eval_val = 99.0 if score.mate() > 0 else -99.0
        else:
            eval_val = score.score() / 100.0
            
        return eval_val, best_move

def analyze_full_game(game):
    """Loops through the entire game and saves data"""
    board = game.board()
    moves = list(game.mainline_moves())
    
    data = {}
    blunders = []
    prev_eval = 0.0 # Starting position is 0.0
    
    # Progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, move in enumerate(moves):
        # Update progress
        status_text.text(f"Analyzing move {i+1} of {len(moves)}...")
        progress_bar.progress((i + 1) / len(moves))
        
        # Make the move
        board.push(move)
        
        # Analyze
        curr_eval, best_move_obj = get_engine_analysis(board)
        
        # Detect Blunder (Significant drop in win probability)
        # We compare current evaluation to previous to see the swing
        # Note: We must flip perspective. If White moves, we want high eval. 
        # If eval drops from +1 to -1, White blundered.
        
        diff = curr_eval - prev_eval
        is_blunder = False
        
        # White's turn (i is even, 0, 2, 4...)
        if i % 2 == 0: 
            if diff < -1.5: is_blunder = True # White lost significant advantage
        # Black's turn (i is odd)
        else:
            if diff > 1.5: is_blunder = True # Eval jumped UP (good for White, bad for Black)

        if is_blunder:
            blunders.append(i + 1) # Store move number (1-based)
            
        # Store Data
        data[i+1] = {
            "eval": curr_eval,
            "best_move": best_move_obj,
            "is_blunder": is_blunder
        }
        
        prev_eval = curr_eval
        
    status_text.text("Analysis Complete!")
    return data, blunders

# --- Sidebar ---
with st.sidebar:
    st.title("♟️ Chess Coach")
    pgn_input = st.text_area("Paste PGN:", height=150)
    
    if st.button("Start New Game"):
        # Reset everything
        st.session_state.move_idx = 0
        st.session_state.analysis_data = {}
        st.session_state.blunders = []

# --- Main Logic ---
if pgn_input:
    pgn = io.StringIO(pgn_input)
    game = chess.pgn.read_game(pgn)
    
    if game:
        moves = list(game.mainline_moves())
        board = game.board()
        
        # 1. ANALYZE BUTTON
        if not st.session_state.analysis_data:
            st.info("Game loaded. Click below to generate the report.")
            if st.button("🔍 Analyze Full Game (Find Blunders)"):
                data, blunders = analyze_full_game(game)
                st.session_state.analysis_data = data
                st.session_state.blunders = blunders
                st.rerun()
        
        # 2. NAVIGATION & DISPLAY
        else:
            # Sync board to current move
            for i in range(st.session_state.move_idx):
                board.push(moves[i])
            
            # --- Layout ---
            col1, col2 = st.columns([1, 1])
            
            with col1:
                # Determine Arrows (Show BEST move if current move was a blunder)
                arrows = []
                current_data = st.session_state.analysis_data.get(st.session_state.move_idx)
                
                # If the move we just made was a blunder, show what we SHOULD have done
                # Note: We need the best move from the PREVIOUS position to show the alternative
                # But for simplicity, we usually show the best move in the CURRENT position for the opponent
                # Let's show the "Missed Opportunity":
                # If move 5 was a blunder, we want to show the arrow for what Move 5 SHOULD have been.
                # That requires re-analyzing the board at Move 4. 
                # For speed, let's just use the current board. 
                
                # Check if current move index is in our blunder list
                is_blunder = st.session_state.move_idx in st.session_state.blunders
                
                # Draw Board
                board_svg = chess.svg.board(
                    board, 
                    size=450, 
                    lastmove=moves[st.session_state.move_idx-1] if st.session_state.move_idx > 0 else None,
                    # If it's a blunder, we could draw an arrow, but we'd need the 'best move' from the previous state.
                    # Simple version: Just show the board.
                )
                st.image(board_svg, use_column_width=False)
                
                # Navigation Buttons
                c1, c2, c3, c4 = st.columns(4)
                if c1.button("⏮ Start"): st.session_state.move_idx = 0
                if c2.button("◀ Prev") and st.session_state.move_idx > 0: 
                    st.session_state.move_idx -= 1
                    st.rerun()
                if c3.button("Next ▶") and st.session_state.move_idx < len(moves): 
                    st.session_state.move_idx += 1
                    st.rerun()
                
                # Blunder Skipper
                if st.session_state.blunders:
                    # Find next blunder greater than current index
                    next_blunders = [b for b in st.session_state.blunders if b > st.session_state.move_idx]
                    if next_blunders:
                        if c4.button("Next Blunder 🚨"):
                            st.session_state.move_idx = next_blunders[0]
                            st.rerun()
                    else:
                        c4.button("No more blunders", disabled=True)

            with col2:
                # --- Analysis Panel ---
                st.subheader(f"Move {st.session_state.move_idx}")
                
                # Get data for THIS move
                data_point = st.session_state.analysis_data.get(st.session_state.move_idx)
                
                if data_point:
                    score = data_point['eval']
                    st.metric("Evaluation", f"{score:.2f}")
                    
                    if data_point['is_blunder']:
                        st.error("🚨 BLUNDER DETECTED")
                        st.write("This move significantly hurt your position.")
                        
                        # To show the better move, we need to know what the engine liked BEFORE this move.
                        # Since we are batch processing, we can re-query the previous position quickly here
                        # or simpler: Just tell them "Look for a better move".
                        
                        # Let's do a quick 'Spot Check' for the better move:
                        if st.session_state.move_idx > 0:
                            temp_board = game.board()
                            for k in range(st.session_state.move_idx - 1):
                                temp_board.push(moves[k])
                            
                            # Ask engine quickly
                            val, best_move = get_engine_analysis(temp_board, time_limit=0.1)
                            st.success(f"💡 Better move was: **{best_move}**")

                else:
                    if st.session_state.move_idx == 0:
                        st.info("Start of game.")