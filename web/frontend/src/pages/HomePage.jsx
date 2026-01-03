// src/pages/HomePage.jsx
import { useRef, useLayoutEffect } from 'react';
import { Link } from 'react-router-dom';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

function HomePage() {
    const component = useRef(null);

    useLayoutEffect(() => {
        let ctx = gsap.context(() => {
            // Hero Animations
            const heroTl = gsap.timeline();
            heroTl.fromTo('.hero-badge', { y: -20, opacity: 0 }, { y: 0, opacity: 1, duration: 0.8, ease: 'power3.out' })
                .fromTo('.hero-title', { y: 30, opacity: 0 }, { y: 0, opacity: 1, duration: 0.8, ease: 'power3.out' }, '-=0.6')
                .fromTo('.hero-description', { y: 20, opacity: 0 }, { y: 0, opacity: 1, duration: 0.8, ease: 'power3.out' }, '-=0.6')
                .fromTo('.hero-actions', { y: 20, opacity: 0 }, { y: 0, opacity: 1, duration: 0.8, ease: 'power3.out' }, '-=0.6')
                .fromTo('.hero-visual', { scale: 0.8, opacity: 0 }, { scale: 1, opacity: 1, duration: 1, ease: 'back.out(1.7)' }, '-=0.8');

            // Hero Parallax on Scroll
            gsap.to('.hero-visual', {
                scrollTrigger: {
                    trigger: '.hero',
                    start: 'top top',
                    end: 'bottom top',
                    scrub: true
                },
                y: 100,
                scale: 0.9
            });

            // Operational Modes - Staggered Reveal
            gsap.fromTo('.mode-card',
                { y: 50, opacity: 0 },
                {
                    scrollTrigger: {
                        trigger: '.modes-grid',
                        start: 'top 80%',
                        toggleActions: 'play none none reverse'
                    },
                    y: 0,
                    opacity: 1,
                    duration: 0.8,
                    stagger: 0.2,
                    ease: 'power3.out'
                }
            );

            // Core Capabilities - Grid Reveal
            gsap.fromTo('.feature-card',
                { y: 30, opacity: 0 },
                {
                    scrollTrigger: {
                        trigger: '.features-grid',
                        start: 'top 85%',
                        toggleActions: 'play none none reverse'
                    },
                    y: 0,
                    opacity: 1,
                    duration: 0.6,
                    stagger: 0.1,
                    ease: 'power2.out'
                }
            );

            // Tech Stack - Pop in
            gsap.fromTo('.tech-item',
                { scale: 0.5, opacity: 0 },
                {
                    scrollTrigger: {
                        trigger: '.tech-grid',
                        start: 'top 90%',
                        toggleActions: 'play none none reverse'
                    },
                    scale: 1,
                    opacity: 1,
                    duration: 0.5,
                    stagger: 0.05,
                    ease: 'back.out(1.5)'
                }
            );

            // Team Section - Reveal
            gsap.fromTo('.team-card',
                { y: 40, opacity: 0 },
                {
                    scrollTrigger: {
                        trigger: '.team-grid',
                        start: 'top 85%',
                        toggleActions: 'play none none reverse'
                    },
                    y: 0,
                    opacity: 1,
                    duration: 0.8,
                    stagger: 0.2,
                    ease: 'power3.out'
                }
            );

            // Supervisor - Fade Up
            gsap.fromTo('.supervisor-card',
                { y: 30, opacity: 0 },
                {
                    scrollTrigger: {
                        trigger: '.supervisor-card',
                        start: 'top 90%',
                        toggleActions: 'play none none reverse'
                    },
                    y: 0,
                    opacity: 1,
                    duration: 0.8,
                    ease: 'power2.out'
                }
            );

            // Footer CTA - Scale Up
            gsap.fromTo('.footer-cta-title, .footer-cta-description, .footer-cta .btn',
                { y: 30, opacity: 0 },
                {
                    scrollTrigger: {
                        trigger: '.footer-cta',
                        start: 'top 80%',
                        toggleActions: 'play none none reverse'
                    },
                    y: 0,
                    opacity: 1,
                    duration: 0.8,
                    stagger: 0.1,
                    ease: 'power2.out'
                }
            );

        }, component);

        return () => ctx.revert();
    }, []);

    return (
        <div className="home-page" ref={component}>
            {/* Floating Vote Button */}
            <a
                href="https://padlet.com/izzmatar/fit-expo-2025-1-cof44zd77fup1mml/wish/yEPVZkn5pxvRQb0Y"
                target="_blank"
                rel="noopener noreferrer"
                className="vote-bubble"
            >
                <span className="vote-icon">🗳️</span>
                <span className="vote-text">Vote for Us!</span>
            </a>

            {/* Hero Section */}
            <section className="hero">
                <div className="hero-background">
                    <div className="hero-gradient" />
                    <div className="hero-grid" />
                </div>

                <nav className="home-nav">
                    <div className="home-nav-brand">
                        <img src="/logo.svg" alt="SAHTD Logo" className="home-nav-logo-img" />
                        <span className="home-nav-title">SAHTD</span>
                    </div>
                    <div className="home-nav-links">
                        <Link to="/about" className="home-nav-link">About</Link>
                        <Link to="/login" className="btn btn--primary btn--sm">Dashboard →</Link>
                    </div>
                </nav>

                <div className="hero-content">
                    <div className="hero-badge">
                        <span className="hero-badge-dot" />
                        University of Petra — Graduation Project 2025-2026
                    </div>

                    <h1 className="hero-title">
                        <span className="hero-title-line">Security-Aware</span>
                        <span className="hero-title-highlight">Human Tracking Drone</span>
                    </h1>

                    <p className="hero-description">
                        An autonomous UAV that detects, tracks, and follows designated persons
                        with geo-fencing safety and real-time monitoring.
                    </p>

                    <div className="hero-actions">
                        <Link to="/login" className="btn btn--primary btn--lg hero-cta">
                            <span>Enter Dashboard</span>
                            <span className="hero-cta-arrow">→</span>
                        </Link>
                        <Link to="/about" className="btn btn--secondary btn--lg">
                            Learn More
                        </Link>
                    </div>
                </div>

                <div className="hero-visual">
                    <div className="hero-tracking-scene">
                        {/* Drone at top */}
                        <div className="scene-drone">
                            <img src="/Drone.svg" alt="SAHTD Drone" className="scene-drone-img" />
                            <div className="drone-scan-pulse" />
                        </div>

                        {/* Tracking beams */}
                        <div className="tracking-beams">
                            <div className="beam beam-1" />
                            <div className="beam beam-2" />
                            <div className="beam beam-3" />
                        </div>

                        {/* Humans being tracked */}
                        <div className="scene-humans">
                            <div className="human-target human-1">
                                <span className="target-id-label">ID: 1</span>
                                <div className="bounding-box">
                                    <div className="human-icon">👤</div>
                                </div>
                            </div>
                            <div className="human-target human-2">
                                <span className="target-id-label active">ID: 2 • LOCKED</span>
                                <div className="bounding-box active">
                                    <div className="human-icon">👤</div>
                                </div>
                            </div>
                            <div className="human-target human-3">
                                <span className="target-id-label">ID: 3</span>
                                <div className="bounding-box">
                                    <div className="human-icon">👤</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* Operational Modes Section */}
            <section className="modes-section">
                <div className="section-container">
                    <h2 className="section-title">Three Operational Modes</h2>
                    <p className="section-subtitle">
                        Designed for diverse real-world security and safety scenarios
                    </p>

                    <div className="modes-grid">
                        <div className="mode-card">
                            <div className="mode-icon">🛡️</div>
                            <h3 className="mode-title">Personal Protection</h3>
                            <p className="mode-description">
                                Autonomously escorts and monitors individuals in high-risk areas,
                                issuing alerts upon detection of abnormal proximity or movement patterns.
                            </p>
                            <ul className="mode-features">
                                <li>Dynamic following</li>
                                <li>Proximity analysis</li>
                                <li>Alert notifications</li>
                            </ul>
                        </div>

                        <div className="mode-card mode-card--featured">
                            <div className="mode-icon">🔍</div>
                            <h3 className="mode-title">Search & Rescue</h3>
                            <p className="mode-description">
                                Assists emergency teams by autonomously identifying and tracking
                                individuals in complex environments, minimizing response times.
                            </p>
                            <ul className="mode-features">
                                <li>Autonomous exploration</li>
                                <li>Vision-based detection</li>
                                <li>Real-time localization</li>
                            </ul>
                        </div>

                        <div className="mode-card">
                            <div className="mode-icon">📡</div>
                            <h3 className="mode-title">Security Patrol</h3>
                            <p className="mode-description">
                                Executes predefined coverage routes, monitors behavioral anomalies,
                                and relays alerts to response units in real-time.
                            </p>
                            <ul className="mode-features">
                                <li>Zone patrolling</li>
                                <li>Anomaly detection</li>
                                <li>Instant alerts</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </section>

            {/* Features Section */}
            <section className="features-section">
                <div className="section-container">
                    <h2 className="section-title">Core Capabilities</h2>
                    <p className="section-subtitle">
                        Built on cutting-edge robotics and AI technologies
                    </p>

                    <div className="features-grid">
                        <div className="feature-card">
                            <div className="feature-icon">👁️</div>
                            <h3 className="feature-title">Real-Time Detection</h3>
                            <p className="feature-description">
                                YOLOv8-powered person detection at 15+ FPS with bounding boxes and confidence scores.
                            </p>
                        </div>

                        <div className="feature-card">
                            <div className="feature-icon">🎯</div>
                            <h3 className="feature-title">Persistent Tracking</h3>
                            <p className="feature-description">
                                ByteTrack multi-object tracking maintains identity across occlusions and viewpoint changes.
                            </p>
                        </div>

                        <div className="feature-card">
                            <div className="feature-icon">🚀</div>
                            <h3 className="feature-title">Autonomous Following</h3>
                            <p className="feature-description">
                                Image-based control keeps the target centered while maintaining configurable stand-off distance.
                            </p>
                        </div>

                        <div className="feature-card">
                            <div className="feature-icon">🛑</div>
                            <h3 className="feature-title">Geo-Fence Safety</h3>
                            <p className="feature-description">
                                Dynamic geo-guard prevents boundary violations with soft hold and hard stop zones.
                            </p>
                        </div>

                        <div className="feature-card">
                            <div className="feature-icon">⚡</div>
                            <h3 className="feature-title">Real-Time Alerts</h3>
                            <p className="feature-description">
                                Instant WebSocket delivery of target lost, reacquired, and geo-fence breach events.
                            </p>
                        </div>

                        <div className="feature-card">
                            <div className="feature-icon">🔐</div>
                            <h3 className="feature-title">Secure Access</h3>
                            <p className="feature-description">
                                JWT-based authentication with role-based access control for operators and viewers.
                            </p>
                        </div>
                    </div>
                </div>
            </section>

            {/* Technology Stack Section */}
            <section className="tech-section">
                <div className="section-container">
                    <h2 className="section-title">Technology Stack</h2>
                    <p className="section-subtitle">
                        Industry-standard tools for simulation, perception, and control
                    </p>

                    <div className="tech-grid">
                        <div className="tech-item">
                            <div className="tech-icon">🤖</div>
                            <span className="tech-name">ROS 2 Humble</span>
                        </div>
                        <div className="tech-item">
                            <div className="tech-icon">🌍</div>
                            <span className="tech-name">Gazebo Harmonic</span>
                        </div>
                        <div className="tech-item">
                            <div className="tech-icon">✈️</div>
                            <span className="tech-name">PX4 SITL</span>
                        </div>
                        <div className="tech-item">
                            <div className="tech-icon">🧠</div>
                            <span className="tech-name">YOLOv8</span>
                        </div>
                        <div className="tech-item">
                            <div className="tech-icon">📊</div>
                            <span className="tech-name">ByteTrack</span>
                        </div>
                        <div className="tech-item">
                            <div className="tech-icon">⚡</div>
                            <span className="tech-name">FastAPI</span>
                        </div>
                        <div className="tech-item">
                            <div className="tech-icon">⚛️</div>
                            <span className="tech-name">React</span>
                        </div>
                        <div className="tech-item">
                            <div className="tech-icon">☁️</div>
                            <span className="tech-name">Render Cloud</span>
                        </div>
                    </div>
                </div>
            </section>

            {/* Team Section */}
            <section className="team-section">
                <div className="section-container">
                    <h2 className="section-title">Our Team</h2>
                    <p className="section-subtitle">
                        Faculty of Information Technology, University of Petra
                    </p>

                    <div className="team-grid">
                        <div className="team-card">
                            <img src="/MR.jpg" alt="Mohammad Ramadan" className="team-avatar-img" />
                            <h3 className="team-name">Mohammad Ramadan</h3>
                            <p className="team-id">202210108</p>
                            <p className="team-role">Lead Developer</p>
                        </div>

                        <div className="team-card">
                            <div className="team-avatar">A</div>
                            <h3 className="team-name">Abdulrahman Wael</h3>
                            <p className="team-id">202210293</p>
                            <p className="team-role">Developer</p>
                        </div>

                        <div className="team-card">
                            <div className="team-avatar">F</div>
                            <h3 className="team-name">Fouad Mohammad</h3>
                            <p className="team-id">202210142</p>
                            <p className="team-role">Developer</p>
                        </div>
                    </div>

                    <div className="supervisor-card">
                        <span className="supervisor-label">Supervised by</span>
                        <span className="supervisor-name">Dr. Abdelkarem Al-Banna</span>
                    </div>
                </div>
            </section>

            {/* Footer CTA */}
            <section className="footer-cta">
                <div className="section-container">
                    <h2 className="footer-cta-title">Ready to see it in action?</h2>
                    <p className="footer-cta-description">
                        Experience the live dashboard with real-time telemetry, alerts, and drone visualization.
                    </p>
                    <Link to="/login" className="btn btn--primary btn--lg">
                        Enter Dashboard →
                    </Link>
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

export default HomePage;
