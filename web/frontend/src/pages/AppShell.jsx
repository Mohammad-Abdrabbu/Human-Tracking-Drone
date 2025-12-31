// src/pages/AppShell.jsx
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getToken, clearAuth } from '../auth';
import Layout from '../ui/Layout';

import { API_BASE_URL, WS_BASE_URL, VIDEO_URL, APP_MODE, toggleEnvironment, setVideoOverride } from '../config';

function AppShell() {
  const navigate = useNavigate();

  const [cmdStatus, setCmdStatus] = useState(null);
  const [stateMsg, setStateMsg] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [lastTelemetryAge, setLastTelemetryAge] = useState(null);

  const [alerts, setAlerts] = useState([]);
  const [alertsStatus, setAlertsStatus] = useState('disconnected');
  const [selectStatus, setSelectStatus] = useState(null);

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

    ws.onclose = (event) => {
      console.log('WebSocket /ws/state closed:', { code: event.code, reason: event.reason, wasClean: event.wasClean });
      // Auth-related close codes from backend: 1008=no token, 4001=expired, 4002=invalid
      if (event.code === 4001 || event.code === 4002 || event.code === 1008) {
        clearAuth();
        navigate('/login', { replace: true });
        return;
      }
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

    ws.onclose = (event) => {
      // Auth-related close codes from backend: 1008=no token, 4001=expired, 4002=invalid
      if (event.code === 4001 || event.code === 4002 || event.code === 1008) {
        clearAuth();
        navigate('/login', { replace: true });
        return;
      }
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

  const handleSelectTarget = async (targetId) => {
    const token = getToken();
    if (!token) {
      clearAuth();
      navigate('/login', { replace: true });
      return;
    }

    setSelectStatus({ state: 'sending', message: `Selecting target ${targetId}...` });

    try {
      const response = await fetch(`${API_BASE_URL}/cmd/select`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ target_id: targetId }),
      });

      const data = await response.json();

      if (response.ok && data.status === 'selected') {
        setSelectStatus({ state: 'ok', message: `✓ Target ${targetId} selected` });
      } else {
        setSelectStatus({ state: 'error', message: data.message || 'Selection failed' });
      }

      // Clear status after 3 seconds
      setTimeout(() => setSelectStatus(null), 3000);
    } catch (err) {
      console.error('Select error:', err);
      setSelectStatus({ state: 'error', message: 'Network error' });
      setTimeout(() => setSelectStatus(null), 3000);
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


          {/* Environment Toggle */}
          {/* Environment Toggle */}
          <div className="connection-card">
            <div className="connection-header">
              <span className="connection-title">Environment</span>
              <span className={`connection-dot ${APP_MODE === 'local' ? 'connection-dot--connected' : 'connection-dot--connecting'}`} />
            </div>
            <div className="flex items-center justify-between gap-2">
              <span className={`env-label env-label--${APP_MODE}`}>{APP_MODE}</span>
              <button
                onClick={toggleEnvironment}
                className="env-btn"
              >
                Switch
              </button>
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

        {/* Target Selection Section */}
        <section className="target-section">
          <div className="target-header">
            <h2 className="target-title">Target Selection</h2>
            <div className="target-current">
              <span className="target-label">Following:</span>
              <span className="target-id">{stateMsg?.selected_id ?? '--'}</span>
            </div>
          </div>

          {/* Live Video Feed with tracked targets */}
          <div className="target-video-container">
            {VIDEO_URL ? (
              <img
                src={VIDEO_URL}
                alt="Live camera feed with tracked targets"
                className="target-video"
                onError={(e) => {
                  e.target.style.display = 'none';
                  e.target.nextElementSibling.style.display = 'flex';
                }}
                onLoad={(e) => {
                  e.target.style.display = 'block';
                  e.target.nextElementSibling.style.display = 'none';
                }}
              />
            ) : null}

            <div className="target-video-placeholder" style={{ display: VIDEO_URL ? 'none' : 'flex' }}>
              <span className="target-video-icon">📹</span>
              <span className="target-video-text">
                {APP_MODE === 'cloud' ? 'Cloud Video Stream' : 'Video stream unavailable'}
              </span>
              <span className="target-video-hint">
                {APP_MODE === 'cloud'
                  ? 'Cloud requires a public ngrok URL for video.'
                  : 'Run: ros2 run sahtd_web_bridge video_bridge_node'}
              </span>

              {APP_MODE === 'cloud' && (
                <button
                  onClick={() => {
                    const url = prompt('Enter your ngrok video URL (e.g. https://xxxx.ngrok-free.app/video):', VIDEO_URL);
                    if (url !== null) setVideoOverride(url);
                  }}
                  className="mt-4 btn btn--sm btn--primary"
                >
                  {VIDEO_URL ? 'Change Stream URL' : 'Set Stream URL'}
                </button>
              )}
            </div>

            {/* Overlay button for Cloud mode to change existing URL */}
            {APP_MODE === 'cloud' && VIDEO_URL && (
              <button
                onClick={() => {
                  const url = prompt('Update ngrok video URL:', VIDEO_URL);
                  if (url !== null) setVideoOverride(url);
                }}
                className="absolute top-2 right-2 btn btn--sm btn--secondary opacity-50 hover:opacity-100"
              >
                ⚙️ Stream
              </button>
            )}
          </div>
          <div className="target-ids-container">
            <span className="target-ids-label">Visible Targets:</span>
            <div className="target-ids-list">
              {(() => {
                // Parse seen_ids from format "ids=1,2,3"
                const seenIdsRaw = stateMsg?.seen_ids || '';
                const match = seenIdsRaw.match(/ids=(.+)/);
                const ids = match && match[1]
                  ? match[1].split(',').map(s => parseInt(s.trim(), 10)).filter(n => !isNaN(n))
                  : [];

                if (ids.length === 0) {
                  return <span className="target-ids-empty">No targets visible</span>;
                }

                return ids.map(id => (
                  <button
                    key={id}
                    className={`target-id-btn ${stateMsg?.selected_id === id ? 'target-id-btn--selected' : ''}`}
                    onClick={() => handleSelectTarget(id)}
                  >
                    {id}
                  </button>
                ));
              })()}
            </div>
          </div>

          <div className="target-manual">
            <input
              type="number"
              className="target-input"
              placeholder="Enter ID"
              min="1"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  const val = parseInt(e.target.value, 10);
                  if (!isNaN(val) && val > 0) {
                    handleSelectTarget(val);
                    e.target.value = '';
                  }
                }
              }}
            />
            <button
              className="target-select-btn"
              onClick={(e) => {
                const input = e.target.previousElementSibling;
                const val = parseInt(input.value, 10);
                if (!isNaN(val) && val > 0) {
                  handleSelectTarget(val);
                  input.value = '';
                }
              }}
            >
              Select
            </button>
          </div>

          {selectStatus && (
            <div className={`target-status target-status--${selectStatus.state}`}>
              {selectStatus.message}
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
