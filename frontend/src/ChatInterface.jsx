import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import './ChatInterface.css';

const ChatInterface = ({ projectId }) => {
  const [messages, setMessages] = useState([
    {
      id: 1,
      text: "Hello! I'm your Requirements Gathering Assistant. I'll help you capture and organize your project requirements. Let's start by understanding your project.",
      sender: 'bot',
      timestamp: new Date()
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [summary, setSummary] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    fetchSummary();
    const interval = setInterval(fetchSummary, 5000);
    return () => clearInterval(interval);
  }, [projectId]);

  const fetchSummary = async () => {
    try {
      const response = await axios.get(`http://localhost:5000/api/projects/${projectId}/summary`);
      if (response.data.success) {
        setSummary(response.data.summary);
      }
    } catch (error) {
      console.error('Error fetching summary:', error);
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();

    if (!inputValue.trim()) return;

    const userMessage = {
      id: messages.length + 1,
      text: inputValue,
      sender: 'user',
      timestamp: new Date()
    };

    setMessages([...messages, userMessage]);
    setInputValue('');
    setIsLoading(true);

    try {
      const response = await axios.post('http://localhost:5000/api/chat', {
        message: inputValue,
        project_id: projectId,
        sender_id: 'user_1'
      });

      if (response.data.success) {
        const botMessage = {
          id: messages.length + 2,
          text: response.data.bot_response,
          sender: 'bot',
          timestamp: new Date()
        };
        setMessages(prev => [...prev, botMessage]);
        fetchSummary();
      }
    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage = {
        id: messages.length + 2,
        text: 'Sorry, I encountered an error. Please try again.',
        sender: 'bot',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExport = async () => {
    try {
      const response = await axios.get(`http://localhost:5000/api/projects/${projectId}/export`);
      if (response.data.success) {
        const element = document.createElement('a');
        const file = new Blob([response.data.document], { type: 'text/plain' });
        element.href = URL.createObjectURL(file);
        element.download = `requirements_${projectId}_${new Date().toISOString().split('T')[0]}.txt`;
        document.body.appendChild(element);
        element.click();
        document.body.removeChild(element);
      }
    } catch (error) {
      console.error('Error exporting requirements:', error);
      alert('Failed to export requirements');
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <h1>Requirements Gathering Assistant</h1>
        <button className="export-btn" onClick={handleExport}>
          📥 Export Requirements
        </button>
      </div>

      <div className="chat-content">
        <div className="messages-panel">
          <div className="messages-list">
            {messages.map((message) => (
              <div key={message.id} className={`message ${message.sender}`}>
                <div className="message-content">
                  <p>{message.text}</p>
                  <span className="timestamp">
                    {message.timestamp.toLocaleTimeString()}
                  </span>
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="message bot">
                <div className="message-content">
                  <p className="typing">Bot is typing...</p>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <form className="input-form" onSubmit={handleSendMessage}>
            <input
              type="text"
              placeholder="Type your requirement or response..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              disabled={isLoading}
              className="message-input"
            />
            <button
              type="submit"
              disabled={isLoading || !inputValue.trim()}
              className="send-btn"
            >
              Send
            </button>
          </form>
        </div>

        <div className="sidebar">
          <div className="summary-card">
            <h3>📊 Project Summary</h3>
            {summary ? (
              <div className="summary-stats">
                <div className="stat">
                  <span className="label">Requirements Captured:</span>
                  <span className="value">{summary.total_requirements}</span>
                </div>
                <div className="stat">
                  <span className="label">Ambiguities Detected:</span>
                  <span className="value warning">{summary.total_ambiguities}</span>
                </div>
                <div className="stat">
                  <span className="label">Ambiguities Resolved:</span>
                  <span className="value success">{summary.ambiguities_resolved}</span>
                </div>
                <div className="stat">
                  <span className="label">Contradictions Detected:</span>
                  <span className="value warning">{summary.total_contradictions}</span>
                </div>
                <div className="stat">
                  <span className="label">Contradictions Resolved:</span>
                  <span className="value success">{summary.contradictions_resolved}</span>
                </div>
              </div>
            ) : (
              <p className="loading">Loading summary...</p>
            )}
          </div>

          <div className="tips-card">
            <h3>💡 Tips</h3>
            <ul>
              <li>Be specific when describing requirements</li>
              <li>Answer clarification questions honestly</li>
              <li>Mention constraints early (budget, timeline)</li>
              <li>Specify your target users</li>
              <li>Use export to save your requirements</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;