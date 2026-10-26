import React, { useEffect, useState } from "react";
import { adminApi } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { PropertyDetail, PropertyListItem } from "../types";

export const PropertiesPage: React.FC = () => {
  const { hasPerm } = useAuth();
  const canModerate = hasPerm("properties.moderate");

  const [properties, setProperties] = useState<PropertyListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>("pending_approval");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [selectedProperty, setSelectedProperty] = useState<PropertyDetail | null>(null);

  // Moderation state
  const [rejectReason, setRejectReason] = useState("");
  const [isRejecting, setIsRejecting] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const fetchProperties = async () => {
    setLoading(true);
    try {
      const res = await adminApi.listProperties({
        page,
        page_size: 15,
        status: statusFilter || undefined,
        search: search.trim() || undefined,
      });
      setProperties(res.items);
      setTotal(res.total);
    } catch (err: unknown) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProperties();
  }, [page, statusFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchProperties();
  };

  const handleOpenDetail = async (propId: number) => {
    setActionError(null);
    setIsRejecting(false);
    setRejectReason("");
    try {
      const detail = await adminApi.getProperty(propId);
      setSelectedProperty(detail);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "E'lon yuklanmadi");
    }
  };

  const handleApprove = async () => {
    if (!selectedProperty) return;
    setActionLoading(true);
    setActionError(null);
    try {
      await adminApi.approveProperty(selectedProperty.id);
      setSelectedProperty(null);
      fetchProperties();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Tasdiqlashda xatolik");
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!selectedProperty) return;
    if (rejectReason.trim().length < 5) {
      setActionError("Rad etish sababi kamida 5 ta belgidan iborat bo'lishi kerak.");
      return;
    }
    setActionLoading(true);
    setActionError(null);
    try {
      await adminApi.rejectProperty(selectedProperty.id, rejectReason.trim());
      setSelectedProperty(null);
      fetchProperties();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Rad etishda xatolik");
    } finally {
      setActionLoading(false);
    }
  };

  const handleArchive = async () => {
    if (!selectedProperty) return;
    if (!confirm("Haqiqatan ham bu e'lonni arxivlamoqchimisiz?")) return;
    setActionLoading(true);
    setActionError(null);
    try {
      await adminApi.archiveProperty(selectedProperty.id);
      setSelectedProperty(null);
      fetchProperties();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Arxivlashda xatolik");
    } finally {
      setActionLoading(false);
    }
  };

  const formatPrice = (price: number, currency: string) => {
    return `${Number(price).toLocaleString()} ${currency}`;
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
        <div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 700, color: "#f8fafc" }}>
            E'lonlar va Moderatsiya
          </h1>
          <p style={{ fontSize: "0.875rem", color: "#94a3b8" }}>
            Jami: {total} ta e'lon topildi
          </p>
        </div>

        {/* Filters */}
        <div style={{ display: "flex", gap: "10px" }}>
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            data-testid="status-filter"
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
            <option value="pending_approval">Moderatsiyada (Kutilmoqda)</option>
            <option value="approved">Tasdiqlangan</option>
            <option value="rejected">Rad etilgan</option>
            <option value="archived">Arxivlangan</option>
          </select>

          <form onSubmit={handleSearchSubmit} style={{ display: "flex", gap: "6px" }}>
            <input
              type="text"
              placeholder="Qidiruv (manzil, sarlavha)..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                padding: "8px 12px",
                backgroundColor: "#1e293b",
                border: "1px solid #334155",
                borderRadius: "6px",
                color: "#f8fafc",
                fontSize: "0.875rem",
              }}
            />
            <button
              type="submit"
              style={{
                padding: "8px 14px",
                backgroundColor: "#3b82f6",
                color: "#ffffff",
                border: "none",
                borderRadius: "6px",
                fontSize: "0.875rem",
                cursor: "pointer",
              }}
            >
              Izlash
            </button>
          </form>
        </div>
      </div>

      {/* Properties Table */}
      <div style={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px", overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "0.875rem" }}>
          <thead>
            <tr style={{ backgroundColor: "#0f172a", borderBottom: "1px solid #334155", color: "#94a3b8" }}>
              <th style={{ padding: "12px 16px" }}>ID</th>
              <th style={{ padding: "12px 16px" }}>Sarlavha</th>
              <th style={{ padding: "12px 16px" }}>Tuman</th>
              <th style={{ padding: "12px 16px" }}>Xonalar</th>
              <th style={{ padding: "12px 16px" }}>Maydon</th>
              <th style={{ padding: "12px 16px" }}>Narx</th>
              <th style={{ padding: "12px 16px" }}>Holat</th>
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
            ) : properties.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ padding: "24px", textAlign: "center", color: "#94a3b8" }}>
                  E'lonlar topilmadi.
                </td>
              </tr>
            ) : (
              properties.map((p) => (
                <tr
                  key={p.id}
                  style={{ borderBottom: "1px solid #334155", transition: "background-color 0.1s ease" }}
                >
                  <td style={{ padding: "12px 16px", color: "#64748b" }}>#{p.id}</td>
                  <td style={{ padding: "12px 16px", fontWeight: 500, color: "#f8fafc" }}>
                    {p.title || `${p.district} ${p.property_type}`}
                  </td>
                  <td style={{ padding: "12px 16px", color: "#cbd5e1" }}>{p.district}</td>
                  <td style={{ padding: "12px 16px", color: "#cbd5e1" }}>{p.rooms}</td>
                  <td style={{ padding: "12px 16px", color: "#cbd5e1" }}>{p.total_area} m²</td>
                  <td style={{ padding: "12px 16px", fontWeight: 600, color: "#10b981" }}>
                    {formatPrice(p.price, p.currency)}
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    <span
                      style={{
                        padding: "2px 8px",
                        borderRadius: "12px",
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        backgroundColor:
                          p.status === "approved"
                            ? "rgba(16, 185, 129, 0.2)"
                            : p.status === "pending_approval"
                            ? "rgba(245, 158, 11, 0.2)"
                            : "rgba(239, 68, 68, 0.2)",
                        color:
                          p.status === "approved"
                            ? "#34d399"
                            : p.status === "pending_approval"
                            ? "#fbbf24"
                            : "#f87171",
                      }}
                    >
                      {p.status}
                    </span>
                  </td>
                  <td style={{ padding: "12px 16px", textAlign: "right" }}>
                    <button
                      onClick={() => handleOpenDetail(p.id)}
                      data-testid={`inspect-property-${p.id}`}
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
                      Ko'rish
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Controls */}
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
          disabled={properties.length < 15}
          onClick={() => setPage(page + 1)}
          style={{
            padding: "6px 12px",
            backgroundColor: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "4px",
            color: "#f8fafc",
            cursor: properties.length < 15 ? "not-allowed" : "pointer",
          }}
        >
          Keyingi
        </button>
      </div>

      {/* Property Detail Drawer / Modal */}
      {selectedProperty && (
        <div
          data-testid="property-detail-modal"
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
              maxWidth: "600px",
              maxHeight: "90vh",
              overflowY: "auto",
              padding: "24px",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h2 style={{ fontSize: "1.25rem", fontWeight: 700, color: "#f8fafc" }}>
                E'lon #{selectedProperty.id} ma'lumotlari
              </h2>
              <button
                onClick={() => setSelectedProperty(null)}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "#94a3b8",
                  fontSize: "1.25rem",
                  cursor: "pointer",
                }}
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
              <div><strong>Sarlavha:</strong> {selectedProperty.title || "—"}</div>
              <div><strong>Turi:</strong> {selectedProperty.property_type} ({selectedProperty.listing_type})</div>
              <div><strong>Manzil:</strong> {selectedProperty.region}, {selectedProperty.district}, {selectedProperty.address}</div>
              <div><strong>Narx:</strong> {formatPrice(selectedProperty.price, selectedProperty.currency)}</div>
              <div><strong>Xonalar va Maydon:</strong> {selectedProperty.rooms} xona, {selectedProperty.total_area} m²</div>
              <div><strong>Ta'mir holati:</strong> {selectedProperty.condition}</div>
              <div><strong>Kadastr:</strong> {selectedProperty.cadastre_status}</div>
              <div><strong>Tavsif:</strong> {selectedProperty.description || "Yo'q"}</div>

              {selectedProperty.owner && (
                <div style={{ marginTop: "10px", padding: "10px", backgroundColor: "#0f172a", borderRadius: "6px" }}>
                  <strong>Mulkdor ma'lumoti:</strong> {selectedProperty.owner.name}
                  {selectedProperty.owner.phone && (
                    <div style={{ color: "#38bdf8", marginTop: "4px" }}>Tel: {selectedProperty.owner.phone}</div>
                  )}
                </div>
              )}
            </div>

            {/* Moderation Controls */}
            {canModerate && (
              <div style={{ marginTop: "24px", borderTop: "1px solid #334155", paddingTop: "16px" }}>
                {!isRejecting ? (
                  <div style={{ display: "flex", gap: "10px" }}>
                    <button
                      onClick={handleApprove}
                      disabled={actionLoading}
                      data-testid="approve-property-btn"
                      style={{
                        flex: 1,
                        padding: "10px",
                        backgroundColor: "#10b981",
                        color: "#ffffff",
                        border: "none",
                        borderRadius: "6px",
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      Tasdiqlash (Approve)
                    </button>
                    <button
                      onClick={() => setIsRejecting(true)}
                      disabled={actionLoading}
                      data-testid="reject-prompt-btn"
                      style={{
                        flex: 1,
                        padding: "10px",
                        backgroundColor: "#ef4444",
                        color: "#ffffff",
                        border: "none",
                        borderRadius: "6px",
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      Rad etish (Reject)
                    </button>
                    <button
                      onClick={handleArchive}
                      disabled={actionLoading}
                      style={{
                        padding: "10px 16px",
                        backgroundColor: "#64748b",
                        color: "#ffffff",
                        border: "none",
                        borderRadius: "6px",
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      Arxivlash
                    </button>
                  </div>
                ) : (
                  <div>
                    <label style={{ display: "block", fontSize: "0.85rem", color: "#cbd5e1", marginBottom: "6px" }}>
                      Rad etish sababini kiriting (kamida 5 belgi):
                    </label>
                    <textarea
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      data-testid="reject-reason-input"
                      rows={3}
                      placeholder="Masalan: Kadastr hujjati yuklanmagan yoki narx bozor talabiga mos emas"
                      style={{
                        width: "100%",
                        padding: "8px",
                        backgroundColor: "#0f172a",
                        border: "1px solid #475569",
                        borderRadius: "6px",
                        color: "#f8fafc",
                        fontSize: "0.85rem",
                        marginBottom: "10px",
                      }}
                    />
                    <div style={{ display: "flex", gap: "8px" }}>
                      <button
                        onClick={handleReject}
                        disabled={actionLoading}
                        data-testid="confirm-reject-btn"
                        style={{
                          padding: "8px 16px",
                          backgroundColor: "#ef4444",
                          color: "#ffffff",
                          border: "none",
                          borderRadius: "6px",
                          fontWeight: 600,
                          cursor: "pointer",
                        }}
                      >
                        Tasdiqlash va Rad etish
                      </button>
                      <button
                        onClick={() => setIsRejecting(false)}
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
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
