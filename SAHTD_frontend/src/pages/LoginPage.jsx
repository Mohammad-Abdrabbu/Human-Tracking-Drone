// src/pages/LoginPage.jsx
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { saveAuth, isAuthenticated } from '../auth';

const API_BASE_URL = 'http://127.0.0.1:8000';

function LoginPage() {
  const navigate = useNavigate();

  const [email, setEmail] = useState('operator@uop.edu.jo');
  const [password, setPassword] = useState('secret123');
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
    <div className="sahtd-screen">
      <div className="sahtd-card">
        <h1 className="sahtd-title">SAHTD Operator Login</h1>

        <form onSubmit={handleSubmit} className="sahtd-form">
          <label className="sahtd-label">
            Email
            <input
              className="sahtd-input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
            />
          </label>

          <label className="sahtd-label">
            Password
            <input
              className="sahtd-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </label>

          {error && (
            <p className="sahtd-error">
              {error}
            </p>
          )}

          <button type="submit" className="sahtd-button" disabled={loading}>
            {loading ? 'Logging in…' : 'Log in'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default LoginPage;
