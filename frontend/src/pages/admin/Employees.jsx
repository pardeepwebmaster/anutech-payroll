import { useEffect, useState } from "react";
import api from "../../lib/api";
import DataTable from "../../components/DataTable";
import { inr, isoDate } from "../../lib/format";

const empty = {
  name: "",
  email: "",
  role: "",
  department: "",
  basic_salary: "",
  joining_date: new Date().toISOString().slice(0, 10),
  pan: "",
  bank_account: "",
  bank_ifsc: "",
};

export default function Employees() {
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(empty);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = () => api.get("/employees").then((r) => setRows(r.data));

  useEffect(() => { load(); }, []);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/employees", { ...draft, basic_salary: parseFloat(draft.basic_salary) });
      setOpen(false);
      setDraft(empty);
      await load();
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to add employee");
    } finally {
      setBusy(false);
    }
  };

  const columns = [
    { key: "name", header: "Name", render: (r) => <span className="font-medium">{r.name}</span> },
    { key: "role", header: "Role" },
    { key: "department", header: "Department" },
    { key: "basic_salary", header: "Salary", render: (r) => inr(r.basic_salary) },
    { key: "joining_date", header: "Joined", render: (r) => isoDate(r.joining_date) },
    {
      key: "status", header: "Status",
      render: (r) => (
        <span className={r.status === "active" ? "text-green-700" : "text-gray-400"}>
          {r.status}
        </span>
      ),
    },
  ];

  const update = (k) => (e) => setDraft({ ...draft, [k]: e.target.value });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Employees</h1>
          <p className="text-sm text-gray-500 mt-1">Manage your workforce.</p>
        </div>
        <div className="flex gap-2">
          <a className="btn-secondary text-sm" href="/api/v1/employees/export.csv">Export CSV</a>
          <button className="btn-primary text-sm" onClick={() => setOpen(true)}>Add employee</button>
        </div>
      </div>

      <DataTable columns={columns} rows={rows} emptyMessage="No employees yet." />

      {open && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-10 p-4" onClick={() => setOpen(false)}>
          <form
            className="card w-full max-w-2xl space-y-4"
            onClick={(e) => e.stopPropagation()}
            onSubmit={submit}
          >
            <h2 className="text-lg font-semibold">Add employee</h2>
            {error && <div className="text-sm text-red-600">{error}</div>}

            <div className="grid grid-cols-2 gap-3">
              <Field label="Name" required value={draft.name} onChange={update("name")} />
              <Field label="Email" type="email" value={draft.email} onChange={update("email")} />
              <Field label="Role" required value={draft.role} onChange={update("role")} />
              <Field label="Department" required value={draft.department} onChange={update("department")} />
              <Field label="Basic salary (₹/month)" type="number" required value={draft.basic_salary} onChange={update("basic_salary")} />
              <Field label="Joining date" type="date" required value={draft.joining_date} onChange={update("joining_date")} />
              <Field label="PAN" maxLength={10} value={draft.pan} onChange={update("pan")} />
              <Field label="Bank account" value={draft.bank_account} onChange={update("bank_account")} />
              <Field label="IFSC" value={draft.bank_ifsc} onChange={update("bank_ifsc")} />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button type="button" className="btn-secondary text-sm" onClick={() => setOpen(false)}>Cancel</button>
              <button type="submit" className="btn-primary text-sm" disabled={busy}>
                {busy ? "Saving..." : "Save"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

function Field({ label, ...rest }) {
  return (
    <div>
      <label className="block text-sm font-medium mb-1">{label}</label>
      <input className="input" {...rest} />
    </div>
  );
}
