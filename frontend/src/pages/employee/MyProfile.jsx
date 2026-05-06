import { useEffect, useState } from "react";
import api from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { inr, isoDate } from "../../lib/format";

function Row({ label, value }) {
  return (
    <div className="flex justify-between py-2 border-b border-gray-100 last:border-0">
      <span className="text-gray-500 text-sm">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export default function MyProfile() {
  const { user } = useAuth();
  const [me, setMe] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!user?.user_id) return;
    api.get(`/employees/${user.user_id}`)
      .then((r) => setMe(r.data))
      .catch((e) => setError(e?.response?.data?.detail || "Failed to load profile"));
  }, [user]);

  if (error) return <div className="card text-red-600">{error}</div>;
  if (!me) return <div className="text-gray-400">Loading...</div>;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">My profile</h1>
      <div className="card">
        <Row label="Name" value={me.name} />
        <Row label="Email" value={me.email ?? "—"} />
        <Row label="Role" value={me.role} />
        <Row label="Department" value={me.department} />
        <Row label="Joining date" value={isoDate(me.joining_date)} />
        <Row label="Status" value={me.status} />
        <Row label="PAN" value={me.pan ?? "—"} />
        <Row label="Bank account" value={me.bank_account ?? "—"} />
        <Row label="IFSC" value={me.bank_ifsc ?? "—"} />
        <Row label="Basic salary" value={inr(me.basic_salary)} />
      </div>
    </div>
  );
}
