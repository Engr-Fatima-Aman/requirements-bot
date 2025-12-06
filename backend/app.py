# backend/app.py (V4 - FIXED)

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import sqlite3
from datetime import datetime
import os
import sys
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
CORS(app)

RASA_SERVER_URL = "http://localhost:5005"
DB_PATH = "../requirements.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def send_message_to_rasa(message, sender_id="user_1"):
    """Send message to Rasa and get response. Rasa will call Ollama via actions."""
    try:
        payload = {"sender": sender_id, "message": message}
        response = requests.post(
            f"{RASA_SERVER_URL}/webhooks/rest/webhook",
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        print("Error: RASA request timed out.")
        return []
    except Exception as e:
        print(f"Error communicating with RASA: {e}")
        return {"error": str(e)}

def save_conversation(project_id, user_message, bot_response, intent):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO conversation_history (project_id, user_message, bot_response, intent)
            VALUES (?, ?, ?, ?)
        ''', (project_id, user_message, bot_response, intent))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving conversation: {e}")
        return False

# ==================== API ENDPOINTS ====================

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "message": "Backend server is running"}), 200

@app.route('/api/projects', methods=['POST'])
def create_project():
    try:
        data = request.get_json()
        project_name = data.get('project_name', 'Unnamed Project')
        description = data.get('description', '')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO projects (project_name, description)
            VALUES (?, ?)
        ''', (project_name, description))
        conn.commit()
        project_id = cursor.lastrowid
        conn.close()

        return jsonify({
            "success": True,
            "project_id": project_id,
            "message": "Project created successfully"
        }), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/projects/<int:project_id>', methods=['GET'])
