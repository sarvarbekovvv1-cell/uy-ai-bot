import React, { useEffect, useState } from "react";
import { adminApi } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { CRMOutboxEventItem } from "../types";

export const CRMPage: React.FC = () => {
  const { hasPerm } = useAuth();
  const canRetry = hasPerm("crm.retry");

  const [events, setEvents] = useState<CRMOutboxEventItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("failed");
  const [loading, setLoading] = useState(true);

  // Error modal
  const [selectedError, setSelectedError] = useState<string | null>(null);
  const [retryingId, setRetryingId] = useState<number | null>(null);

  const fetchEvents = async () => {
    setLoading(true);
    try {
      const res = await adminApi.listCRMOutbox({
        page,
        page_size: 15,
        status: statusFilter || undefined,
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
    fetchEvents();
  }, [page, statusFilter]);

  const handleRetry = async (id: number) => {
    setRetryingId(id);
    try {
      await adminApi.retryCRMEvent(id);
      fetchEvents();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Qayta urinish amalga oshmadi.");
    } finally {
      setRetryingId(null);
    }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
        <div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 700, color: "#f8fafc" }}>
            amoCRM Outbox Navbati va Monitoring
          </h1>
          <p style={{ fontSize: "0.875rem", color: "#94a3b8" }}>
            Jami: {total} ta hodisa
          </p>
        </div>

        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          data-testid="crm-status-filter"
          style={{
            padding: "8px 12px",
            backgroundColor: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "6px",
            color: "#f8fafc",
            fontSize: "0.875rem",
          }}
        >
          <option value="">Barchasi</option>
          <option value="failed">Xatolar (Failed)</option>
          <option value="pending">Kutilmoqda (Pending)</option>
          <option value="succeeded">Muvaffaqiyatli (Succeeded)</option>
        </select>
      </div>

      <div style={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px", overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "0.875rem" }}>
          <thead>
            <tr style={{ backgroundColor: "#0f172a", borderBottom: "1px solid #334155", color: "#94a3b8" }}>
              <th style={{ padding: "12px 16px" }}>ID</th>
              <th style={{ padding: "12px 16px" }}>Provayder</th>
              <th style={{ padding: "12px 16px" }}>Hodisa Turi</th>
              <th style={{ padding: "12px 16px" }}>Ob'ekt</th>
              <th style={{ padding: "12px 16px" }}>Holat</th>
              <th style={{ padding: "12px 16px" }}>Urinishlar</th>
              <th style={{ padding: "12px 16px" }}>Xatolik</th>
              <th style={{ padding: "12px 16px", textAlign: "right" }}>Amallar</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8} style={{ padding: "24px", textAlign: "center", color: "#94a3b8" }}>
                  Yuklanmoqda...
                </td>
              </tr>
            ) : events.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ padding: "24px", textAlign: "center", color: "#94a3b8" }}>
                  Hodisalar topilmadi.
                </td>
              </tr>
            ) : (
              events.map((e) => (
                <tr key={e.id} style={{ borderBottom: "1px solid #334155" }}>
                  <td style={{ padding: "12px 16px", color: "#64748b" }}>#{e.id}</td>
                  <td style={{ padding: "12px 16px", color: "#93c5fd" }}>{e.provider}</td>
                  <td style={{ padding: "12px 16px", fontWeight: 500, color: "#f8fafc" }}>{e.event_type}</td>
                  <td style={{ padding: "12px 16px", color: "#cbd5e1" }}>
                    {e.entity_type}:{e.entity_id}
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    <span
                      style={{
                        padding: "2px 8px",
                        borderRadius: "12px",
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        backgroundColor:
                          e.status === "succeeded"
                            ? "rgba(16, 185, 129, 0.2)"
                            : e.status === "failed"
                            ? "rgba(239, 68, 68, 0.2)"
                            : "rgba(245, 158, 11, 0.2)",
                        color:
                          e.status === "succeeded"
                            ? "#34d399"
                            : e.status === "failed"
                            ? "#f87171"
                            : "#fbbf24",
                      }}
                    >
                      {e.status}
                    </span>
                  </td>
                  <td style={{ padding: "12px 16px", color: "#cbd5e1" }}>
                    {e.attempts} / {e.max_attempts}
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    {e.last_error_sanitized ? (
                      <button
                        onClick={() => setSelectedError(e.last_error_sanitized)}
                        style={{
                          background: "none",
                          border: "none",
                          color: "#f87171",
                          textDecoration: "underline",
                          cursor: "pointer",
                          fontSize: "0.8rem",
                        }}
                      >
                        Xatoni ko'rish
                      </button>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td style={{ padding: "12px 16px", textAlign: "right" }}>
                    {canRetry && e.status === "failed" && (
                      <button
                        onClick={() => handleRetry(e.id)}
                        disabled={retryingId === e.id}
                        data-testid={`retry-crm-${e.id}`}
                        style={{
                          padding: "4px 10px",
                          backgroundColor: "#3b82f6",
                          color: "#ffffff",
                          border: "none",
                          borderRadius: "4px",
                          fontSize: "0.75rem",
                          fontWeight: 600,
                          cursor: "pointer",
                        }}
                      >
                        {retryingId === e.id ? "Urinilmoqda..." : "Qayta urinish"}
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Error Details Modal */}
      {selectedError && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.7)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
            zIndex: 1000,
          }}
        >
          <div
            style={{
              backgroundColor: "#1e293b",
              border: "1px solid #334155",
              borderRadius: "12px",
              width: "100%",
              maxWidth: "500px",
              padding: "24px",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h2 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#f87171" }}>
                Sanitizatsiya qilingan xatolik tafsilotlari
              </h2>
              <button
                onClick={() => setSelectedError(null)}
                style={{ background: "transparent", border: "none", color: "#94a3b8", fontSize: "1.2rem", cursor: "pointer" }}
              >
                ✕
              </button>
            </div>

            <pre
              style={{
                backgroundColor: "#0f172a",
                padding: "12px",
                borderRadius: "6px",
                color: "#fca5a5",
                fontSize: "0.8rem",
                overflowX: "auto",
                whiteSpace: "pre-wrap",
              }}
            >
              {selectedError}
            </pre>

            <div style={{ marginTop: "20px", textAlign: "right" }}>
              <button
                onClick={() => setSelectedError(null)}
                style={{
                  padding: "8px 16px",
                  backgroundColor: "#334155",
                  color: "#f8fafc",
                  border: "none",
                  borderRadius: "6px",
                  cursor: "pointer",
                }}
              >
                Yopish
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
