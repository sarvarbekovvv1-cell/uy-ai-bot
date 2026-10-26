import React, { useEffect, useState } from "react";
import { adminApi } from "../api/client";
import type { DashboardKPIs } from "../types";

export const DashboardPage: React.FC<{ onNavigate: (tab: any) => void }> = ({ onNavigate }) => {
  const [kpis, setKpis] = useState<DashboardKPIs | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadKPIs = () => {
    setLoading(true);
    setError(null);
    adminApi
      .getDashboardKPIs()
      .then((data) => setKpis(data))
      .catch((err) => setError(err instanceof Error ? err.message : "KPI yuklanmadi"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadKPIs();
  }, []);

  if (loading) {
    return <div style={{ color: "#94a3b8" }}>Ko'rsatkichlar yuklanmoqda...</div>;
  }

  if (error) {
    return (
      <div style={{ padding: "20px", backgroundColor: "#1e293b", borderRadius: "8px", border: "1px solid #ef4444" }}>
        <div style={{ color: "#ef4444", fontWeight: 600, marginBottom: "8px" }}>Xatolik: {error}</div>
        <p style={{ color: "#94a3b8", fontSize: "0.875rem", marginBottom: "12px" }}>
          Ko'rsatkichlarni yuklab bo'lmadi. Server bilan aloqa mavjudligini tekshiring.
        </p>
        <button
          onClick={loadKPIs}
          style={{
            padding: "8px 16px",
            backgroundColor: "#3b82f6",
            color: "#ffffff",
            border: "none",
            borderRadius: "6px",
            fontSize: "0.875rem",
            cursor: "pointer",
          }}
        >
          Qayta urinish
        </button>
      </div>
    );
  }

  const cards = [
    {
      title: "Kutilayotgan moderatsiya",
      value: kpis?.pending_moderation_properties ?? 0,
      color: "#f59e0b",
      onClick: () => onNavigate("properties"),
    },
    {
      title: "Tasdiqlangan e'lonlar",
      value: kpis?.approved_properties ?? 0,
      color: "#10b981",
      onClick: () => onNavigate("properties"),
    },
    {
      title: "Faol lidlar",
      value: kpis?.active_leads ?? 0,
      color: "#3b82f6",
      onClick: () => onNavigate("leads"),
    },
    {
      title: "Yutilgan bitimlar (Won)",
      value: kpis?.won_leads ?? 0,
      color: "#8b5cf6",
      onClick: () => onNavigate("leads"),
    },
    {
      title: "Kutilayotgan ko'rishlar",
      value: kpis?.pending_viewings ?? 0,
      color: "#06b6d4",
      onClick: () => onNavigate("viewings"),
    },
    {
      title: "amoCRM xatolari (Failed)",
      value: kpis?.crm_failed_events ?? 0,
      color: (kpis?.crm_failed_events ?? 0) > 0 ? "#ef4444" : "#10b981",
      onClick: () => onNavigate("crm"),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: "24px" }}>
        <h1 style={{ fontSize: "1.5rem", fontWeight: 700, color: "#f8fafc" }}>
          Tizim Boshqaruvi va Ko'rsatkichlar
        </h1>
        <p style={{ fontSize: "0.875rem", color: "#94a3b8", marginTop: "4px" }}>
          Real vaqtdagi operatsion monitoring
        </p>
      </div>

      <div
        data-testid="kpi-grid"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
          gap: "16px",
          marginBottom: "32px",
        }}
      >
        {cards.map((c, idx) => (
          <div
            key={idx}
            onClick={c.onClick}
            style={{
              backgroundColor: "#1e293b",
              border: "1px solid #334155",
              borderRadius: "10px",
              padding: "20px",
              cursor: "pointer",
              transition: "transform 0.15s ease, border-color 0.15s ease",
            }}
          >
            <div style={{ fontSize: "0.8rem", fontWeight: 500, color: "#94a3b8" }}>{c.title}</div>
            <div style={{ fontSize: "2rem", fontWeight: 700, color: c.color, marginTop: "8px" }}>
              {c.value}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
