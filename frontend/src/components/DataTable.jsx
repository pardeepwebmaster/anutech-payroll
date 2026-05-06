import { useMemo, useState } from "react";

export default function DataTable({ columns, rows, searchable = true, emptyMessage = "No records." }) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    if (!query) return rows;
    const q = query.toLowerCase();
    return rows.filter((row) =>
      columns.some((col) => {
        const v = typeof col.accessor === "function" ? col.accessor(row) : row[col.key];
        return String(v ?? "").toLowerCase().includes(q);
      })
    );
  }, [rows, columns, query]);

  return (
    <div className="card p-0 overflow-hidden">
      {searchable && (
        <div className="flex items-center justify-between gap-3 border-b border-gray-200 px-4 py-3">
          <input
            className="input max-w-xs"
            placeholder="Search..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <span className="text-sm text-gray-500">
            {filtered.length} of {rows.length}
          </span>
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-primary-50 text-primary-800">
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`px-4 py-2 text-left font-semibold ${col.headerClassName ?? ""}`}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-12 text-center text-gray-400">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              filtered.map((row, i) => (
                <tr key={row.id ?? i} className="hover:bg-gray-50">
                  {columns.map((col) => (
                    <td key={col.key} className={`px-4 py-2 ${col.cellClassName ?? ""}`}>
                      {col.render
                        ? col.render(row)
                        : typeof col.accessor === "function"
                        ? col.accessor(row)
                        : row[col.key] ?? ""}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
