import React, { useEffect, useState } from "react";
import { useAuth } from "./auth/AuthContext";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { AdminLayout, type AdminTab } from "./layouts/AdminLayout";
import { AuditPage } from "./pages/AuditPage";
import { BrokersPage } from "./pages/BrokersPage";
import { CRMPage } from "./pages/CRMPage";
import { DashboardPage } from "./pages/DashboardPage";
import { KaizenPage } from "./pages/KaizenPage";
import { LeadsPage } from "./pages/LeadsPage";
import { LoginPage } from "./pages/LoginPage";
import { PropertiesPage } from "./pages/PropertiesPage";
import { SettingsPage } from "./pages/SettingsPage";
import { UsersPage } from "./pages/UsersPage";
import { ViewingsPage } from "./pages/ViewingsPage";

const VALID_TABS: AdminTab[] = [
  "dashboard",
  "properties",
  "leads",
  "viewings",
  "brokers",
  "users",
  "crm",
  "kaizen",
  "audit",
  "settings",
];

function getTabFromPathname(): AdminTab {
  if (typeof window === "undefined") return "dashboard";
  const path = window.location.pathname.replace(/\/+$/, "").replace(/^\//, "");
  if (VALID_TABS.includes(path as AdminTab)) {
    return path as AdminTab;
  }
  return "dashboard";
}

export const App: React.FC = () => {
  const { status, user, checkSession, hasPerm } = useAuth();
  const [currentTab, setCurrentTab] = useState<AdminTab>(getTabFromPathname);
  const [filterBrokerId, setFilterBrokerId] = useState<number | undefined>(undefined);

  // Sync route on popstate (browser back/forward)
  useEffect(() => {
    const handlePopState = () => {
      const tab = getTabFromPathname();
      setCurrentTab(tab);
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  // Update browser history when tab changes
  const handleSelectTab = (tab: AdminTab) => {
    setCurrentTab(tab);
    if (typeof window !== "undefined") {
      const targetPath = tab === "dashboard" ? "/dashboard" : `/${tab}`;
      if (window.location.pathname !== targetPath) {
        window.history.pushState({}, "", targetPath);
      }
    }
  };

  // If authenticated user lands on /login, redirect to /dashboard
  useEffect(() => {
    if (status === "authenticated" && typeof window !== "undefined") {
      if (window.location.pathname === "/login") {
        window.history.replaceState({}, "", "/dashboard");
        setCurrentTab("dashboard");
      }
    }
  }, [status]);

  // 1. Initial State: Checking session
  if (status === "checking") {
    return (
      <div
        data-testid="auth-checking"
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "100vh",
          backgroundColor: "#0f172a",
          color: "#94a3b8",
          fontSize: "1rem",
          gap: "16px",
        }}
      >
        <div
          style={{
            width: "36px",
            height: "36px",
            border: "3px solid #334155",
            borderTopColor: "#3b82f6",
            borderRadius: "50%",
            animation: "spin 1s linear infinite",
          }}
        />
        <p style={{ margin: 0 }}>Sessiya tekshirilmoqda...</p>
      </div>
    );
  }

  // 2. Server connection error state
  if (status === "error") {
    return (
      <div
        data-testid="auth-error"
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "100vh",
          backgroundColor: "#0f172a",
          color: "#f87171",
          padding: "24px",
          textAlign: "center",
        }}
      >
        <div style={{ fontSize: "2.5rem", marginBottom: "12px" }}>⚠️</div>
        <h2 style={{ fontSize: "1.25rem", fontWeight: 700, margin: "0 0 8px 0" }}>
          Server bilan bog‘lanib bo‘lmadi
        </h2>
        <p style={{ color: "#94a3b8", margin: "0 0 20px 0", fontSize: "0.9rem", maxWidth: "360px" }}>
          Tarmoq aloqasini tekshiring yoki birozdan so‘ng qayta urinib ko‘ring.
        </p>
        <button
          data-testid="auth-retry-btn"
          onClick={checkSession}
          style={{
            padding: "10px 20px",
            backgroundColor: "#3b82f6",
            color: "#ffffff",
            border: "none",
            borderRadius: "6px",
            cursor: "pointer",
            fontWeight: 600,
            fontSize: "0.9rem",
          }}
        >
          Qayta urinish
        </button>
      </div>
    );
  }

  // 3. Unauthenticated or Expired state
  if (status === "unauthenticated" || status === "expired" || !user) {
    return <LoginPage />;
  }

  // 4. Authenticated state
  const handleSelectBroker = (brokerId: number) => {
    setFilterBrokerId(brokerId);
    handleSelectTab("leads");
  };

  const renderContent = () => {
    switch (currentTab) {
      case "dashboard":
        return hasPerm("dashboard.view") ? (
          <DashboardPage onNavigate={handleSelectTab} />
        ) : (
          <ForbiddenMessage />
        );
      case "properties":
        return hasPerm("properties.view") ? <PropertiesPage /> : <ForbiddenMessage />;
      case "leads":
        return hasPerm("leads.view") ? (
          <LeadsPage initialBrokerId={filterBrokerId} />
        ) : (
          <ForbiddenMessage />
        );
      case "viewings":
        return hasPerm("viewings.view") ? <ViewingsPage /> : <ForbiddenMessage />;
      case "brokers":
        return hasPerm("brokers.view") || hasPerm("leads.assign") ? (
          <BrokersPage onSelectBroker={handleSelectBroker} />
        ) : (
          <ForbiddenMessage />
        );
      case "users":
        return hasPerm("users.view") ? <UsersPage /> : <ForbiddenMessage />;
      case "crm":
        return hasPerm("crm.view") ? <CRMPage /> : <ForbiddenMessage />;
      case "kaizen":
        return hasPerm("kaizen.view") ? <KaizenPage /> : <ForbiddenMessage />;
      case "audit":
        return hasPerm("audit.view") ? <AuditPage /> : <ForbiddenMessage />;
      case "settings":
        return <SettingsPage />;
      default:
        return <div>Sahifa topilmadi</div>;
    }
  };

  return (
    <AdminLayout currentTab={currentTab} onSelectTab={handleSelectTab}>
      <ErrorBoundary key={currentTab}>
        {renderContent()}
      </ErrorBoundary>
    </AdminLayout>
  );
};

const ForbiddenMessage: React.FC = () => (
  <div data-testid="forbidden-message" style={{ padding: "40px", textAlign: "center", color: "#f87171" }}>
    <h2>Ruxsat berilmagan (403 Forbidden)</h2>
    <p style={{ marginTop: "8px", color: "#94a3b8" }}>
      Bu bo‘limga kirish uchun ruxsatingiz yo‘q.
    </p>
  </div>
);
