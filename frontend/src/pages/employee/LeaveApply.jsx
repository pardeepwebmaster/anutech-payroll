import { useEffect, useState } from "react";
import api from "../../lib/api";
import DataTable from "../../components/DataTable";
import { isoDate } from "../../lib/format";

const empty = { type: "casual", from_date: "", to_date: "", reason: "" };

export default function LeaveApply() {
  const [rows, setRows] = useState([]);
  const [balance, setBalance] = useState({});
  const [draft, setDraft] = useState(empty);
  const [error, setError] = useState(null);
  const [info, setInfo] = useState(null);

  const load = async () => {
    const [leaves, bal] = await Promise.all([
      api.get("/leaves"),
      api.get("/leaves/balance/me"),
    ]);
    setRows(leaves.data);
    setBalance(bal.data);
  };
  useEffect(() => { load(); }, []);

  const submit = async (e) => {
    e.preventDefault();
    setError(null); setInfo(null);
    try {
      await api.post("/leaves", draft);
      setInfo("Leave applied. Awaiting approval.");
      setDraft(empty);
      await load();
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed");
    }
  };

  const update = (k) => (e) => setDraft({ ...draft, [k]: e.target.value });

  const columns = [
    { key: "type", header: "Type" },
    { key: "from_date", header: "From", render: (r) => isoDate(r.from_date) },
    { key: "to_date", header: "To", render: (r) => isoDate(r.to_date) },
    { key: "reason", header: "Reason", render: (r) => r.reason ?? "—" },
    {
      key: "status", header: "Status",
      render: (r) => {
        const cls = r.status === "approved" ? "text-green-700" :
          r.status === "rejected" ? "text-red-600" : "text-amber-700";
        return <span className={cls}>{r.status}</span>;
      },
    },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Leave</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {Object.entries(balance).map(([k, v]) => (
          <div key={k} className="card">
            <div className="text-xs uppercase tracking-wider text-gray-500">{k}</div>
            <div className="text-2xl font-semibold mt-1">{v}</div>
            <div className="text-xs text-gray-400">days remaining</div>
          </div>
        ))}
      </div>

      <form onSubmit={submit} className="card space-y-3">
        <h2 className="text-lg font-semibold">Apply for leave</h2>
        {error && <div className="text-sm text-red-600">{error}</div>}
        {info && <div className="text-sm text-green-700">{info}</div>}

        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="block text-sm font-medium mb-1">Type</label>
            <select className="input" value={draft.type} onChange={update("type")}>
              <option value="casual">Casual</option>
              <option value="sick">Sick</option>
              <option value="earned">Earned</option>
              <option value="unpaid">Unpaid</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">From</label>
            <input type="date" className="input" value={draft.from_date} onChange={update("from_date")} required />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">To</label>
            <input type="date" className="input" value={draft.to_date} onChange={update("to_date")} required />
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Reason</label>
          <textarea className="input" rows={3} value={draft.reason} onChange={update("reason")} />
        </div>
        <button type="submit" className="btn-primary">Apply</button>
      </form>

      <div>
        <h2 className="text-lg font-semibold mb-3">My leave requests</h2>
        <DataTable columns={columns} rows={rows} searchable={false} emptyMessage="No leave requests yet." />
      </div>
    </div>
  );
}
