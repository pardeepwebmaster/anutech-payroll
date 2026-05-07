import { useEffect, useState } from "react";
import api from "../../lib/api";
import DataTable from "../../components/DataTable";
import { isoDate } from "../../lib/format";

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

export default function Leaves() {
  const [rows, setRows] = useState([]);
  const [filter, setFilter] = useState("all");

  const load = () => api.get("/leaves").then((r) => setRows(r.data));
  useEffect(() => { load(); }, []);

  const decide = async (id, status) => {
    await api.patch(`/leaves/${id}`, { status });
    await load();
  };

  const filtered = filter === "all" ? rows : rows.filter((r) => r.status === filter);
  const counts = {
    all: rows.length,
    pending: rows.filter((r) => r.status === "pending").length,
    approved: rows.filter((r) => r.status === "approved").length,
    rejected: rows.filter((r) => r.status === "rejected").length,
  };

  const columns = [
    {
      key: "employee_name", header: "Employee",
      render: (r) => <span className="font-medium">{r.employee_name || r.employee_id.slice(0, 8)}</span>,
    },
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
        ) : r.approved_by_name ? (
          <span className="text-xs text-gray-400">by {r.approved_by_name}</span>
        ) : null,
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Leave requests</h1>
        <p className="text-sm text-gray-500 mt-1">
          Approve or reject employee leave applications.
          <span className="ml-1 text-orange-700 font-medium">Unpaid</span> leaves do not deduct from any annual balance — they're a record only.
          <span className="ml-1 text-green-700 font-medium">Paid</span> leaves (Casual / Sick / Earned) reduce the employee's annual quota.
        </p>
        <details className="mt-3 text-sm text-gray-600">
          <summary className="cursor-pointer text-primary-700">How does an employee submit a leave request?</summary>
          <ol className="list-decimal pl-6 mt-2 space-y-1">
            <li>Go to <strong>Employees</strong>, click <strong>Set password</strong> on the row of the employee you want to give login access.</li>
            <li>Share the slug (<code>anutech</code>), their email, and the password you set.</li>
            <li>The employee logs in at the same URL and lands on their personal portal — they can apply for leave from the <strong>Leave</strong> tab.</li>
            <li>Their request appears here as <em>pending</em>. Approve or reject — they'll see the status update on their portal.</li>
          </ol>
        </details>
      </div>

      <div className="flex gap-2">
        {["all", "pending", "approved", "rejected"].map((k) => (
          <button
            key={k}
            onClick={() => setFilter(k)}
            className={`text-sm px-3 py-1 rounded-full transition ${
              filter === k
                ? "bg-primary-500 text-white"
                : "bg-white border border-gray-300 text-gray-700 hover:bg-gray-50"
            }`}
          >
            <span className="capitalize">{k}</span>
            <span className="ml-1.5 opacity-70">{counts[k]}</span>
          </button>
        ))}
      </div>

      <DataTable
        columns={columns}
        rows={filtered}
        emptyMessage={filter === "pending" ? "No pending requests." : "No leave requests."}
      />
    </div>
  );
}
