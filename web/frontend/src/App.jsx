// src/App.jsx
import { Routes, Route, Navigate } from 'react-router-dom';
import HomePage from './pages/HomePage.jsx';
import AboutPage from './pages/AboutPage.jsx';
import LoginPage from './pages/LoginPage.jsx';
import AppShell from './pages/AppShell.jsx';
import TelemetryPage from './pages/TelemetryPage.jsx';
import MapPage from './pages/MapPage.jsx';
import DemoPage from './pages/DemoPage.jsx';
import { isAuthenticated } from './auth';

function RequireAuth({ children }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/" element={<HomePage />} />
      <Route path="/about" element={<AboutPage />} />
      <Route path="/login" element={<LoginPage />} />

      {/* Protected dashboard routes */}
      <Route
        path="/app"
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      />
      <Route
        path="/app/telemetry"
        element={
          <RequireAuth>
            <TelemetryPage />
          </RequireAuth>
        }
      />
      <Route
        path="/app/map"
        element={
          <RequireAuth>
            <MapPage />
          </RequireAuth>
        }
      />
      <Route
        path="/app/demos"
        element={
          <RequireAuth>
            <DemoPage />
          </RequireAuth>
        }
      />

      {/* Default: go to home */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
