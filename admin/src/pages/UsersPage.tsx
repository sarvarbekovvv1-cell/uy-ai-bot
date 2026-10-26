import React, { useEffect, useState } from "react";
import { adminApi } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { UserItem } from "../types";

const ALL_ROLES = [
  "superadmin",
  "head_broker",
  "sales_broker",
  "rental_broker",
  "crm_operator",
  "marketing_specialist",
  "moderator",
  "property_owner",
  "buyer",
  "tenant",
];

export const UsersPage: React.FC = () => {
  const { hasPerm } = useAuth();
  const canManageRoles = hasPerm("users.manage_roles");

  const [users, setUsers] = useState<UserItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [roleFilter, setRoleFilter] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  // Edit Roles Modal
  const [editingUser, setEditingUser] = useState<UserItem | null>(null);
  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const res = await adminApi.listUsers({
        page,
        page_size: 15,
        role: roleFilter || undefined,
        search: search.trim() || undefined,
      });
      setUsers(res.items);
      setTotal(res.total);
    } catch (err: unknown) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [page, roleFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchUsers();
  };

  const handleOpenEdit = (u: UserItem) => {
    setEditingUser(u);
    setSelectedRoles([...u.roles]);
    setSaveError(null);
  };

  const handleToggleRole = (role: string) => {
    if (selectedRoles.includes(role)) {
      setSelectedRoles(selectedRoles.filter((r) => r !== role));
    } else {
      setSelectedRoles([...selectedRoles, role]);
    }
  };

  const handleSaveRoles = async () => {
    if (!editingUser) return;
    setSaving(true);
    setSaveError(null);
    try {
      await adminApi.updateUserRoles(editingUser.id, selectedRoles);
      setEditingUser(null);
      fetchUsers();
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : "Rollar saqlanmadi.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
        <div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 700, color: "#f8fafc" }}>
            Foydalanuvchilar va Rollar Boshqaruvi
          </h1>
          <p style={{ fontSize: "0.875rem", color: "#94a3b8" }}>
            Jami: {total} ta foydalanuvchi
          </p>
        </div>

        <div style={{ display: "flex", gap: "10px" }}>
          <select
            value={roleFilter}
            onChange={(e) => {
              setRoleFilter(e.target.value);
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
            <option value="">Barcha rollar</option>
            {ALL_ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>

          <form onSubmit={handleSearchSubmit} style={{ display: "flex", gap: "6px" }}>
            <input
              type="text"
              placeholder="Ism, login, telefon..."
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

      {/* Users Table */}
      <div style={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "8px", overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "0.875rem" }}>
          <thead>
            <tr style={{ backgroundColor: "#0f172a", borderBottom: "1px solid #334155", color: "#94a3b8" }}>
              <th style={{ padding: "12px 16px" }}>ID</th>
              <th style={{ padding: "12px 16px" }}>Telegram ID</th>
              <th style={{ padding: "12px 16px" }}>Ism / Familiya</th>
              <th style={{ padding: "12px 16px" }}>Telefon (Masked)</th>
              <th style={{ padding: "12px 16px" }}>Rollar</th>
              <th style={{ padding: "12px 16px", textAlign: "right" }}>Amallar</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} style={{ padding: "24px", textAlign: "center", color: "#94a3b8" }}>
                  Yuklanmoqda...
                </td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ padding: "24px", textAlign: "center", color: "#94a3b8" }}>
                  Foydalanuvchilar topilmadi.
                </td>
              </tr>
            ) : (
              users.map((u) => (
                <tr key={u.id} style={{ borderBottom: "1px solid #334155" }}>
                  <td style={{ padding: "12px 16px", color: "#64748b" }}>#{u.id}</td>
                  <td style={{ padding: "12px 16px", color: "#93c5fd" }}>{u.telegram_id}</td>
                  <td style={{ padding: "12px 16px", fontWeight: 500, color: "#f8fafc" }}>
                    {`${u.first_name || ""} ${u.last_name || ""}`.trim() || u.username || "—"}
                  </td>
                  <td style={{ padding: "12px 16px", color: "#cbd5e1" }}>
                    {u.phone_masked || "—"}
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                      {u.roles.map((r) => (
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
                  <td style={{ padding: "12px 16px", textAlign: "right" }}>
                    {canManageRoles && (
                      <button
                        onClick={() => handleOpenEdit(u)}
                        data-testid={`edit-roles-${u.id}`}
                        style={{
                          padding: "6px 12px",
                          backgroundColor: "#3b82f6",
                          color: "#ffffff",
                          border: "none",
                          borderRadius: "4px",
                          fontSize: "0.8rem",
                          cursor: "pointer",
                        }}
                      >
                        Rollarni o'zgartirish
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Edit Roles Modal */}
      {editingUser && (
        <div
          data-testid="edit-roles-modal"
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
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h2 style={{ fontSize: "1.2rem", fontWeight: 700, color: "#f8fafc" }}>
                Foydalanuvchi #{editingUser.id} rollari
              </h2>
              <button
                onClick={() => setEditingUser(null)}
                style={{ background: "transparent", border: "none", color: "#94a3b8", fontSize: "1.2rem", cursor: "pointer" }}
              >
                ✕
              </button>
            </div>

            {saveError && (
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
                {saveError}
              </div>
            )}

            <div style={{ display: "flex", flexDirection: "column", gap: "8px", maxHeight: "300px", overflowY: "auto" }}>
              {ALL_ROLES.map((role) => (
                <label
                  key={role}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    padding: "8px",
                    backgroundColor: "#0f172a",
                    borderRadius: "6px",
                    cursor: "pointer",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={selectedRoles.includes(role)}
                    onChange={() => handleToggleRole(role)}
                  />
                  <span style={{ fontSize: "0.875rem", color: "#f8fafc" }}>{role}</span>
                </label>
              ))}
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "20px" }}>
              <button
                onClick={() => setEditingUser(null)}
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
                onClick={handleSaveRoles}
                disabled={saving}
                data-testid="save-roles-btn"
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
                {saving ? "Saqlanmoqda..." : "Saqlash"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
