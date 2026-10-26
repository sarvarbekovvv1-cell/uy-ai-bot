import React, { useEffect, useState } from "react";
import { adminApi } from "../api/client";
import type { AuditEventItem } from "../types";

export const AuditPage: React.FC = () => {
  const [events, setEvents] = useState<AuditEventItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState("");
  const [loading, setLoading] = useState(true);

  const fetchAuditEvents = async () => {
    setLoading(true);
    try {
      const res = await adminApi.listAuditEvents({
        page,
        page_size: 20,
        action: actionFilter || undefined,
      });
      setEvents(res.items);
      setTotal(res.total);
    } catch (err: unknown) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAuditEvents();
  }, [page, actionFilter]);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
        <div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 700, color: "#f8fafc" }}>
            Ma'muriy Audit Jurnali (Immutable)
          </h1>
          <p style={{ fontSize: "0.875rem", color: "#94a3b8" }}>
            Tizimdagi barcha ma'muriy harakatlarning o'zgarmas tarixi ({total} ta yozuv)
          </p>
        </div>

        <select
          value={actionFilter}
          onChange={(e) => {
            setActionFilter(e.target.value);
            setPage(1);
          }}
          data-testid="audit-action-filter"
          style={{
            padding: "8px 12px",
            backgroundColor: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "6px",
            color: "#f8fafc",
            fontSize: "0.875rem",
          }}
        >
          <option value="">Barcha harakatlar</option>
          <option value="auth.login">auth.login</option>
          <option value="auth.logout">auth.logout</option>
          <option value="property.approve">property.approve</option>
          <option value="property.reject">property.reject</option>
          <option value="property.archive">property.archive</option>
          <option value="lead.change_stage">lead.change_stage</option>
          <option value="lead.assign">lead.assign</option>
          <option value="lead.add_note">lead.add_note</option>
          <option value="viewing.accept">viewing.accept</option>
          <option value="viewing.complete">viewing.complete</option>
          <option value="viewing.reject">viewing.reject</option>
          <option value="crm.retry">crm.retry</option>
          <option value="users.update_roles">users.update_roles</option>
        </select>
      </div>

      <div style={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px", overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "0.875rem" }}>
          <thead>
            <tr style={{ backgroundColor: "#0f172a", borderBottom: "1px solid #334155", color: "#94a3b8" }}>
              <th style={{ padding: "12px 16px" }}>ID</th>
              <th style={{ padding: "12px 16px" }}>Vaqt</th>
              <th style={{ padding: "12px 16px" }}>Ijrochi (Actor)</th>
              <th style={{ padding: "12px 16px" }}>Harakat (Action)</th>
              <th style={{ padding: "12px 16px" }}>Ob'ekt</th>
              <th style={{ padding: "12px 16px" }}>IP Manzil</th>
              <th style={{ padding: "12px 16px" }}>Metama'lumot</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} style={{ padding: "24px", textAlign: "center", color: "#94a3b8" }}>
                  Yuklanmoqda...
                </td>
              </tr>
            ) : events.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ padding: "24px", textAlign: "center", color: "#94a3b8" }}>
                  Audit yozuvlari mavjud emas.
                </td>
              </tr>
            ) : (
              events.map((e) => (
                <tr key={e.id} style={{ borderBottom: "1px solid #334155" }}>
                  <td style={{ padding: "12px 16px", color: "#64748b" }}>#{e.id}</td>
                  <td style={{ padding: "12px 16px", color: "#cbd5e1" }}>
                    {new Date(e.created_at).toLocaleString()}
                  </td>
                  <td style={{ padding: "12px 16px", fontWeight: 500, color: "#f8fafc" }}>
                    {e.actor_name || `User #${e.actor_user_id || "System"}`}
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    <code
                      style={{
                        padding: "2px 6px",
                        borderRadius: "4px",
                        backgroundColor: "#0f172a",
                        color: "#93c5fd",
                        fontSize: "0.8rem",
                      }}
                    >
                      {e.action}
                    </code>
                  </td>
                  <td style={{ padding: "12px 16px", color: "#cbd5e1" }}>
                    {e.entity_type} {e.entity_id ? `(#${e.entity_id})` : ""}
                  </td>
                  <td style={{ padding: "12px 16px", color: "#94a3b8", fontFamily: "monospace" }}>
                    {e.ip_address || "—"}
                  </td>
                  <td style={{ padding: "12px 16px", color: "#64748b", fontSize: "0.8rem" }}>
                    {e.metadata_sanitized ? JSON.stringify(e.metadata_sanitized) : "—"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "16px" }}>
        <button
          disabled={page <= 1}
          onClick={() => setPage(page - 1)}
          style={{
            padding: "6px 12px",
            backgroundColor: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "4px",
            color: "#f8fafc",
            cursor: page <= 1 ? "not-allowed" : "pointer",
          }}
        >
          Oldingi
        </button>
        <span style={{ alignSelf: "center", fontSize: "0.875rem", color: "#94a3b8" }}>
          Sahifa {page}
        </span>
        <button
          disabled={events.length < 20}
          onClick={() => setPage(page + 1)}
          style={{
            padding: "6px 12px",
            backgroundColor: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "4px",
            color: "#f8fafc",
            cursor: events.length < 20 ? "not-allowed" : "pointer",
          }}
        >
          Keyingi
        </button>
      </div>
    </div>
  );
};
