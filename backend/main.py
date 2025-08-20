# backend/main.py
import os
import sqlite3
import json
import uuid
from fastapi import FastAPI, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv 
import database
import openai
import vector_db
from socratic_graph import socratic_graph

# --- Configuration & Initialization ---
load_dotenv()
app = FastAPI(title="Personalized Learning API")
DATABASE_NAME = "learning_platform.db"
openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI()
TEMP_AUDIO_DIR = "temp_audio"

os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)
app.mount(f"/{TEMP_AUDIO_DIR}", StaticFiles(directory=TEMP_AUDIO_DIR), name="temp_audio")

@app.on_event("startup")
def on_startup():
    database.init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---
class CourseCreate(BaseModel):
    course_name: str
    teacher_id: int 

class LessonCreate(BaseModel):
    lesson_title: str
    course_id: int
    original_text: str

class AdaptationRequest(BaseModel):
    lesson_id: int
    style: str

class SocraticRequest(BaseModel):
    lesson_id: int
    style: str
    chat_history: list

# --- GenAI Helper Functions ---
def generate_text_from_gpt(prompt):
    messages = [{"role": "system", "content": "You are a helpful AI assistant."}]
    if isinstance(prompt, list):
        messages.extend(prompt)
    else:
        messages.append({"role": "user", "content": prompt})
        
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages
    )
    return response.choices[0].message.content

def generate_image_from_dalle(prompt: str) -> str:
    response = client.images.generate(model="dall-e-3", prompt=prompt, n=1, size="1024x1024", response_format="url")
    return response.data[0].url

def generate_audio_from_openai(prompt: str) -> dict:
    script_text = generate_text_from_gpt(prompt)
    response = client.audio.speech.create(model="tts-1", voice="alloy", input=script_text)
    file_name = f"{uuid.uuid4()}.mp3"
    file_path = os.path.join(TEMP_AUDIO_DIR, file_name)
    response.stream_to_file(file_path)
    audio_url = f"/{TEMP_AUDIO_DIR}/{file_name}"
    return {"url": audio_url, "transcript": script_text}

# --- Teacher Endpoints ---
@app.post("/courses", status_code=status.HTTP_201_CREATED)
def create_course(course: CourseCreate):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO courses (course_name, teacher_id) VALUES (?, ?)", (course.course_name, course.teacher_id))
    conn.commit()
    course_id = cursor.lastrowid
    conn.close()
    return {"course_id": course_id, "course_name": course.course_name}

@app.post("/lessons", status_code=status.HTTP_201_CREATED)
def create_lesson(lesson: LessonCreate):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO lessons (lesson_title, course_id, original_text) VALUES (?, ?, ?)", (lesson.lesson_title, lesson.course_id, lesson.original_text))
    conn.commit()
    lesson_id = cursor.lastrowid
    conn.close()
    vector_db.upsert_lesson(lesson_id=lesson_id, lesson_text=lesson.original_text)
    return {"lesson_id": lesson_id, **lesson.dict()}

@app.get("/courses")
def get_all_courses():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, course_name FROM courses")
    courses = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return courses

@app.get("/courses/{course_id}/lessons")
def get_lessons_for_course(course_id: int):
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, lesson_title FROM lessons WHERE course_id = ?", (course_id,))
    lessons = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return lessons

@app.delete("/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lesson(lesson_id: int):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lessons WHERE id = ?", (lesson_id,))
    conn.commit()
    conn.close()
    return

# --- Student Endpoints ---
@app.get("/lessons/{lesson_id}/similar")
def get_similar_lessons(lesson_id: int):
    similar_ids = vector_db.find_similar_lessons(lesson_id)
    if not similar_ids: return []
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    placeholders = ','.join('?' for _ in similar_ids)
    query = f"SELECT l.id, l.lesson_title, c.course_name FROM lessons l JOIN courses c ON l.course_id = c.id WHERE l.id IN ({placeholders})"
    cursor.execute(query, similar_ids)
    lessons = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return lessons

