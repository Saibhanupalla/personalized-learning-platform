# frontend/app.py
import streamlit as st
import requests
import uuid
import hmac # Used for secure password checking

# --- Configuration ---
# We will change this to the live URL after deploying the backend
BACKEND_BASE_URL = "http://127.0.0.1:8000" 

# --- Page Setup ---
st.set_page_config(page_title="Personalized Learning Platform", layout="wide", initial_sidebar_state="expanded")

# --- Password Protection Logic ---
def check_password():
    """Returns `True` if the user has the correct password."""
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if hmac.compare_digest(st.session_state["password"], st.secrets["APP_PASSWORD"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    # Show the password input form
    st.title("📚 Personalized Learning Platform")
    st.header("Login")
    st.text_input("Password", type="password", on_change=password_entered, key="password")
    if "password_correct" in st.session_state and not st.session_state.password_correct:
        st.error("😕 Password incorrect")
    return False

# --- Main App ---
# This line will stop the app from running until the password is correct.
if not check_password():
    st.stop()

# --- The rest of your app starts here ---
st.title("📚 Personalized Learning Platform")

# --- Initialize Session State ---
if 'role' not in st.session_state: st.session_state.role = None
if 'active_lesson_content' not in st.session_state: st.session_state.active_lesson_content = None
if 'student_style' not in st.session_state: st.session_state.student_style = None
if 'session_history' not in st.session_state: st.session_state.session_history = []
if 'chat_history' not in st.session_state: st.session_state.chat_history = None
if 'final_score' not in st.session_state: st.session_state.final_score = None
if 'session_id' not in st.session_state: st.session_state.session_id = str(uuid.uuid4())
if 'selected_lesson_id' not in st.session_state: st.session_state.selected_lesson_id = None
if 'style_choice' not in st.session_state: st.session_state.style_choice = None
if 'courses' not in st.session_state: st.session_state.courses = None
if 'lessons_cache' not in st.session_state: st.session_state.lessons_cache = {}


# --- API Helper ---
def api_request(method, endpoint, data=None):
    url = f"{BACKEND_BASE_URL}{endpoint}"
    try:
        if method.lower() == 'post': response = requests.post(url, json=data)
        elif method.lower() == 'delete': response = requests.delete(url)
        else: response = requests.get(url)
        response.raise_for_status()
        if response.status_code == 204: return True
        return response.json()
    except Exception as e:
        st.error(f"An error occurred: {e}")
    return None

# --- VARK Quiz Logic & Callbacks ---
VARK_QUESTIONS = {
    "questions": [
        {"question": "When learning a new skill, I prefer to...", "options": ["V) Watch a video demonstration.", "A) Listen to an expert explain it.", "R) Read the instructions.", "K) Jump in and try it myself."]},
        {"question": "When I'm trying to remember directions, I...", "options": ["V) Picture the route in my head.", "A) Repeat the street names out loud.", "R) Write down the directions.", "K) Rely on my sense of direction."]},
    ]
}

def calculate_style(answers):
    counts = {'V': 0, 'A': 0, 'R': 0, 'K': 0}
    for answer in answers.values():
        if answer: counts[answer[0]] += 1
    dominant_style = max(counts, key=counts.get)
    style_map = {'V': 'Visual', 'A': 'Auditory', 'R': 'Reading/Writing', 'K': 'Kinesthetic'}
    st.session_state.student_style = style_map[dominant_style]
    st.rerun()

# --- Role Selection Screen ---
if st.session_state.role is None:
    st.header("Welcome!")
    st.write("Please select your role to get started.")
    col1, col2 = st.columns(2)
    if col1.button("I am a Teacher 👩‍🏫", use_container_width=True): st.session_state.role = 'teacher'; st.rerun()
    if col2.button("I am a Student 🧑‍🎓", use_container_width=True): st.session_state.role = 'student'; st.rerun()

# --- Main App Logic ---
else:
    st.sidebar.success(f"Current Role: **{st.session_state.role.title()}**")
    if st.sidebar.button("Switch Role"):
        for key in st.session_state.keys():
            if key != 'password_correct':
                del st.session_state[key]
        st.rerun()

    # --- Teacher View ---
    if st.session_state.role == 'teacher':
        st.header("Teacher Dashboard")
        st.subheader("Create a New Course")
        with st.form("new_course_form", clear_on_submit=True):
            course_name = st.text_input("Course Name")
            if st.form_submit_button("Create Course"):
                if course_name:
                    payload = {"course_name": course_name, "teacher_id": 1}
                    if api_request('post', '/courses', payload):
                        st.success(f"Course '{course_name}' created!")
                        st.session_state.courses = None
        st.write("---")
        st.subheader("Add or Manage Lessons")
        
        if st.session_state.courses is None:
            st.session_state.courses = api_request('get', '/courses')
        courses = st.session_state.courses
        
        if not courses:
            st.warning("No courses found. Please create a course first.")
        else:
            course_options = {c['course_name']: c['id'] for c in courses}
            selected_course_name = st.selectbox("Choose a course:", options=course_options.keys())
            selected_course_id = course_options[selected_course_name]

            if selected_course_id not in st.session_state.lessons_cache:
                st.session_state.lessons_cache[selected_course_id] = api_request('get', f'/courses/{selected_course_id}/lessons')
            existing_lessons = st.session_state.lessons_cache[selected_course_id]

            if existing_lessons:
                with st.expander("View existing lessons in this course", expanded=True):
                    for lesson in existing_lessons:
                        col1, col2 = st.columns([4, 1])
                        col1.markdown(f"- {lesson['lesson_title']}")
                        if col2.button("Delete", key=f"delete_{lesson['id']}", use_container_width=True):
                            if api_request('delete', f"/lessons/{lesson['id']}"):
                                st.success(f"Lesson '{lesson['lesson_title']}' deleted.")
                                st.session_state.lessons_cache[selected_course_id] = None
                                st.rerun()
            with st.form(f"lesson_form_{selected_course_id}", clear_on_submit=True):
                lesson_title = st.text_input("New Lesson Title")
                original_text = st.text_area("Lesson Content (Text)", height=250)
                if st.form_submit_button("Add Lesson"):
                    existing_titles = [l['lesson_title'].lower() for l in existing_lessons] if existing_lessons else []
                    if lesson_title.lower() in existing_titles:
                        st.error(f"A lesson with the title '{lesson_title}' already exists in this course.")
                    elif all([selected_course_name, lesson_title, original_text]):
                        payload = {"course_id": selected_course_id, "lesson_title": lesson_title, "original_text": original_text}
                        if api_request('post', '/lessons', payload):
                            st.success(f"Lesson '{lesson_title}' added!")
                            st.session_state.lessons_cache[selected_course_id] = None
                            st.rerun()

    # --- Student View ---
    elif st.session_state.role == 'student':
        if not st.session_state.student_style:
            st.header("Let's discover your learning style!", divider="rainbow")
            with st.form("vark_quiz"):
                answers = {}
                for i, q in enumerate(VARK_QUESTIONS["questions"]):
                    answers[f'q{i}'] = st.radio(q['question'], q['options'], index=None)
                if st.form_submit_button("Find My Style", type="primary"):
                    calculate_style(answers)
        else:
            st.sidebar.header("🎓 Student Portal")
            st.sidebar.info(f"Your preferred style is **{st.session_state.student_style}**.")
            
            if st.session_state.courses is None:
                st.session_state.courses = api_request('get', '/courses')
            courses = st.session_state.courses
            
            if courses:
                course_options = {c['course_name']: c['id'] for c in courses}
                selected_course_name = st.sidebar.selectbox("Select a course:", options=course_options.keys(), key="student_course_select")
                selected_course_id = course_options[selected_course_name]

                if selected_course_id not in st.session_state.lessons_cache:
                    st.session_state.lessons_cache[selected_course_id] = api_request('get', f'/courses/{selected_course_id}/lessons')
                lessons = st.session_state.lessons_cache[selected_course_id]

                if lessons:
                    st.sidebar.subheader("Lessons")
                    for lesson in lessons:
                        if st.sidebar.button(lesson['lesson_title'], key=f"lesson_{lesson['id']}", use_container_width=True):
                            st.session_state.selected_lesson_id = lesson['id']
                            st.session_state.active_lesson_content = None 
                            st.session_state.style_choice = None 
                            st.session_state.chat_history = None
                            st.session_state.final_score = None
                            st.rerun()

            if st.session_state.selected_lesson_id and not st.session_state.active_lesson_content:
                lesson_id = st.session_state.selected_lesson_id
                recommendation = api_request('get', f'/lessons/{lesson_id}/recommend-style')
                recommended_style = recommendation.get('recommended_style') if recommendation else None
                if recommended_style and not st.session_state.style_choice:
                    st.info(f"💡 Based on previous student performance, the **{recommended_style}** style is most effective for this topic.")
                    col1, col2 = st.columns(2)
                    if col1.button(f"Use recommended style ({recommended_style})", use_container_width=True, type="primary"):
                        st.session_state.style_choice = recommended_style
                        st.rerun()
                    if col2.button(f"Use my default style ({st.session_state.student_style})", use_container_width=True):
                        st.session_state.style_choice = st.session_state.student_style
                        st.rerun()
                else:
                    style_to_use = st.session_state.style_choice or st.session_state.student_style
                    with st.spinner(f"Adapting lesson using '{style_to_use}' style..."):
                        payload = {"lesson_id": lesson_id, "style": style_to_use}
                        adapted_content = api_request('post', '/generate-adapted-content', payload)
                        if adapted_content:
                            st.session_state.active_lesson_content = adapted_content
                            st.rerun()

            elif st.session_state.active_lesson_content:
                content = st.session_state.active_lesson_content
                st.header(f"Lesson: {content.get('lesson_title', 'Content')}")
                st.subheader(f"Style: {content.get('learning_style')}")
                st.write("---")
                content_type = content.get("content_type")
                content_data = content.get("data", {})
                if content_type == 'text': st.markdown(content_data.get("text"))
                elif content_type == 'image': st.image(content_data.get("url"))
                elif content_type == 'audio':
                    full_audio_url = f"{BACKEND_BASE_URL}{content_data.get('url')}"
                    st.audio(full_audio_url)
                    if transcript := content_data.get("transcript"):
                        with st.expander("View Transcript"): st.write(transcript)
                
                st.write("---")
                st.header("✅ Check Your Understanding")
                if 'chat_history' not in st.session_state or st.session_state.chat_history is None:
                    st.session_state.chat_history = []
                    with st.spinner("Tutor is preparing a question..."):
                        payload = {"lesson_id": content['lesson_id'], "style": content['learning_style'], "chat_history": []}
                        response = api_request('post', '/socratic-chat', payload)
                        if response:
                            st.session_state.chat_history = [("assistant", response['content'])]
                            st.rerun()
                
                for role, text in st.session_state.chat_history:
                    with st.chat_message(role):
                        st.markdown(text)
                
                user_messages_count = sum(1 for role, _ in st.session_state.chat_history if role == 'user')
                CONVERSATION_TURNS = 2

                if st.session_state.get('final_score') is not None:
                    st.success(f"Great discussion! Your final understanding score is: **{st.session_state.final_score}/5**")
                elif user_messages_count >= CONVERSATION_TURNS:
                    st.info("You've completed the discussion. Let's see how you did!")
                    if st.button("Grade My Understanding", type="primary"):
                        with st.spinner("Grading your conversation..."):
                            payload = {"lesson_id": content['lesson_id'], "style": content['learning_style'], "chat_history": st.session_state.chat_history}
                            response = api_request('post', '/grade-conversation', payload)
                            if response:
                                st.session_state.final_score = response.get('final_score')
                                st.rerun()
                else:
                    if prompt := st.chat_input("Explain what you learned..."):
                        st.session_state.chat_history.append(("user", prompt))
                        with st.chat_message("user"): st.markdown(prompt)
                        with st.spinner("Tutor is thinking..."):
                            payload = {"lesson_id": content['lesson_id'], "style": content['learning_style'], "chat_history": st.session_state.chat_history}
                            response = api_request('post', '/socratic-chat', payload)
                            if response:
                                st.session_state.chat_history.append(("assistant", response['content']))
                                st.rerun()
            else:
                st.info("Welcome, Student! Please select a lesson from the sidebar to begin.")
