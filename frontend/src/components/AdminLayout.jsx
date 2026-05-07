import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../lib/auth";

const NAV = [
  { to: "/admin", end: true, label: "Dashboard", icon: "▦" },
  { to: "/admin/employees", label: "Employees", icon: "👤" },
  { to: "/admin/payroll", label: "Payroll", icon: "₹" },
  { to: "/admin/leaves", label: "Leaves", icon: "✓", badge: "leaves" },
  { to: "/admin/compliance", label: "Compliance", icon: "⚖" },
  { to: "/admin/reports", label: "Reports", icon: "📊" },
  { to: "/admin/ai-chat", label: "AI Chat", icon: "✻" },
];

export default function AdminLayout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [pendingLeaves, setPendingLeaves] = useState(0);

  // Refetch the badge count whenever the route changes (so approving a leave
  // updates the sidebar without a hard refresh).
  useEffect(() => {
    let cancelled = false;
    api.get("/leaves/pending-count")
      .then((r) => { if (!cancelled) setPendingLeaves(r.data?.pending ?? 0); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [loc.pathname]);

  const handleLogout = () => {
    logout();
    nav("/login");
  };

  return (
    <div className="min-h-screen flex bg-gray-50">
      <aside className="w-60 shrink-0 bg-white border-r border-gray-200 flex flex-col">
        <div className="px-5 py-5 border-b border-gray-200">
          <div className="text-lg font-semibold text-primary-700">Anutech</div>
          <div className="text-xs text-gray-500">Payroll &middot; {user?.tenant_schema}</div>
        </div>
        <nav className="flex-1 py-3">
          {NAV.map((item) => {
            const count = item.badge === "leaves" ? pendingLeaves : 0;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-5 py-2 text-sm transition ${
                    isActive
                      ? "bg-primary-50 text-primary-700 border-r-2 border-primary-500 font-medium"
                      : "text-gray-700 hover:bg-gray-50"
                  }`
                }
              >
                <span className="w-5 text-center text-primary-500">{item.icon}</span>
                <span className="flex-1">{item.label}</span>
                {count > 0 && (
                  <span className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 rounded-full text-xs font-semibold bg-orange-500 text-white">
                    {count}
                  </span>
                )}
              </NavLink>
            );
          })}
        </nav>
        <div className="p-4 border-t border-gray-200">
          <button onClick={handleLogout} className="w-full btn-secondary text-sm">
            Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto">
        <div className="max-w-7xl mx-auto px-6 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
