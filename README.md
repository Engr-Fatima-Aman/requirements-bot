# Requirements Gathering AI Chatbot

## Overview
The **Requirements Gathering AI Chatbot** is an intelligent virtual assistant designed to act as a **Business Analyst** or **Requirements Engineer**. It automates the initial phase of the software development lifecycle by eliciting, clarifying, and documenting project requirements from stakeholders.

Unlike standard chatbots, this system combines **RASA** (for structured dialogue management) with **Ollama** (for local Large Language Model capabilities) to ask dynamic follow-up questions, understand complex technical context, and generate professional requirement documents.

## Key Features
* **Automated Elicitation:** Conducts natural language interviews to gather functional and non-functional requirements.
* **Hybrid AI Engine:** Uses RASA for intent recognition and flow control, enhanced by Ollama (LLM) for generating contextual, deep-dive questions.
* **Dynamic Adaptation:** Recognizes vague answers and asks clarifying questions (e.g., "Can you define the specific user role for this feature?").
* **Documentation Generation:** Compiles the conversation into a structured requirements summary (SRS draft).
* **Modern Web Interface:** A clean, responsive chat interface built with React.

## Tech Stack
This project operates on a microservices architecture:
* **AI Core (NLU & Dialogue):** [RASA Framework](https://rasa.com/)
* **LLM Integration:** [Ollama](https://ollama.com/) (running local models like Llama 3 or Mistral)
* **Backend API:** Node.js (Express)
* **Frontend:** React.js
* **Database (Optional):** MongoDB (for storing conversation logs)

## Architecture
1.  **User** interacts with the **React Frontend**.
2.  **Node.js Backend** receives messages and forwards them to the AI engine.
3.  **RASA** handles the structured flow (greetings, specific intents).
4.  **Ollama** is triggered for complex, open-ended elicitation or when the user provides detailed technical descriptions that require summarization.
5.  **Response** is sent back to the user in real-time.

## Installation & Setup

### Prerequisites
* Node.js & npm installed
* Python 3.8+ (for RASA)
* Ollama installed and running locally

### 1. Setup the AI Engine (RASA & Ollama)
```bash
# Navigate to the RASA directory
cd rasa-bot

# Install dependencies
pip install -r requirements.txt

# Train the RASA model
rasa train

# Start the RASA action server (if using custom actions)
rasa run actions

# Start the RASA server with API enabled
rasa run --enable-api --cors "*"

# Navigate to the backend directory
cd backend

# Install dependencies
npm install

# Start the server
node server.js

# Navigate to the frontend directory
cd frontend

# Install dependencies
npm install

# Start the application
npm start

