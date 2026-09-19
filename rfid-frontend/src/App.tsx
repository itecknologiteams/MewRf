import { Routes, Route, Navigate } from 'react-router';
import { AuthProvider } from '@/context/AuthContext';
import { ThemeProvider } from '@/context/ThemeContext';
import { ToastProvider } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import ErrorBoundary from '@/components/ErrorBoundary';
import DashboardLayout from '@/components/DashboardLayout';
import Login from '@/pages/Login';
import Dashboard from '@/pages/Dashboard';
import Registration from '@/pages/Registration';
import Vehicles from '@/pages/Vehicles';
import Transactions from '@/pages/Transactions';
import Reports from '@/pages/Reports';
import Profile from '@/pages/Profile';
import PlazasPage from '@/pages/PlazasPage';
import TollOperations from '@/pages/TollOperations';
import TripsPage from '@/pages/TripsPage';
import AdminUsersPage from '@/pages/AdminUsersPage';
import BalanceTransfer from '@/pages/BalanceTransfer';
import TopupPage from '@/pages/TopupPage';
import InventoryManagement from '@/pages/InventoryManagement';
import BoothAssignmentPage from '@/pages/BoothAssignmentPage';
import LanesPage from '@/pages/LanesPage';
import BoothDeploymentsPage from '@/pages/BoothDeploymentsPage';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <>{children}</> : <Navigate to="/login"replace />;
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login"replace />;
  if (user?.role !== 'admin') return <Navigate to="/dashboard"replace />;
  return <>{children}</>;
}

function AppRoutes() {
  const { user } = useAuth();

  // Operators staff the registration desk and nothing else: one page, and any
  // other URL — including the /dashboard that Login sends everyone to — lands
  // back on it.
  if (user?.role === 'operator') {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <DashboardLayout />
            </ProtectedRoute>
          }
        >
          <Route path="register" element={<Registration />} />
          <Route index element={<Navigate to="/register" replace />} />
          <Route path="*" element={<Navigate to="/register" replace />} />
        </Route>
      </Routes>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="register" element={<Registration />} />
        <Route path="vehicles" element={<Vehicles />} />
        <Route path="transactions" element={<Transactions />} />
        <Route path="reports" element={<Reports />} />
        <Route path="profile" element={<Profile />} />
        <Route path="operations" element={<TollOperations />} />
        <Route path="plazas" element={<PlazasPage />} />
        <Route path="trips" element={<TripsPage />} />
        <Route path="admin/users" element={<AdminRoute><AdminUsersPage /></AdminRoute>} />
        <Route path="admin/inventory" element={<AdminRoute><InventoryManagement /></AdminRoute>} />
        <Route path="admin/booth-assignment" element={<AdminRoute><BoothAssignmentPage /></AdminRoute>} />
        <Route path="admin/lanes" element={<AdminRoute><LanesPage /></AdminRoute>} />
        <Route path="admin/booth-updates" element={<AdminRoute><BoothDeploymentsPage /></AdminRoute>} />
        <Route path="transfer" element={<BalanceTransfer />} />
        <Route path="topup" element={<TopupPage />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <ErrorBoundary>
        <AuthProvider>
          <ToastProvider>
            <ErrorBoundary>
              <AppRoutes />
            </ErrorBoundary>
          </ToastProvider>
        </AuthProvider>
      </ErrorBoundary>
    </ThemeProvider>
  );
}
