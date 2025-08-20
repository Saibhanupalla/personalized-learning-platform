# backend/simulate_data.py
import sqlite3
import random
import json

DATABASE_NAME = "learning_platform.db"

def run_simulation():
    """Generates simulated student performance data and saves it to the database."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Clear any old simulation data from the correct table
    cursor.execute("DELETE FROM socratic_dialogues")
    conn.commit()

    # --- Simulation Parameters ---
    lessons_to_test = [1, 2, 3] # IDs of the lessons you want to simulate
    num_students_per_group = 50
    styles = ["Visual", "Auditory", "Reading/Writing"]
    
    # Define the "best" style for each lesson to test our hypothesis
    optimal_styles = {
        1: "Visual",            # e.g., "What is a Cell?" is best visually
        2: "Reading/Writing",   # e.g., "The Silk Road" is best with text
        3: "Auditory"           # e.g., "Supply and Demand" is best explained
    }

    # Simulate sessions for 100 virtual students
    for i in range(num_students_per_group * 2):
        session_id = f"simulated_session_{i}"
        for lesson_id in lessons_to_test:
            chosen_style = random.choice(styles)
            
            # Simulate a higher score if the chosen style is the "optimal" one
            is_optimal = chosen_style == optimal_styles.get(lesson_id)
            if is_optimal:
                # Assign a high score (4 or 5)
                score = random.choice([4, 5])
            else:
                # Assign a lower score (1, 2, or 3)
                score = random.choice([1, 2, 3])

            # Create a dummy conversation history
            conversation_history = json.dumps([
                ("assistant", "What was the main idea?"),
                ("user", f"A simulated answer for style {chosen_style}.")
            ])
            
            cursor.execute(
                "INSERT INTO socratic_dialogues (lesson_id, session_id, style, conversation_history, understanding_score) VALUES (?, ?, ?, ?, ?)",
                (lesson_id, session_id, chosen_style, conversation_history, score)
            )
    
    conn.commit()
    conn.close()
    print(f"Successfully simulated data for {num_students_per_group * 2} virtual students.")
    return {"status": "success", "message": "Simulated data generated."}

