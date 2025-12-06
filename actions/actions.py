# --- V10: Phased Elicitation Fix ---
print("\n[ACTIONS.PY] --- Loading actions.py (V10) ---")

from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, BotUttered
import json
import sqlite3
import requests
from datetime import datetime
import re
print("[ACTIONS.PY] All V10 imports successful.")

# ============================================
# OLLAMA & DB CONFIG
# ============================================
OLLAMA_API_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "phi3:mini"
OLLAMA_TIMEOUT = 120 
DB_PATH = "requirements.db"

# ============================================
# PROMPT DICTIONARY
# This is the new "brain" for your bot
# ============================================
SYSTEM_PROMPTS = {
    "vision": """
You are a friendly Business Analyst. Your goal is to understand the user's high-level project vision.
Ask simple, open-ended questions about the project, what it is, and who it is for.
DO NOT ask about specific features, performance, or budget yet.
When you feel you understand the vision, in your analysis JSON set "next_phase" to "functional".

You MUST respond with a SINGLE, valid JSON object with "reply" and "analysis" keys.
The "analysis" object MUST have "type", "priority", "requirement", and "next_phase" keys.
""",
    "functional": """
You are a Business Analyst. You have the project vision. Now, your goal is to elicit FUNCTIONAL requirements (features).
Ask simple, one-at-a-time questions like "What about user logins?", "Do you need a search bar?", "Will you sell products online?".
Refer to the attached SRS.doc for feature examples (e.g., shopping cart, product reviews).
Keep asking for features until the user says they are done.
When the user has no more features, set "next_phase" to "non_functional".

You MUST respond with a SINGLE, valid JSON object with "reply" and "analysis" keys.
The "analysis" object MUST have "type", "priority", "requirement", and "next_phase" keys.
""",
    "non_functional": """
You are a Business Analyst. You have the features. Now, elicit NON-FUNCTIONAL requirements.
Ask simple, one-at-a-time questions about:
1.  **Performance:** "How many users should it support?" (like the user said 200,000)
2.  **Usability:** "Should the design be simple? Any accessibility needs?"
3.  **Security:** "How important is security? (e.g., for payments)"
When you have enough NFRs, set "next_phase" to "constraints".

You MUST respond with a SINGLE, valid JSON object with "reply" and "analysis" keys.
The "analysis" object MUST have "type", "priority", "requirement", and "next_phase" keys.
""",
    "constraints": """
You are a Business Analyst. You have the features and NFRs. Now, you MUST ask about CONSTRAINTS.
Ask simple, direct questions one at a time about:
1.  **Timeline:** "What is your deadline for this project?"
2.  **Budget:** "Is there a specific budget we should work within?"
3.  **Technology:** "Are there any preferred technologies (e.g., Python, AWS)?"
When you are done, set "next_phase" to "done".

You MUST respond with a SINGLE, valid JSON object with "reply" and "analysis" keys.
The "analysis" object MUST have "type", "priority", "requirement", and "next_phase" keys.
"""
}


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_conversation_history(tracker: Tracker) -> List[Dict[str, str]]:
    print("[HISTORY] Building conversation history...")
    history = []
    for event in reversed(tracker.events):
        if event['event'] == 'user':
            history.append({"role": "user", "content": event['text']})
        elif event['event'] == 'bot':
            if event.get('text'):
                history.append({"role": "assistant", "content": event['text']})
        if len(history) >= 10:
            break
    print(f"[HISTORY] Found {len(history)} messages.")
    return list(reversed(history))

# ============================================
# THE "MASTER" ACTION (V10)
# ============================================

