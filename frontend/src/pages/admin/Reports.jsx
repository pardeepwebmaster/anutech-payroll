import { useEffect, useState } from "react";
import api from "../../lib/api";
import DataTable from "../../components/DataTable";
import { inr, monthName } from "../../lib/format";

export default function Reports() {
  const [year, setYear] = useState(new Date().getFullYear());
  const [salary, setSalary] = useState(null);
  const [departments, setDepartments] = useState([]);

  useEffect(() => {
    api.get(`/reports/salary?year=${year}`).then((r) => setSalary(r.data));
    api.get(`/reports/department-spend`).then((r) => setDepartments(r.data));
  }, [year]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Reports</h1>
        <p className="text-sm text-gray-500 mt-1">Annual salary and department spend.</p>
      </div>

      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">Salary by month</h2>
          <input type="number" className="input w-28"
                 value={year} onChange={(e) => setYear(+e.target.value)} />
        </div>
        {salary && (
          <>
            <DataTable
              searchable={false}
              columns={[
                { key: "month", header: "Month", render: (r) => monthName(r.month) },
                { key: "total_gross", header: "Gross", render: (r) => inr(r.total_gross) },
                { key: "total_net", header: "Net", render: (r) => inr(r.total_net) },
              ]}
              rows={salary.rows}
              emptyMessage={`No completed runs for ${year}.`}
            />
            <div className="mt-3 text-sm text-right text-gray-600">
              Year total: <strong className="text-primary-700">{inr(salary.total_net)}</strong> net (gross {inr(salary.total_gross)})
            </div>
          </>
        )}
      </div>

      <div>
        <h2 className="text-lg font-semibold mb-3">Department spend (active employees)</h2>
        <DataTable
          searchable={false}
          columns={[
            { key: "department", header: "Department" },
            { key: "monthly_total", header: "Monthly", render: (r) => inr(r.monthly_total) },
          ]}
          rows={departments}
        />
      </div>
    </div>
  );
}
