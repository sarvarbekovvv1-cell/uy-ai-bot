import React, { useEffect, useState } from "react";
import { adminApi } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { ViewingItem } from "../types";

const OUTCOMES = [
  { value: "interested", label: "Mijozga yoqdi (Interested)" },
  { value: "not_interested", label: "Mijozga yoqmadi (Not Interested)" },
  { value: "reschedule_requested", label: "Qayta rejalashtirish so'raldi" },
  { value: "no_show", label: "Mijoz kelmadi (No show)" },
];

export const ViewingsPage: React.FC = () => {
  const { hasPerm } = useAuth();
  const canManage = hasPerm("viewings.manage");

  const [viewings, setViewings] = useState<ViewingItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("pending");
  const [loading, setLoading] = useState(true);

  // Complete / Cancel Modal
  const [activeViewing, setActiveViewing] = useState<ViewingItem | null>(null);
  const [modalMode, setModalMode] = useState<"complete" | "reject" | "cancel" | null>(null);
  const [selectedOutcome, setSelectedOutcome] = useState("interested");
  const [reasonText, setReasonText] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const fetchViewings = async () => {
    setLoading(true);
    try {
      const res = await adminApi.listViewings({
        page,
        page_size: 15,
        status: statusFilter || undefined,
      });
      setViewings(res.items);
      setTotal(res.total);
    } catch (err: unknown) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchViewings();
  }, [page, statusFilter]);

  const handleAccept = async (id: number) => {
    try {
      await adminApi.acceptViewing(id);
      fetchViewings();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Qabul qilib bo'lmadi.");
    }
  };

  const handleModalSubmit = async () => {
    if (!activeViewing || !modalMode) return;
    setActionLoading(true);
    setActionError(null);
    try {
      if (modalMode === "complete") {
        await adminApi.completeViewing(activeViewing.id, selectedOutcome, reasonText);
      } else if (modalMode === "reject") {
        await adminApi.rejectViewing(activeViewing.id, reasonText || "Rad etildi");
      } else if (modalMode === "cancel") {
        await adminApi.cancelViewing(activeViewing.id, reasonText || "Bekor qilindi");
      }
      setActiveViewing(null);
      setModalMode(null);
      fetchViewings();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Amalni bajarib bo'lmadi.");
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
        <div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 700, color: "#f8fafc" }}>
            Ko'rish So'rovlari Boshqaruvi
          </h1>
          <p style={{ fontSize: "0.875rem", color: "#94a3b8" }}>
            Jami: {total} ta ko'rish so'rovi
          </p>
        </div>

        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          data-testid="viewing-status-filter"
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
          <option value="pending">Kutilmoqda (Pending)</option>
          <option value="accepted">Qabul qilingan</option>
          <option value="completed">Yakunlangan</option>
          <option value="rejected">Rad etilgan</option>
          <option value="cancelled">Bekor qilingan</option>
        </select>
      </div>

      <div style={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px", overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "0.875rem" }}>
          <thead>
            <tr style={{ backgroundColor: "#0f172a", borderBottom: "1px solid #334155", color: "#94a3b8" }}>
              <th style={{ padding: "12px 16px" }}>ID</th>
              <th style={{ padding: "12px 16px" }}>Mulk</th>
              <th style={{ padding: "12px 16px" }}>Mijoz</th>
              <th style={{ padding: "12px 16px" }}>Vaqt</th>
              <th style={{ padding: "12px 16px" }}>Turi</th>
              <th style={{ padding: "12px 16px" }}>Holat</th>
              <th style={{ padding: "12px 16px", textAlign: "right" }}>Amallar</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} style={{ padding: "24px", textAlign: "center", color: "#94a3b8" }}>
                  Yuklanmoqda...
                </td>
              </tr>
            ) : viewings.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ padding: "24px", textAlign: "center", color: "#94a3b8" }}>
                  Ko'rish so'rovlari mavjud emas.
                </td>
              </tr>
            ) : (
              viewings.map((v) => (
                <tr key={v.id} style={{ borderBottom: "1px solid #334155" }}>
                  <td style={{ padding: "12px 16px", color: "#64748b" }}>#{v.id}</td>
                  <td style={{ padding: "12px 16px", fontWeight: 500, color: "#f8fafc" }}>
                    {v.property_title || `Mulk #${v.property_id}`}
                  </td>
                  <td style={{ padding: "12px 16px", color: "#cbd5e1" }}>{v.customer_name}</td>
                  <td style={{ padding: "12px 16px", color: "#cbd5e1" }}>
                    {v.preferred_date || "—"} {v.preferred_time || ""}
                  </td>
                  <td style={{ padding: "12px 16px", color: "#94a3b8" }}>{v.request_type}</td>
                  <td style={{ padding: "12px 16px" }}>
                    <span
                      style={{
                        padding: "2px 8px",
                        borderRadius: "12px",
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        backgroundColor:
                          v.status === "completed"
                            ? "rgba(16, 185, 129, 0.2)"
                            : v.status === "accepted"
                            ? "rgba(59, 130, 246, 0.2)"
                            : v.status === "pending"
                            ? "rgba(245, 158, 11, 0.2)"
                            : "rgba(239, 68, 68, 0.2)",
                        color:
                          v.status === "completed"
                            ? "#34d399"
                            : v.status === "accepted"
                            ? "#93c5fd"
                            : v.status === "pending"
                            ? "#fbbf24"
                            : "#f87171",
                      }}
                    >
                      {v.status}
                    </span>
                  </td>
                  <td style={{ padding: "12px 16px", textAlign: "right" }}>
                    {canManage && (
                      <div style={{ display: "flex", gap: "6px", justifyContent: "flex-end" }}>
                        {v.status === "pending" && (
                          <>
                            <button
                              onClick={() => handleAccept(v.id)}
                              style={{
                                padding: "4px 8px",
                                backgroundColor: "#10b981",
                                color: "#ffffff",
                                border: "none",
                                borderRadius: "4px",
                                fontSize: "0.75rem",
                                cursor: "pointer",
                              }}
                            >
                              Qabul
                            </button>
                            <button
                              onClick={() => {
                                setActiveViewing(v);
                                setModalMode("reject");
                                setReasonText("");
                              }}
                              style={{
                                padding: "4px 8px",
                                backgroundColor: "#ef4444",
                                color: "#ffffff",
                                border: "none",
                                borderRadius: "4px",
                                fontSize: "0.75rem",
                                cursor: "pointer",
                              }}
                            >
                              Rad
                            </button>
                          </>
                        )}
                        {v.status === "accepted" && (
                          <button
                            onClick={() => {
                              setActiveViewing(v);
                              setModalMode("complete");
                              setSelectedOutcome("interested");
                              setReasonText("");
                            }}
                            data-testid={`complete-viewing-${v.id}`}
                            style={{
                              padding: "4px 8px",
                              backgroundColor: "#3b82f6",
                              color: "#ffffff",
                              border: "none",
                              borderRadius: "4px",
                              fontSize: "0.75rem",
                              cursor: "pointer",
                            }}
                          >
                            Yakunlash
                          </button>
                        )}
                      </div>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Action Modal */}
      {activeViewing && modalMode && (
        <div
          data-testid="viewing-action-modal"
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
              maxWidth: "480px",
              padding: "24px",
            }}
          >
            <h2 style={{ fontSize: "1.2rem", fontWeight: 700, color: "#f8fafc", marginBottom: "16px" }}>
              {modalMode === "complete"
                ? "Ko'rishni yakunlash"
                : modalMode === "reject"
                ? "Ko'rishni rad etish"
                : "Ko'rishni bekor qilish"}
            </h2>

            {actionError && (
              <div
                style={{
                  padding: "10px",
                  backgroundColor: "rgba(239, 68, 68, 0.2)",
                  color: "#fca5a5",
                  borderRadius: "6px",
                  fontSize: "0.85rem",
                  marginBottom: "16px",
                }}
              >
                {actionError}
              </div>
            )}

            {modalMode === "complete" && (
              <div style={{ marginBottom: "16px" }}>
                <label style={{ display: "block", fontSize: "0.85rem", color: "#cbd5e1", marginBottom: "6px" }}>
                  Ko'rish natijasi:
                </label>
                <select
                  value={selectedOutcome}
                  onChange={(e) => setSelectedOutcome(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    backgroundColor: "#0f172a",
                    border: "1px solid #475569",
                    borderRadius: "6px",
                    color: "#f8fafc",
                    fontSize: "0.85rem",
                  }}
                >
                  {OUTCOMES.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div style={{ marginBottom: "20px" }}>
              <label style={{ display: "block", fontSize: "0.85rem", color: "#cbd5e1", marginBottom: "6px" }}>
                Izoh / Sabab:
              </label>
              <textarea
                value={reasonText}
                onChange={(e) => setReasonText(e.target.value)}
                rows={3}
                placeholder="Qo'shimcha tafsilotlar..."
                style={{
                  width: "100%",
                  padding: "8px",
                  backgroundColor: "#0f172a",
                  border: "1px solid #475569",
                  borderRadius: "6px",
                  color: "#f8fafc",
                  fontSize: "0.85rem",
                }}
              />
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
              <button
                onClick={() => {
                  setActiveViewing(null);
                  setModalMode(null);
                }}
                disabled={actionLoading}
                style={{
                  padding: "8px 16px",
                  backgroundColor: "transparent",
                  color: "#94a3b8",
                  border: "1px solid #475569",
                  borderRadius: "6px",
                  cursor: "pointer",
                }}
              >
                Bekor qilish
              </button>
              <button
                onClick={handleModalSubmit}
                disabled={actionLoading}
                data-testid="submit-viewing-action"
                style={{
                  padding: "8px 16px",
                  backgroundColor: "#3b82f6",
                  color: "#ffffff",
                  border: "none",
                  borderRadius: "6px",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                {actionLoading ? "Bajarilmoqda..." : "Tasdiqlash"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
