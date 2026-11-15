import React from 'react';
import { Sun, Moon, CheckCircle2, Cpu, Database, RefreshCw } from 'lucide-react';
import { HealthStatus } from '../types';

interface NavbarProps {
  health: HealthStatus | null;
  darkMode: boolean;
  onToggleTheme: () => void;
  onRefresh: () => void;
  isEvaluating?: boolean;
}

const GithubIcon: React.FC<{ size?: number }> = ({ size = 16 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4" />
    <path d="M9 18c-4.51 2-5-2-7-2" />
  </svg>
);

export const Navbar: React.FC<NavbarProps> = ({
  health,
  darkMode,
  onToggleTheme,
  onRefresh,
  isEvaluating,
}) => {
  return (
    <header className="app-navbar">
      <div className="navbar-left">
        <div className="brand-logo-container">
          <div className="brand-badge-icon">AI</div>
        </div>
        <div className="brand-titles">
          <h1 className="brand-title">AI Lead Business Discovery System</h1>
          <p className="brand-subtitle">
            Enterprise Procurement Intelligence, Intent Classification &amp; 5-Factor Lead Scoring
          </p>
        </div>
      </div>

      <div className="navbar-right">
        {/* AI Engine Status */}
        <div className={`status-pill ${isEvaluating ? 'status-evaluating' : 'status-ready'}`}>
          <Cpu className="pill-icon" size={14} />
          <span>
            {isEvaluating
              ? 'Evaluating...'
              : health?.ai_providers?.openai_configured
              ? 'OpenAI + Gemini Ready'
              : health?.ai_providers?.gemini_configured
              ? 'Gemini Ready'
              : 'Deterministic NLP Ready'}
          </span>
        </div>

        {/* Database Status */}
        <div className="status-pill status-db">
          <Database className="pill-icon" size={14} />
          <span>{health?.database_type || 'SQLite'}</span>
        </div>

        {/* Refresh App State */}
        <button
          onClick={onRefresh}
          className="icon-action-btn"
          title="Refresh dashboard and metrics"
          aria-label="Refresh data"
        >
          <RefreshCw size={16} />
        </button>

        {/* Theme Toggle */}
        <button
          onClick={onToggleTheme}
          className="icon-action-btn theme-btn"
          title={darkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
          aria-label="Toggle color theme"
        >
          {darkMode ? <Sun size={17} /> : <Moon size={17} />}
        </button>

        {/* GitHub Shortcut */}
        <a
          href="https://github.com/Sagar-satapathy/AI-Lead-Business-Discovery-System"
          target="_blank"
          rel="noopener noreferrer"
          className="icon-action-btn github-btn"
          title="View source on GitHub"
          aria-label="GitHub Repository"
        >
          <GithubIcon size={17} />
        </a>
      </div>
    </header>
  );
};
