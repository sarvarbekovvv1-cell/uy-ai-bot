import React, { useState } from "react";
import { useAuth } from "./auth/AuthContext";
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

export const App: React.FC = () => {
  const { user, loading, hasPerm } = useAuth();
  const [currentTab, setCurrentTab] = useState<AdminTab>("dashboard");
  const [filterBrokerId, setFilterBrokerId] = useState<number | undefined>(undefined);

  if (loading) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "100vh",
          color: "#94a3b8",
          fontSize: "1rem",
        }}
      >
        Tizim ma'lumotlari tekshirilmoqda...
      </div>
    );
  }

  if (!user) {
    return <LoginPage />;
  }

  const handleSelectBroker = (brokerId: number) => {
    setFilterBrokerId(brokerId);
    setCurrentTab("leads");
  };

  const renderContent = () => {
    switch (currentTab) {
      case "dashboard":
        return hasPerm("dashboard.view") ? (
          <DashboardPage onNavigate={(tab) => setCurrentTab(tab)} />
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
        return hasPerm("leads.assign") ? (
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
    <AdminLayout currentTab={currentTab} onSelectTab={setCurrentTab}>
      {renderContent()}
    </AdminLayout>
  );
};

const ForbiddenMessage: React.FC = () => (
  <div style={{ padding: "40px", textAlign: "center", color: "#f87171" }}>
    <h2>Ruxsat berilmagan (403 Forbidden)</h2>
    <p style={{ marginTop: "8px", color: "#94a3b8" }}>
      Sizning rolingizda ushbu bo'limni ko'rish huquqi mavjud emas.
    </p>
  </div>
);
