import React, { useState, useEffect } from 'react';
import axios from 'axios';
import ChatInterface from './ChatInterface';
import './App.css';

function App() {
  const [projectId, setProjectId] = useState(null);
  const [showProjectForm, setShowProjectForm] = useState(true);
  const [projectName, setProjectName] = useState('');
  const [projectDescription, setProjectDescription] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [projects, setProjects] = useState([]);

  const handleCreateProject = async (e) => {
    e.preventDefault();

    if (!projectName.trim()) {
      alert('Please enter a project name');
      return;
    }

    setIsCreating(true);

    try {
      const response = await axios.post('http://localhost:5000/api/projects', {
        project_name: projectName,
        description: projectDescription
      });

      if (response.data.success) {
        setProjectId(response.data.project_id);
        setShowProjectForm(false);
        setProjectName('');
        setProjectDescription('');
        alert('Project created! Starting requirements gathering...');
      }
    } catch (error) {
      console.error('Error creating project:', error);
      alert('Failed to create project. Make sure the backend is running on http://localhost:5000');
    } finally {
      setIsCreating(false);
    }
  };

  const handleNewProject = () => {
    setProjectId(null);
    setShowProjectForm(true);
    setProjectName('');
    setProjectDescription('');
  };

  return (
    <div className="app">
      {showProjectForm ? (
        <div className="project-form-container">
          <div className="form-card">
            <div className="form-header">
              <h1>🚀 Requirements Gathering Bot</h1>
              <p>Start a new project to capture requirements</p>
            </div>

            <form onSubmit={handleCreateProject} className="project-form">
              <div className="form-group">
                <label htmlFor="projectName">Project Name *</label>
                <input
                  type="text"
                  id="projectName"
                  placeholder="e.g., Customer Portal, Mobile App, CRM System"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  disabled={isCreating}
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="projectDescription">Project Description</label>
                <textarea
                  id="projectDescription"
                  placeholder="Briefly describe your project (optional)"
                  value={projectDescription}
                  onChange={(e) => setProjectDescription(e.target.value)}
                  disabled={isCreating}
                  rows="4"
                />
              </div>

              <button
                type="submit"
                className="submit-btn"
                disabled={isCreating}
              >
                {isCreating ? 'Creating Project...' : 'Start Gathering Requirements'}
              </button>
            </form>

            <div className="form-footer">
              <h3>How it works:</h3>
              <ol>
                <li>Create a project with a name</li>
                <li>Chat with the bot about your requirements</li>
                <li>Bot will detect ambiguities and contradictions</li>
                <li>Export your requirements document anytime</li>
              </ol>
            </div>
          </div>

          <div className="info-panel">
            <div className="info-card">
              <h3>📝 Elicitation</h3>
              <p>Systematically gather all project requirements through natural conversation</p>
            </div>
            <div className="info-card">
              <h3>🔍 Analysis</h3>
              <p>Bot automatically detects ambiguities and contradictions in your requirements</p>
            </div>
            <div className="info-card">
              <h3>📋 Specification</h3>
              <p>Generate organized requirements documents ready for stakeholder review</p>
            </div>
            <div className="info-card">
              <h3>🎯 Validation</h3>
              <p>Track and manage requirement changes with full audit trail</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="chat-wrapper">
          <ChatInterface projectId={projectId} />
          <button className="new-project-btn" onClick={handleNewProject}>
            ➕ New Project
          </button>
        </div>
      )}
    </div>
  );
}

export default App;