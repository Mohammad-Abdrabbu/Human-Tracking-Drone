// src/pages/DemoPage.jsx
import LaunchPanel from '../components/LaunchPanel';

export default function DemoPage() {
    return (
        <div className="page-container">
            <header className="page-header">
                <h1 className="page-title">Demos & Utilities</h1>
                <p className="page-subtitle">Manage system demos and launch configurations</p>
            </header>

            <div className="page-content">
                <div style={{ maxWidth: '600px', margin: '0 auto' }}>
                    <LaunchPanel />
                </div>
            </div>
        </div>
    );
}