def get_project(project_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM projects WHERE id = ?', (project_id,))
        project = dict(cursor.fetchone() or {})
        conn.close()
        
        if not project:
            return jsonify({"error": "Project not found"}), 404
        
        return jsonify(project), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """
    FIX #1: Send message to Rasa which routes through action_intelligent_analysis.
    This action calls Ollama and saves analysis to DB.
    """
    try:
        data = request.get_json()
        message = data.get('message', '')
        project_id = data.get('project_id', 1)
        sender_id = data.get('sender_id', 'user_1')
        
        if not message:
            return jsonify({"error": "Message cannot be empty"}), 400
        
        # Send to Rasa - it will invoke action_intelligent_analysis -> Ollama
        rasa_response = send_message_to_rasa(message, sender_id)
        
        bot_messages = []
        if isinstance(rasa_response, list):
            for response in rasa_response:
                if 'text' in response:
                    bot_messages.append(response['text'])
        
        bot_response = " ".join(bot_messages) if bot_messages else "I didn't understand that. Could you rephrase?"
        
        # Save conversation
        save_conversation(project_id, message, bot_response, "user_message")
        
        return jsonify({
            "success": True,
            "user_message": message,
            "bot_response": bot_response,
            "project_id": project_id
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/projects/<int:project_id>/summary', methods=['GET'])
def get_project_summary(project_id):
    """
    FIX #2: Correctly count captured requirements and detected issues.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all requirements
        cursor.execute('SELECT * FROM requirements WHERE project_id = ?', (project_id,))
        requirements = [dict(row) for row in cursor.fetchall()]

        # Count by type
        functional = sum(1 for req in requirements if 'func' in req.get('req_type', '').lower() and 'non' not in req.get('req_type', '').lower())
        non_functional = sum(1 for req in requirements if 'non-func' in req.get('req_type', '').lower() or 'nonfunc' in req.get('req_type', '').lower())
        
        # Get ambiguities and contradictions (detected but not resolved)
        cursor.execute('SELECT COUNT(*) as count FROM ambiguities WHERE project_id = ? AND status = ?', (project_id, 'detected'))
        ambiguities = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(*) as count FROM contradictions WHERE project_id = ? AND status = ?', (project_id, 'flagged'))
        contradictions = cursor.fetchone()['count']
        
        conn.close()
        
        return jsonify({
            "success": True,
            "project_id": project_id,
            "summary": {
                "total_requirements": len(requirements),
                "functional_requirements": functional,
                "non_functional_requirements": non_functional,
                "total_ambiguities": ambiguities,
                "ambiguities_resolved": 0,
                "total_contradictions": contradictions,
                "contradictions_resolved": 0
            }
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/projects/<int:project_id>/export', methods=['GET'])
def export_requirements(project_id):
    """Export SRS document with all captured data."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM projects WHERE id = ?', (project_id,))
        project = dict(cursor.fetchone() or {})
        
        cursor.execute('SELECT * FROM requirements WHERE project_id = ? ORDER BY timestamp DESC', (project_id,))
        requirements = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute('SELECT * FROM conversation_history WHERE project_id = ? ORDER BY timestamp', (project_id,))
        conversations = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute('SELECT * FROM ambiguities WHERE project_id = ? ORDER BY timestamp DESC', (project_id,))
        ambiguities = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute('SELECT * FROM contradictions WHERE project_id = ? ORDER BY timestamp DESC', (project_id,))
        contradictions = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        doc = f"""
{'='*80}
SOFTWARE REQUIREMENTS SPECIFICATION (SRS)
{'='*80}

PROJECT INFORMATION
{'-'*80}
Project Name: {project.get('project_name', 'Unnamed Project')}
Description: {project.get('description', 'No description provided')}
Created: {project.get('created_date', 'Unknown')}
Last Modified: {project.get('modified_date', 'Unknown')}
Document Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'='*80}
1. CONVERSATION HISTORY & REQUIREMENTS ELICITATION
{'='*80}

"""
        
        for i, conv in enumerate(conversations, 1):
            doc += f"\n[Exchange {i}]\n"
            doc += f"User: {conv.get('user_message', '')}\n"
            doc += f"Bot: {conv.get('bot_response', '')}\n"
            doc += f"Timestamp: {conv.get('timestamp', '')}\n"
            doc += "-" * 40 + "\n"
            
        # Categorize requirements
        functional_reqs = [r for r in requirements if 'func' in r.get('req_type', '').lower() and 'non' not in r.get('req_type', '').lower()]
        nonfunctional_reqs = [r for r in requirements if 'non-func' in r.get('req_type', '').lower() or 'nonfunc' in r.get('req_type', '').lower()]
        constraint_reqs = [r for r in requirements if 'constraint' in r.get('req_type', '').lower()]

        doc += f"\n{'='*80}\n2. FUNCTIONAL REQUIREMENTS\n{'='*80}\n\n"
        if functional_reqs:
            for i, req in enumerate(functional_reqs, 1):
                doc += f"FR-{i}: {req.get('content', '')}\n"
                doc += f"     Priority: {req.get('priority', 'medium')}\n\n"
        else:
            doc += "No functional requirements captured yet.\n"
            
        doc += f"\n{'='*80}\n3. NON-FUNCTIONAL REQUIREMENTS\n{'='*80}\n\n"
        if nonfunctional_reqs:
            for i, req in enumerate(nonfunctional_reqs, 1):
                doc += f"NFR-{i}: {req.get('content', '')}\n"
                doc += f"     Priority: {req.get('priority', 'medium')}\n\n"
        else:
            doc += "No non-functional requirements captured yet.\n"
            
        doc += f"\n{'='*80}\n4. CONSTRAINTS & LIMITATIONS\n{'='*80}\n\n"
        if constraint_reqs:
            for i, req in enumerate(constraint_reqs, 1):
                doc += f"C-{i}: {req.get('content', '')}\n\n"
        else:
            doc += "No constraints captured yet.\n"
        
        doc += f"\n{'='*80}\n5. AMBIGUITIES DETECTED\n{'='*80}\n\n"
        if ambiguities:
            for i, amb in enumerate(ambiguities, 1):
                doc += f"AMB-{i}: {amb.get('content', '')}\n"
                doc += f"     Status: {amb.get('status', 'detected')}\n\n"
        else:
            doc += "No ambiguities detected.\n"
            
        doc += f"\n{'='*80}\n6. CONTRADICTIONS DETECTED\n{'='*80}\n\n"
        if contradictions:
            for i, contra in enumerate(contradictions, 1):
                doc += f"CTR-{i}: {contra.get('message', '')}\n"
                doc += f"     Status: {contra.get('status', 'flagged')}\n\n"
        else:
            doc += "No contradictions detected.\n"
            
        doc += f"\n{'='*80}\n7. SUMMARY STATISTICS\n{'='*80}\n\n"
        doc += f"Total Requirements Captured: {len(requirements)}\n"
        doc += f"Functional Requirements: {len(functional_reqs)}\n"
        doc += f"Non-Functional Requirements: {len(nonfunctional_reqs)}\n"
        doc += f"Constraints: {len(constraint_reqs)}\n"
        doc += f"Ambiguities Detected: {len(ambiguities)}\n"
        doc += f"Contradictions Detected: {len(contradictions)}\n"
        doc += f"Total Conversation Exchanges: {len(conversations)}\n"
        
        doc += f"\n{'='*80}\nEND OF DOCUMENT\n{'='*80}\n"
        
        return jsonify({
            "success": True,
            "document": doc,
            "project_id": project_id
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    if not os.path.exists(DB_PATH):
        print("Database not found. Creating...")
        os.system(f'python {os.path.join(os.path.dirname(__file__), "../database/setup.py")}')
    
    print("Starting Flask backend server...")
    print("Access at: http://localhost:5000")
    app.run(debug=True, port=5000, use_reloader=False)