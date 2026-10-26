import React, { useEffect, useState } from "react";
import { adminApi } from "../api/client";
import type { BrokerWorkloadItem } from "../types";

export const BrokersPage: React.FC<{ onSelectBroker?: (brokerId: number) => void }> = ({
  onSelectBroker,
}) => {
  const [brokers, setBrokers] = useState<BrokerWorkloadItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchBrokers = () => {
    setLoading(true);
    setError(null);
    adminApi
      .listBrokers()
      .then((data) => {
        setBrokers(Array.isArray(data) ? data : []);
      })
      .catch((err: any) => {
        const msg =
          err?.status === 403
            ? "Ruxsat berilmagan (403 Forbidden). Ushbu bo'lim faqat rahbar yoki ruxsatli xodimlar uchun."
            : err?.message || "Brokerlar ma'lumotlarini yuklab bo'lmadi.";
        setError(msg);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchBrokers();
  }, []);

  return (
    <div>
      <div style={{ marginBottom: "20px" }}>
        <h1 style={{ fontSize: "1.5rem", fontWeight: 700, color: "#f8fafc" }}>
          Brokerlar va Ish Yuklamasi
        </h1>
        <p style={{ fontSize: "0.875rem", color: "#94a3b8" }}>
          Brokerlarning faol lidlari va kutilayotgan ko'rishlar balansi
        </p>
      </div>

      {error && (
        <div
          data-testid="brokers-error-state"
          style={{
            padding: "16px 20px",
            backgroundColor: "rgba(239, 68, 68, 0.15)",
            border: "1px solid #ef4444",
            borderRadius: "8px",
            color: "#fca5a5",
            marginBottom: "20px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            fontSize: "0.875rem",
          }}
        >
          <span>{error}</span>
          <button
            onClick={fetchBrokers}
            style={{
              padding: "6px 14px",
              backgroundColor: "#ef4444",
              color: "#ffffff",
              border: "none",
              borderRadius: "6px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Qayta urinish
          </button>
        </div>
      )}

      <div
        style={{
          backgroundColor: "#1e293b",
          border: "1px solid #334155",
          borderRadius: "8px",
          overflow: "hidden",
        }}
      >
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            textAlign: "left",
            fontSize: "0.875rem",
          }}
        >
          <thead>
            <tr
              style={{
                backgroundColor: "#0f172a",
                borderBottom: "1px solid #334155",
                color: "#94a3b8",
              }}
            >
              <th style={{ padding: "12px 16px" }}>ID</th>
              <th style={{ padding: "12px 16px" }}>F.I.SH / Login</th>
              <th style={{ padding: "12px 16px" }}>Telefon</th>
              <th style={{ padding: "12px 16px" }}>Rollar</th>
              <th style={{ padding: "12px 16px" }}>Faol Lidlar</th>
              <th style={{ padding: "12px 16px" }}>Kutilayotgan Ko'rishlar</th>
              <th style={{ padding: "12px 16px", textAlign: "right" }}>Filtrlash</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td
                  colSpan={7}
                  data-testid="brokers-loading-state"
                  style={{ padding: "24px", textAlign: "center", color: "#94a3b8" }}
                >
                  Yuklanmoqda...
                </td>
              </tr>
            ) : !error && brokers.length === 0 ? (
              <tr>
                <td
                  colSpan={7}
                  data-testid="brokers-empty-state"
                  style={{ padding: "32px", textAlign: "center", color: "#94a3b8" }}
                >
                  Hozircha brokerlar mavjud emas.
                </td>
              </tr>
            ) : (
              brokers.map((b) => {
                const displayName =
                  b.full_name ||
                  [b.first_name, b.last_name].filter(Boolean).join(" ") ||
                  (b.username ? `@${b.username}` : `Broker #${b.id}`);

                const rolesList =
                  Array.isArray(b.roles) && b.roles.length > 0
                    ? b.roles
                    : b.role
                    ? [b.role]
                    : [];

                const phoneDisplay = b.phone_masked || "—";
                const activeLeads = b.active_leads_count ?? 0;
                const pendingViewings =
                  b.pending_viewings_count ?? b.viewings_count ?? 0;

                return (
                  <tr
                    key={b.id}
                    data-testid={`broker-row-${b.id}`}
                    style={{ borderBottom: "1px solid #334155" }}
                  >
                    <td style={{ padding: "12px 16px", color: "#64748b" }}>
                      #{b.id}
                    </td>
                    <td
                      style={{
                        padding: "12px 16px",
                        fontWeight: 500,
                        color: "#f8fafc",
                      }}
                    >
                      {displayName}
                    </td>
                    <td style={{ padding: "12px 16px", color: "#cbd5e1" }}>
                      {phoneDisplay}
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
                        {rolesList.length > 0 ? (
                          rolesList.map((r) => (
                            <span
                              key={r}
                              style={{
                                padding: "2px 6px",
                                borderRadius: "10px",
                                fontSize: "0.7rem",
                                backgroundColor: "#334155",
                                color: "#93c5fd",
                              }}
                            >
                              {r}
                            </span>
                          ))
                        ) : (
                          <span style={{ color: "#64748b" }}>—</span>
                        )}
                      </div>
                    </td>
                    <td
                      style={{
                        padding: "12px 16px",
                        fontWeight: 600,
                        color: "#60a5fa",
                      }}
                    >
                      {activeLeads}
                    </td>
                    <td
                      style={{
                        padding: "12px 16px",
                        fontWeight: 600,
                        color: "#f59e0b",
                      }}
                    >
                      {pendingViewings}
                    </td>
                    <td style={{ padding: "12px 16px", textAlign: "right" }}>
                      {onSelectBroker && (
                        <button
                          onClick={() => onSelectBroker(b.id)}
                          style={{
                            padding: "6px 12px",
                            backgroundColor: "#334155",
                            color: "#f8fafc",
                            border: "none",
                            borderRadius: "4px",
                            fontSize: "0.8rem",
                            cursor: "pointer",
                          }}
                        >
                          Lidlarini ko'rish
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
