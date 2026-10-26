import React, { useEffect, useState } from "react";
import { adminApi } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { BrokerWorkloadItem, LeadDetail, LeadItem } from "../types";

const ALL_STAGES = [
  "new",
  "contacted",
  "qualified",
  "viewing_scheduled",
  "negotiation",
  "won",
  "lost",
];

export const LeadsPage: React.FC<{ initialBrokerId?: number }> = ({ initialBrokerId }) => {
  const { hasPerm } = useAuth();
  const canChangeStage = hasPerm("leads.change_stage");
  const canAddNote = hasPerm("leads.add_note");
  const canAssign = hasPerm("leads.assign");

  const [leads, setLeads] = useState<LeadItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [stageFilter, setStageFilter] = useState("");
  const [brokerFilter, setBrokerFilter] = useState<number | undefined>(initialBrokerId);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  // Selected Lead Detail
  const [selectedLead, setSelectedLead] = useState<LeadDetail | null>(null);
  const [brokersList, setBrokersList] = useState<BrokerWorkloadItem[]>([]);
  const [newNoteText, setNewNoteText] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const fetchLeads = async () => {
    setLoading(true);
    try {
      const res = await adminApi.listLeads({
        page,
        page_size: 15,
        stage: stageFilter || undefined,
        broker_id: brokerFilter,
        search: search.trim() || undefined,
      });
      setLeads(res.items);
      setTotal(res.total);
    } catch (err: unknown) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLeads();
  }, [page, stageFilter, brokerFilter]);

  useEffect(() => {
    if (canAssign) {
      adminApi.listBrokers().then(setBrokersList).catch(console.error);
    }
  }, [canAssign]);

  const handleOpenLead = async (id: number) => {
    setActionError(null);
    setNewNoteText("");
    try {
      const detail = await adminApi.getLead(id);
      setSelectedLead(detail);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Lid yuklanmadi");
    }
  };

  const handleStageChange = async (targetStage: string) => {
    if (!selectedLead) return;
    setActionLoading(true);
    setActionError(null);
    try {
      await adminApi.updateLeadStage(selectedLead.id, targetStage);
      const updated = await adminApi.getLead(selectedLead.id);
      setSelectedLead(updated);
      fetchLeads();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Bosqich o'zgartirilmadi.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleAssignBroker = async (brokerId: number) => {
    if (!selectedLead) return;
    setActionLoading(true);
    setActionError(null);
    try {
      await adminApi.assignLead(selectedLead.id, brokerId);
      const updated = await adminApi.getLead(selectedLead.id);
      setSelectedLead(updated);
      fetchLeads();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Broker tayinlanmadi.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedLead || !newNoteText.trim()) return;
    setActionLoading(true);
    setActionError(null);
    try {
      await adminApi.addLeadNote(selectedLead.id, newNoteText.trim());
      setNewNoteText("");
      const updated = await adminApi.getLead(selectedLead.id);
      setSelectedLead(updated);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Eslatma qo'shilmadi.");
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
        <div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 700, color: "#f8fafc" }}>
            Lidlar Pipeline Boshqaruvi
          </h1>
          <p style={{ fontSize: "0.875rem", color: "#94a3b8" }}>
            Jami: {total} ta lid
          </p>
        </div>

        <div style={{ display: "flex", gap: "10px" }}>
          <select
            value={stageFilter}
            onChange={(e) => {
              setStageFilter(e.target.value);
              setPage(1);
            }}
            data-testid="stage-filter"
            style={{
              padding: "8px 12px",
              backgroundColor: "#1e293b",
              border: "1px solid #334155",
              borderRadius: "6px",
              color: "#f8fafc",
              fontSize: "0.875rem",
            }}
          >
            <option value="">Barcha bosqichlar</option>
            {ALL_STAGES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>

          {canAssign && (
            <select
              value={brokerFilter ?? ""}
              onChange={(e) => {
                const val = e.target.value ? Number(e.target.value) : undefined;
                setBrokerFilter(val);
                setPage(1);
              }}
              style={{
                padding: "8px 12px",
                backgroundColor: "#1e293b",
                border: "1px solid #334155",
                borderRadius: "6px",
                color: "#f8fafc",
                fontSize: "0.875rem",
              }}
            >
              <option value="">Barcha brokerlar</option>
              {brokersList.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.full_name}
                </option>
              ))}
            </select>
          )}

          <input
            type="text"
            placeholder="Mijoz ismi yoki tel..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                setPage(1);
                fetchLeads();
              }
            }}
            style={{
              padding: "8px 12px",
              backgroundColor: "#1e293b",
              border: "1px solid #334155",
              borderRadius: "6px",
              color: "#f8fafc",
              fontSize: "0.875rem",
            }}
          />
        </div>
      </div>

      {/* Leads Table */}
      <div style={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px", overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "0.875rem" }}>
          <thead>
            <tr style={{ backgroundColor: "#0f172a", borderBottom: "1px solid #334155", color: "#94a3b8" }}>
              <th style={{ padding: "12px 16px" }}>ID</th>
              <th style={{ padding: "12px 16px" }}>Mijoz</th>
              <th style={{ padding: "12px 16px" }}>Telefon</th>
              <th style={{ padding: "12px 16px" }}>E'lon</th>
              <th style={{ padding: "12px 16px" }}>Bosqich</th>
              <th style={{ padding: "12px 16px" }}>Broker</th>
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
            ) : leads.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ padding: "24px", textAlign: "center", color: "#94a3b8" }}>
                  Lidlar mavjud emas.
                </td>
              </tr>
            ) : (
              leads.map((l) => (
                <tr key={l.id} style={{ borderBottom: "1px solid #334155" }}>
                  <td style={{ padding: "12px 16px", color: "#64748b" }}>#{l.id}</td>
                  <td style={{ padding: "12px 16px", fontWeight: 500, color: "#f8fafc" }}>
                    {l.customer_name}
                  </td>
                  <td style={{ padding: "12px 16px", color: "#cbd5e1" }}>{l.customer_phone || "—"}</td>
                  <td style={{ padding: "12px 16px", color: "#93c5fd" }}>
                    {l.property_title || `Mulk #${l.property_id}`}
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    <span
                      style={{
                        padding: "2px 8px",
                        borderRadius: "12px",
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        backgroundColor:
                          l.stage === "won"
                            ? "rgba(16, 185, 129, 0.2)"
                            : l.stage === "lost"
                            ? "rgba(239, 68, 68, 0.2)"
                            : "rgba(59, 130, 246, 0.2)",
                        color:
                          l.stage === "won"
                            ? "#34d399"
                            : l.stage === "lost"
                            ? "#f87171"
                            : "#93c5fd",
                      }}
                    >
                      {l.stage}
                    </span>
                  </td>
                  <td style={{ padding: "12px 16px", color: "#cbd5e1" }}>
                    {l.broker_name || "Biriktirilmagan"}
                  </td>
                  <td style={{ padding: "12px 16px", textAlign: "right" }}>
                    <button
                      onClick={() => handleOpenLead(l.id)}
                      data-testid={`inspect-lead-${l.id}`}
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
                      Batafsil
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Lead Detail Modal */}
      {selectedLead && (
        <div
          data-testid="lead-detail-modal"
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
              maxWidth: "650px",
              maxHeight: "90vh",
              overflowY: "auto",
              padding: "24px",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h2 style={{ fontSize: "1.25rem", fontWeight: 700, color: "#f8fafc" }}>
                Lid #{selectedLead.id} — {selectedLead.customer_name}
              </h2>
              <button
                onClick={() => setSelectedLead(null)}
                style={{ background: "transparent", border: "none", color: "#94a3b8", fontSize: "1.25rem", cursor: "pointer" }}
              >
                ✕
              </button>
            </div>

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

            <div style={{ display: "flex", flexDirection: "column", gap: "10px", fontSize: "0.9rem", color: "#cbd5e1" }}>
              <div><strong>Telefon:</strong> {selectedLead.customer_phone || "Mavjud emas"}</div>
              <div><strong>Mulk:</strong> {selectedLead.property_title || `#${selectedLead.property_id}`}</div>
              <div><strong>Manba:</strong> {selectedLead.source}</div>
              <div>
                <strong>Hozirgi Bosqich:</strong>{" "}
                <span style={{ color: "#60a5fa", fontWeight: 600 }}>{selectedLead.stage}</span>
              </div>
              <div>
                <strong>Mas'ul Broker:</strong> {selectedLead.broker_name || "Biriktirilmagan"}
              </div>
              {selectedLead.amo_crm_lead_id && (
                <div style={{ color: "#10b981" }}>
                  <strong>amoCRM Lead ID:</strong> #{selectedLead.amo_crm_lead_id} (Sinxronlangan)
                </div>
              )}
            </div>

            {/* Actions: Stage transition & Assign broker */}
            <div style={{ marginTop: "20px", display: "flex", gap: "12px", flexWrap: "wrap", borderTop: "1px solid #334155", paddingTop: "16px" }}>
              {canChangeStage && (
                <div>
                  <label style={{ display: "block", fontSize: "0.8rem", color: "#94a3b8", marginBottom: "4px" }}>
                    Bosqichni o'zgartirish:
                  </label>
                  <select
                    value={selectedLead.stage}
                    disabled={actionLoading}
                    onChange={(e) => handleStageChange(e.target.value)}
                    data-testid="stage-select"
                    style={{
                      padding: "6px 10px",
                      backgroundColor: "#0f172a",
                      border: "1px solid #475569",
                      borderRadius: "6px",
                      color: "#f8fafc",
                      fontSize: "0.85rem",
                    }}
                  >
                    {ALL_STAGES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {canAssign && (
                <div>
                  <label style={{ display: "block", fontSize: "0.8rem", color: "#94a3b8", marginBottom: "4px" }}>
                    Brokerni qayta tayinlash:
                  </label>
                  <select
                    value={selectedLead.broker_id ?? ""}
                    disabled={actionLoading}
                    onChange={(e) => {
                      if (e.target.value) handleAssignBroker(Number(e.target.value));
                    }}
                    data-testid="assign-broker-select"
                    style={{
                      padding: "6px 10px",
                      backgroundColor: "#0f172a",
                      border: "1px solid #475569",
                      borderRadius: "6px",
                      color: "#f8fafc",
                      fontSize: "0.85rem",
                    }}
                  >
                    <option value="">Tanlang...</option>
                    {brokersList.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.full_name} ({b.active_leads_count} faol)
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            {/* Notes Section */}
            <div style={{ marginTop: "24px", borderTop: "1px solid #334155", paddingTop: "16px" }}>
              <h3 style={{ fontSize: "1rem", fontWeight: 600, color: "#f8fafc", marginBottom: "12px" }}>
                Ichki Eslatmalar ({selectedLead.notes.length})
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px", maxHeight: "150px", overflowY: "auto", marginBottom: "12px" }}>
                {selectedLead.notes.map((n) => (
                  <div key={n.id} style={{ padding: "8px", backgroundColor: "#0f172a", borderRadius: "6px", fontSize: "0.85rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", color: "#94a3b8", fontSize: "0.75rem" }}>
                      <span>{n.author_name}</span>
                      <span>{new Date(n.created_at).toLocaleString()}</span>
                    </div>
                    <div style={{ color: "#f8fafc", marginTop: "4px" }}>{n.note_text}</div>
                  </div>
                ))}
              </div>

              {canAddNote && (
                <form onSubmit={handleAddNote} style={{ display: "flex", gap: "8px" }}>
                  <input
                    type="text"
                    value={newNoteText}
                    onChange={(e) => setNewNoteText(e.target.value)}
                    placeholder="Yangi ichki eslatma yozing..."
                    data-testid="note-input"
                    style={{
                      flex: 1,
                      padding: "8px 12px",
                      backgroundColor: "#0f172a",
                      border: "1px solid #475569",
                      borderRadius: "6px",
                      color: "#f8fafc",
                      fontSize: "0.85rem",
                    }}
                  />
                  <button
                    type="submit"
                    disabled={actionLoading || !newNoteText.trim()}
                    data-testid="add-note-btn"
                    style={{
                      padding: "8px 16px",
                      backgroundColor: "#3b82f6",
                      color: "#ffffff",
                      border: "none",
                      borderRadius: "6px",
                      fontSize: "0.85rem",
                      fontWeight: 600,
                      cursor: "pointer",
                    }}
                  >
                    Qo'shish
                  </button>
                </form>
              )}
            </div>

            {/* Timeline Events */}
            <div style={{ marginTop: "24px", borderTop: "1px solid #334155", paddingTop: "16px" }}>
              <h3 style={{ fontSize: "1rem", fontWeight: 600, color: "#f8fafc", marginBottom: "12px" }}>
                Harakatlar Tarixi ({selectedLead.events.length})
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px", maxHeight: "120px", overflowY: "auto", fontSize: "0.8rem", color: "#94a3b8" }}>
                {selectedLead.events.map((e) => (
                  <div key={e.id}>
                    • {new Date(e.created_at).toLocaleTimeString()}: {e.event_type}{" "}
                    {e.from_stage && e.to_stage ? `(${e.from_stage} -> ${e.to_stage})` : ""}{" "}
                    {e.actor_name ? `tomonidan: ${e.actor_name}` : ""}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
