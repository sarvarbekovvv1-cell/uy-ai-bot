import React, { useEffect, useState } from "react";
import { adminApi } from "../api/client";
import type { BrokerWorkloadItem } from "../types";

export const BrokersPage: React.FC<{ onSelectBroker?: (brokerId: number) => void }> = ({
  onSelectBroker,
}) => {
  const [brokers, setBrokers] = useState<BrokerWorkloadItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminApi
      .listBrokers()
      .then((data) => setBrokers(data))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
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

      <div style={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px", overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "0.875rem" }}>
          <thead>
            <tr style={{ backgroundColor: "#0f172a", borderBottom: "1px solid #334155", color: "#94a3b8" }}>
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
                <td colSpan={7} style={{ padding: "24px", textAlign: "center", color: "#94a3b8" }}>
                  Yuklanmoqda...
                </td>
              </tr>
            ) : brokers.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ padding: "24px", textAlign: "center", color: "#94a3b8" }}>
                  Brokerlar topilmadi.
                </td>
              </tr>
            ) : (
              brokers.map((b) => (
                <tr key={b.id} style={{ borderBottom: "1px solid #334155" }}>
                  <td style={{ padding: "12px 16px", color: "#64748b" }}>#{b.id}</td>
                  <td style={{ padding: "12px 16px", fontWeight: 500, color: "#f8fafc" }}>
                    {b.full_name} {b.username ? `(@${b.username})` : ""}
                  </td>
                  <td style={{ padding: "12px 16px", color: "#cbd5e1" }}>{b.phone_masked || "—"}</td>
                  <td style={{ padding: "12px 16px" }}>
                    <div style={{ display: "flex", gap: "4px" }}>
                      {b.roles.map((r) => (
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
                      ))}
                    </div>
                  </td>
                  <td style={{ padding: "12px 16px", fontWeight: 600, color: "#60a5fa" }}>
                    {b.active_leads_count}
                  </td>
                  <td style={{ padding: "12px 16px", fontWeight: 600, color: "#f59e0b" }}>
                    {b.pending_viewings_count}
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
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
