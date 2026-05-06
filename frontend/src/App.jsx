import { Routes, Route, Link } from "react-router-dom";

// Phase 0 placeholder shell — `frontend` teammate replaces this with the
// real router (login, admin layout, employee layout, protected routes).
function Home() {
  return (
    <div className="mx-auto max-w-2xl p-10">
      <div className="card">
        <h1 className="text-2xl font-semibold text-primary-700">
          Anutech Payroll
        </h1>
        <p className="mt-2 text-gray-600">
          Multi-tenant SaaS payroll for Indian companies.
        </p>
        <p className="mt-6 text-sm text-gray-500">
          Frontend scaffold ready. The <code>frontend</code> teammate will
          replace this with the real admin and employee portals.
        </p>
        <div className="mt-6 flex gap-3">
          <Link to="/admin" className="btn-primary">Admin (TBD)</Link>
          <Link to="/me" className="btn-secondary">Employee (TBD)</Link>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/admin/*" element={<div className="p-10">Admin shell — to be implemented</div>} />
      <Route path="/me/*" element={<div className="p-10">Employee portal — to be implemented</div>} />
    </Routes>
  );
}
