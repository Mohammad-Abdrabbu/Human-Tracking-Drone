// src/components/LaunchPanel.jsx
import { useState, useEffect } from 'react';
import Card from '../ui/Card';
import Button from '../ui/Button';
import Badge from '../ui/Badge';

const API_Base = import.meta.env.VITE_API_Base || 'http://localhost:8000';

export default function LaunchPanel() {
    const [status, setStatus] = useState('unknown');
    const [details, setDetails] = useState({});
    const [loading, setLoading] = useState(false);
    const [logs, setLogs] = useState([]);

    // Demo Config
    const [headless, setHeadless] = useState(false);
    const [extras, setExtras] = useState(0);

    const token = localStorage.getItem('token');

    const fetchStatus = async () => {
        try {
            const res = await fetch(`${API_Base}/demo/fitexpo/status`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                setStatus(data.status);
                setDetails(data.details || {});
            }
        } catch (err) {
            console.error("Status fetch failed", err);
        }
    };

    useEffect(() => {
        fetchStatus();
        const timer = setInterval(fetchStatus, 3000);
        return () => clearInterval(timer);
    }, []);

    const addLog = (msg) => {
        setLogs(prev => [`[${new Date().toLocaleTimeString()}] ${msg}`, ...prev].slice(0, 10));
    };

    const handleStart = async () => {
        setLoading(true);
        addLog("Requesting demo start...");
        try {
            // Use query params for basic types
            const res = await fetch(`${API_Base}/demo/fitexpo/start?extras=${extras}&headless=${headless}`, {
                method: 'POST',
                headers: { Authorization: `Bearer ${token}` }
            });

            if (!res.ok) {
                throw new Error((await res.json()).detail || "Failed to start");
            }
            addLog("Start command sent successfully");
            fetchStatus();
        } catch (err) {
            addLog(`Error: ${err.message}`);
        } finally {
            setLoading(false);
        }
    };

    const handleStop = async () => {
        setLoading(true);
        addLog("Requesting demo stop...");
        try {
            const res = await fetch(`${API_Base}/demo/fitexpo/stop`, {
                method: 'POST',
                headers: { Authorization: `Bearer ${token}` }
            });
            if (!res.ok) {
                throw new Error("Failed to stop");
            }
            addLog("Stop command sent successfully");
            fetchStatus();
        } catch (err) {
            addLog(`Error: ${err.message}`);
        } finally {
            setLoading(false);
        }
    };

    const getStatusBadge = (svcName) => {
        const s = details[svcName];
        if (s === 'active') return <Badge variant="success">Active</Badge>;
        if (s === 'activating') return <Badge variant="warning">Starting</Badge>;
        if (s === 'failed') return <Badge variant="danger">Failed</Badge>;
        return <Badge variant="neutral">Stopped</Badge>;
    };

    return (
        <div className="launch-panel">
            <Card title="Fit Expo Demo Launcher">
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>

                    {/* Status Section */}
                    <div className="status-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                        <div className="status-item">
                            <strong>Overall Status:</strong>
                            <div style={{ marginTop: '0.5rem' }}>
                                {status === 'running' ? <Badge variant="success">Running</Badge> :
                                    status === 'starting' ? <Badge variant="warning">Starting</Badge> :
                                        <Badge variant="neutral">Stopped</Badge>}
                            </div>
                        </div>

                        <div className="status-details">
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                                <span>Target:</span> {getStatusBadge('fitexpo.target')}
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                                <span>PX4/Gazebo:</span> {getStatusBadge('fitexpo-px4.service')}
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                                <span>ROS Nodes:</span> {getStatusBadge('fitexpo-ros.service')}
                            </div>
                        </div>
                    </div>

                    <hr style={{ borderColor: 'var(--border-color)', opacity: 0.3 }} />

                    {/* Configuration */}
                    <div className="config-section">
                        <h4 style={{ margin: '0 0 1rem 0', color: 'var(--text-secondary)' }}>Configuration</h4>

                        <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap' }}>
                            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                                <input
                                    type="checkbox"
                                    checked={headless}
                                    onChange={e => setHeadless(e.target.checked)}
                                />
                                Run Headless (No GUI)
                            </label>

                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                <label>Extra Humans:</label>
                                <select
                                    value={extras}
                                    onChange={e => setExtras(parseInt(e.target.value))}
                                    style={{
                                        padding: '0.25rem 0.5rem',
                                        borderRadius: '4px',
                                        background: 'var(--bg-input)',
                                        border: '1px solid var(--border-color)',
                                        color: 'var(--text-primary)'
                                    }}
                                >
                                    <option value="0">None</option>
                                    <option value="1">1 (Booth 1)</option>
                                    <option value="2">2 (Booths 1-2)</option>
                                    <option value="3">3 (Booths 1-3)</option>
                                    <option value="4">4 (All Booths)</option>
                                </select>
                            </div>
                        </div>
                    </div>

                    {/* Actions */}
                    <div className="action-row" style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
                        <Button
                            onClick={handleStart}
                            disabled={loading || status === 'running'}
                            variant="primary"
                            style={{ flex: 1 }}
                        >
                            Start Demo
                        </Button>

                        <Button
                            onClick={handleStop}
                            disabled={loading || status === 'stopped'}
                            variant="danger"
                            style={{ flex: 1 }}
                        >
                            Stop Demo
                        </Button>
                    </div>

                    {/* Logs */}
                    <div className="logs-section" style={{
                        background: 'rgba(0,0,0,0.2)',
                        padding: '0.75rem',
                        borderRadius: '6px',
                        fontFamily: 'monospace',
                        fontSize: '0.85rem',
                        maxHeight: '150px',
                        overflowY: 'auto',
                        border: '1px solid var(--border-color)'
                    }}>
                        {logs.length === 0 ? <span style={{ color: 'var(--text-disabled)' }}>No logs yet...</span> :
                            logs.map((log, i) => <div key={i}>{log}</div>)
                        }
                    </div>

                </div>
            </Card>
        </div>
    );
}
