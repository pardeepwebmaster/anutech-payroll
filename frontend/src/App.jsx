import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./lib/auth";

import AdminLayout from "./components/AdminLayout";
import EmployeeLayout from "./components/EmployeeLayout";

import Login from "./pages/Login";
import Register from "./pages/Register";

import Dashboard from "./pages/admin/Dashboard";
import Employees from "./pages/admin/Employees";
import RunPayroll from "./pages/admin/RunPayroll";
import Reports from "./pages/admin/Reports";
import Compliance from "./pages/admin/Compliance";
import Leaves from "./pages/admin/Leaves";
import AIChat from "./pages/admin/AIChat";

import MyPayslips from "./pages/employee/MyPayslips";
import LeaveApply from "./pages/employee/LeaveApply";
import MyProfile from "./pages/employee/MyProfile";

function Protected({ role, children }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (role && user.role !== role) {
    return <Navigate to={user.role === "admin" ? "/admin" : "/me"} replace />;
  }
  return children;
}

function RootRedirect() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={user.role === "admin" ? "/admin" : "/me"} replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<RootRedirect />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        <Route path="/admin" element={<Protected role="admin"><AdminLayout /></Protected>}>
          <Route index element={<Dashboard />} />
          <Route path="employees" element={<Employees />} />
          <Route path="payroll" element={<RunPayroll />} />
          <Route path="leaves" element={<Leaves />} />
          <Route path="compliance" element={<Compliance />} />
          <Route path="reports" element={<Reports />} />
          <Route path="ai-chat" element={<AIChat />} />
        </Route>

        <Route path="/me" element={<Protected><EmployeeLayout /></Protected>}>
          <Route index element={<MyPayslips />} />
          <Route path="leave" element={<LeaveApply />} />
          <Route path="profile" element={<MyProfile />} />
        </Route>

        <Route path="*" element={<RootRedirect />} />
      </Routes>
    </AuthProvider>
  );
}