@app.post("/generate-adapted-content")
def generate_adapted_content(request: AdaptationRequest):
    lesson_id = request.lesson_id
    style = request.style
    cached = database.get_cached_content(lesson_id, style)
    if cached:
        print(f"Serving lesson {lesson_id} ({style}) from cache.")
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT lesson_title FROM lessons WHERE id = ?", (lesson_id,))
        lesson_title_tuple = cursor.fetchone()
        conn.close()
        lesson_title = lesson_title_tuple[0] if lesson_title_tuple else "Unknown Topic"
        return {"lesson_id": lesson_id, "lesson_title": lesson_title, "learning_style": style, "content_type": cached["content_type"], "data": cached["data"]}
    
    print(f"Lesson {lesson_id} ({style}) not in cache. Generating new content.")
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT lesson_title, original_text FROM lessons WHERE id = ?", (lesson_id,))
    lesson_row = cursor.fetchone()
    conn.close()
    if not lesson_row: raise HTTPException(status_code=404, detail="Lesson not found")
    
    original_text, lesson_title = lesson_row['original_text'], lesson_row['lesson_title']
    content_data = {}
    content_type = "text"

    if style == "Visual":
        content_type = "image"
        prompt = f"Based on the following text, create a simple, clear educational infographic. Text: '{original_text}'"
        content_data = {"url": generate_image_from_dalle(prompt)}
    elif style == "Auditory":
        content_type = "audio"
        prompt = f"Based on the following text, create a short, engaging audio script. Text: '{original_text}'"
        content_data = generate_audio_from_openai(prompt)
    else:
        content_type = "text"
        prompt = f"Rewrite the following text in a clear, well-structured format. Text: '{original_text}'"
        content_data = {"text": generate_text_from_gpt(prompt)}
    
    database.cache_content(lesson_id, style, content_type, content_data, None)
    
    return {"lesson_id": lesson_id, "lesson_title": lesson_title, "learning_style": style, "content_type": content_type, "data": content_data}

# --- CORRECTED Socratic Endpoints ---
@app.post("/socratic-chat")
def socratic_chat(request: SocraticRequest):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT lesson_title, original_text FROM lessons WHERE id = ?", (request.lesson_id,))
    lesson_row = cursor.fetchone()
    conn.close()
    if not lesson_row: raise HTTPException(status_code=404, detail="Lesson not found")
    
    lesson_title, original_text = lesson_row
    
    system_prompt = f"""
    You are a Socratic Tutor helping a student understand '{lesson_title}'.
    The lesson text is: "{original_text}"
    Your rules: NEVER give direct answers. ALWAYS ask short, open-ended questions to guide the student.
    Start the conversation with a broad opening question.
    """
    
    messages = [{"role": "system", "content": system_prompt}]
    for role, content in request.chat_history:
        messages.append({"role": role, "content": content})

    response = client.chat.completions.create(model="gpt-4o", messages=messages)
    tutor_response = response.choices[0].message.content

    return {"role": "assistant", "content": tutor_response}

@app.post("/grade-conversation")
def grade_conversation(request: SocraticRequest):
    grader_prompt = f"""
    Based on the following conversation, rate the student's understanding on a scale of 1 to 5.
    Respond ONLY with a single number.
    Conversation: {json.dumps(request.chat_history, indent=2)}
    """
    try:
        score_str = generate_text_from_gpt(grader_prompt)
        score = int(score_str.strip())
        
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO socratic_dialogues (lesson_id, session_id, style, conversation_history, understanding_score) VALUES (?, ?, ?, ?, ?)",
            (request.lesson_id, "session_placeholder", request.style, json.dumps(request.chat_history), score)
        )
        conn.commit()
        conn.close()
        
        return {"final_score": score}
    except Exception as e:
        return {"final_score": 0}

@app.get("/lessons/{lesson_id}/recommend-style")
def recommend_style(lesson_id: int):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT style, AVG(understanding_score) as avg_score
        FROM socratic_dialogues
        WHERE lesson_id = ?
        GROUP BY style
        ORDER BY avg_score DESC, COUNT(id) DESC
    """, (lesson_id,))
    result = cursor.fetchone()
    conn.close()
    if result and result[1] >= 4.0:
        return {"recommended_style": result[0]}
    return {"recommended_style": None}

