// src/pages/MapPage.jsx
import { useEffect, useState, useRef, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { getToken, clearAuth } from '../auth';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || 'ws://127.0.0.1:8000';
const MAX_TRAIL_POINTS = 300;
const TRAIL_DURATION_S = 30;

function MapPage() {
    const navigate = useNavigate();
    const [latest, setLatest] = useState({});
    const [connectionStatus, setConnectionStatus] = useState('disconnected');
    const [fenceData, setFenceData] = useState(null);
    const [fenceError, setFenceError] = useState(null);
    const [fenceStatus, setFenceStatus] = useState(null);
    const [lastUpdateAge, setLastUpdateAge] = useState(null);
    const [trail, setTrail] = useState([]);

    const minimapCanvasRef = useRef(null);
    const ageIntervalRef = useRef(null);

    // Fetch fence data
    const fetchFence = useCallback(async () => {
        setFenceStatus('loading');
        setFenceError(null);
        try {
            const token = getToken();
            const response = await fetch(`${API_BASE_URL}/guard/fence`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (response.ok) {
                const data = await response.json();
                setFenceData(data);
                setFenceStatus('loaded');
                setTimeout(() => setFenceStatus(null), 2000);
            } else {
                const err = await response.json().catch(() => ({}));
                setFenceError(err.detail || `HTTP ${response.status}`);
                setFenceStatus('error');
            }
        } catch (err) {
            setFenceError('Network error');
            setFenceStatus('error');
        }
    }, []);

    // Fetch fence on mount
    useEffect(() => {
        fetchFence();
    }, [fetchFence]);

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
                    setLatest(data);
                    // Update trail
                    if (data.pose && data.pose.x !== undefined && data.pose.y !== undefined) {
                        const now = Date.now();
                        setTrail((prev) => {
                            const newPoint = { x: data.pose.x, y: data.pose.y, ts: now };
                            // Filter old points and cap
                            const cutoff = now - TRAIL_DURATION_S * 1000;
                            const filtered = prev.filter((p) => p.ts > cutoff);
                            return [newPoint, ...filtered].slice(0, MAX_TRAIL_POINTS);
                        });
                    }
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
            if (latest.ts) {
                const msgTime = new Date(latest.ts).getTime();
                setLastUpdateAge(Date.now() - msgTime);
            }
        }, 100);
        return () => clearInterval(ageIntervalRef.current);
    }, [latest]);

    // Draw map
    useEffect(() => {
        drawMap(minimapCanvasRef.current, fenceData, latest, trail);
    }, [latest, fenceData, trail]);

    const handleLogout = () => {
        clearAuth();
        navigate('/login', { replace: true });
    };

    // Determine status color
    const guardStatus = latest.guard_status || '--';
    let statusColor = '#22c55e';
    if (guardStatus.includes('VIOLATION')) {
        statusColor = '#ef4444';
    } else if (guardStatus.includes('HOLD')) {
        statusColor = '#facc15';
    }

    const poseAge = latest.stale?.pose_age_s;
    if (poseAge && poseAge > 2.0) {
        statusColor = '#ef4444';
    } else if (poseAge && poseAge > 0.5) {
        statusColor = '#facc15';
    }


    return (
        <div className="map-screen">
            <div className="map-container">
                <header className="map-header">
                    <h1 className="map-title">Live Map</h1>
                    <div className="map-header-actions">
                        <button
                            className="map-btn-small"
                            onClick={fetchFence}
                            disabled={fenceStatus === 'loading'}
                        >
                            {fenceStatus === 'loading' ? '...' : '↻ Reload Fence'}
                        </button>
                        {fenceStatus === 'loaded' && <span className="map-fence-ok">✓</span>}
                        <Link to="/app" className="map-link">Control Panel</Link>
                        <Link to="/app/telemetry" className="map-link">Telemetry</Link>
                        <button className="map-btn-outlined" onClick={handleLogout}>Logout</button>
                    </div>
                </header>

                {/* Essential Data Cards */}
                <section className="map-data-row">
                    <div className="map-data-card" style={{ borderColor: statusColor }}>
                        <div className="map-data-label">Status</div>
                        <div className="map-data-value" style={{ color: statusColor }}>{guardStatus}</div>
                    </div>
                    <div className="map-data-card">
                        <div className="map-data-label">Follow State</div>
                        <div className="map-data-value">{latest.follow_state ?? '--'}</div>
                    </div>
                    <div className="map-data-card">
                        <div className="map-data-label">Inside Fence</div>
                        <div className="map-data-value">
                            {latest.inside !== null && latest.inside !== undefined ? (latest.inside ? 'YES' : 'NO') : '--'}
                        </div>
                    </div>
                    <div className="map-data-card">
                        <div className="map-data-label">Distance to Fence</div>
                        <div className="map-data-value">{latest.distance_to_fence_m?.toFixed(1) ?? '--'} m</div>
                    </div>
                </section>

                <section className="map-data-row">
                    <div className="map-data-card">
                        <div className="map-data-label">Position</div>
                        <div className="map-data-value">
                            {latest.pose ? `(${latest.pose.x?.toFixed(1)}, ${latest.pose.y?.toFixed(1)}, ${latest.pose.z?.toFixed(1)})` : '--'}
                        </div>
                    </div>
                    <div className="map-data-card">
                        <div className="map-data-label">Heading</div>
                        <div className="map-data-value">{latest.pose?.yaw_deg?.toFixed(0) ?? '--'}°</div>
                    </div>
                    <div className="map-data-card">
                        <div className="map-data-label">Target ID</div>
                        <div className="map-data-value">{latest.selected_id ?? '--'}</div>
                    </div>
                    <div className="map-data-card">
                        <div className="map-data-label">Update Age</div>
                        <div className="map-data-value">
                            {lastUpdateAge !== null ? (lastUpdateAge < 1000 ? `${lastUpdateAge} ms` : `${(lastUpdateAge / 1000).toFixed(1)} s`) : '--'}
                        </div>
                    </div>
                </section>

                {/* Controls */}
                <div className="map-controls">
                    <span>WebSocket: <strong>{connectionStatus}</strong></span>
                    {fenceError && <span className="map-error">Fence: {fenceError}</span>}
                </div>

                {/* Large Map Canvas */}
                <section className="map-canvas-section">
                    <canvas ref={minimapCanvasRef} className="map-canvas" width={800} height={500}></canvas>
                </section>

                {/* Legend */}
                <div className="map-legend">
                    <span><span className="map-legend-dot" style={{ background: '#22c55e' }}></span> Drone Normal</span>
                    <span><span className="map-legend-dot" style={{ background: '#facc15' }}></span> Hold / Stale</span>
                    <span><span className="map-legend-dot" style={{ background: '#ef4444' }}></span> Violation</span>
                    <span><span className="map-legend-line"></span> Fence</span>
                    <span><span className="map-legend-line" style={{ background: 'rgba(56,189,248,0.3)' }}></span> Margin</span>
                    <span><span className="map-legend-line" style={{ background: '#22c55e', opacity: 0.5 }}></span> Trail</span>
                </div>
            </div>
        </div>
    );
}

