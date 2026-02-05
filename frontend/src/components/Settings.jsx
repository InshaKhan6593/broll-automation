import React, { useState, useEffect } from 'react';
import './Settings.css';

const Settings = ({ onKeysChange }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [keys, setKeys] = useState({
    groq_api_key: '',
    ollama_api_key: '',
    openai_api_key: '',
    ollama_host: ''
  });

  // Load from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem('api_keys');
    if (saved) {
      const parsed = JSON.parse(saved);
      setKeys(parsed);
      onKeysChange(parsed);
    }
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    const newKeys = { ...keys, [name]: value };
    setKeys(newKeys);
    localStorage.setItem('api_keys', JSON.stringify(newKeys));
    onKeysChange(newKeys);
  };

  return (
    <div className={`settings-container ${isOpen ? 'open' : ''}`}>
      <button className="settings-toggle" onClick={() => setIsOpen(!isOpen)}>
        {isOpen ? '✕ Close Settings' : '⚙️ API Settings'}
      </button>

      {isOpen && (
        <div className="settings-panel">
          <h3>API Configuration</h3>
          <p className="settings-hint">Leave blank to use server-side .env keys</p>
          
          <div className="setting-item">
            <label>Groq API Key</label>
            <input
              type="password"
              name="groq_api_key"
              value={keys.groq_api_key}
              onChange={handleChange}
              placeholder="gsk_..."
            />
          </div>

          <div className="setting-item">
            <label>Ollama API Key</label>
            <input
              type="password"
              name="ollama_api_key"
              value={keys.ollama_api_key}
              onChange={handleChange}
              placeholder="Your Ollama Cloud Key"
            />
          </div>

          <div className="setting-item">
            <label>Ollama Host (Optional)</label>
            <input
              type="text"
              name="ollama_host"
              value={keys.ollama_host}
              onChange={handleChange}
              placeholder="e.g. https://api.ollamacloud.com"
            />
          </div>

          <div className="setting-item">
            <label>OpenAI API Key (Embeddings)</label>
            <input
              type="password"
              name="openai_api_key"
              value={keys.openai_api_key}
              onChange={handleChange}
              placeholder="sk-..."
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default Settings;
