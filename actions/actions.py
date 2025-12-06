# actions/actions.py (V11 - ENHANCED OLLAMA INTEGRATION)
print("\n[ACTIONS.PY] --- Loading actions.py (V11 - Enhanced Ollama) ---")

from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, BotUttered
import json
import sqlite3
import requests
from datetime import datetime
import re

print("[ACTIONS.PY] All imports successful.")

# ============================================
# OLLAMA & DB CONFIG
# ============================================
OLLAMA_API_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "phi3:mini"
OLLAMA_TIMEOUT = 120 
DB_PATH = "requirements.db"

# ============================================
# SYSTEM PROMPTS WITH EXAMPLES
# ============================================
SYSTEM_PROMPTS = {
    "vision": """
You are a Business Analyst helping capture project requirements. You are in the VISION phase.

Your GOAL: Understand the user's high-level project vision and goals.
Ask about:
- What is the project about?
- Who will use it?
- What problem does it solve?

DO NOT ask about specific features, performance, or budget yet.

IMPORTANT: Respond with VALID JSON only, no other text.
{
  "reply": "Your conversational response here",
  "analysis": {
    "type": "General|Requirement|Ambiguity|Contradiction",
    "priority": "high|medium|low",
    "requirement": "Extracted requirement or observation",
    "next_phase": "vision|functional|non_functional|constraints|done"
  }
}

When you have understood the vision, set "next_phase" to "functional".
""",
    
    "functional": """
You are a Business Analyst. You are in the FUNCTIONAL REQUIREMENTS phase.

Your GOAL: Elicit FEATURES and FUNCTIONAL requirements one at a time.
Ask about:
- What key features should it have?
- Who are the main users?
- What main tasks should users perform?
- Any specific workflows or processes?

When asking about a new feature, extract it as a requirement.
When user says they're done with features, set "next_phase" to "non_functional".

IMPORTANT: Respond with VALID JSON only, no other text.
{
  "reply": "Your conversational response here",
  "analysis": {
    "type": "General|Requirement|Ambiguity|Contradiction",
    "priority": "high|medium|low",
    "requirement": "Extracted feature or requirement",
    "next_phase": "vision|functional|non_functional|constraints|done"
  }
}

Example ambiguity: "You mentioned users but didn't specify HOW MANY. This is ambiguous."
""",
    
    "non_functional": """
You are a Business Analyst. You are in the NON-FUNCTIONAL REQUIREMENTS phase.

Your GOAL: Elicit NON-FUNCTIONAL requirements about performance, usability, security, etc.
Ask about:
1. Performance: "How many users should it support simultaneously?"
2. Usability: "Should it be mobile-friendly? Any accessibility needs?"
3. Security: "How sensitive is the data? Do you need encryption?"
4. Reliability: "What uptime percentage do you need?"

Extract each as a non-functional requirement.
When done, set "next_phase" to "constraints".

IMPORTANT: Respond with VALID JSON only, no other text.
{
  "reply": "Your conversational response here",
  "analysis": {
    "type": "General|Requirement|Ambiguity|Contradiction",
    "priority": "high|medium|low",
    "requirement": "Non-functional requirement extracted",
    "next_phase": "vision|functional|non_functional|constraints|done"
  }
}
""",
    
    "constraints": """
You are a Business Analyst. You are in the CONSTRAINTS phase.

Your GOAL: Elicit PROJECT CONSTRAINTS.
Ask about:
1. Timeline: "What's your deadline?"
2. Budget: "Is there a budget constraint?"
3. Technology: "Any preferred/restricted technologies?"
4. Resources: "How many people will work on this?"

Extract constraints as requirements with type "Constraint".
When done, set "next_phase" to "done".

IMPORTANT: Respond with VALID JSON only, no other text.
{
  "reply": "Your conversational response here",
  "analysis": {
    "type": "General|Requirement|Ambiguity|Contradiction|Constraint",
    "priority": "high|medium|low",
    "requirement": "Constraint extracted",
    "next_phase": "vision|functional|non_functional|constraints|done"
  }
}
""",
}

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_conversation_history(tracker: Tracker) -> List[Dict[str, str]]:
    """Extract recent conversation history from Rasa tracker."""
    print("[HISTORY] Building conversation history...")
    history = []
    
    # Get events in reverse to collect recent messages
    for event in reversed(tracker.events):
        if event['event'] == 'user':
            history.insert(0, {"role": "user", "content": event['text']})
        elif event['event'] == 'bot':
            if event.get('text'):
                history.insert(0, {"role": "assistant", "content": event['text']})
        
        # Keep last 10 exchanges to avoid token limits
        if len(history) >= 20:
            break
    
    print(f"[HISTORY] Found {len(history)} messages.")
    return history

