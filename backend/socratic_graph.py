# backend/socratic_graph.py
import os
import json
from typing import List, TypedDict
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END

# --- Define the State for our Graph ---
class SocraticState(TypedDict):
    lesson_title: str
    lesson_text: str
    chat_history: List[tuple]
    understanding_score: int

# --- Initialize the AI Models ---
tutor_llm = ChatOpenAI(model="gpt-4o", temperature=0.7)
grader_llm = ChatOpenAI(model="gpt-4o", temperature=0)

# --- Define the Nodes of the Graph ---
def tutor_node(state: SocraticState):
    """Asks a guiding question based on the chat history."""
    system_prompt = f"""
    You are a Socratic Tutor. Your goal is to help a student understand the topic of '{state['lesson_title']}' based on the provided text.
    The original lesson text is: "{state['lesson_text']}"
    Your rules are:
    1. NEVER give the student the answer directly.
    2. ALWAYS ask open-ended, guiding questions that force the student to think.
    3. If the chat history is empty, start with a broad opening question.
    4. Keep your responses short and conversational.
    """
    
    messages = [SystemMessage(content=system_prompt)]
    for role, content in state['chat_history']:
        if role == 'user': messages.append(HumanMessage(content=content))
        else: messages.append(AIMessage(content=content))

    response = tutor_llm.invoke(messages)
    state['chat_history'].append(("assistant", response.content))
    return state

def grader_node(state: SocraticState):
    """Analyzes the conversation and provides a final score."""
    grader_prompt = f"""
    Based on the following conversation, rate the student's understanding on a scale of 1 to 5 (1=no understanding, 5=excellent).
    Respond ONLY with a single number.
    Conversation: {json.dumps(state['chat_history'], indent=2)}
    """
    response = grader_llm.invoke(grader_prompt)
    try:
        state['understanding_score'] = int(response.content.strip())
    except ValueError:
        state['understanding_score'] = 0
    return state

# --- Build the Graph ---
workflow = StateGraph(SocraticState)
workflow.add_node("tutor", tutor_node)
workflow.add_node("grader", grader_node)

# --- THIS IS THE CORRECTED LINE ---
# We set a default entry point to make the graph valid.
workflow.set_entry_point("tutor")

socratic_graph = workflow.compile()
