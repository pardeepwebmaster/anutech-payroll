import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";

const NAV = [
  { to: "/me", end: true, label: "Payslips" },
  { to: "/me/leave", label: "Leave" },
  { to: "/me/profile", label: "Profile" },
];

export default function EmployeeLayout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <div className="text-lg font-semibold text-primary-700">Anutech Payroll</div>
            <div className="text-xs text-gray-500">{user?.tenant_schema}</div>
          </div>
          <button onClick={() => { logout(); nav("/login"); }} className="btn-secondary text-sm">
            Sign out
          </button>
        </div>
        <div className="max-w-4xl mx-auto px-6">
          <nav className="flex gap-6 -mb-px">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `py-3 text-sm border-b-2 transition ${
                    isActive
                      ? "border-primary-500 text-primary-700 font-medium"
                      : "border-transparent text-gray-600 hover:text-gray-900"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="max-w-4xl mx-auto px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
