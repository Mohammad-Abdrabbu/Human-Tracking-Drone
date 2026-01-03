// src/pages/LoginPage.jsx
import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { saveAuth, isAuthenticated } from '../auth';

import { API_BASE_URL, APP_MODE, toggleEnvironment } from '../config';

function LoginPage() {
  const navigate = useNavigate();

  const [email, setEmail] = useState('operator@uop.edu.jo');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // If already logged in, redirect once after mount
  useEffect(() => {
    if (isAuthenticated()) {
      navigate('/app', { replace: true });
    }
  }, [navigate]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        const detail = body.detail || 'Login failed';
        setError(detail);
        setLoading(false);
        return;
      }

      const data = await response.json();
      // { access_token, token_type, role }
      saveAuth(data.access_token, data.role);

      setLoading(false);
      navigate('/app', { replace: true });
    } catch (err) {
      console.error('Login error:', err);
      setError('Unable to reach backend. Is FastAPI running on :8000?');
      setLoading(false);
    }
  };

  return (
    <div className="login-screen">
      <div className="env-pill">
        <span className={`env-label env-label--${APP_MODE}`}>{APP_MODE}</span>
        <button
          onClick={toggleEnvironment}
          className="env-btn"
        >
          Switch
        </button>
      </div>
      <div className="login-card">
        <header className="login-header">
          <div className="login-logo">◆</div>
          <h1 className="login-title">SAHTD</h1>
          <p className="login-subtitle">Operator Dashboard Login</p>
        </header>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="login-field">
            <label className="login-label" htmlFor="email">
              Email Address
            </label>
            <input
              id="email"
              className="login-input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
              placeholder="Enter your email"
            />
          </div>

          <div className="login-field">
            <label className="login-label" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              className="login-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              placeholder="Enter your password"
            />
          </div>

          {error && (
            <div className="login-error">
              <span className="login-error-icon">⚠</span>
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            className="btn btn--primary btn--lg btn--full login-submit"
            disabled={loading}
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <div className="login-back">
          <Link to="/" className="login-back-link">← Back to Home</Link>
        </div>
      </div>
    </div>
  );
}

export default LoginPage;
