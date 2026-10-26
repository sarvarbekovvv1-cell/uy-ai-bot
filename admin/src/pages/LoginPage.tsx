import React, { useState } from "react";
import { useAuth } from "../auth/AuthContext";

export const LoginPage: React.FC = () => {
  const { login, notice } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading) return; // Prevent double submit

    const cleanUser = username.trim();
    if (!cleanUser || !password) {
      setError("Foydalanuvchi nomi va parolni kiriting.");
      return;
    }
    setError(null);
    setLoading(true);

    try {
      await login(cleanUser, password);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Tizimga kirishda xatolik yuz berdi.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        backgroundColor: "#0f172a",
        padding: "16px",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "400px",
          backgroundColor: "#1e293b",
          border: "1px solid #334155",
          borderRadius: "12px",
          padding: "32px",
          boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.5)",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: "24px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "8px", marginBottom: "4px" }}>
            <span style={{ fontSize: "1.75rem" }}>🏢</span>
            <h1 style={{ fontSize: "1.5rem", fontWeight: 700, color: "#60a5fa", margin: 0 }}>
              UyAI Boshqaruv
            </h1>
          </div>
          <p style={{ fontSize: "0.875rem", color: "#94a3b8", marginTop: "6px" }}>
            Xodimlar va ma'murlar uchun kirish
          </p>
        </div>

        {notice && (
          <div
            data-testid="login-notice"
            style={{
              padding: "12px",
              backgroundColor: "rgba(34, 197, 94, 0.15)",
              border: "1px solid #22c55e",
              borderRadius: "8px",
              color: "#86efac",
              fontSize: "0.875rem",
              marginBottom: "20px",
            }}
          >
            {notice}
          </div>
        )}

        {error && (
          <div
            data-testid="login-error"
            style={{
              padding: "12px",
              backgroundColor: "rgba(239, 68, 68, 0.15)",
              border: "1px solid #ef4444",
              borderRadius: "8px",
              color: "#fca5a5",
              fontSize: "0.875rem",
              marginBottom: "20px",
            }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div>
            <label
              htmlFor="username"
              style={{ display: "block", fontSize: "0.8rem", fontWeight: 500, color: "#cbd5e1", marginBottom: "6px" }}
            >
              Foydalanuvchi nomi
            </label>
            <input
              id="username"
              data-testid="username-input"
              type="text"
              autoComplete="username"
              disabled={loading}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin_username"
              required
              style={{
                width: "100%",
                padding: "10px 12px",
                backgroundColor: "#0f172a",
                border: "1px solid #475569",
                borderRadius: "6px",
                color: "#f8fafc",
                fontSize: "0.9rem",
                boxSizing: "border-box",
              }}
            />
          </div>

          <div>
            <label
              htmlFor="password"
              style={{ display: "block", fontSize: "0.8rem", fontWeight: 500, color: "#cbd5e1", marginBottom: "6px" }}
            >
              Parol
            </label>
            <div style={{ position: "relative", width: "100%" }}>
              <input
                id="password"
                data-testid="password-input"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                disabled={loading}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                style={{
                  width: "100%",
                  padding: "10px 42px 10px 12px",
                  backgroundColor: "#0f172a",
                  border: "1px solid #475569",
                  borderRadius: "6px",
                  color: "#f8fafc",
                  fontSize: "0.9rem",
                  boxSizing: "border-box",
                }}
              />
              <button
                type="button"
                data-testid="toggle-password-visibility"
                aria-label={showPassword ? "Parolni yashirish" : "Parolni ko'rsatish"}
                disabled={loading}
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  position: "absolute",
                  right: "8px",
                  top: "50%",
                  transform: "translateY(-50%)",
                  background: "transparent",
                  border: "none",
                  color: "#94a3b8",
                  cursor: "pointer",
                  fontSize: "0.9rem",
                  padding: "4px",
                }}
              >
                {showPassword ? "🙈" : "👁"}
              </button>
            </div>
          </div>

          <button
            type="submit"
            data-testid="login-submit"
            disabled={loading}
            style={{
              marginTop: "8px",
              padding: "12px",
              backgroundColor: loading ? "#2563eb" : "#3b82f6",
              color: "#ffffff",
              border: "none",
              borderRadius: "6px",
              fontSize: "0.9rem",
              fontWeight: 600,
              cursor: loading ? "not-allowed" : "pointer",
              transition: "background-color 0.15s ease",
            }}
          >
            {loading ? "Kirilmoqda..." : "Kirish"}
          </button>
        </form>

        <div style={{ marginTop: "24px", textAlign: "center", fontSize: "0.75rem", color: "#64748b" }}>
          Mijoz hisoblari (Telegram orqali) bu panelga kira olmaydi.
        </div>
      </div>
    </div>
  );
};
