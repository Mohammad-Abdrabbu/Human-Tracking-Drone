// src/pages/AppShell.jsx
import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { getToken, clearAuth } from '../auth';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || 'ws://127.0.0.1:8000';

function AppShell() {
  const navigate = useNavigate();

  const [cmdStatus, setCmdStatus] = useState(null);
  const [stateMsg, setStateMsg] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [lastTelemetryAge, setLastTelemetryAge] = useState(null);

  const [alerts, setAlerts] = useState([]);
  const [alertsStatus, setAlertsStatus] = useState('disconnected');

  // --- WebSocket: /ws/state ---
  useEffect(() => {
    const token = getToken();
    if (!token) {
      navigate('/login', { replace: true });
      return;
    }

    const url = `${WS_BASE_URL}/ws/state?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);

    setConnectionStatus('connecting');

    ws.onopen = () => {
      setConnectionStatus('connected');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setStateMsg(data);

        // Compute telemetry age from timestamp
        if (data.ts) {
          const msgTime = new Date(data.ts).getTime();
          const now = Date.now();
          setLastTelemetryAge(now - msgTime);
        }
      } catch (err) {
        console.error('Error parsing /ws/state message:', err);
      }
    };

    ws.onerror = (event) => {
      console.error('WebSocket error (/ws/state):', event);
      setConnectionStatus('error');
    };

    ws.onclose = () => {
      setConnectionStatus('disconnected');
    };

    return () => {
      ws.close();
    };
  }, [navigate]);

  // --- WebSocket: /ws/alerts ---
  useEffect(() => {
    const token = getToken();
    if (!token) {
      navigate('/login', { replace: true });
      return;
    }

    const url = `${WS_BASE_URL}/ws/alerts?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);

    setAlertsStatus('connecting');

    ws.onopen = () => {
      setAlertsStatus('connected');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        // Prepend new alerts, keep last 50
        setAlerts((prev) => [data, ...prev].slice(0, 50));
      } catch (err) {
        console.error('Error parsing /ws/alerts message:', err);
      }
    };

    ws.onerror = (event) => {
      console.error('WebSocket error (/ws/alerts):', event);
      setAlertsStatus('error');
    };

    ws.onclose = () => {
      setAlertsStatus('disconnected');
    };

    return () => {
      ws.close();
    };
  }, [navigate]);

  const handleLogout = () => {
    clearAuth();
    navigate('/login', { replace: true });
  };

  const handleCommand = async (cmd, label) => {
    const token = getToken();
    if (!token) {
      clearAuth();
      navigate('/login', { replace: true });
      return;
    }

    setCmdStatus({
      state: 'sending',
      label,
      detail: null,
    });

    try {
      const response = await fetch(`${API_BASE_URL}/cmd/${cmd}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ source: 'ui' }),
      });

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        setCmdStatus({
          state: 'error',
          label,
          detail: body.detail || `HTTP ${response.status}`,
        });
        return;
      }

      const data = await response.json();
      setCmdStatus({
        state: 'ok',
        label,
        detail: data.message || 'Command accepted',
      });
    } catch (err) {
      console.error('Command error:', err);
      setCmdStatus({
        state: 'error',
        label,
        detail: 'Network error talking to backend',
      });
    }
  };

  // Derive UI from stateMsg
  const followState = stateMsg?.follow_state ?? 'UNKNOWN';
  const guardStatus = stateMsg?.guard_status ?? 'UNKNOWN';
  const standOff = stateMsg?.stand_off_m ?? null;
  const fenceMode = stateMsg?.fence_mode ?? null;

  let pillClass = 'sahtd-pill-normal';
  if (guardStatus === 'GEOGUARD_HOLD') {
    pillClass = 'sahtd-pill-hold';
  } else if (guardStatus === 'GEOGUARD_VIOLATION') {
    pillClass = 'sahtd-pill-violation';
  }

  return (
    <div className="sahtd-screen">
      <div className="sahtd-card sahtd-card-app">
        <header className="sahtd-app-header">
          <h1 className="sahtd-title">SAHTD Control Panel</h1>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <Link to="/app/telemetry" className="sahtd-button-outlined" style={{ textDecoration: 'none' }}>
              Telemetry
            </Link>
            <button className="sahtd-button-outlined" onClick={handleLogout}>
              Logout
            </button>
          </div>
        </header>

        <section className="sahtd-state-section">
          <div className={`sahtd-pill ${pillClass}`}>
            <span className="sahtd-pill-main">{followState}</span>
            <span className="sahtd-pill-sub">{guardStatus}</span>
          </div>
          <div className="sahtd-state-meta">
            <div>
              <span className="sahtd-meta-label">State WS:</span>{' '}
              <span className="sahtd-meta-value">{connectionStatus}</span>
            </div>
            <div>
              <span className="sahtd-meta-label">Alerts WS:</span>{' '}
              <span className="sahtd-meta-value">{alertsStatus}</span>
            </div>
            {lastTelemetryAge !== null && (
              <div>
                <span className="sahtd-meta-label">Last telemetry:</span>{' '}
                <span className="sahtd-meta-value">
                  {lastTelemetryAge < 1000 ? `${lastTelemetryAge} ms` : `${(lastTelemetryAge / 1000).toFixed(1)} s`} ago
                </span>
              </div>
            )}
            {stateMsg?.pose && (
              <div>
                <span className="sahtd-meta-label">Position:</span>{' '}
                <span className="sahtd-meta-value">
                  x={stateMsg.pose.x?.toFixed(1)}, y={stateMsg.pose.y?.toFixed(1)}, z={stateMsg.pose.z?.toFixed(1)}
                </span>
              </div>
            )}
            {stateMsg?.selected_id !== null && stateMsg?.selected_id !== undefined && (
              <div>
                <span className="sahtd-meta-label">Target ID:</span>{' '}
                <span className="sahtd-meta-value">{stateMsg.selected_id}</span>
              </div>
            )}
          </div>
        </section>

        <section className="sahtd-alerts-section">
          <h2 className="sahtd-subtitle">Alerts</h2>
          <div className="sahtd-alerts-list">
            {alerts.length === 0 && (
              <p className="sahtd-text sahtd-text-muted">
                No alerts received yet.
              </p>
            )}
            {alerts.map((alert) => (
              <div key={alert.id} className="sahtd-alert-item">
                <div className="sahtd-alert-main">
                  <span className={`sahtd-alert-badge sahtd-alert-${alert.type?.toLowerCase() || 'info'}`}>
                    {alert.type || 'INFO'}
                  </span>
                  <span className="sahtd-alert-message">{alert.message}</span>
                </div>
                <div className="sahtd-alert-meta">
                  <span className="sahtd-alert-source">{alert.source}</span>
                  <span className="sahtd-alert-time">
                    {alert.ts}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="sahtd-controls-section">
          <h2 className="sahtd-subtitle">Controls</h2>
          <div className="sahtd-controls-row">
            <button
              className="sahtd-control-button"
              onClick={() => handleCommand('pause', 'Pause follow')}
            >
              Pause
            </button>
            <button
              className="sahtd-control-button"
              onClick={() => handleCommand('resume', 'Resume follow')}
            >
              Resume
            </button>
            <button
              className="sahtd-control-button"
              onClick={() => handleCommand('rtl', 'Return to launch')}
            >
              RTL
            </button>
            <button
              className="sahtd-control-button sahtd-control-button-danger"
              onClick={() => handleCommand('land', 'Land now')}
            >
              Land
            </button>
          </div>

          {cmdStatus && (
            <p
              className={`sahtd-cmd-status sahtd-cmd-status-${cmdStatus.state}`}
            >
              <span className="sahtd-meta-label">Last command:</span>{' '}
              <span className="sahtd-meta-value">{cmdStatus.label}</span>
              {cmdStatus.detail && (
                <>
                  {' '}
                  — <span>{cmdStatus.detail}</span>
                </>
              )}
            </p>
          )}
        </section>

        <section className="sahtd-text-section">
          <p className="sahtd-text">
            This dashboard is currently driven by mock WebSocket data from the FastAPI backend
            (<code>/ws/state</code> and <code>/ws/alerts</code>).
          </p>
          <p className="sahtd-text">
            Later we&apos;ll plug these into real ROS topics (follower state, geo-guard events, failsafes).
          </p>
        </section>
      </div>
    </div>
  );
}

export default AppShell;
