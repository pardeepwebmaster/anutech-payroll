import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";

export default function Register() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({
    company_name: "",
    slug: "",
    plan: "Starter",
    admin_name: "",
    admin_email: "",
    admin_password: "",
  });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await register(form);
      nav("/admin", { replace: true });
    } catch (err) {
      setError(err?.response?.data?.detail || "Registration failed");
    } finally {
      setBusy(false);
    }
  };

  const update = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 via-white to-primary-100 px-4 py-10">
      <form onSubmit={submit} className="card w-full max-w-lg space-y-4">
        <h1 className="text-xl font-semibold">Create your tenant</h1>
        {error && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded p-3">
            {error}
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium mb-1">Company name</label>
            <input className="input" value={form.company_name} onChange={update("company_name")} required />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Slug</label>
            <input
              className="input"
              value={form.slug}
              onChange={update("slug")}
              placeholder="acme"
              pattern="^[a-z][a-z0-9-]{2,32}$"
              title="lowercase, 3-32 chars, starts with a letter"
              required
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Plan</label>
          <select className="input" value={form.plan} onChange={update("plan")}>
            <option>Starter</option>
            <option>Growth</option>
            <option>Scale</option>
          </select>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium mb-1">Admin name</label>
            <input className="input" value={form.admin_name} onChange={update("admin_name")} required />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Admin email</label>
            <input type="email" className="input" value={form.admin_email} onChange={update("admin_email")} required />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Admin password</label>
          <input type="password" className="input" minLength={8} value={form.admin_password} onChange={update("admin_password")} required />
        </div>

        <button type="submit" className="btn-primary w-full" disabled={busy}>
          {busy ? "Creating..." : "Create tenant"}
        </button>

        <div className="text-center text-sm text-gray-500 pt-2">
          Already have an account?{" "}
          <Link to="/login" className="text-primary-600 hover:underline">Sign in</Link>
        </div>
      </form>
    </div>
  );
}
