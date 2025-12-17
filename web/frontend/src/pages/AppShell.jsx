// src/pages/AppShell.jsx
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getToken, clearAuth } from '../auth';
import Layout from '../ui/Layout';

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

  // Determine status variant
  let statusClass = 'status-normal';
  if (guardStatus === 'GEOGUARD_HOLD') {
    statusClass = 'status-hold';
  } else if (guardStatus === 'GEOGUARD_VIOLATION') {
    statusClass = 'status-violation';
  }

  // Format telemetry age
  const formatAge = (ms) => {
    if (ms === null) return '--';
    if (ms < 1000) return `${ms} ms`;
    return `${(ms / 1000).toFixed(1)} s`;
  };

  return (
    <Layout currentPage="control">
      <div className="control-panel">
        {/* Status Section */}
        <section className="status-section">
          {/* Main State Display */}
          <div className="status-main-card">
            <div className={`status-display ${statusClass}`}>
              <div className="status-state">
                <span className="status-primary">{followState}</span>
                <span className="status-secondary">{guardStatus}</span>
              </div>
              <div className="status-meta">
                {stateMsg?.pose && (
                  <div className="status-meta-row">
                    <span className="status-meta-label">Position</span>
                    <span className="status-meta-value">
                      ({stateMsg.pose.x?.toFixed(1)}, {stateMsg.pose.y?.toFixed(1)}, {stateMsg.pose.z?.toFixed(1)})
                    </span>
                  </div>
                )}
                {stateMsg?.selected_id !== null && stateMsg?.selected_id !== undefined && (
                  <div className="status-meta-row">
                    <span className="status-meta-label">Target ID</span>
                    <span className="status-meta-value">{stateMsg.selected_id}</span>
                  </div>
                )}
                {lastTelemetryAge !== null && (
                  <div className="status-meta-row">
                    <span className="status-meta-label">Last Update</span>
                    <span className="status-meta-value">{formatAge(lastTelemetryAge)} ago</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Connection Status Cards */}
          <div className="connection-card">
            <div className="connection-header">
              <span className="connection-title">State WebSocket</span>
              <span className={`connection-dot connection-dot--${connectionStatus}`} />
            </div>
            <div className={`connection-status connection-status--${connectionStatus}`}>
              {connectionStatus}
            </div>
          </div>

          <div className="connection-card">
            <div className="connection-header">
              <span className="connection-title">Alerts WebSocket</span>
              <span className={`connection-dot connection-dot--${alertsStatus}`} />
            </div>
            <div className={`connection-status connection-status--${alertsStatus}`}>
              {alertsStatus}
            </div>
          </div>
        </section>

        {/* Controls Section */}
        <section className="controls-section">
          <div className="controls-header">
            <h2 className="controls-title">Flight Controls</h2>
          </div>
          <div className="controls-grid">
            <button
              className="control-btn control-btn--primary"
              onClick={() => handleCommand('pause', 'Pause follow')}
            >
              <span className="control-btn-icon">⏸</span>
              <span>Pause</span>
            </button>
            <button
              className="control-btn control-btn--success"
              onClick={() => handleCommand('resume', 'Resume follow')}
            >
              <span className="control-btn-icon">▶</span>
              <span>Resume</span>
            </button>
            <button
              className="control-btn control-btn--warning"
              onClick={() => handleCommand('rtl', 'Return to launch')}
            >
              <span className="control-btn-icon">🏠</span>
              <span>RTL</span>
            </button>
            <button
              className="control-btn control-btn--danger"
              onClick={() => handleCommand('land', 'Land now')}
            >
              <span className="control-btn-icon">⬇</span>
              <span>Land</span>
            </button>
          </div>

          {cmdStatus && (
            <div className={`controls-status controls-status--${cmdStatus.state}`}>
              <span className="status-meta-label">Last command:</span>{' '}
              <span className="font-semibold">{cmdStatus.label}</span>
              {cmdStatus.detail && (
                <> — <span>{cmdStatus.detail}</span></>
              )}
            </div>
          )}
        </section>

        {/* Alerts Section */}
        <section className="alerts-section">
          <div className="alerts-header">
            <h2 className="alerts-title">Recent Alerts</h2>
            <span className="alerts-count">{alerts.length} alerts</span>
          </div>
          <div className="alerts-list">
            {alerts.length === 0 ? (
              <div className="alerts-empty">
                No alerts received yet. Alerts will appear here in real-time.
              </div>
            ) : (
              alerts.map((alert) => (
                <div
                  key={alert.id}
                  className={`alert-item alert-item--${alert.type?.toLowerCase() || 'info'}`}
                >
                  <div className="alert-header">
                    <span className={`alert-badge alert-badge--${alert.type?.toLowerCase() || 'info'}`}>
                      {alert.type || 'INFO'}
                    </span>
                    <span className="alert-message">{alert.message}</span>
                  </div>
                  <div className="alert-meta">
                    <span className="alert-source">{alert.source}</span>
                    <span className="alert-time">{alert.ts}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </Layout>
  );
}

export default AppShell;
