// src/App.jsx
import { Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage.jsx';
import AppShell from './pages/AppShell.jsx';
import TelemetryPage from './pages/TelemetryPage.jsx';
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
      <Route path="/login" element={<LoginPage />} />
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
      {/* Default: go to /login */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

export default App;
