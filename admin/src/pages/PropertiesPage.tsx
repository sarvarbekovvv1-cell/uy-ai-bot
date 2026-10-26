import React, { useEffect, useState } from "react";
import { adminApi } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { PropertyDetail, PropertyListItem } from "../types";

export const PropertiesPage: React.FC = () => {
  const { hasPerm } = useAuth();
  const canModerate = hasPerm("properties.moderate");
  const canCreate = hasPerm("properties.create");

  const [properties, setProperties] = useState<PropertyListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedProperty, setSelectedProperty] = useState<PropertyDetail | null>(null);

  // Property Creation Modal State
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [formListingType, setFormListingType] = useState<"sale" | "rent">("sale");
  const [formPropertyType, setFormPropertyType] = useState<"apartment" | "house" | "commercial" | "land">("apartment");
  const [formTitle, setFormTitle] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formRegion, setFormRegion] = useState("Toshkent");
  const [formDistrict, setFormDistrict] = useState("Chilonzor");
  const [formAddress, setFormAddress] = useState("");
  const [formRooms, setFormRooms] = useState("3");
  const [formTotalArea, setFormTotalArea] = useState("75");
  const [formLivingArea, setFormLivingArea] = useState("");
  const [formFloor, setFormFloor] = useState("4");
  const [formTotalFloors, setFormTotalFloors] = useState("9");
  const [formCondition, setFormCondition] = useState<"new" | "renovated" | "needs_renovation" | "shell">("renovated");
  const [formConstructionType, setFormConstructionType] = useState("G'isht");
  const [formHasFurniture, setFormHasFurniture] = useState(false);
  const [formCadastreStatus, setFormCadastreStatus] = useState<"available" | "not_available" | "in_process" | "unknown">("available");
  const [formPrice, setFormPrice] = useState("");
  const [formCurrency, setFormCurrency] = useState<"USD" | "UZS">("USD");
  const [formNegotiable, setFormNegotiable] = useState(false);
  const [formAutoApprove, setFormAutoApprove] = useState(false);

  // Photo uploads
  const [uploadedPhotos, setUploadedPhotos] = useState<{ id: string; url: string; name: string }[]>([]);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const TASHKENT_DISTRICTS = [
    "Chilonzor",
    "Yunusobod",
    "Mirzo Ulug'bek",
    "Yakkasaroy",
    "Mirobod",
    "Shayxontohur",
    "Olmazor",
    "Uchtepa",
    "Sergeli",
    "Yangi Hayot",
    "Bektemir",
    "Yashnobod",
  ];

  const resetCreateForm = () => {
    setFormListingType("sale");
    setFormPropertyType("apartment");
    setFormTitle("");
    setFormDescription("");
    setFormRegion("Toshkent");
    setFormDistrict("Chilonzor");
    setFormAddress("");
    setFormRooms("3");
    setFormTotalArea("75");
    setFormLivingArea("");
    setFormFloor("4");
    setFormTotalFloors("9");
    setFormCondition("renovated");
    setFormConstructionType("G'isht");
    setFormHasFurniture(false);
    setFormCadastreStatus("available");
    setFormPrice("");
    setFormCurrency("USD");
    setFormNegotiable(false);
    setFormAutoApprove(false);
    setUploadedPhotos([]);
    setCreateError(null);
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setUploadLoading(true);
    setCreateError(null);
    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        if (file.size > 5 * 1024 * 1024) {
          throw new Error(`"${file.name}" fayl hajmi 5MB dan oshmasligi kerak.`);
        }
        const res = await adminApi.uploadPropertyMedia(file);
        setUploadedPhotos((prev) => [
          ...prev,
          { id: res.media_unique_id, url: res.safe_url, name: file.name },
        ]);
      }
    } catch (err: unknown) {
      setCreateError(err instanceof Error ? err.message : "Rasm yuklashda xatolik yuz berdi");
    } finally {
      setUploadLoading(false);
      e.target.value = "";
    }
  };

  const handleRemovePhoto = (id: string) => {
    setUploadedPhotos((prev) => prev.filter((p) => p.id !== id));
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError(null);

    const priceNum = Number(formPrice);
    if (!priceNum || priceNum <= 0) {
      setCreateError("Narx musbat son bo'lishi kerak.");
      return;
    }
    const roomsNum = Number(formRooms);
    if (!roomsNum || roomsNum < 1 || roomsNum > 30) {
      setCreateError("Xonalar soni 1 dan 30 gacha bo'lishi kerak.");
      return;
    }
    const totalAreaNum = Number(formTotalArea);
    if (!totalAreaNum || totalAreaNum < 5) {
      setCreateError("Umumiy maydon kamida 5 m² bo'lishi kerak.");
      return;
    }
    if (!formAddress.trim()) {
      setCreateError("Manzil kiritilishi shart.");
      return;
    }

    setCreateSubmitting(true);
    try {
      await adminApi.createProperty({
        listing_type: formListingType,
        property_type: formPropertyType,
        title: formTitle.trim() || undefined,
        description: formDescription.trim() || undefined,
        region: formRegion.trim(),
        district: formDistrict.trim(),
        address: formAddress.trim(),
        rooms: roomsNum,
        total_area: totalAreaNum,
        living_area: formLivingArea ? Number(formLivingArea) : undefined,
        floor: formFloor ? Number(formFloor) : undefined,
        total_floors: formTotalFloors ? Number(formTotalFloors) : undefined,
        condition: formCondition,
        construction_type: formConstructionType.trim() || undefined,
        has_furniture: formHasFurniture,
        cadastre_status: formCadastreStatus,
        price: priceNum,
        currency: formCurrency,
        negotiable: formNegotiable,
        auto_approve: canModerate ? formAutoApprove : false,
        media_unique_ids: uploadedPhotos.map((p) => p.id),
      });

      setShowCreateModal(false);
      resetCreateForm();
      fetchProperties();
    } catch (err: unknown) {
      setCreateError(err instanceof Error ? err.message : "E'lon yaratishda xatolik yuz berdi");
    } finally {
      setCreateSubmitting(false);
    }
  };

  // Moderation state
  const [rejectReason, setRejectReason] = useState("");
  const [isRejecting, setIsRejecting] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const fetchProperties = async () => {
    setLoading(true);
    setLoadError(null);
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
      setLoadError(err instanceof Error ? err.message : "E'lonlarni yuklab bo'lmadi");
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
        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          {canCreate && (
            <button
              onClick={() => {
                resetCreateForm();
                setShowCreateModal(true);
              }}
              data-testid="open-create-property-btn"
              style={{
                padding: "8px 16px",
                backgroundColor: "#10b981",
                color: "#ffffff",
                border: "none",
                borderRadius: "6px",
                fontSize: "0.875rem",
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "6px",
              }}
            >
              <span>+</span>
              <span>E'lon qo'shish</span>
            </button>
          )}

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
            <option value="submitted">Yuborilgan (Submitted)</option>
            <option value="under_review">Ko'rib chiqilmoqda (Under Review)</option>
            <option value="approved">Tasdiqlangan</option>
            <option value="rejected">Rad etilgan</option>
            <option value="archived">Arxivlangan</option>
            <option value="draft">Qoralama</option>
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

      {/* Error banner */}
      {loadError && (
        <div
          style={{
            padding: "12px 16px",
            backgroundColor: "rgba(239, 68, 68, 0.15)",
            border: "1px solid #ef4444",
            borderRadius: "8px",
            color: "#fca5a5",
            marginBottom: "16px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span>Xatolik: {loadError}</span>
          <button
            onClick={fetchProperties}
            style={{
              padding: "4px 10px",
              backgroundColor: "#ef4444",
              color: "#ffffff",
              border: "none",
              borderRadius: "4px",
              fontSize: "0.8rem",
              cursor: "pointer",
            }}
          >
            Qayta urinish
          </button>
        </div>
      )}

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
                    {p.title || (p.district ? `${p.district} ${p.property_type}` : `E'lon #${p.id}`)}
                  </td>
                  <td style={{ padding: "12px 16px", color: "#cbd5e1" }}>{p.district || "—"}</td>
                  <td style={{ padding: "12px 16px", color: "#cbd5e1" }}>{p.rooms ?? "—"}</td>
                  <td style={{ padding: "12px 16px", color: "#cbd5e1" }}>{p.total_area ? `${p.total_area} m²` : "—"}</td>
                  <td style={{ padding: "12px 16px", fontWeight: 600, color: "#10b981" }}>
                    {p.price ? formatPrice(p.price, p.currency) : "—"}
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
                            : p.status === "pending_approval" || p.status === "submitted" || p.status === "under_review"
                            ? "rgba(245, 158, 11, 0.2)"
                            : p.status === "rejected"
                            ? "rgba(239, 68, 68, 0.2)"
                            : "rgba(148, 163, 184, 0.2)",
                        color:
                          p.status === "approved"
                            ? "#34d399"
                            : p.status === "pending_approval" || p.status === "submitted" || p.status === "under_review"
                            ? "#fbbf24"
                            : p.status === "rejected"
                            ? "#f87171"
                            : "#94a3b8",
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

      {/* Create Property Modal */}
      {showCreateModal && (
        <div
          data-testid="create-property-modal"
          style={{
            position: "fixed",
            inset: 0,
            backgroundColor: "rgba(0,0,0,0.75)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: "20px",
          }}
        >
          <div
            style={{
              backgroundColor: "#1e293b",
              border: "1px solid #334155",
              borderRadius: "12px",
              width: "100%",
              maxWidth: "800px",
              maxHeight: "90vh",
              overflowY: "auto",
              padding: "24px",
              boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.5)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h2 style={{ fontSize: "1.25rem", fontWeight: 700, color: "#f8fafc" }}>
                Yangi ko'chmas mulk e'loni qo'shish
              </h2>
              <button
                onClick={() => setShowCreateModal(false)}
                style={{
                  background: "none",
                  border: "none",
                  color: "#94a3b8",
                  fontSize: "1.5rem",
                  cursor: "pointer",
                  lineHeight: 1,
                }}
              >
                &times;
              </button>
            </div>

            {createError && (
              <div
                style={{
                  padding: "10px 14px",
                  backgroundColor: "rgba(239, 68, 68, 0.15)",
                  border: "1px solid #ef4444",
                  borderRadius: "6px",
                  color: "#fca5a5",
                  marginBottom: "16px",
                  fontSize: "0.875rem",
                }}
              >
                {createError}
              </div>
            )}

            <form onSubmit={handleCreateSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {/* Listing Type & Property Type */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", color: "#94a3b8", marginBottom: "6px" }}>
                    Bitim turi (Listing type) *
                  </label>
                  <div style={{ display: "flex", gap: "8px" }}>
                    <button
                      type="button"
                      onClick={() => setFormListingType("sale")}
                      style={{
                        flex: 1,
                        padding: "8px 12px",
                        backgroundColor: formListingType === "sale" ? "#3b82f6" : "#0f172a",
                        color: formListingType === "sale" ? "#ffffff" : "#cbd5e1",
                        border: "1px solid #334155",
                        borderRadius: "6px",
                        fontSize: "0.875rem",
                        cursor: "pointer",
                        fontWeight: formListingType === "sale" ? 600 : 400,
                      }}
                    >
                      Sotish (Sale)
                    </button>
                    <button
                      type="button"
                      onClick={() => setFormListingType("rent")}
                      style={{
                        flex: 1,
                        padding: "8px 12px",
                        backgroundColor: formListingType === "rent" ? "#3b82f6" : "#0f172a",
                        color: formListingType === "rent" ? "#ffffff" : "#cbd5e1",
                        border: "1px solid #334155",
                        borderRadius: "6px",
                        fontSize: "0.875rem",
                        cursor: "pointer",
                        fontWeight: formListingType === "rent" ? 600 : 400,
                      }}
                    >
                      Ijara (Rent)
                    </button>
                  </div>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", color: "#94a3b8", marginBottom: "6px" }}>
                    Mulk turi (Property type) *
                  </label>
                  <select
                    value={formPropertyType}
                    onChange={(e) => setFormPropertyType(e.target.value as any)}
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      backgroundColor: "#0f172a",
                      border: "1px solid #334155",
                      borderRadius: "6px",
                      color: "#f8fafc",
                      fontSize: "0.875rem",
                    }}
                  >
                    <option value="apartment">Kvartira (Apartment)</option>
                    <option value="house">Hovli / Uy (House)</option>
                    <option value="commercial">Tijorat mulki (Commercial)</option>
                    <option value="land">Yer uchastkasi (Land)</option>
                  </select>
                </div>
              </div>

              {/* Title & Description */}
              <div>
                <label style={{ display: "block", fontSize: "0.85rem", color: "#94a3b8", marginBottom: "6px" }}>
                  Sarlavha (Ixtiyoriy)
                </label>
                <input
                  type="text"
                  placeholder="Masalan: Chilonzor 9-mavzeda shinam 3 xonali xonadon"
                  value={formTitle}
                  onChange={(e) => setFormTitle(e.target.value)}
                  data-testid="create-property-title"
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    backgroundColor: "#0f172a",
                    border: "1px solid #334155",
                    borderRadius: "6px",
                    color: "#f8fafc",
                    fontSize: "0.875rem",
                  }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.85rem", color: "#94a3b8", marginBottom: "6px" }}>
                  Batafsil tavsif
                </label>
                <textarea
                  placeholder="Mulkning afzalliklari, infratuzilma, qulayliklar..."
                  rows={3}
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  data-testid="create-property-description"
                  style={{
                    width: "100%",
                    padding: "8px 12px",
                    backgroundColor: "#0f172a",
                    border: "1px solid #334155",
                    borderRadius: "6px",
                    color: "#f8fafc",
                    fontSize: "0.875rem",
                  }}
                />
              </div>

              {/* Location */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 2fr", gap: "12px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", color: "#94a3b8", marginBottom: "6px" }}>
                    Viloyat / Shahar *
                  </label>
                  <input
                    type="text"
                    value={formRegion}
                    onChange={(e) => setFormRegion(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      backgroundColor: "#0f172a",
                      border: "1px solid #334155",
                      borderRadius: "6px",
                      color: "#f8fafc",
                      fontSize: "0.875rem",
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", color: "#94a3b8", marginBottom: "6px" }}>
                    Tuman *
                  </label>
                  <select
                    value={formDistrict}
                    onChange={(e) => setFormDistrict(e.target.value)}
                    data-testid="create-property-district"
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      backgroundColor: "#0f172a",
                      border: "1px solid #334155",
                      borderRadius: "6px",
                      color: "#f8fafc",
                      fontSize: "0.875rem",
                    }}
                  >
                    {TASHKENT_DISTRICTS.map((d) => (
                      <option key={d} value={d}>
                        {d}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", color: "#94a3b8", marginBottom: "6px" }}>
                    Aniq manzil (Ko'cha, uy, mo'ljal) *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="Qatortol ko'chasi, 12-uy"
                    value={formAddress}
                    onChange={(e) => setFormAddress(e.target.value)}
                    data-testid="create-property-address"
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      backgroundColor: "#0f172a",
                      border: "1px solid #334155",
                      borderRadius: "6px",
                      color: "#f8fafc",
                      fontSize: "0.875rem",
                    }}
                  />
                </div>
              </div>

              {/* Price & Currency */}
              <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: "12px", alignItems: "flex-end" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", color: "#94a3b8", marginBottom: "6px" }}>
                    Narxi *
                  </label>
                  <input
                    type="number"
                    required
                    min={1}
                    placeholder="75000"
                    value={formPrice}
                    onChange={(e) => setFormPrice(e.target.value)}
                    data-testid="create-property-price"
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      backgroundColor: "#0f172a",
                      border: "1px solid #334155",
                      borderRadius: "6px",
                      color: "#f8fafc",
                      fontSize: "0.875rem",
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", color: "#94a3b8", marginBottom: "6px" }}>
                    Valyuta *
                  </label>
                  <select
                    value={formCurrency}
                    onChange={(e) => setFormCurrency(e.target.value as "USD" | "UZS")}
                    data-testid="create-property-currency"
                    style={{
                      width: "100%",
                      padding: "8px 12px",
                      backgroundColor: "#0f172a",
                      border: "1px solid #334155",
                      borderRadius: "6px",
                      color: "#f8fafc",
                      fontSize: "0.875rem",
                    }}
                  >
                    <option value="USD">USD ($)</option>
                    <option value="UZS">UZS (so'm)</option>
                  </select>
                </div>
                <div style={{ display: "flex", alignItems: "center", height: "38px" }}>
                  <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.875rem", color: "#cbd5e1", cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={formNegotiable}
                      onChange={(e) => setFormNegotiable(e.target.checked)}
                      style={{ accentColor: "#3b82f6", width: "16px", height: "16px" }}
                    />
                    Kelishiladi
                  </label>
                </div>
              </div>

              {/* Rooms & Dimensions */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr 1fr", gap: "10px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.8rem", color: "#94a3b8", marginBottom: "4px" }}>
                    Xonalar *
                  </label>
                  <input
                    type="number"
                    required
                    min={1}
                    max={30}
                    value={formRooms}
                    onChange={(e) => setFormRooms(e.target.value)}
                    data-testid="create-property-rooms"
                    style={{
                      width: "100%",
                      padding: "8px",
                      backgroundColor: "#0f172a",
                      border: "1px solid #334155",
                      borderRadius: "6px",
                      color: "#f8fafc",
                      fontSize: "0.875rem",
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.8rem", color: "#94a3b8", marginBottom: "4px" }}>
                    Maydon (m²) *
                  </label>
                  <input
                    type="number"
                    required
                    min={5}
                    value={formTotalArea}
                    onChange={(e) => setFormTotalArea(e.target.value)}
                    data-testid="create-property-total-area"
                    style={{
                      width: "100%",
                      padding: "8px",
                      backgroundColor: "#0f172a",
                      border: "1px solid #334155",
                      borderRadius: "6px",
                      color: "#f8fafc",
                      fontSize: "0.875rem",
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.8rem", color: "#94a3b8", marginBottom: "4px" }}>
                    Yashash maydoni
                  </label>
                  <input
                    type="number"
                    min={1}
                    placeholder="Masalan: 50"
                    value={formLivingArea}
                    onChange={(e) => setFormLivingArea(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px",
                      backgroundColor: "#0f172a",
                      border: "1px solid #334155",
                      borderRadius: "6px",
                      color: "#f8fafc",
                      fontSize: "0.875rem",
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.8rem", color: "#94a3b8", marginBottom: "4px" }}>
                    Qavat
                  </label>
                  <input
                    type="number"
                    min={1}
                    value={formFloor}
                    onChange={(e) => setFormFloor(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px",
                      backgroundColor: "#0f172a",
                      border: "1px solid #334155",
                      borderRadius: "6px",
                      color: "#f8fafc",
                      fontSize: "0.875rem",
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.8rem", color: "#94a3b8", marginBottom: "4px" }}>
                    Jami qavatlar
                  </label>
                  <input
                    type="number"
                    min={1}
                    value={formTotalFloors}
                    onChange={(e) => setFormTotalFloors(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px",
                      backgroundColor: "#0f172a",
                      border: "1px solid #334155",
                      borderRadius: "6px",
                      color: "#f8fafc",
                      fontSize: "0.875rem",
                    }}
                  />
                </div>
              </div>

              {/* Condition & Features */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: "10px", alignItems: "center" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.8rem", color: "#94a3b8", marginBottom: "4px" }}>
                    Ta'mir holati *
                  </label>
                  <select
                    value={formCondition}
                    onChange={(e) => setFormCondition(e.target.value as any)}
                    data-testid="create-property-condition"
                    style={{
                      width: "100%",
                      padding: "8px",
                      backgroundColor: "#0f172a",
                      border: "1px solid #334155",
                      borderRadius: "6px",
                      color: "#f8fafc",
                      fontSize: "0.875rem",
                    }}
                  >
                    <option value="new">Yangi qurilgan (New)</option>
                    <option value="renovated">Yaxshi ta'mirlangan (Renovated)</option>
                    <option value="needs_renovation">Ta'mir talab (Needs renovation)</option>
                    <option value="shell">Qora suvoq (Shell)</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.8rem", color: "#94a3b8", marginBottom: "4px" }}>
                    Qurilish turi
                  </label>
                  <input
                    type="text"
                    value={formConstructionType}
                    onChange={(e) => setFormConstructionType(e.target.value)}
                    style={{
                      width: "100%",
                      padding: "8px",
                      backgroundColor: "#0f172a",
                      border: "1px solid #334155",
                      borderRadius: "6px",
                      color: "#f8fafc",
                      fontSize: "0.875rem",
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.8rem", color: "#94a3b8", marginBottom: "4px" }}>
                    Kadastr
                  </label>
                  <select
                    value={formCadastreStatus}
                    onChange={(e) => setFormCadastreStatus(e.target.value as any)}
                    style={{
                      width: "100%",
                      padding: "8px",
                      backgroundColor: "#0f172a",
                      border: "1px solid #334155",
                      borderRadius: "6px",
                      color: "#f8fafc",
                      fontSize: "0.875rem",
                    }}
                  >
                    <option value="available">Mavjud (Available)</option>
                    <option value="not_available">Yo'q (Not available)</option>
                    <option value="in_process">Jarayonda (In process)</option>
                    <option value="unknown">Noma'lum (Unknown)</option>
                  </select>
                </div>
                <div style={{ display: "flex", alignItems: "center", height: "38px", paddingTop: "14px" }}>
                  <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.85rem", color: "#cbd5e1", cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={formHasFurniture}
                      onChange={(e) => setFormHasFurniture(e.target.checked)}
                      style={{ accentColor: "#3b82f6", width: "16px", height: "16px" }}
                    />
                    Jihozlangan (Mebel bor)
                  </label>
                </div>
              </div>

              {/* Photos Upload */}
              <div style={{ borderTop: "1px solid #334155", paddingTop: "14px" }}>
                <label style={{ display: "block", fontSize: "0.85rem", color: "#94a3b8", marginBottom: "6px" }}>
                  Rasmlar yuklash (JPEG, PNG, WEBP — maks 5MB)
                </label>
                <div style={{ display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap", marginBottom: "10px" }}>
                  <label
                    style={{
                      padding: "8px 14px",
                      backgroundColor: "#334155",
                      color: "#f8fafc",
                      borderRadius: "6px",
                      fontSize: "0.85rem",
                      cursor: uploadLoading ? "not-allowed" : "pointer",
                      display: "inline-block",
                    }}
                  >
                    {uploadLoading ? "Rasm yuklanmoqda..." : "📁 Rasm tanlash"}
                    <input
                      type="file"
                      multiple
                      accept="image/jpeg,image/png,image/webp"
                      onChange={handleFileUpload}
                      disabled={uploadLoading}
                      style={{ display: "none" }}
                    />
                  </label>
                  <span style={{ fontSize: "0.8rem", color: "#64748b" }}>
                    {uploadedPhotos.length} ta rasm yuklandi
                  </span>
                </div>

                {uploadedPhotos.length > 0 && (
                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    {uploadedPhotos.map((photo) => (
                      <div
                        key={photo.id}
                        style={{
                          position: "relative",
                          width: "70px",
                          height: "70px",
                          borderRadius: "6px",
                          overflow: "hidden",
                          border: "1px solid #475569",
                        }}
                      >
                        <img
                          src={photo.url}
                          alt={photo.name}
                          style={{ width: "100%", height: "100%", objectFit: "cover" }}
                        />
                        <button
                          type="button"
                          onClick={() => handleRemovePhoto(photo.id)}
                          style={{
                            position: "absolute",
                            top: "2px",
                            right: "2px",
                            backgroundColor: "rgba(239, 68, 68, 0.8)",
                            color: "#ffffff",
                            border: "none",
                            borderRadius: "50%",
                            width: "18px",
                            height: "18px",
                            fontSize: "10px",
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                          }}
                        >
                          &times;
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Auto-approve (only for moderators / superadmins) */}
              {canModerate && (
                <div
                  style={{
                    padding: "10px 14px",
                    backgroundColor: "rgba(16, 185, 129, 0.1)",
                    border: "1px solid rgba(16, 185, 129, 0.3)",
                    borderRadius: "6px",
                  }}
                >
                  <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.875rem", color: "#6ee7b7", cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={formAutoApprove}
                      onChange={(e) => setFormAutoApprove(e.target.checked)}
                      data-testid="create-property-auto-approve"
                      style={{ accentColor: "#10b981", width: "16px", height: "16px" }}
                    />
                    <strong>Darhol tasdiqlash</strong> (moderatsiyadan o'tkazmasdan to'g'ridan-to'g'ri ommaga chiqarish)
                  </label>
                </div>
              )}

              {/* Form Buttons */}
              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "10px" }}>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  disabled={createSubmitting}
                  style={{
                    padding: "10px 18px",
                    backgroundColor: "transparent",
                    color: "#94a3b8",
                    border: "1px solid #475569",
                    borderRadius: "6px",
                    cursor: "pointer",
                    fontSize: "0.875rem",
                  }}
                >
                  Bekor qilish
                </button>
                <button
                  type="submit"
                  disabled={createSubmitting || uploadLoading}
                  data-testid="submit-create-property-btn"
                  style={{
                    padding: "10px 22px",
                    backgroundColor: "#10b981",
                    color: "#ffffff",
                    border: "none",
                    borderRadius: "6px",
                    fontWeight: 600,
                    cursor: createSubmitting ? "not-allowed" : "pointer",
                    fontSize: "0.875rem",
                  }}
                >
                  {createSubmitting ? "Saqlanmoqda..." : "E'lonni yaratish"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
