import { useEffect, useState } from "react";
import api from "../../lib/api";
import DataTable from "../../components/DataTable";
import { isoDate } from "../../lib/format";

export default function Leaves() {
  const [rows, setRows] = useState([]);

  const load = () => api.get("/leaves").then((r) => setRows(r.data));
  useEffect(() => { load(); }, []);

  const decide = async (id, status) => {
    await api.patch(`/leaves/${id}`, { status });
    await load();
  };

  const columns = [
    { key: "employee_id", header: "Employee", render: (r) => r.employee_id.slice(0, 8) },
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
    {
      key: "actions", header: "",
      render: (r) =>
        r.status === "pending" ? (
          <div className="flex gap-2">
            <button className="text-green-700 text-sm hover:underline" onClick={() => decide(r.id, "approved")}>
              Approve
            </button>
            <button className="text-red-600 text-sm hover:underline" onClick={() => decide(r.id, "rejected")}>
              Reject
            </button>
          </div>
        ) : null,
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Leave requests</h1>
        <p className="text-sm text-gray-500 mt-1">Approve or reject employee leave applications.</p>
      </div>
      <DataTable columns={columns} rows={rows} emptyMessage="No leave requests." />
    </div>
  );
}
