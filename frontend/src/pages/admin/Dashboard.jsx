import { useEffect, useState } from "react";
import api from "../../lib/api";
import { inr, monthName } from "../../lib/format";

function Stat({ label, value, hint }) {
  return (
    <div className="card">
      <div className="text-sm text-gray-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-gray-900">{value}</div>
      {hint && <div className="mt-1 text-xs text-gray-400">{hint}</div>}
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.get("/reports/dashboard")
      .then((r) => setData(r.data))
      .catch((e) => setError(e?.response?.data?.detail || "Failed to load"));
  }, []);

  if (error) return <div className="card text-red-600">{error}</div>;
  if (!data) return <div className="text-gray-400">Loading dashboard...</div>;

  const last = data.last_payroll_run;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">Overview of your payroll operations.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Stat label="Active employees" value={data.active_employees} />
        <Stat label="Pending leaves" value={data.pending_leaves} />
        <Stat label="Open compliance filings" value={data.open_filings} />
        <Stat
          label="Last payroll run"
          value={last ? `${monthName(last.month)} ${last.year}` : "—"}
          hint={last ? `Net: ${inr(last.total_net)}` : "Run your first payroll"}
        />
      </div>

      {last && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-3">Last payroll snapshot</h2>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <div className="text-gray-500">Total gross</div>
              <div className="text-lg font-medium">{inr(last.total_gross)}</div>
            </div>
            <div>
              <div className="text-gray-500">Total net</div>
              <div className="text-lg font-medium">{inr(last.total_net)}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