class ActionIntelligentAnalysis(Action):

    def name(self) -> Text:
        return "action_intelligent_analysis"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        print("\n--- [ACTION] 'action_intelligent_analysis' CALLED ---")

        # 1. Get current state
        user_message = tracker.latest_message.get("text", "")
        current_phase = tracker.get_slot("elicitation_phase") or "vision"
        
        # Handle the 'done' phase
        if current_phase == "done":
            print("[ACTION] Elicitation is done.")
            return [BotUttered(text="I believe I have all the core requirements. Thank you! You can now export the SRS.", metadata={"from_action": "action_intelligent_analysis"})]

        project_id = tracker.get_slot("project_id") or 1
        print(f"[ACTION] Project ID: {project_id}, Phase: {current_phase}, User Message: {user_message}")
        conversation_history = get_conversation_history(tracker)
        conversation_history.append({"role": "user", "content": user_message})

        # 2. Get the correct prompt for the current phase
        system_prompt = SYSTEM_PROMPTS.get(current_phase, SYSTEM_PROMPTS["vision"])

        # 3. Format payload
        messages_payload = [
            {"role": "system", "content": system_prompt}
        ]
        messages_payload.extend(conversation_history)
        
        payload = {
            "model": OLLAMA_MODEL,
            "messages": messages_payload,
            "stream": False,
            "format": "json"
        }

        # 4. Call Ollama
        try:
            print(f"[ACTION] Calling Ollama for phase '{current_phase}'...")
            response = requests.post(
                OLLAMA_API_URL,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=OLLAMA_TIMEOUT
            )
            response.raise_for_status()
            print("[ACTION] Ollama request successful.")

            response_data = response.json()
            response_json = json.loads(response_data['message']['content'])
            print("[ACTION] Successfully decoded JSON from Ollama.")
            
            bot_response_text_raw = response_json.get("reply")
            bot_response_text = str(bot_response_text_raw) if bot_response_text_raw is not None else "I'm not sure what to say. Could you rephrase?"

            analysis_data_raw = response_json.get("analysis")
            analysis_data = analysis_data_raw if isinstance(analysis_data_raw, dict) else {}
            
            print(f"[ACTION] Ollama reply: {bot_response_text[:50]}...")
            self.save_analysis_to_db(analysis_data, project_id, user_message)

            # 5. Check for phase change
            next_phase = analysis_data.get("next_phase", current_phase)
            if next_phase != current_phase and next_phase in ["functional", "non_functional", "constraints", "done"]:
                print(f"[ACTION] === CHANGING PHASE TO: {next_phase} ===")
                return [SlotSet("elicitation_phase", next_phase), BotUttered(text=bot_response_text, metadata={"from_action": "action_intelligent_analysis"})]

        except requests.exceptions.Timeout:
            print(f"[OLLAMA ERROR] Request timed out after {OLLAMA_TIMEOUT}s.")
            bot_response_text = "I'm taking a bit longer to think than usual. Could you please repeat that?"
        except Exception as e:
            print(f"[ACTION ERROR] An unexpected error occurred: {e}")
            bot_response_text = "I seem to have run into an unknown error. Please try again."
        
        print(f"[ACTION] Returning message to Rasa Core.")
        return [BotUttered(text=bot_response_text, metadata={"from_action": "action_intelligent_analysis"})]

    def save_analysis_to_db(self, analysis_data: Dict[str, Any], project_id: int, user_message: str):
        try:
            # Use the analysis data to save
            req_type = analysis_data.get("type", "General")
            priority = analysis_data.get("priority", "medium")
            content = analysis_data.get("requirement", user_message) # Default to user message

            if req_type == "General":
                print("[DB SAVE] 'General' message, not saving.")
                return 

            table_name = "requirements"
            if req_type == "Ambiguity":
                table_name = "ambiguities"
            elif req_type == "Contradiction":
                table_name = "contradictions"

            conn = get_db_connection()
            cursor = conn.cursor()
            
            if table_name == "requirements":
                cursor.execute(
                    "INSERT INTO requirements (project_id, content, req_type, priority, status, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                    (project_id, content, req_type, priority, 'captured', datetime.now().isoformat())
                )
            else: 
                db_content = f"Original Message: '{user_message}' | Analysis: '{content}'"
                cursor.execute(
                    f"INSERT INTO {table_name} (project_id, content, status, timestamp) VALUES (?, ?, ?, ?)",
                    (project_id, db_content, 'detected', datetime.now().isoformat())
                )
            
            conn.commit()
            conn.close()
            print(f"[DB SAVE] Saved '{req_type}' to {table_name}.")

        except Exception as e:
            print(f"[DB SAVE ERROR] {e}")

# ============================================
# PROJECT ID ACTION
# ============================================
class ActionSetProjectId(Action):
    def name(self) -> Text:
        return "action_set_project_id"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        print("\n--- [ACTION] 'action_set_project_id' CALLED ---")
        print("[ACTION] Set project_id to 1.0")
        # Start the elicitation in the 'vision' phase
        return [SlotSet("project_id", 1.0), SlotSet("elicitation_phase", "vision")]

# --- V10: FILE HAS FINISHED LOADING ---
print("[ACTIONS.PY] --- Finished loading actions.py (V10) ---")