// Map drawing function
function drawMap(canvas, fenceData, latest, trail) {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    const padding = 50;

    // Clear canvas
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, w, h);

    // Determine drone color based on status
    let droneColor = '#22c55e';
    const guardStatus = latest.guard_status || '';
    const poseAge = latest.stale?.pose_age_s;

    if (guardStatus.includes('VIOLATION')) {
        droneColor = '#ef4444';
    } else if (guardStatus.includes('HOLD') || (poseAge && poseAge > 0.5)) {
        droneColor = '#facc15';
    }

    // Check for fence data
    if (!fenceData || !fenceData.vertices || fenceData.vertices.length < 3) {
        ctx.fillStyle = '#94a3b8';
        ctx.font = '16px system-ui';
        ctx.textAlign = 'center';
        ctx.fillText('No fence data available', w / 2, h / 2);
        return;
    }

    const vertices = fenceData.vertices;
    const marginM = fenceData.margin_m || 0;

    // Compute bounds
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const v of vertices) {
        minX = Math.min(minX, v.x);
        maxX = Math.max(maxX, v.x);
        minY = Math.min(minY, v.y);
        maxY = Math.max(maxY, v.y);
    }

    // Add padding (15%)
    const rangeX = maxX - minX || 1;
    const rangeY = maxY - minY || 1;
    const padFactor = 0.15;
    minX -= rangeX * padFactor;
    maxX += rangeX * padFactor;
    minY -= rangeY * padFactor;
    maxY += rangeY * padFactor;

    // Map ENU to canvas
    const scaleX = (w - 2 * padding) / (maxX - minX);
    const scaleY = (h - 2 * padding) / (maxY - minY);
    const scale = Math.min(scaleX, scaleY);

    const centerOffsetX = (w - 2 * padding - (maxX - minX) * scale) / 2;
    const centerOffsetY = (h - 2 * padding - (maxY - minY) * scale) / 2;

    const toCanvasX = (x) => padding + centerOffsetX + (x - minX) * scale;
    const toCanvasY = (y) => h - padding - centerOffsetY - (y - minY) * scale;

    // Draw grid
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = 1;
    const gridStep = Math.pow(10, Math.floor(Math.log10(Math.max(rangeX, rangeY) / 4)));

    ctx.font = '10px system-ui';
    ctx.fillStyle = '#475569';
    ctx.textAlign = 'center';

    for (let gx = Math.ceil(minX / gridStep) * gridStep; gx <= maxX; gx += gridStep) {
        const cx = toCanvasX(gx);
        ctx.beginPath();
        ctx.moveTo(cx, padding);
        ctx.lineTo(cx, h - padding);
        ctx.stroke();
        ctx.fillText(gx.toFixed(0), cx, h - padding + 15);
    }

    ctx.textAlign = 'right';
    for (let gy = Math.ceil(minY / gridStep) * gridStep; gy <= maxY; gy += gridStep) {
        const cy = toCanvasY(gy);
        ctx.beginPath();
        ctx.moveTo(padding, cy);
        ctx.lineTo(w - padding, cy);
        ctx.stroke();
        ctx.fillText(gy.toFixed(0), padding - 8, cy + 4);
    }

    // Draw margin band (thicker semi-transparent stroke around fence)
    if (marginM > 0) {
        ctx.strokeStyle = 'rgba(56, 189, 248, 0.25)';
        ctx.lineWidth = marginM * scale * 2; // Visual representation
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.beginPath();
        ctx.moveTo(toCanvasX(vertices[0].x), toCanvasY(vertices[0].y));
        for (let i = 1; i < vertices.length; i++) {
            ctx.lineTo(toCanvasX(vertices[i].x), toCanvasY(vertices[i].y));
        }
        ctx.closePath();
        ctx.stroke();
    }

    // Draw fence polygon
    ctx.strokeStyle = '#38bdf8';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(toCanvasX(vertices[0].x), toCanvasY(vertices[0].y));
    for (let i = 1; i < vertices.length; i++) {
        ctx.lineTo(toCanvasX(vertices[i].x), toCanvasY(vertices[i].y));
    }
    ctx.closePath();
    ctx.stroke();

    // Fill fence
    ctx.fillStyle = 'rgba(56, 189, 248, 0.08)';
    ctx.fill();

    // Draw fence vertices
    ctx.fillStyle = '#38bdf8';
    for (const v of vertices) {
        ctx.beginPath();
        ctx.arc(toCanvasX(v.x), toCanvasY(v.y), 4, 0, 2 * Math.PI);
        ctx.fill();
    }

    // Draw axis labels
    ctx.fillStyle = '#64748b';
    ctx.font = '12px system-ui';
    ctx.textAlign = 'center';
    ctx.fillText('X (East) →', w / 2, h - 10);
    ctx.save();
    ctx.translate(15, h / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('Y (North) →', 0, 0);
    ctx.restore();

    // Draw origin marker
    const originX = toCanvasX(0);
    const originY = toCanvasY(0);
    if (originX > padding && originX < w - padding && originY > padding && originY < h - padding) {
        ctx.strokeStyle = '#475569';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(originX - 10, originY);
        ctx.lineTo(originX + 10, originY);
        ctx.moveTo(originX, originY - 10);
        ctx.lineTo(originX, originY + 10);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = '#475569';
        ctx.font = '10px system-ui';
        ctx.textAlign = 'left';
        ctx.fillText('(0,0)', originX + 5, originY - 5);
    }

    // Draw trajectory trail
    if (trail.length > 1) {
        const now = Date.now();
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';

        for (let i = 0; i < trail.length - 1; i++) {
            const p1 = trail[i];
            const p2 = trail[i + 1];
            const age1 = (now - p1.ts) / 1000;
            const alpha = Math.max(0.1, 1 - age1 / TRAIL_DURATION_S);

            ctx.beginPath();
            ctx.moveTo(toCanvasX(p1.x), toCanvasY(p1.y));
            ctx.lineTo(toCanvasX(p2.x), toCanvasY(p2.y));
            ctx.strokeStyle = `rgba(34, 197, 94, ${alpha * 0.6})`;
            ctx.lineWidth = 3;
            ctx.stroke();
        }
    }

    // Check for pose data
    if (!latest.pose || latest.pose.x === undefined || latest.pose.y === undefined) {
        ctx.fillStyle = '#94a3b8';
        ctx.font = '14px system-ui';
        ctx.textAlign = 'center';
        ctx.fillText('Waiting for drone position...', w / 2, h / 2 + 30);
        return;
    }

    const droneX = toCanvasX(latest.pose.x);
    const droneY = toCanvasY(latest.pose.y);

    // Draw drone glow
    ctx.beginPath();
    ctx.arc(droneX, droneY, 18, 0, 2 * Math.PI);
    ctx.fillStyle = `${droneColor}33`;
    ctx.fill();

    // Draw drone dot
    ctx.beginPath();
    ctx.arc(droneX, droneY, 12, 0, 2 * Math.PI);
    ctx.fillStyle = droneColor;
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Draw heading arrow
    if (latest.pose.yaw_deg !== undefined) {
        const yawRad = (latest.pose.yaw_deg * Math.PI) / 180;
        const arrowLen = 35;
        const arrowX = droneX + arrowLen * Math.cos(yawRad);
        const arrowY = droneY - arrowLen * Math.sin(yawRad);

        ctx.beginPath();
        ctx.moveTo(droneX, droneY);
        ctx.lineTo(arrowX, arrowY);
        ctx.strokeStyle = droneColor;
        ctx.lineWidth = 4;
        ctx.stroke();

        // Arrowhead
        const headLen = 10;
        const angle = Math.atan2(droneY - arrowY, arrowX - droneX);
        ctx.beginPath();
        ctx.moveTo(arrowX, arrowY);
        ctx.lineTo(arrowX - headLen * Math.cos(angle - Math.PI / 6), arrowY + headLen * Math.sin(angle - Math.PI / 6));
        ctx.lineTo(arrowX - headLen * Math.cos(angle + Math.PI / 6), arrowY + headLen * Math.sin(angle + Math.PI / 6));
        ctx.closePath();
        ctx.fillStyle = droneColor;
        ctx.fill();
    }

    // Draw position label
    ctx.fillStyle = '#f9fafb';
    ctx.font = 'bold 12px system-ui';
    ctx.textAlign = 'left';
    ctx.fillText(`Drone: (${latest.pose.x.toFixed(1)}, ${latest.pose.y.toFixed(1)})`, droneX + 18, droneY + 5);
    if (latest.pose.z !== undefined) {
        ctx.font = '11px system-ui';
        ctx.fillStyle = '#94a3b8';
        ctx.fillText(`Alt: ${latest.pose.z.toFixed(1)}m`, droneX + 18, droneY + 20);
    }
}

export default MapPage;