class ActionIntelligentAnalysis(Action):
    """
    FIX #3: This is the MAIN action that calls Ollama and saves analysis to DB.
    It's triggered for every user message and handles phase progression.
    """
    
    def name(self) -> Text:
        return "action_intelligent_analysis"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        print("\n" + "="*60)
        print("[ACTION] 'action_intelligent_analysis' CALLED")
        print("="*60)

        # 1. Get current state
        user_message = tracker.latest_message.get("text", "")
        current_phase = tracker.get_slot("elicitation_phase") or "vision"
        project_id = tracker.get_slot("project_id") or 1
        
        print(f"[STATE] Project: {project_id}, Phase: {current_phase}")
        print(f"[USER] Message: {user_message[:100]}...")
        
        # Handle 'done' phase
        if current_phase == "done":
            print("[ACTION] Elicitation complete.")
            return [BotUttered(
                text="✅ I believe I have captured all essential requirements. You can now export your SRS document. Great work!",
                metadata={"from_action": "action_intelligent_analysis"}
            )]

        # 2. Build conversation history
        conversation_history = get_conversation_history(tracker)
        conversation_history.append({"role": "user", "content": user_message})

        # 3. Get system prompt for current phase
        system_prompt = SYSTEM_PROMPTS.get(current_phase, SYSTEM_PROMPTS["vision"])

        # 4. Build Ollama payload
        messages_payload = [{"role": "system", "content": system_prompt}]
        messages_payload.extend(conversation_history)
        
        payload = {
            "model": OLLAMA_MODEL,
            "messages": messages_payload,
            "stream": False
        }

        # 5. Call Ollama
        try:
            print(f"[OLLAMA] Calling {OLLAMA_MODEL} for phase '{current_phase}'...")
            response = requests.post(
                OLLAMA_API_URL,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=OLLAMA_TIMEOUT
            )
            response.raise_for_status()
            print("[OLLAMA] Request successful.")

            # 6. Parse Ollama response
            response_data = response.json()
            response_text = response_data.get('message', {}).get('content', '')
            
            # Try to extract JSON
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    response_json = json.loads(json_match.group())
                    print("[PARSE] JSON extracted successfully.")
                except json.JSONDecodeError:
                    print("[PARSE] JSON parsing failed, using plain text.")
                    response_json = {"reply": response_text, "analysis": {"type": "General"}}
            else:
                print("[PARSE] No JSON found, using plain text.")
                response_json = {"reply": response_text, "analysis": {"type": "General"}}
            
            # 7. Extract analysis and reply
            bot_response_text = response_json.get("reply", response_text)
            analysis_data = response_json.get("analysis", {})
            
            print(f"[RESPONSE] {bot_response_text[:80]}...")
            
            # 8. Save analysis to database
            self.save_analysis_to_db(analysis_data, project_id, user_message)

            # 9. Check for phase transition
            next_phase = analysis_data.get("next_phase", current_phase)
            if next_phase != current_phase and next_phase in ["functional", "non_functional", "constraints", "done"]:
                print(f"[PHASE CHANGE] {current_phase} → {next_phase}")
                return [
                    SlotSet("elicitation_phase", next_phase),
                    BotUttered(text=bot_response_text, metadata={"from_action": "action_intelligent_analysis"})
                ]
            
            # No phase change
            return [BotUttered(text=bot_response_text, metadata={"from_action": "action_intelligent_analysis"})]

        except requests.exceptions.Timeout:
            print(f"[ERROR] Ollama timeout after {OLLAMA_TIMEOUT}s")
            bot_response_text = "I'm thinking... please give me a moment. Could you repeat that?"
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
            bot_response_text = "I encountered an error. Could you please rephrase that?"
        
        return [BotUttered(text=bot_response_text, metadata={"from_action": "action_intelligent_analysis"})]

    def save_analysis_to_db(self, analysis_data: Dict[str, Any], project_id: int, user_message: str):
        """
        FIX #4: Save Ollama's analysis to the database.
        """
        try:
            req_type = analysis_data.get("type", "General")
            priority = analysis_data.get("priority", "medium")
            content = analysis_data.get("requirement", user_message)

            # Skip generic responses
            if req_type == "General":
                print("[DB] Skipping 'General' type - not saving.")
                return 

            # Determine which table to save to
            if req_type == "Ambiguity":
                table_name = "ambiguities"
                print("[DB] Saving AMBIGUITY...")
            elif req_type == "Contradiction":
                table_name = "contradictions"
                print("[DB] Saving CONTRADICTION...")
            elif req_type == "Constraint":
                table_name = "requirements"
                print("[DB] Saving CONSTRAINT requirement...")
            else:  # Requirement
                table_name = "requirements"
                print("[DB] Saving REQUIREMENT...")

            conn = get_db_connection()
            cursor = conn.cursor()
            
            if table_name == "requirements":
                cursor.execute('''
                    INSERT INTO requirements (project_id, content, req_type, priority, status, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (project_id, content, req_type, priority, 'captured', datetime.now().isoformat()))
                
            elif table_name == "ambiguities":
                cursor.execute('''
                    INSERT INTO ambiguities (project_id, content, status, timestamp)
                    VALUES (?, ?, ?, ?)
                ''', (project_id, content, 'detected', datetime.now().isoformat()))
                
            elif table_name == "contradictions":
                cursor.execute('''
                    INSERT INTO contradictions (project_id, message, status, timestamp)
                    VALUES (?, ?, ?, ?)
                ''', (project_id, content, 'flagged', datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            print(f"[DB] ✓ Saved to {table_name}: {content[:60]}...")

        except Exception as e:
            print(f"[DB ERROR] {e}")


class ActionSetProjectId(Action):
    """Initialize project and elicitation phase at the start."""
    
    def name(self) -> Text:
        return "action_set_project_id"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        print("\n[ACTION] Setting initial state...")
        print("[ACTION] Project ID: 1, Elicitation Phase: vision")
        
        # Start in 'vision' phase
        return [
            SlotSet("project_id", 1.0),
            SlotSet("elicitation_phase", "vision")
        ]


class ActionGenerateSRS(Action):
    """Generate SRS document (triggered via export endpoint)."""
    
    def name(self) -> Text:
        return "nodoc: "
    
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # This is handled by the backend export endpoint
        return []

print("[ACTIONS.PY] ✓ Successfully loaded actions.py (V11)")