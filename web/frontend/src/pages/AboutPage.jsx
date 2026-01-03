// src/pages/AboutPage.jsx
import { Link } from 'react-router-dom';

function AboutPage() {
    return (
        <div className="about-page">
            {/* Navigation */}
            <nav className="home-nav">
                <div className="home-nav-brand">
                    <Link to="/" className="home-nav-brand-link">
                        <img src="/logo.svg" alt="SAHTD Logo" className="home-nav-logo-img" />
                        <span className="home-nav-title">SAHTD</span>
                    </Link>
                </div>
                <div className="home-nav-links">
                    <Link to="/" className="home-nav-link">Home</Link>
                    <Link to="/login" className="btn btn--primary btn--sm">Dashboard →</Link>
                </div>
            </nav>

            {/* Hero */}
            <section className="about-hero">
                <div className="section-container">
                    <h1 className="about-hero-title">About the Project</h1>
                    <p className="about-hero-subtitle">
                        A deep dive into the Security-Aware Human Tracking Drone system architecture,
                        requirements, and implementation.
                    </p>
                </div>
            </section>

            {/* Problem Statement */}
            <section className="about-section">
                <div className="section-container">
                    <h2 className="section-title">The Problem</h2>
                    <div className="about-content">
                        <p>
                            Public-safety operations such as personal protection, search and rescue, and event security
                            still face delays in detection, localization, and decision-making—particularly in large or
                            cluttered areas where ground teams have limited coverage.
                        </p>
                        <p>
                            Small unmanned aerial vehicles (UAVs) can extend situational awareness, but most deployments
                            remain operator-centric and struggle with persistent, autonomous person-following in dynamic scenes.
                        </p>
                        <p>
                            Vision-based tracking from a moving aerial camera is brittle: people appear small, are frequently
                            occluded, and backgrounds change rapidly—driving identity switches and target loss.
                        </p>
                    </div>
                </div>
            </section>

            {/* Solution */}
            <section className="about-section about-section--alt">
                <div className="section-container">
                    <h2 className="section-title">Our Solution</h2>
                    <div className="about-content">
                        <p>
                            SAHTD integrates reliable real-time person detection and tracking with privacy-aware geofencing
                            and contextual alerting, enabling a UAV to:
                        </p>
                        <ul className="about-list">
                            <li>Follow a designated person safely</li>
                            <li>Re-acquire after occlusion</li>
                            <li>Notify responders in near real-time</li>
                            <li>Operate across escort, SAR, and patrol scenarios</li>
                        </ul>
                    </div>
                </div>
            </section>

            {/* System Architecture */}
            <section className="about-section">
                <div className="section-container">
                    <h2 className="section-title">System Architecture</h2>
                    <div className="architecture-diagram">
                        <div className="arch-layer">
                            <div className="arch-layer-title">Simulation Layer</div>
                            <div className="arch-boxes">
                                <div className="arch-box">Gazebo Harmonic</div>
                                <div className="arch-box">PX4 SITL</div>
                                <div className="arch-box">Camera Sensor</div>
                            </div>
                        </div>
                        <div className="arch-arrow">↓</div>
                        <div className="arch-layer">
                            <div className="arch-layer-title">Autonomy Layer (ROS 2)</div>
                            <div className="arch-boxes">
                                <div className="arch-box">ros_gz_bridge</div>
                                <div className="arch-box">yolo_node</div>
                                <div className="arch-box">bytetrack_node</div>
                                <div className="arch-box">follow_node</div>
                                <div className="arch-box">geo_guard_node</div>
                            </div>
                        </div>
                        <div className="arch-arrow">↓</div>
                        <div className="arch-layer">
                            <div className="arch-layer-title">Web Layer</div>
                            <div className="arch-boxes">
                                <div className="arch-box">FastAPI Backend</div>
                                <div className="arch-box">React Frontend</div>
                                <div className="arch-box">PostgreSQL DB</div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* Functional Requirements */}
            <section className="about-section about-section--alt">
                <div className="section-container">
                    <h2 className="section-title">Functional Requirements</h2>
                    <div className="requirements-grid">
                        <div className="requirement-card">
                            <span className="requirement-id">FR1</span>
                            <p>Detect people in forward camera view with bounding boxes and confidence</p>
                        </div>
                        <div className="requirement-card">
                            <span className="requirement-id">FR2</span>
                            <p>Allow authorized user to designate one person to follow</p>
                        </div>
                        <div className="requirement-card">
                            <span className="requirement-id">FR3</span>
                            <p>Track designated person with persistent track ID</p>
                        </div>
                        <div className="requirement-card">
                            <span className="requirement-id">FR4</span>
                            <p>Follow with configurable stand-off distance and altitude band</p>
                        </div>
                        <div className="requirement-card">
                            <span className="requirement-id">FR5</span>
                            <p>Ingest geo-fences and prevent boundary crossing</p>
                        </div>
                        <div className="requirement-card">
                            <span className="requirement-id">FR6</span>
                            <p>Deliver alerts: target lost, reacquired, breach, override, land</p>
                        </div>
                        <div className="requirement-card">
                            <span className="requirement-id">FR7</span>
                            <p>Provide manual override commands: pause, resume, RTL, land</p>
                        </div>
                        <div className="requirement-card">
                            <span className="requirement-id">FR8</span>
                            <p>Log alerts, commands, status changes with timestamps</p>
                        </div>
                        <div className="requirement-card">
                            <span className="requirement-id">FR9</span>
                            <p>Real-time dashboard with video, targets, geo-fences, alerts</p>
                        </div>
                        <div className="requirement-card">
                            <span className="requirement-id">FR10</span>
                            <p>Secure login with JWT-based authentication and roles</p>
                        </div>
                    </div>
                </div>
            </section>

            {/* Demo Video Placeholder */}
            <section className="about-section">
                <div className="section-container">
                    <h2 className="section-title">Demo Video</h2>
                    <div className="video-placeholder">
                        <div className="video-placeholder-content">
                            <span className="video-placeholder-icon">🎬</span>
                            <p>Demo video coming soon</p>
                            <span className="video-placeholder-hint">Check back after the expo presentation</span>
                        </div>
                    </div>
                </div>
            </section>

            {/* Links */}
            <section className="about-section about-section--alt">
                <div className="section-container">
                    <h2 className="section-title">Resources</h2>
                    <div className="resources-grid">
                        <a href="https://github.com" target="_blank" rel="noopener noreferrer" className="resource-card">
                            <span className="resource-icon">📂</span>
                            <span className="resource-title">GitHub Repository</span>
                            <span className="resource-hint">Source code and documentation</span>
                        </a>
                        <Link to="/login" className="resource-card">
                            <span className="resource-icon">📊</span>
                            <span className="resource-title">Live Dashboard</span>
                            <span className="resource-hint">Real-time monitoring interface</span>
                        </Link>
                    </div>
                </div>
            </section>

            {/* Footer */}
            <footer className="home-footer">
                <div className="section-container">
                    <div className="footer-content">
                        <div className="footer-brand">
                            <span className="footer-logo">◆</span>
                            <span className="footer-title">SAHTD</span>
                        </div>
                        <p className="footer-text">
                            © 2025-2026 University of Petra — Graduation Project
                        </p>
                    </div>
                </div>
            </footer>
        </div>
    );
}

export default AboutPage;
