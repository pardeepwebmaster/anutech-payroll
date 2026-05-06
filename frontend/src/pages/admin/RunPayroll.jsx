import { useEffect, useState } from "react";
import api, { downloadFile } from "../../lib/api";
import DataTable from "../../components/DataTable";
import { inr, monthName } from "../../lib/format";

export default function RunPayroll() {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth() === 0 ? 12 : today.getMonth());
  const [runs, setRuns] = useState([]);
  const [payslips, setPayslips] = useState([]);
  const [selectedRun, setSelectedRun] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [info, setInfo] = useState(null);

  const loadRuns = () => api.get("/payroll/runs").then((r) => setRuns(r.data));
  useEffect(() => { loadRuns(); }, []);

  const run = async () => {
    setBusy(true); setError(null); setInfo(null);
    try {
      const { data } = await api.post("/payroll/run", { year, month, force: false });
      setInfo(`Payroll completed for ${monthName(month)} ${year}: ${data.payslip_count} payslips, net ${inr(data.total_net)}`);
      await loadRuns();
    } catch (err) {
      setError(err?.response?.data?.detail || "Run failed");
    } finally {
      setBusy(false);
    }
  };

  const view = async (r) => {
    setSelectedRun(r);
    const { data } = await api.get(`/payroll/runs/${r.id}/payslips`);
    setPayslips(data);
  };

  const runColumns = [
    { key: "period", header: "Period", render: (r) => `${monthName(r.month)} ${r.year}` },
    { key: "status", header: "Status" },
    { key: "payslip_count", header: "Payslips" },
    { key: "total_gross", header: "Gross", render: (r) => inr(r.total_gross) },
    { key: "total_net", header: "Net", render: (r) => inr(r.total_net) },
    {
      key: "actions", header: "",
      render: (r) => (
        <button className="text-primary-600 text-sm hover:underline" onClick={() => view(r)}>
          View payslips
        </button>
      ),
    },
  ];

  const psColumns = [
    { key: "employee_id", header: "Employee", render: (p) => p.employee_id.slice(0, 8) },
    { key: "gross", header: "Gross", render: (p) => inr(p.gross) },
    { key: "basic", header: "Basic", render: (p) => inr(p.basic) },
    { key: "pf_employee", header: "PF", render: (p) => inr(p.pf_employee) },
    { key: "tds", header: "TDS", render: (p) => inr(p.tds) },
    { key: "net_pay", header: "Net", render: (p) => <strong>{inr(p.net_pay)}</strong> },
    {
      key: "pdf", header: "",
      render: (p) => (
        <button className="text-primary-600 text-sm hover:underline"
                onClick={() => downloadFile(`/payroll/payslips/${p.id}/pdf`, `payslip-${p.id}.pdf`)}>
          PDF
        </button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Payroll</h1>
        <p className="text-sm text-gray-500 mt-1">Run monthly payroll and view payslips.</p>
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold mb-3">Run payroll</h2>
        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="block text-sm font-medium mb-1">Year</label>
            <input type="number" className="input w-28" value={year} onChange={(e) => setYear(+e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Month</label>
            <select className="input w-40" value={month} onChange={(e) => setMonth(+e.target.value)}>
              {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                <option key={m} value={m}>{monthName(m)}</option>
              ))}
            </select>
          </div>
          <button className="btn-primary" disabled={busy} onClick={run}>
            {busy ? "Running..." : "Run payroll"}
          </button>
        </div>
        {info && <div className="mt-3 text-sm text-green-700 bg-green-50 border border-green-200 rounded p-3">{info}</div>}
        {error && <div className="mt-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded p-3">{error}</div>}
      </div>

      <div>
        <h2 className="text-lg font-semibold mb-3">Recent runs</h2>
        <DataTable columns={runColumns} rows={runs} emptyMessage="No payroll runs yet." />
      </div>

      {selectedRun && (
        <div>
          <h2 className="text-lg font-semibold mb-3">
            Payslips — {monthName(selectedRun.month)} {selectedRun.year}
          </h2>
          <DataTable columns={psColumns} rows={payslips} searchable={false} />
        </div>
      )}
    </div>
  );
}
