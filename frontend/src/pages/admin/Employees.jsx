import { useEffect, useState } from "react";
import api, { downloadFile } from "../../lib/api";
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
  const [pwTarget, setPwTarget] = useState(null);  // {id, name} of employee whose password we're setting
  const [pwValue, setPwValue] = useState("");
  const [pwInfo, setPwInfo] = useState(null);

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

  const setPassword = async (e) => {
    e.preventDefault();
    if (pwValue.length < 8) {
      setPwInfo({ error: "Password must be at least 8 characters" });
      return;
    }
    try {
      await api.patch(`/employees/${pwTarget.id}`, { password: pwValue });
      setPwInfo({
        ok: true,
        message: `Password set for ${pwTarget.name}. Share these login details with them: tenant=anutech, email=${pwTarget.email}, password=${pwValue}`,
      });
      setPwValue("");
    } catch (err) {
      setPwInfo({ error: err?.response?.data?.detail || "Failed" });
    }
  };

  const closePwModal = () => {
    setPwTarget(null);
    setPwValue("");
    setPwInfo(null);
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
    {
      key: "login", header: "Login",
      render: (r) => (
        <button
          className="text-primary-600 text-xs hover:underline"
          onClick={() => setPwTarget({ id: r.id, name: r.name, email: r.email })}
          disabled={!r.email}
          title={!r.email ? "Add an email first" : "Set a password so this employee can log in"}
        >
          {r.email ? "Set password" : "No email"}
        </button>
      ),
    },
  ];

  const update = (k) => (e) => setDraft({ ...draft, [k]: e.target.value });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Employees</h1>
          <p className="text-sm text-gray-500 mt-1">Manage your workforce. Use "Set password" to give an employee login access to apply leave / view payslips.</p>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary text-sm"
                  onClick={() => downloadFile("/employees/export.csv", "employees.csv")}>
            Export CSV
          </button>
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

      {pwTarget && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-10 p-4" onClick={closePwModal}>
          <form
            className="card w-full max-w-md space-y-3"
            onClick={(e) => e.stopPropagation()}
            onSubmit={setPassword}
          >
            <h2 className="text-lg font-semibold">Set login password</h2>
            <p className="text-sm text-gray-600">
              Set a password for <strong>{pwTarget.name}</strong> ({pwTarget.email}).
              They can then log in to apply leave and download payslips.
            </p>

            {pwInfo?.ok ? (
              <>
                <div className="text-sm text-green-700 bg-green-50 border border-green-200 rounded p-3 break-all">
                  {pwInfo.message}
                </div>
                <button type="button" className="btn-primary w-full text-sm" onClick={closePwModal}>Done</button>
              </>
            ) : (
              <>
                {pwInfo?.error && (
                  <div className="text-sm text-red-600">{pwInfo.error}</div>
                )}
                <div>
                  <label className="block text-sm font-medium mb-1">New password (min 8 chars)</label>
                  <input
                    type="text"
                    className="input"
                    value={pwValue}
                    onChange={(e) => setPwValue(e.target.value)}
                    minLength={8}
                    autoFocus
                    placeholder="e.g. Welcome2026!"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <button type="button" className="btn-secondary text-sm" onClick={closePwModal}>Cancel</button>
                  <button type="submit" className="btn-primary text-sm">Set password</button>
                </div>
              </>
            )}
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
