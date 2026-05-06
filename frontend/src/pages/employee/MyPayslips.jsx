import { useEffect, useState } from "react";
import api from "../../lib/api";
import DataTable from "../../components/DataTable";
import { inr, isoDate } from "../../lib/format";

export default function MyPayslips() {
  const [rows, setRows] = useState([]);
  useEffect(() => { api.get("/payroll/payslips/me").then((r) => setRows(r.data)); }, []);

  const columns = [
    { key: "created_at", header: "Issued", render: (r) => isoDate(r.created_at) },
    { key: "gross", header: "Gross", render: (r) => inr(r.gross) },
    { key: "pf_employee", header: "PF", render: (r) => inr(r.pf_employee) },
    { key: "tds", header: "TDS", render: (r) => inr(r.tds) },
    { key: "net_pay", header: "Net", render: (r) => <strong>{inr(r.net_pay)}</strong> },
    {
      key: "pdf", header: "",
      render: (p) => (
        <a className="text-primary-600 text-sm hover:underline"
           href={`/api/v1/payroll/payslips/${p.id}/pdf`}>Download PDF</a>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">My payslips</h1>
      <DataTable columns={columns} rows={rows} searchable={false} emptyMessage="No payslips yet." />
    </div>
  );
}
