import { useEffect, useState } from "react";
import api from "../../lib/api";
import DataTable from "../../components/DataTable";
import { inr, isoDate } from "../../lib/format";

const empty = { type: "PF", period: new Date().toISOString().slice(0, 7), due_date: "", amount: "" };

export default function Compliance() {
  const [filings, setFilings] = useState([]);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(empty);
  const [error, setError] = useState(null);

  const load = () => api.get("/compliance").then((r) => setFilings(r.data));
  useEffect(() => { load(); }, []);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/compliance", { ...draft, amount: parseFloat(draft.amount || 0) });
      setOpen(false); setDraft(empty); await load();
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed");
    }
  };

  const markFiled = async (id) => {
    await api.patch(`/compliance/${id}`, { filed_date: new Date().toISOString().slice(0, 10), status: "filed" });
    await load();
  };

  const update = (k) => (e) => setDraft({ ...draft, [k]: e.target.value });

  const columns = [
    { key: "type", header: "Type" },
    { key: "period", header: "Period" },
    { key: "due_date", header: "Due", render: (r) => isoDate(r.due_date) },
    { key: "filed_date", header: "Filed", render: (r) => isoDate(r.filed_date) },
    {
      key: "status", header: "Status",
      render: (r) => {
        const cls = r.status === "filed" ? "text-green-700" : r.status === "overdue" ? "text-red-700" : "text-amber-700";
        return <span className={cls}>{r.status}</span>;
      },
    },
    { key: "amount", header: "Amount", render: (r) => inr(r.amount) },
    {
      key: "actions", header: "",
      render: (r) =>
        r.status !== "filed" ? (
          <button className="text-primary-600 text-sm hover:underline" onClick={() => markFiled(r.id)}>
            Mark filed
          </button>
        ) : null,
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Compliance</h1>
          <p className="text-sm text-gray-500 mt-1">PF, ESI, TDS, and Professional Tax filings.</p>
        </div>
        <button className="btn-primary text-sm" onClick={() => setOpen(true)}>Add filing</button>
      </div>

      <DataTable columns={columns} rows={filings} emptyMessage="No filings tracked yet." />

      {open && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-10 p-4" onClick={() => setOpen(false)}>
          <form className="card w-full max-w-md space-y-3" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
            <h2 className="text-lg font-semibold">Add filing</h2>
            {error && <div className="text-sm text-red-600">{error}</div>}

            <div>
              <label className="block text-sm font-medium mb-1">Type</label>
              <select className="input" value={draft.type} onChange={update("type")}>
                <option>PF</option><option>ESI</option><option>TDS</option><option>PT</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Period (YYYY-MM)</label>
              <input className="input" pattern="^\d{4}-\d{2}$" value={draft.period} onChange={update("period")} required />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Due date</label>
              <input type="date" className="input" value={draft.due_date} onChange={update("due_date")} required />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Amount (₹)</label>
              <input type="number" step="0.01" className="input" value={draft.amount} onChange={update("amount")} />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button type="button" className="btn-secondary text-sm" onClick={() => setOpen(false)}>Cancel</button>
              <button type="submit" className="btn-primary text-sm">Save</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
