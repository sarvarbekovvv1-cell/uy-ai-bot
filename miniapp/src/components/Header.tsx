import React from "react";
import type { MiniAppUser } from "../types/miniapp";

interface HeaderProps {
  user: MiniAppUser | null;
  onOpenFilter?: () => void;
  activeFilterCount?: number;
  currentTab: "list" | "map" | "favorites" | "detail";
  onBack?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  user,
  onOpenFilter,
  activeFilterCount = 0,
  currentTab,
  onBack,
}) => {
  return (
    <header className="app-header">
      {currentTab === "detail" && onBack ? (
        <button className="header-btn" onClick={onBack}>
          ← Orqaga
        </button>
      ) : (
        <div className="brand-title">
          <span>🏠</span>
          <span>UyAI</span>
        </div>
      )}

      <div className="header-actions">
        {currentTab === "list" && onOpenFilter && (
          <button className="header-btn" onClick={onOpenFilter}>
            🔍 Filtrlar {activeFilterCount > 0 ? `(${activeFilterCount})` : ""}
          </button>
        )}
        {user && (
          <span style={{ fontSize: "12px", color: "var(--hint-color)" }}>
            {user.first_name || "Mijoz"}
          </span>
        )}
      </div>
    </header>
  );
};
