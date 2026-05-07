import { useEffect, useState } from "react";
import api from "../../lib/api";
import DataTable from "../../components/DataTable";
import { isoDate } from "../../lib/format";

const empty = { type: "casual", from_date: "", to_date: "", reason: "" };

const TYPE_HELP = {
  casual: "Short personal leave (1-3 days). Paid; counts against your annual quota.",
  sick: "Illness or medical reason. Paid; counts against your annual quota.",
  earned: "Long planned leave (e.g. vacation). Paid; counts against your annual quota.",
  unpaid: "When you've used up paid leave or it doesn't apply. Salary for those days is deducted.",
};

function PaidBadge({ isPaid }) {
  return isPaid ? (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
      Paid
    </span>
  ) : (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
      Unpaid
    </span>
  );
}

function StatusBadge({ status }) {
  const map = {
    approved: "bg-green-100 text-green-800",
    rejected: "bg-red-100 text-red-700",
    pending: "bg-amber-100 text-amber-800",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${map[status] || "bg-gray-100"}`}>
      {status}
    </span>
  );
}

export default function LeaveApply() {
  const [rows, setRows] = useState([]);
  const [balance, setBalance] = useState({});
  const [draft, setDraft] = useState(empty);
  const [error, setError] = useState(null);
  const [info, setInfo] = useState(null);
  const [busy, setBusy] = useState(false);

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
    setError(null); setInfo(null); setBusy(true);
    try {
      await api.post("/leaves", draft);
      setInfo("Leave applied. Awaiting your manager's approval.");
      setDraft(empty);
      await load();
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to apply leave");
    } finally {
      setBusy(false);
    }
  };

  const update = (k) => (e) => setDraft({ ...draft, [k]: e.target.value });

  const days = (() => {
    if (!draft.from_date || !draft.to_date) return 0;
    const a = new Date(draft.from_date);
    const b = new Date(draft.to_date);
    if (b < a) return 0;
    return Math.round((b - a) / (1000 * 60 * 60 * 24)) + 1;
  })();

  const columns = [
    {
      key: "type", header: "Type",
      render: (r) => (
        <div className="flex items-center gap-2">
          <span className="capitalize">{r.type}</span>
          <PaidBadge isPaid={r.is_paid} />
        </div>
      ),
    },
    { key: "from_date", header: "From", render: (r) => isoDate(r.from_date) },
    { key: "to_date", header: "To", render: (r) => isoDate(r.to_date) },
    { key: "days", header: "Days", render: (r) => <span className="font-medium">{r.days}</span> },
    { key: "reason", header: "Reason", render: (r) => r.reason ?? "—" },
    { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Leave</h1>

      <div>
        <h2 className="text-sm font-medium text-gray-700 mb-2">Annual balance</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Object.entries(balance).map(([k, v]) => (
            <div key={k} className="card">
              <div className="flex items-center justify-between">
                <div className="text-xs uppercase tracking-wider text-gray-500">{k}</div>
                <PaidBadge isPaid={v.is_paid} />
              </div>
              <div className="mt-2 text-2xl font-semibold">{v.remaining}</div>
              <div className="text-xs text-gray-400">
                of {v.total} days &middot; {v.used} used
              </div>
            </div>
          ))}
        </div>
      </div>

      <form onSubmit={submit} className="card space-y-3">
        <div>
          <h2 className="text-lg font-semibold">Apply for leave</h2>
          <p className="text-sm text-gray-500 mt-1">
            Fill in the dates and reason. Your manager will get a notification and can approve or reject.
          </p>
        </div>
        {error && <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded p-3">{error}</div>}
        {info && <div className="text-sm text-green-700 bg-green-50 border border-green-200 rounded p-3">{info}</div>}

        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="block text-sm font-medium mb-1">Type</label>
            <select className="input" value={draft.type} onChange={update("type")}>
              <option value="casual">Casual (paid)</option>
              <option value="sick">Sick (paid)</option>
              <option value="earned">Earned (paid)</option>
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

        <div className="text-xs text-gray-500 -mt-1">{TYPE_HELP[draft.type]}</div>

        {days > 0 && (
          <div className="text-sm text-primary-700 bg-primary-50 rounded p-2">
            Total: <strong>{days} day{days > 1 ? "s" : ""}</strong>
            {balance[draft.type] && draft.type !== "unpaid" && (
              <span className="ml-2 text-gray-600">
                (you'll have {Math.max(balance[draft.type].remaining - days, 0)} {draft.type} day(s) remaining after approval)
              </span>
            )}
          </div>
        )}

        <div>
          <label className="block text-sm font-medium mb-1">Reason</label>
          <textarea
            className="input"
            rows={3}
            value={draft.reason}
            onChange={update("reason")}
            placeholder="Brief reason — visible to your manager"
          />
        </div>
        <button type="submit" className="btn-primary" disabled={busy || !draft.from_date || !draft.to_date}>
          {busy ? "Applying..." : "Apply"}
        </button>
      </form>

      <div>
        <h2 className="text-lg font-semibold mb-3">My leave history</h2>
        <DataTable columns={columns} rows={rows} searchable={false} emptyMessage="No leave requests yet." />
      </div>
    </div>
  );
}
