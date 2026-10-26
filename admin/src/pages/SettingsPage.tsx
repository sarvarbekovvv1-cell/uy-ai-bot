import React, { useState } from "react";
import { useAuth } from "../auth/AuthContext";

export const SettingsPage: React.FC = () => {
  const { user, updateUsername, updatePassword } = useAuth();

  // Username form state
  const [newUsername, setNewUsername] = useState("");
  const [usernameLoading, setUsernameLoading] = useState(false);
  const [usernameError, setUsernameError] = useState<string | null>(null);
  const [usernameSuccess, setUsernameSuccess] = useState<string | null>(null);

  // Password form state
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  const handleUsernameSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setUsernameError(null);
    setUsernameSuccess(null);

    const trimmed = newUsername.trim();
    if (!trimmed) {
      setUsernameError("Yangi foydalanuvchi nomini kiriting.");
      return;
    }
    if (trimmed.length < 3) {
      setUsernameError("Foydalanuvchi nomi kamida 3 ta belgidan iborat bo'lishi kerak.");
      return;
    }
    if (trimmed.length > 50) {
      setUsernameError("Foydalanuvchi nomi 50 ta belgidan oshmasligi kerak.");
      return;
    }
    if (!/^[a-zA-Z0-9_.-]+$/.test(trimmed)) {
      setUsernameError("Foydalanuvchi nomida faqat lotin harflari, raqamlar, chiziqcha va nuqta ruxsat etilgan.");
      return;
    }

    setUsernameLoading(true);
    try {
      await updateUsername(trimmed);
      setUsernameSuccess("Foydalanuvchi nomi muvaffaqiyatli yangilandi!");
      setNewUsername("");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setUsernameError(err.message);
      } else {
        setUsernameError("Foydalanuvchi nomini yangilashda xatolik yuz berdi.");
      }
    } finally {
      setUsernameLoading(false);
    }
  };

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError(null);

    if (!currentPassword) {
      setPasswordError("Joriy parolni kiriting.");
      return;
    }
    if (!newPassword) {
      setPasswordError("Yangi parolni kiriting.");
      return;
    }
    if (newPassword.length < 8) {
      setPasswordError("Yangi parol kamida 8 ta belgidan iborat bo'lishi kerak.");
      return;
    }
    if (newPassword.length > 128) {
      setPasswordError("Yangi parol 128 ta belgidan oshmasligi kerak.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("Yangi parollar bir-biriga mos kelmadi.");
      return;
    }

    setPasswordLoading(true);
    try {
      await updatePassword(currentPassword, newPassword, confirmPassword);
      // On success, updatePassword clears the user session and redirects to Login with notice.
    } catch (err: unknown) {
      if (err instanceof Error) {
        setPasswordError(err.message);
      } else {
        setPasswordError("Parolni o'zgartirishda xatolik yuz berdi.");
      }
      setPasswordLoading(false);
    }
  };

  return (
    <div style={{ padding: "32px", maxWidth: "800px", margin: "0 auto" }}>
      <div style={{ marginBottom: "32px" }}>
        <h1 style={{ fontSize: "1.75rem", fontWeight: 700, color: "#f8fafc" }}>
          ⚙️ Sozlamalar
        </h1>
        <p style={{ color: "#94a3b8", fontSize: "0.875rem", marginTop: "4px" }}>
          Shaxsiy profil va hisob xavfsizligi sozlamalari
        </p>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "28px" }}>
        {/* Username Card */}
        <section
          style={{
            backgroundColor: "#1e293b",
            borderRadius: "12px",
            border: "1px solid #334155",
            padding: "24px",
          }}
        >
          <h2 style={{ fontSize: "1.125rem", fontWeight: 600, color: "#e2e8f0", marginBottom: "16px" }}>
            👤 Profil / Login ma'lumotlari
          </h2>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "12px",
              marginBottom: "20px",
              padding: "12px 16px",
              backgroundColor: "#0f172a",
              borderRadius: "8px",
              border: "1px solid #334155",
            }}
          >
            <span style={{ color: "#94a3b8", fontSize: "0.875rem" }}>Hozirgi username:</span>
            <span
              data-testid="current-username"
              style={{
                fontFamily: "monospace",
                fontWeight: 600,
                color: "#60a5fa",
                fontSize: "1rem",
              }}
            >
              {user?.username || "—"}
            </span>
            <span
              style={{
                marginLeft: "auto",
                fontSize: "0.75rem",
                color: "#94a3b8",
                backgroundColor: "#334155",
                padding: "2px 8px",
                borderRadius: "4px",
              }}
            >
              ID: {user?.id}
            </span>
          </div>

          {usernameSuccess && (
            <div
              data-testid="username-success"
              style={{
                padding: "12px 16px",
                backgroundColor: "rgba(34, 197, 94, 0.15)",
                border: "1px solid #22c55e",
                borderRadius: "8px",
                color: "#86efac",
                fontSize: "0.875rem",
                marginBottom: "16px",
              }}
            >
              {usernameSuccess}
            </div>
          )}

          {usernameError && (
            <div
              data-testid="username-error"
              style={{
                padding: "12px 16px",
                backgroundColor: "rgba(239, 68, 68, 0.15)",
                border: "1px solid #ef4444",
                borderRadius: "8px",
                color: "#fca5a5",
                fontSize: "0.875rem",
                marginBottom: "16px",
              }}
            >
              {usernameError}
            </div>
          )}

          <form onSubmit={handleUsernameSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div>
              <label
                htmlFor="new-username-input"
                style={{ display: "block", fontSize: "0.875rem", fontWeight: 500, color: "#cbd5e1", marginBottom: "6px" }}
              >
                Yangi foydalanuvchi nomi
              </label>
              <input
                id="new-username-input"
                type="text"
                data-testid="new-username-input"
                placeholder="Yangi username (masalan: superadmin)"
                value={newUsername}
                onChange={(e) => setNewUsername(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  backgroundColor: "#0f172a",
                  border: "1px solid #334155",
                  borderRadius: "8px",
                  color: "#f8fafc",
                  fontSize: "0.95rem",
                  boxSizing: "border-box",
                }}
              />
            </div>

            <button
              type="submit"
              data-testid="update-username-button"
              disabled={usernameLoading || !newUsername.trim()}
              style={{
                alignSelf: "flex-start",
                padding: "10px 20px",
                backgroundColor: usernameLoading || !newUsername.trim() ? "#475569" : "#2563eb",
                color: "#ffffff",
                border: "none",
                borderRadius: "8px",
                fontWeight: 600,
                fontSize: "0.875rem",
                cursor: usernameLoading || !newUsername.trim() ? "not-allowed" : "pointer",
              }}
            >
              {usernameLoading ? "Yangilanmoqda..." : "Usernameni yangilash"}
            </button>
          </form>
        </section>

        {/* Password Card */}
        <section
          style={{
            backgroundColor: "#1e293b",
            borderRadius: "12px",
            border: "1px solid #334155",
            padding: "24px",
          }}
        >
          <h2 style={{ fontSize: "1.125rem", fontWeight: 600, color: "#e2e8f0", marginBottom: "8px" }}>
            🔒 Parolni o'zgartirish
          </h2>
          <p style={{ fontSize: "0.8125rem", color: "#94a3b8", marginBottom: "16px" }}>
            Parol o'zgartirilgach, xavfsizlik uchun barcha boshqa faol sessiyalar bekor qilinadi va yangi parol bilan qayta login talab etiladi.
          </p>

          {passwordError && (
            <div
              data-testid="password-error"
              style={{
                padding: "12px 16px",
                backgroundColor: "rgba(239, 68, 68, 0.15)",
                border: "1px solid #ef4444",
                borderRadius: "8px",
                color: "#fca5a5",
                fontSize: "0.875rem",
                marginBottom: "16px",
              }}
            >
              {passwordError}
            </div>
          )}

          <form onSubmit={handlePasswordSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div>
              <label
                htmlFor="current-password-input"
                style={{ display: "block", fontSize: "0.875rem", fontWeight: 500, color: "#cbd5e1", marginBottom: "6px" }}
              >
                Joriy parol
              </label>
              <input
                id="current-password-input"
                type="password"
                data-testid="current-password-input"
                placeholder="Amaldagi parolingiz"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  backgroundColor: "#0f172a",
                  border: "1px solid #334155",
                  borderRadius: "8px",
                  color: "#f8fafc",
                  fontSize: "0.95rem",
                  boxSizing: "border-box",
                }}
              />
            </div>

            <div>
              <label
                htmlFor="new-password-input"
                style={{ display: "block", fontSize: "0.875rem", fontWeight: 500, color: "#cbd5e1", marginBottom: "6px" }}
              >
                Yangi parol (kamida 8 ta belgi)
              </label>
              <input
                id="new-password-input"
                type="password"
                data-testid="new-password-input"
                placeholder="Yangi kuchli parol"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  backgroundColor: "#0f172a",
                  border: "1px solid #334155",
                  borderRadius: "8px",
                  color: "#f8fafc",
                  fontSize: "0.95rem",
                  boxSizing: "border-box",
                }}
              />
            </div>

            <div>
              <label
                htmlFor="confirm-password-input"
                style={{ display: "block", fontSize: "0.875rem", fontWeight: 500, color: "#cbd5e1", marginBottom: "6px" }}
              >
                Yangi parolni tasdiqlash
              </label>
              <input
                id="confirm-password-input"
                type="password"
                data-testid="confirm-password-input"
                placeholder="Yangi parolni qayta kiriting"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  backgroundColor: "#0f172a",
                  border: "1px solid #334155",
                  borderRadius: "8px",
                  color: "#f8fafc",
                  fontSize: "0.95rem",
                  boxSizing: "border-box",
                }}
              />
            </div>

            <button
              type="submit"
              data-testid="update-password-button"
              disabled={passwordLoading || !currentPassword || !newPassword || !confirmPassword}
              style={{
                alignSelf: "flex-start",
                padding: "10px 20px",
                backgroundColor:
                  passwordLoading || !currentPassword || !newPassword || !confirmPassword
                    ? "#475569"
                    : "#dc2626",
                color: "#ffffff",
                border: "none",
                borderRadius: "8px",
                fontWeight: 600,
                fontSize: "0.875rem",
                cursor:
                  passwordLoading || !currentPassword || !newPassword || !confirmPassword
                    ? "not-allowed"
                    : "pointer",
              }}
            >
              {passwordLoading ? "Yangilanmoqda..." : "Parolni yangilash"}
            </button>
          </form>
        </section>
      </div>
    </div>
  );
};
