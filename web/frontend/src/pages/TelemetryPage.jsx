// src/pages/TelemetryPage.jsx
import { useEffect, useState, useRef, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { getToken, clearAuth } from '../auth';

const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || 'ws://127.0.0.1:8000';
const MAX_BUFFER = 300;
const CHART_DURATION_S = 60;

function TelemetryPage() {
    const navigate = useNavigate();
    const [buffer, setBuffer] = useState([]);
    const [connectionStatus, setConnectionStatus] = useState('disconnected');
    const [lastUpdateAge, setLastUpdateAge] = useState(null);
    const [telemetryRate, setTelemetryRate] = useState(null);
    const [autoscroll, setAutoscroll] = useState(true);

    const tableRef = useRef(null);
    const distanceCanvasRef = useRef(null);
    const altitudeCanvasRef = useRef(null);
    const ageIntervalRef = useRef(null);

    // WebSocket connection
    useEffect(() => {
        const token = getToken();
        if (!token) {
            navigate('/login', { replace: true });
            return;
        }

        const url = `${WS_BASE_URL}/ws/state?token=${encodeURIComponent(token)}`;
        const ws = new WebSocket(url);

        setConnectionStatus('connecting');

        ws.onopen = () => setConnectionStatus('connected');

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.ts) {
                    data._receivedAt = Date.now();
                    setBuffer((prev) => {
                        const next = [data, ...prev].slice(0, MAX_BUFFER);
                        return next;
                    });
                }
            } catch (err) {
                console.error('Error parsing telemetry:', err);
            }
        };

        ws.onerror = () => setConnectionStatus('error');
        ws.onclose = () => setConnectionStatus('disconnected');

        return () => ws.close();
    }, [navigate]);

    // Update last age every 100ms
    useEffect(() => {
        ageIntervalRef.current = setInterval(() => {
            if (buffer.length > 0 && buffer[0].ts) {
                const msgTime = new Date(buffer[0].ts).getTime();
                setLastUpdateAge(Date.now() - msgTime);
            }
        }, 100);
        return () => clearInterval(ageIntervalRef.current);
    }, [buffer]);

    // Compute telemetry rate
    useEffect(() => {
        if (buffer.length < 2) {
            setTelemetryRate(null);
            return;
        }
        const now = Date.now();
        const recent = buffer.filter((m) => m._receivedAt && now - m._receivedAt < 10000);
        if (recent.length >= 2) {
            const timeSpan = recent[0]._receivedAt - recent[recent.length - 1]._receivedAt;
            const rate = timeSpan > 0 ? ((recent.length - 1) / (timeSpan / 1000)).toFixed(1) : null;
            setTelemetryRate(rate);
        }
    }, [buffer]);

    // Draw charts
    useEffect(() => {
        drawChart(distanceCanvasRef.current, buffer, 'distance_to_fence_m', '#38bdf8');
        drawChart(altitudeCanvasRef.current, buffer, 'pose.z', '#22c55e');
    }, [buffer]);

    // Auto-scroll table
    useEffect(() => {
        if (autoscroll && tableRef.current) {
            tableRef.current.scrollTop = 0;
        }
    }, [buffer, autoscroll]);

    const latest = buffer[0] || {};

    const handleDownload = useCallback(() => {
        const json = JSON.stringify(buffer, null, 2);
        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `telemetry_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }, [buffer]);

    const handleLogout = () => {
        clearAuth();
        navigate('/login', { replace: true });
    };

    // Stale badge logic
    const poseAge = latest.stale?.pose_age_s;
    let staleBadge = null;
    if (poseAge !== null && poseAge !== undefined) {
        if (poseAge > 2.0) {
            staleBadge = <span className="telem-badge telem-badge-error">STALE ({poseAge.toFixed(1)}s)</span>;
        } else if (poseAge > 0.5) {
            staleBadge = <span className="telem-badge telem-badge-warn">STALE ({poseAge.toFixed(1)}s)</span>;
        }
    }

    return (
        <div className="telem-screen">
            <div className="telem-container">
                <header className="telem-header">
                    <h1 className="telem-title">Telemetry Dashboard</h1>
                    <div className="telem-header-actions">
                        <Link to="/app" className="telem-link">Control Panel</Link>
                        <Link to="/app/map" className="telem-link">Map</Link>
                        <button className="telem-btn-outlined" onClick={handleLogout}>Logout</button>
                    </div>
                </header>

                {/* Status bar */}
                <div className="telem-status-bar">
                    <span>WS: <strong>{connectionStatus}</strong></span>
                    <span>Rate: <strong>{telemetryRate ?? '--'} Hz</strong></span>
                    <span>Age: <strong>{lastUpdateAge !== null ? (lastUpdateAge < 1000 ? `${lastUpdateAge} ms` : `${(lastUpdateAge / 1000).toFixed(1)} s`) : '--'}</strong></span>
                    <span>Buffer: <strong>{buffer.length}/{MAX_BUFFER}</strong></span>
                    {staleBadge}
                </div>

                {/* Live cards */}
                <section className="telem-cards">
                    <div className="telem-card">
                        <div className="telem-card-label">Follow State</div>
                        <div className="telem-card-value">{latest.follow_state ?? '--'}</div>
                    </div>
                    <div className="telem-card">
                        <div className="telem-card-label">Guard Status</div>
                        <div className="telem-card-value">{latest.guard_status ?? '--'}</div>
                    </div>
                    <div className="telem-card">
                        <div className="telem-card-label">Inside Fence</div>
                        <div className="telem-card-value">{latest.inside !== null && latest.inside !== undefined ? (latest.inside ? 'YES' : 'NO') : '--'}</div>
                    </div>
                    <div className="telem-card">
                        <div className="telem-card-label">Distance to Fence</div>
                        <div className="telem-card-value">{latest.distance_to_fence_m?.toFixed(2) ?? '--'} m</div>
                    </div>
                    <div className="telem-card">
                        <div className="telem-card-label">Position (x, y, z)</div>
                        <div className="telem-card-value">
                            {latest.pose ? `${latest.pose.x?.toFixed(1)}, ${latest.pose.y?.toFixed(1)}, ${latest.pose.z?.toFixed(1)}` : '--'}
                        </div>
                    </div>
                    <div className="telem-card">
                        <div className="telem-card-label">Yaw</div>
                        <div className="telem-card-value">{latest.pose?.yaw_deg?.toFixed(0) ?? '--'}°</div>
                    </div>
                    <div className="telem-card">
                        <div className="telem-card-label">Target ID</div>
                        <div className="telem-card-value">{latest.selected_id ?? '--'}</div>
                    </div>
                    <div className="telem-card">
                        <div className="telem-card-label">Seq</div>
                        <div className="telem-card-value">{latest.seq ?? '--'}</div>
                    </div>
                </section>

                {/* Charts */}
                <section className="telem-charts">
                    <div className="telem-chart-box">
                        <div className="telem-chart-title">Distance to Fence (60s)</div>
                        <canvas ref={distanceCanvasRef} className="telem-canvas" width={400} height={120}></canvas>
                    </div>
                    <div className="telem-chart-box">
                        <div className="telem-chart-title">Altitude (60s)</div>
                        <canvas ref={altitudeCanvasRef} className="telem-canvas" width={400} height={120}></canvas>
                    </div>
                </section>

                {/* Controls */}
                <div className="telem-controls">
                    <label className="telem-toggle">
                        <input type="checkbox" checked={autoscroll} onChange={(e) => setAutoscroll(e.target.checked)} />
                        Auto-scroll
                    </label>
                    <button className="telem-btn" onClick={handleDownload}>
                        Download Last {buffer.length} (JSON)
                    </button>
                </div>

                {/* History table */}
                <section className="telem-table-wrap" ref={tableRef}>
                    <table className="telem-table">
                        <thead>
                            <tr>
                                <th>Seq</th>
                                <th>Time</th>
                                <th>Follow</th>
                                <th>Guard</th>
                                <th>X</th>
                                <th>Y</th>
                                <th>Z</th>
                                <th>Yaw</th>
                                <th>Dist</th>
                                <th>Target</th>
                            </tr>
                        </thead>
                        <tbody>
                            {buffer.map((m, i) => (
                                <tr key={m.seq ?? i}>
                                    <td>{m.seq ?? '--'}</td>
                                    <td>{m.ts ? new Date(m.ts).toLocaleTimeString() : '--'}</td>
                                    <td>{m.follow_state ?? '--'}</td>
                                    <td>{m.guard_status ?? '--'}</td>
                                    <td>{m.pose?.x?.toFixed(1) ?? '--'}</td>
                                    <td>{m.pose?.y?.toFixed(1) ?? '--'}</td>
                                    <td>{m.pose?.z?.toFixed(1) ?? '--'}</td>
                                    <td>{m.pose?.yaw_deg?.toFixed(0) ?? '--'}</td>
                                    <td>{m.distance_to_fence_m?.toFixed(1) ?? '--'}</td>
                                    <td>{m.selected_id ?? '--'}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </section>
            </div>
        </div>
    );
}

// Simple chart drawing function
function drawChart(canvas, buffer, fieldPath, color) {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    const padding = 8;

    ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
    ctx.fillRect(0, 0, w, h);

    const now = Date.now();
    const points = [];
    for (const m of buffer) {
        if (!m.ts) continue;
        const age = (now - new Date(m.ts).getTime()) / 1000;
        if (age > CHART_DURATION_S) break;

        let val;
        if (fieldPath === 'pose.z') {
            val = m.pose?.z;
        } else {
            val = m[fieldPath];
        }
        if (val !== null && val !== undefined && !isNaN(val)) {
            points.push({ age, val });
        }
    }

    if (points.length < 2) {
        ctx.fillStyle = '#94a3b8';
        ctx.font = '12px system-ui';
        ctx.textAlign = 'center';
        ctx.fillText('No data', w / 2, h / 2);
        return;
    }

    const vals = points.map((p) => p.val);
    let minVal = Math.min(...vals);
    let maxVal = Math.max(...vals);
    if (minVal === maxVal) {
        minVal -= 1;
        maxVal += 1;
    }

    ctx.strokeStyle = '#334155';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding, h - padding);
    ctx.lineTo(w - padding, h - padding);
    ctx.stroke();

    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    let started = false;
    for (const p of points) {
        const x = w - padding - (p.age / CHART_DURATION_S) * (w - 2 * padding);
        const y = padding + (1 - (p.val - minVal) / (maxVal - minVal)) * (h - 2 * padding);
        if (!started) {
            ctx.moveTo(x, y);
            started = true;
        } else {
            ctx.lineTo(x, y);
        }
    }
    ctx.stroke();

    ctx.fillStyle = '#94a3b8';
    ctx.font = '10px system-ui';
    ctx.textAlign = 'left';
    ctx.fillText(maxVal.toFixed(1), padding + 2, padding + 10);
    ctx.fillText(minVal.toFixed(1), padding + 2, h - padding - 2);
}

export default TelemetryPage;
