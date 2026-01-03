// src/ui/Layout.jsx
import { NavLink, useNavigate } from 'react-router-dom';
import { clearAuth } from '../auth';

/**
 * Shared layout component with header, navigation tabs, and responsive behavior.
 * - Desktop: horizontal tabs in header
 * - Mobile: fixed bottom navigation bar
 */
function Layout({ children, currentPage }) {
    const navigate = useNavigate();

    const handleLogout = () => {
        clearAuth();
        navigate('/login', { replace: true });
    };

    const navItems = [
        { path: '/app', label: 'Control', icon: '⚡' },
        { path: '/app/telemetry', label: 'Telemetry', icon: '📊' },
        { path: '/app/map', label: 'Map', icon: '🗺️' },
    ];

    return (
        <div className="layout">
            {/* Top Header */}
            <header className="layout-header">
                <div className="layout-header-content">
                    <div className="layout-brand">
                        <img src="/logo.svg" alt="SAHTD Logo" className="layout-logo-img" />
                        <span className="layout-title">SAHTD</span>
                        <span className="layout-subtitle">Operator Dashboard</span>
                    </div>

                    {/* Desktop Navigation */}
                    <nav className="layout-nav-desktop">
                        {navItems.map((item) => (
                            <NavLink
                                key={item.path}
                                to={item.path}
                                end={item.path === '/app'}
                                className={({ isActive }) =>
                                    `layout-nav-item ${isActive ? 'layout-nav-item--active' : ''}`
                                }
                            >
                                <span className="layout-nav-icon">{item.icon}</span>
                                <span className="layout-nav-label">{item.label}</span>
                            </NavLink>
                        ))}
                    </nav>

                    <div className="layout-actions">
                        <button className="layout-logout-btn" onClick={handleLogout}>
                            <span className="layout-logout-icon">↪</span>
                            <span className="layout-logout-text">Logout</span>
                        </button>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main className="layout-main">
                <div className="layout-content">
                    {children}
                </div>
            </main>

            {/* Mobile Bottom Navigation */}
            <nav className="layout-nav-mobile">
                {navItems.map((item) => (
                    <NavLink
                        key={item.path}
                        to={item.path}
                        end={item.path === '/app'}
                        className={({ isActive }) =>
                            `layout-nav-mobile-item ${isActive ? 'layout-nav-mobile-item--active' : ''}`
                        }
                    >
                        <span className="layout-nav-mobile-icon">{item.icon}</span>
                        <span className="layout-nav-mobile-label">{item.label}</span>
                    </NavLink>
                ))}
            </nav>
        </div>
    );
}

export default Layout;
