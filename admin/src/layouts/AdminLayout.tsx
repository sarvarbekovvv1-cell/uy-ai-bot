import React from "react";
import { useAuth } from "../auth/AuthContext";

export type AdminTab =
  | "dashboard"
  | "properties"
  | "leads"
  | "viewings"
  | "brokers"
  | "users"
  | "crm"
  | "audit";

interface AdminLayoutProps {
  currentTab: AdminTab;
  onSelectTab: (tab: AdminTab) => void;
  children: React.ReactNode;
}

export const AdminLayout: React.FC<AdminLayoutProps> = ({ currentTab, onSelectTab, children }) => {
  const { user, logout, hasPerm } = useAuth();

  const navItems: { tab: AdminTab; label: string; perm: string }[] = [
    { tab: "dashboard", label: "📊 Bosh sahifa", perm: "dashboard.view" },
    { tab: "properties", label: "🏢 E'lonlar va Moderatsiya", perm: "properties.view" },
    { tab: "leads", label: "🎯 Lidlar Pipeline", perm: "leads.view" },
    { tab: "viewings", label: "🗓 Ko'rishlar", perm: "viewings.view" },
    { tab: "brokers", label: "👥 Brokerlar", perm: "leads.assign" },
    { tab: "users", label: "👤 Foydalanuvchilar", perm: "users.view" },
    { tab: "crm", label: "🔄 amoCRM Outbox", perm: "crm.view" },
    { tab: "audit", label: "🛡 Audit Log", perm: "audit.view" },
  ];

  const visibleNavItems = navItems.filter((item) => hasPerm(item.perm));

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      {/* Sidebar */}
      <aside
        style={{
          width: "260px",
          backgroundColor: "#1e293b",
          borderRight: "1px solid #334155",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div style={{ padding: "20px 24px", borderBottom: "1px solid #334155" }}>
          <h2 style={{ fontSize: "1.25rem", fontWeight: 700, color: "#60a5fa" }}>
            UyAI Admin
          </h2>
          <p style={{ fontSize: "0.75rem", color: "#94a3b8", marginTop: "4px" }}>
            Boshqaruv Paneli
          </p>
        </div>

        <nav style={{ padding: "16px 12px", display: "flex", flexDirection: "column", gap: "6px", flex: 1 }}>
          {visibleNavItems.map((item) => {
            const isActive = currentTab === item.tab;
            return (
              <button
                key={item.tab}
                onClick={() => onSelectTab(item.tab)}
                data-testid={`nav-${item.tab}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  padding: "10px 14px",
                  borderRadius: "8px",
                  fontSize: "0.875rem",
                  fontWeight: 500,
                  color: isActive ? "#ffffff" : "#cbd5e1",
                  backgroundColor: isActive ? "#3b82f6" : "transparent",
                  border: "none",
                  cursor: "pointer",
                  textAlign: "left",
                  transition: "background-color 0.15s ease",
                }}
              >
                {item.label}
              </button>
            );
          })}
        </nav>

        <div style={{ padding: "16px", borderTop: "1px solid #334155" }}>
          <div style={{ fontSize: "0.75rem", color: "#64748b" }}>
            UyAI Platform v11.0 (Staff RBAC)
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        {/* Topbar */}
        <header
          style={{
            height: "64px",
            backgroundColor: "#1e293b",
            borderBottom: "1px solid #334155",
            padding: "0 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <span style={{ fontSize: "0.875rem", color: "#94a3b8" }}>Xodim:</span>
            <strong style={{ fontSize: "0.875rem", color: "#f8fafc" }}>
              {user?.first_name || user?.username || `ID #${user?.id}`}
            </strong>
            <div style={{ display: "flex", gap: "6px" }}>
              {user?.roles.map((role) => (
                <span
                  key={role}
                  style={{
                    backgroundColor: "#334155",
                    color: "#93c5fd",
                    padding: "2px 8px",
                    borderRadius: "12px",
                    fontSize: "0.7rem",
                    fontWeight: 600,
                    textTransform: "uppercase",
                  }}
                >
                  {role}
                </span>
              ))}
            </div>
          </div>

          <button
            onClick={() => logout()}
            data-testid="logout-btn"
            style={{
              padding: "6px 14px",
              backgroundColor: "transparent",
              color: "#f87171",
              border: "1px solid #ef4444",
              borderRadius: "6px",
              fontSize: "0.8rem",
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            Chiqish
          </button>
        </header>

        {/* Viewport */}
        <main style={{ flex: 1, padding: "24px", overflowY: "auto" }}>
          {children}
        </main>
      </div>
    </div>
  );
};
