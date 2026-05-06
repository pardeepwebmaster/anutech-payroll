import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ slug: "anutech", email: "", password: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const u = await login(form);
      nav(u.role === "admin" ? "/admin" : "/me", { replace: true });
    } catch (err) {
      setError(err?.response?.data?.detail || "Login failed");
    } finally {
      setBusy(false);
    }
  };

  const update = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 via-white to-primary-100 px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-6">
          <div className="text-3xl font-bold text-primary-700">Anutech Payroll</div>
          <div className="text-sm text-gray-500 mt-1">Multi-tenant SaaS payroll</div>
        </div>

        <form onSubmit={submit} className="card space-y-4">
          <h1 className="text-xl font-semibold">Sign in</h1>
          {error && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded p-3">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium mb-1">Tenant slug</label>
            <input className="input" value={form.slug} onChange={update("slug")} required />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Email</label>
            <input
              type="email"
              className="input"
              value={form.email}
              onChange={update("email")}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Password</label>
            <input
              type="password"
              className="input"
              value={form.password}
              onChange={update("password")}
              required
            />
          </div>

          <button type="submit" className="btn-primary w-full" disabled={busy}>
            {busy ? "Signing in..." : "Sign in"}
          </button>

          <div className="text-center text-sm text-gray-500 pt-2">
            New company?{" "}
            <Link to="/register" className="text-primary-600 hover:underline">
              Register a tenant
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
