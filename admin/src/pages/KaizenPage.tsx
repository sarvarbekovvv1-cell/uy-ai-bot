import React, { useEffect, useState } from "react";
import { adminApi } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type {
  KaizenCycleItem,
  KaizenOverview,
  KaizenRecommendationItem,
} from "../types";

export const KaizenPage: React.FC = () => {
  const { hasPerm } = useAuth();
  const canManage = hasPerm("kaizen.manage");
  const canGenerate = hasPerm("kaizen.generate");

  // Filter state
  const [days, setDays] = useState<number>(30);
  const [customRange, setCustomRange] = useState(false);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  // Data state
  const [overview, setOverview] = useState<KaizenOverview | null>(null);
  const [cycles, setCycles] = useState<KaizenCycleItem[]>([]);
  const [recommendations, setRecommendations] = useState<KaizenRecommendationItem[]>([]);
  const [cycleFilter, setCycleFilter] = useState<string>("");

  // UI state
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  // Cycle creation modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createTitle, setCreateTitle] = useState("");
  const [createMetric, setCreateMetric] = useState("overall_win_rate");
  const [createTarget, setCreateTarget] = useState("");
  const [createPlan, setCreatePlan] = useState("");
  const [createDesc, setCreateDesc] = useState("");
  const [linkedRecId, setLinkedRecId] = useState<number | undefined>(undefined);
  const [modalSubmitting, setModalSubmitting] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Active selected cycle modal state
  const [selectedCycle, setSelectedCycle] = useState<KaizenCycleItem | null>(null);
  const [actionNotes, setActionNotes] = useState("");
  const [actionOutcome, setActionOutcome] = useState<"successful" | "partially_successful" | "unsuccessful">("successful");
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = customRange && dateFrom && dateTo
        ? { date_from: dateFrom, date_to: dateTo }
        : { days };

      const [ov, cycRes, recRes] = await Promise.all([
        adminApi.getKaizenOverview(params),
        adminApi.listKaizenCycles({ status: cycleFilter || undefined, page_size: 20 }),
        adminApi.listKaizenRecommendations({ status: "new", page_size: 10 }),
      ]);

      setOverview(ov);
      setCycles(cycRes.items);
      setRecommendations(recRes.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Kaizen ma'lumotlarini yuklashda xatolik");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [days, customRange, dateFrom, dateTo, cycleFilter]);

  const handleGenerate = async () => {
    if (!canGenerate) return;
    setGenerating(true);
    try {
      await adminApi.generateKaizenRecommendations({
        date_from: customRange ? dateFrom : undefined,
        date_to: customRange ? dateTo : undefined,
        use_ai: true,
      });
      fetchData();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Tavsiyalarni shakllantirishda xatolik");
    } finally {
      setGenerating(false);
    }
  };

  const handleReviewRec = async (id: number, action: "accept" | "dismiss") => {
    try {
      await adminApi.reviewKaizenRecommendation(id, action);
      fetchData();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Xatolik yuz berdi");
    }
  };

  const openCreateFromRec = (rec: KaizenRecommendationItem) => {
    setCreateTitle(`Improve: ${rec.title}`);
    setCreateMetric(rec.metric_key);
    setCreatePlan(rec.recommendation_text);
    setCreateDesc(rec.description);
    setLinkedRecId(rec.id);
    setShowCreateModal(true);
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createTitle.trim()) {
      setModalError("Sarlavha kiritilishi shart");
      return;
    }
    setModalSubmitting(true);
    setModalError(null);
    try {
      await adminApi.createKaizenCycle({
        title: createTitle.trim(),
        metric_key: createMetric,
        target_value: createTarget ? parseFloat(createTarget) : undefined,
        description: createDesc.trim() || undefined,
        plan_text: createPlan.trim() || undefined,
        recommendation_id: linkedRecId,
      });
      setShowCreateModal(false);
      // Reset form
      setCreateTitle("");
      setCreateTarget("");
      setCreatePlan("");
      setCreateDesc("");
      setLinkedRecId(undefined);
      fetchData();
    } catch (err: unknown) {
      setModalError(err instanceof Error ? err.message : "PDCA tsiklini yaratishda xatolik");
    } finally {
      setModalSubmitting(false);
    }
  };

  const handleCycleAction = async (action: "plan" | "start" | "check" | "complete" | "cancel") => {
    if (!selectedCycle) return;
    setActionLoading(true);
    setActionError(null);
    try {
      let updated: KaizenCycleItem;
      if (action === "plan") {
        updated = await adminApi.planKaizenCycle(selectedCycle.id, {
          plan_text: actionNotes || selectedCycle.plan_text || "Reja tasdiqlandi",
        });
      } else if (action === "start") {
        updated = await adminApi.startKaizenCycle(selectedCycle.id, actionNotes || undefined);
      } else if (action === "check") {
        const checkRes = await adminApi.checkKaizenCycle(selectedCycle.id, actionNotes || undefined);
        updated = checkRes.cycle;
      } else if (action === "complete") {
        updated = await adminApi.completeKaizenCycle(selectedCycle.id, actionOutcome, actionNotes || undefined);
      } else {
        updated = await adminApi.cancelKaizenCycle(selectedCycle.id, actionNotes || undefined);
      }
      setSelectedCycle(updated);
      setActionNotes("");
      fetchData();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Amalni bajarishda xatolik");
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div style={{ color: "#f8fafc" }}>
      {/* Page Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "24px", flexWrap: "wrap", gap: "16px" }}>
        <div>
          <h1 style={{ fontSize: "1.75rem", fontWeight: 700, margin: 0 }}>
            📈 Kaizen / PDCA Intelligence System
          </h1>
          <p style={{ color: "#94a3b8", fontSize: "0.875rem", marginTop: "4px" }}>
            Operatsion samaradorlik tahlili, deterministik KPI va doimiy yaxshilanish boshqaruvi
          </p>
        </div>

        {/* Date Filter Controls */}
        <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
          {!customRange ? (
            <div style={{ display: "flex", backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "6px", padding: "2px" }}>
              {[7, 30, 90].map((d) => (
                <button
                  key={d}
                  onClick={() => setDays(d)}
                  style={{
                    padding: "6px 12px",
                    border: "none",
                    borderRadius: "4px",
                    backgroundColor: days === d ? "#3b82f6" : "transparent",
                    color: days === d ? "#ffffff" : "#94a3b8",
                    fontSize: "0.8rem",
                    cursor: "pointer",
                    fontWeight: days === d ? 600 : 400,
                  }}
                >
                  {d} kun
                </button>
              ))}
              <button
                onClick={() => setCustomRange(true)}
                style={{
                  padding: "6px 12px",
                  border: "none",
                  borderRadius: "4px",
                  backgroundColor: "transparent",
                  color: "#94a3b8",
                  fontSize: "0.8rem",
                  cursor: "pointer",
                }}
              >
                Sana tanlash
              </button>
            </div>
          ) : (
            <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                style={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "6px", color: "#f8fafc", padding: "6px", fontSize: "0.8rem" }}
              />
              <span style={{ color: "#94a3b8" }}>—</span>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                style={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "6px", color: "#f8fafc", padding: "6px", fontSize: "0.8rem" }}
              />
              <button
                onClick={() => setCustomRange(false)}
                style={{ padding: "6px 10px", backgroundColor: "#334155", border: "none", borderRadius: "6px", color: "#f8fafc", fontSize: "0.8rem", cursor: "pointer" }}
              >
                Bekor
              </button>
            </div>
          )}

          {canGenerate && (
            <button
              onClick={handleGenerate}
              disabled={generating}
              style={{
                padding: "8px 14px",
                backgroundColor: "#8b5cf6",
                color: "#ffffff",
                border: "none",
                borderRadius: "6px",
                fontSize: "0.85rem",
                fontWeight: 600,
                cursor: generating ? "not-allowed" : "pointer",
              }}
            >
              {generating ? "Tahlil qilinmoqda..." : "✨ AI Tahlil & Tavsiya"}
            </button>
          )}

          {canManage && (
            <button
              onClick={() => {
                setLinkedRecId(undefined);
                setShowCreateModal(true);
              }}
              data-testid="create-pdca-btn"
              style={{
                padding: "8px 14px",
                backgroundColor: "#10b981",
                color: "#ffffff",
                border: "none",
                borderRadius: "6px",
                fontSize: "0.85rem",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              + Yangi PDCA
            </button>
          )}

          {loading && (
            <span style={{ fontSize: "0.85rem", color: "#60a5fa" }}>Yuklanmoqda...</span>
          )}
        </div>
      </div>

      {error && (
        <div style={{ padding: "12px 16px", backgroundColor: "rgba(239, 68, 68, 0.15)", border: "1px solid #ef4444", borderRadius: "8px", color: "#fca5a5", marginBottom: "20px" }}>
          Xatolik: {error}
        </div>
      )}

      {/* KPI Cards Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "16px", marginBottom: "28px" }}>
        {/* Win Rate */}
        <div style={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px", padding: "16px" }}>
          <div style={{ fontSize: "0.8rem", color: "#94a3b8" }}>Umumiy Win Rate (Konversiya)</div>
          <div style={{ fontSize: "1.75rem", fontWeight: 700, color: "#10b981", marginTop: "6px" }}>
            {overview?.lead_funnel.conversion_rates.overall_win_rate !== null && overview?.lead_funnel.conversion_rates.overall_win_rate !== undefined
              ? `${overview.lead_funnel.conversion_rates.overall_win_rate}%`
              : "Yetarli emas"}
          </div>
          <div style={{ fontSize: "0.75rem", color: "#64748b", marginTop: "4px" }}>
            {overview?.lead_funnel.won_leads ?? 0} ta yutilgan / {overview?.lead_funnel.total_leads ?? 0} ta jami
          </div>
        </div>

        {/* Response Time */}
        <div style={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px", padding: "16px" }}>
          <div style={{ fontSize: "0.8rem", color: "#94a3b8" }}>Median javob vaqti (Birinchi aloqa)</div>
          <div style={{ fontSize: "1.75rem", fontWeight: 700, color: (overview?.response_time.median_minutes ?? 0) > 30 ? "#ef4444" : "#38bdf8", marginTop: "6px" }}>
            {overview?.response_time.median_minutes !== null && overview?.response_time.median_minutes !== undefined
              ? `${overview.response_time.median_minutes} daqiqa`
              : "Yetarli emas"}
          </div>
          <div style={{ fontSize: "0.75rem", color: "#64748b", marginTop: "4px" }}>
            Tanlanma: {overview?.response_time.sample_size ?? 0} ta lid
          </div>
        </div>

        {/* Viewing Completion */}
        <div style={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px", padding: "16px" }}>
          <div style={{ fontSize: "0.8rem", color: "#94a3b8" }}>Ko'rishlar yakunlanish darajasi</div>
          <div style={{ fontSize: "1.75rem", fontWeight: 700, color: "#a855f7", marginTop: "6px" }}>
            {overview?.viewings.completion_rate !== null && overview?.viewings.completion_rate !== undefined
              ? `${overview.viewings.completion_rate}%`
              : "Yetarli emas"}
          </div>
          <div style={{ fontSize: "0.75rem", color: "#64748b", marginTop: "4px" }}>
            {overview?.viewings.completed ?? 0} ta yakunlangan / {overview?.viewings.total_viewings ?? 0} ta
          </div>
        </div>

        {/* Overdue followups */}
        <div style={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px", padding: "16px" }}>
          <div style={{ fontSize: "0.8rem", color: "#94a3b8" }}>Kechikkan follow-uplar</div>
          <div style={{ fontSize: "1.75rem", fontWeight: 700, color: (overview?.brokers.total_overdue_followups ?? 0) > 0 ? "#f59e0b" : "#10b981", marginTop: "6px" }}>
            {overview?.brokers.total_overdue_followups ?? 0}
          </div>
          <div style={{ fontSize: "0.75rem", color: "#64748b", marginTop: "4px" }}>
            Brokerlar bo'yicha operatsion kechikish
          </div>
        </div>

        {/* CRM Health */}
        <div style={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px", padding: "16px" }}>
          <div style={{ fontSize: "0.8rem", color: "#94a3b8" }}>amoCRM Xatolari (Outbox)</div>
          <div style={{ fontSize: "1.75rem", fontWeight: 700, color: (overview?.crm_health.failed_events ?? 0) > 0 ? "#ef4444" : "#10b981", marginTop: "6px" }}>
            {overview?.crm_health.failed_events ?? 0}
          </div>
          <div style={{ fontSize: "0.75rem", color: "#64748b", marginTop: "4px" }}>
            Doimiy xato: {overview?.crm_health.permanent_failed_events ?? 0} ta
          </div>
        </div>

        {/* Moderation backlog */}
        <div style={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px", padding: "16px" }}>
          <div style={{ fontSize: "0.8rem", color: "#94a3b8" }}>Moderatsiya navbati</div>
          <div style={{ fontSize: "1.75rem", fontWeight: 700, color: (overview?.properties.moderation_backlog ?? 0) > 0 ? "#f59e0b" : "#10b981", marginTop: "6px" }}>
            {overview?.properties.moderation_backlog ?? 0}
          </div>
          <div style={{ fontSize: "0.75rem", color: "#64748b", marginTop: "4px" }}>
            Ko'rib chiqish kutilayotgan e'lonlar
          </div>
        </div>
      </div>

      {/* Recommendations Section */}
      <div style={{ marginBottom: "32px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
          <h2 style={{ fontSize: "1.15rem", fontWeight: 600 }}>💡 Boshqaruv Tavsiyalari ({recommendations.length})</h2>
          <span style={{ fontSize: "0.8rem", color: "#94a3b8" }}>Deterministik qoidalar va AI maslahatchi xulosalari</span>
        </div>

        {recommendations.length === 0 ? (
          <div style={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px", padding: "24px", textAlign: "center", color: "#94a3b8", fontSize: "0.875rem" }}>
            Hozircha yangi tavsiyalar mavjud emas. Yuqoridagi "AI Tahlil & Tavsiya" tugmasi orqali yangilashingiz mumkin.
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "16px" }}>
            {recommendations.map((rec) => (
              <div
                key={rec.id}
                style={{
                  backgroundColor: "#1e293b",
                  border: `1px solid ${rec.severity === "critical" ? "#ef4444" : rec.severity === "warning" ? "#f59e0b" : "#3b82f6"}`,
                  borderRadius: "8px",
                  padding: "16px",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                }}
              >
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                    <span
                      style={{
                        padding: "2px 8px",
                        borderRadius: "10px",
                        fontSize: "0.7rem",
                        fontWeight: 600,
                        backgroundColor: rec.severity === "critical" ? "rgba(239, 68, 68, 0.2)" : rec.severity === "warning" ? "rgba(245, 158, 11, 0.2)" : "rgba(59, 130, 246, 0.2)",
                        color: rec.severity === "critical" ? "#f87171" : rec.severity === "warning" ? "#fbbf24" : "#60a5fa",
                      }}
                    >
                      {rec.severity.toUpperCase()}
                    </span>
                    <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
                      Ishonch: {Math.round(rec.confidence * 100)}%
                    </span>
                  </div>

                  <h3 style={{ fontSize: "0.95rem", fontWeight: 600, marginBottom: "6px" }}>{rec.title}</h3>
                  <p style={{ fontSize: "0.825rem", color: "#cbd5e1", lineHeight: 1.4, marginBottom: "8px" }}>{rec.description}</p>

                  <div style={{ backgroundColor: "#0f172a", borderRadius: "6px", padding: "8px 10px", marginBottom: "12px", borderLeft: "3px solid #10b981" }}>
                    <div style={{ fontSize: "0.75rem", color: "#10b981", fontWeight: 600 }}>TAVSIYA ETILGAN CHORA:</div>
                    <div style={{ fontSize: "0.8rem", color: "#e2e8f0", marginTop: "2px" }}>{rec.recommendation_text}</div>
                  </div>
                </div>

                {canManage && (
                  <div style={{ display: "flex", gap: "8px", borderTop: "1px solid #334155", paddingTop: "10px" }}>
                    <button
                      onClick={() => openCreateFromRec(rec)}
                      style={{
                        flex: 1,
                        padding: "6px",
                        backgroundColor: "#10b981",
                        color: "#ffffff",
                        border: "none",
                        borderRadius: "4px",
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      PDCA ga aylantirish
                    </button>
                    <button
                      onClick={() => handleReviewRec(rec.id, "accept")}
                      style={{
                        padding: "6px 10px",
                        backgroundColor: "#334155",
                        color: "#cbd5e1",
                        border: "none",
                        borderRadius: "4px",
                        fontSize: "0.75rem",
                        cursor: "pointer",
                      }}
                    >
                      Qabul
                    </button>
                    <button
                      onClick={() => handleReviewRec(rec.id, "dismiss")}
                      style={{
                        padding: "6px 10px",
                        backgroundColor: "#1e293b",
                        color: "#64748b",
                        border: "1px solid #334155",
                        borderRadius: "4px",
                        fontSize: "0.75rem",
                        cursor: "pointer",
                      }}
                    >
                      ✕
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* PDCA Cycles Section */}
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", flexWrap: "wrap", gap: "8px" }}>
          <h2 style={{ fontSize: "1.15rem", fontWeight: 600 }}>🔄 PDCA Boshqaruv Tsikllari</h2>
          <div style={{ display: "flex", gap: "6px" }}>
            {["", "active", "planned", "checking", "completed", "cancelled"].map((st) => (
              <button
                key={st}
                onClick={() => setCycleFilter(st)}
                style={{
                  padding: "4px 10px",
                  borderRadius: "4px",
                  border: "none",
                  backgroundColor: cycleFilter === st ? "#3b82f6" : "#1e293b",
                  color: cycleFilter === st ? "#ffffff" : "#94a3b8",
                  fontSize: "0.75rem",
                  cursor: "pointer",
                }}
              >
                {st === "" ? "Barchasi" : st.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {cycles.length === 0 ? (
          <div style={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px", padding: "24px", textAlign: "center", color: "#94a3b8", fontSize: "0.875rem" }}>
            Hozircha PDCA tsikllari mavjud emas. Yuqoridagi "+ Yangi PDCA" tugmasi orqali yangi yaxshilanish tsiklini boshlashingiz mumkin.
          </div>
        ) : (
          <div style={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px", overflow: "hidden" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem", textAlign: "left" }}>
              <thead>
                <tr style={{ backgroundColor: "#0f172a", borderBottom: "1px solid #334155", color: "#94a3b8" }}>
                  <th style={{ padding: "12px 16px" }}>ID</th>
                  <th style={{ padding: "12px 16px" }}>Sarlavha</th>
                  <th style={{ padding: "12px 16px" }}>Metrika</th>
                  <th style={{ padding: "12px 16px" }}>Baseline → Target</th>
                  <th style={{ padding: "12px 16px" }}>Holat</th>
                  <th style={{ padding: "12px 16px" }}>Muallif</th>
                  <th style={{ padding: "12px 16px", textAlign: "right" }}>Amallar</th>
                </tr>
              </thead>
              <tbody>
                {cycles.map((c) => (
                  <tr key={c.id} style={{ borderBottom: "1px solid #334155" }}>
                    <td style={{ padding: "12px 16px", color: "#64748b" }}>#{c.id}</td>
                    <td style={{ padding: "12px 16px", fontWeight: 600 }}>{c.title}</td>
                    <td style={{ padding: "12px 16px", color: "#94a3b8" }}>{c.metric_key}</td>
                    <td style={{ padding: "12px 16px", color: "#cbd5e1" }}>
                      {c.baseline_value ?? "—"} → <strong style={{ color: "#10b981" }}>{c.target_value ?? "—"}</strong> {c.unit}
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      <span
                        style={{
                          padding: "2px 8px",
                          borderRadius: "10px",
                          fontSize: "0.75rem",
                          fontWeight: 600,
                          backgroundColor:
                            c.status === "active"
                              ? "rgba(59, 130, 246, 0.2)"
                              : c.status === "completed"
                              ? "rgba(16, 185, 129, 0.2)"
                              : c.status === "checking"
                              ? "rgba(168, 85, 247, 0.2)"
                              : c.status === "planned"
                              ? "rgba(245, 158, 11, 0.2)"
                              : "rgba(148, 163, 184, 0.2)",
                          color:
                            c.status === "active"
                              ? "#60a5fa"
                              : c.status === "completed"
                              ? "#34d399"
                              : c.status === "checking"
                              ? "#c084fc"
                              : c.status === "planned"
                              ? "#fbbf24"
                              : "#94a3b8",
                        }}
                      >
                        {c.status.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ padding: "12px 16px", color: "#94a3b8" }}>{c.created_by_name || "Staff"}</td>
                    <td style={{ padding: "12px 16px", textAlign: "right" }}>
                      <button
                        onClick={() => setSelectedCycle(c)}
                        data-testid={`inspect-cycle-${c.id}`}
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
                        Boshqarish
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* New PDCA Wizard Modal */}
      {showCreateModal && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, backgroundColor: "rgba(0,0,0,0.7)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: "20px" }}>
          <div style={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "12px", width: "100%", maxWidth: "540px", padding: "24px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h3 style={{ fontSize: "1.2rem", fontWeight: 700, margin: 0 }}>+ Yangi PDCA Yaxshilanish Tsikli</h3>
              <button onClick={() => setShowCreateModal(false)} style={{ background: "transparent", border: "none", color: "#94a3b8", fontSize: "1.2rem", cursor: "pointer" }}>✕</button>
            </div>

            {modalError && (
              <div style={{ padding: "10px", backgroundColor: "rgba(239, 68, 68, 0.2)", color: "#fca5a5", borderRadius: "6px", fontSize: "0.85rem", marginBottom: "16px" }}>
                {modalError}
              </div>
            )}

            <form onSubmit={handleCreateSubmit} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.8rem", color: "#94a3b8", marginBottom: "4px" }}>Tsikl Sarlavhasi *</label>
                <input
                  type="text"
                  required
                  placeholder="Masalan: Birinchi aloqa vaqtini 15 daqiqaga tushirish"
                  value={createTitle}
                  onChange={(e) => setCreateTitle(e.target.value)}
                  style={{ width: "100%", padding: "8px 12px", backgroundColor: "#0f172a", border: "1px solid #334155", borderRadius: "6px", color: "#f8fafc", fontSize: "0.875rem" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.8rem", color: "#94a3b8", marginBottom: "4px" }}>Kuzatiladigan Metrika (KPI) *</label>
                <select
                  value={createMetric}
                  onChange={(e) => setCreateMetric(e.target.value)}
                  style={{ width: "100%", padding: "8px 12px", backgroundColor: "#0f172a", border: "1px solid #334155", borderRadius: "6px", color: "#f8fafc", fontSize: "0.875rem" }}
                >
                  <option value="overall_win_rate">Umumiy Win Rate (%)</option>
                  <option value="median_response_time">Median javob vaqti (daqiqa)</option>
                  <option value="viewing_completion_rate">Ko'rishlar yakunlanish darajasi (%)</option>
                  <option value="viewing_cancellation_rate">Ko'rishlar bekor qilinishi (%)</option>
                  <option value="overdue_followups">Kechikkan follow-uplar soni</option>
                  <option value="crm_failed_events">amoCRM xatoliklari soni</option>
                  <option value="moderation_backlog">Moderatsiya navbati soni</option>
                </select>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.8rem", color: "#94a3b8", marginBottom: "4px" }}>Target (Maqsadli ko'rsatkich)</label>
                <input
                  type="number"
                  step="any"
                  placeholder="Masalan: 25.0"
                  value={createTarget}
                  onChange={(e) => setCreateTarget(e.target.value)}
                  style={{ width: "100%", padding: "8px 12px", backgroundColor: "#0f172a", border: "1px solid #334155", borderRadius: "6px", color: "#f8fafc", fontSize: "0.875rem" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.8rem", color: "#94a3b8", marginBottom: "4px" }}>Harakatlar rejasi (Plan)</label>
                <textarea
                  rows={3}
                  placeholder="Qanday o'zgarishlar va choralar ko'riladi..."
                  value={createPlan}
                  onChange={(e) => setCreatePlan(e.target.value)}
                  style={{ width: "100%", padding: "8px 12px", backgroundColor: "#0f172a", border: "1px solid #334155", borderRadius: "6px", color: "#f8fafc", fontSize: "0.875rem", resize: "vertical" }}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "12px" }}>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  style={{ padding: "8px 16px", backgroundColor: "#334155", color: "#f8fafc", border: "none", borderRadius: "6px", cursor: "pointer", fontSize: "0.875rem" }}
                >
                  Bekor qilish
                </button>
                <button
                  type="submit"
                  disabled={modalSubmitting}
                  style={{ padding: "8px 16px", backgroundColor: "#10b981", color: "#ffffff", border: "none", borderRadius: "6px", cursor: "pointer", fontWeight: 600, fontSize: "0.875rem" }}
                >
                  {modalSubmitting ? "Saqlanmoqda..." : "Yaratish (Baseline lock)"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Cycle Detail & PDCA Action Modal */}
      {selectedCycle && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, backgroundColor: "rgba(0,0,0,0.7)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: "20px" }}>
          <div style={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "12px", width: "100%", maxWidth: "600px", maxHeight: "90vh", overflowY: "auto", padding: "24px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <div>
                <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>PDCA #{selectedCycle.id}</span>
                <h3 style={{ fontSize: "1.25rem", fontWeight: 700, margin: "2px 0 0 0" }}>{selectedCycle.title}</h3>
              </div>
              <button onClick={() => setSelectedCycle(null)} style={{ background: "transparent", border: "none", color: "#94a3b8", fontSize: "1.2rem", cursor: "pointer" }}>✕</button>
            </div>

            {actionError && (
              <div style={{ padding: "10px", backgroundColor: "rgba(239, 68, 68, 0.2)", color: "#fca5a5", borderRadius: "6px", fontSize: "0.85rem", marginBottom: "16px" }}>
                {actionError}
              </div>
            )}

            {/* Stages overview */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "8px", marginBottom: "20px" }}>
              {["PLAN", "DO", "CHECK", "ACT"].map((step, idx) => {
                const isCurrent =
                  (step === "PLAN" && (selectedCycle.status === "draft" || selectedCycle.status === "planned")) ||
                  (step === "DO" && selectedCycle.status === "active") ||
                  (step === "CHECK" && selectedCycle.status === "checking") ||
                  (step === "ACT" && selectedCycle.status === "completed");
                return (
                  <div
                    key={step}
                    style={{
                      textAlign: "center",
                      padding: "8px 4px",
                      borderRadius: "6px",
                      backgroundColor: isCurrent ? "#3b82f6" : "#0f172a",
                      color: isCurrent ? "#ffffff" : "#64748b",
                      fontWeight: 600,
                      fontSize: "0.75rem",
                    }}
                  >
                    {idx + 1}. {step}
                  </div>
                );
              })}
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "10px", fontSize: "0.875rem", marginBottom: "20px" }}>
              <div><strong>Metrika:</strong> {selectedCycle.metric_key}</div>
              <div><strong>Baseline (boshlang'ich):</strong> {selectedCycle.baseline_value ?? "—"} {selectedCycle.unit}</div>
              <div><strong>Target (maqsad):</strong> {selectedCycle.target_value ?? "—"} {selectedCycle.unit}</div>
              {selectedCycle.observed_value !== null && (
                <div><strong>Kuzatilgan natija (Check):</strong> <strong style={{ color: "#10b981" }}>{selectedCycle.observed_value} {selectedCycle.unit}</strong></div>
              )}
              <div><strong>Reja (Plan):</strong> {selectedCycle.plan_text || "—"}</div>
              {selectedCycle.do_text && <div><strong>Ijro eslatmasi (Do):</strong> {selectedCycle.do_text}</div>}
              {selectedCycle.check_text && <div><strong>O'lchov xulosasi (Check):</strong> {selectedCycle.check_text}</div>}
              {selectedCycle.act_text && <div><strong>Yakuniy chora (Act):</strong> {selectedCycle.act_text}</div>}
            </div>

            {/* Action controls */}
            {canManage && selectedCycle.status !== "completed" && selectedCycle.status !== "cancelled" && (
              <div style={{ borderTop: "1px solid #334155", paddingTop: "16px" }}>
                <label style={{ display: "block", fontSize: "0.8rem", color: "#94a3b8", marginBottom: "6px" }}>
                  Qo'shimcha izoh / chora matni:
                </label>
                <textarea
                  rows={2}
                  value={actionNotes}
                  onChange={(e) => setActionNotes(e.target.value)}
                  placeholder="Bosqich bo'yicha ma'lumot yoki qaror..."
                  style={{ width: "100%", padding: "8px 12px", backgroundColor: "#0f172a", border: "1px solid #334155", borderRadius: "6px", color: "#f8fafc", fontSize: "0.875rem", marginBottom: "12px" }}
                />

                {selectedCycle.status === "checking" && (
                  <div style={{ marginBottom: "12px" }}>
                    <label style={{ display: "block", fontSize: "0.8rem", color: "#94a3b8", marginBottom: "4px" }}>Yakuniy natija (Outcome):</label>
                    <select
                      value={actionOutcome}
                      onChange={(e) => setActionOutcome(e.target.value as any)}
                      style={{ width: "100%", padding: "8px 12px", backgroundColor: "#0f172a", border: "1px solid #334155", borderRadius: "6px", color: "#f8fafc", fontSize: "0.875rem" }}
                    >
                      <option value="successful">Muvaffaqiyatli (Successful)</option>
                      <option value="partially_successful">Qisman muvaffaqiyatli</option>
                      <option value="unsuccessful">Kutilgan natija bermadi</option>
                    </select>
                  </div>
                )}

                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                  {selectedCycle.status === "draft" && (
                    <button
                      onClick={() => handleCycleAction("plan")}
                      disabled={actionLoading}
                      style={{ flex: 1, padding: "8px 14px", backgroundColor: "#f59e0b", color: "#ffffff", border: "none", borderRadius: "6px", fontWeight: 600, cursor: "pointer" }}
                    >
                      Rejani tasdiqlash (PLAN)
                    </button>
                  )}
                  {selectedCycle.status === "planned" && (
                    <button
                      onClick={() => handleCycleAction("start")}
                      disabled={actionLoading}
                      style={{ flex: 1, padding: "8px 14px", backgroundColor: "#3b82f6", color: "#ffffff", border: "none", borderRadius: "6px", fontWeight: 600, cursor: "pointer" }}
                    >
                      Ijroni boshlash (DO)
                    </button>
                  )}
                  {selectedCycle.status === "active" && (
                    <button
                      onClick={() => handleCycleAction("check")}
                      disabled={actionLoading}
                      style={{ flex: 1, padding: "8px 14px", backgroundColor: "#8b5cf6", color: "#ffffff", border: "none", borderRadius: "6px", fontWeight: 600, cursor: "pointer" }}
                    >
                      Natijani o'lchash (CHECK)
                    </button>
                  )}
                  {selectedCycle.status === "checking" && (
                    <button
                      onClick={() => handleCycleAction("complete")}
                      disabled={actionLoading}
                      style={{ flex: 1, padding: "8px 14px", backgroundColor: "#10b981", color: "#ffffff", border: "none", borderRadius: "6px", fontWeight: 600, cursor: "pointer" }}
                    >
                      Tsiklni yakunlash (ACT)
                    </button>
                  )}
                  <button
                    onClick={() => handleCycleAction("cancel")}
                    disabled={actionLoading}
                    style={{ padding: "8px 14px", backgroundColor: "#ef4444", color: "#ffffff", border: "none", borderRadius: "6px", cursor: "pointer" }}
                  >
                    Bekor qilish
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
