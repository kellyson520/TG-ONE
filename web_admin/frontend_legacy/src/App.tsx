import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAppStore } from '@/store';
import { Layout } from '@/components/layout/Layout';
import { Login } from '@/pages/Login';
import { Dashboard } from '@/pages/Dashboard';
import { Rules } from '@/pages/Rules';
import { Users } from '@/pages/Users';
import { Logs } from '@/pages/Logs';
import { Tasks } from '@/pages/Tasks';
import { Security } from '@/pages/Security';
import { Settings } from '@/pages/Settings';
import { History } from '@/pages/History';
import { ArchivePage } from '@/pages/Archive';
import { AuditLogs } from '@/pages/AuditLogs';
import { Visualization } from '@/pages/Visualization';
import { Downloads } from '@/pages/Downloads';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAppStore();
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" />;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="rules" element={<Rules />} />
          <Route path="visualization" element={<Visualization />} />
          <Route path="history" element={<History />} />
          <Route path="tasks" element={<Tasks />} />
          <Route path="downloads" element={<Downloads />} />
          <Route path="logs" element={<Logs />} />
          <Route path="archive" element={<ArchivePage />} />
          <Route path="audit-logs" element={<AuditLogs />} />
          <Route path="users" element={<Users />} />
          <Route path="security" element={<Security />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
