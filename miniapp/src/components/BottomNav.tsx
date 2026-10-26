import React from "react";
import { triggerHaptic } from "../telegram/webapp";

interface BottomNavProps {
  currentTab: "list" | "map" | "favorites";
  onTabChange: (tab: "list" | "map" | "favorites") => void;
  favoritesCount?: number;
}

export const BottomNav: React.FC<BottomNavProps> = ({
  currentTab,
  onTabChange,
  favoritesCount = 0,
}) => {
  const handleSelect = (tab: "list" | "map" | "favorites") => {
    triggerHaptic("selection");
    onTabChange(tab);
  };

  return (
    <nav className="bottom-nav">
      <button
        className={`nav-item ${currentTab === "list" ? "active" : ""}`}
        onClick={() => handleSelect("list")}
      >
        <span className="nav-icon">🏢</span>
        <span>E’lonlar</span>
      </button>

      <button
        className={`nav-item ${currentTab === "map" ? "active" : ""}`}
        onClick={() => handleSelect("map")}
      >
        <span className="nav-icon">🗺</span>
        <span>Xarita</span>
      </button>

      <button
        className={`nav-item ${currentTab === "favorites" ? "active" : ""}`}
        onClick={() => handleSelect("favorites")}
      >
        <span className="nav-icon">❤️</span>
        <span>Saqlanganlar {favoritesCount > 0 ? `(${favoritesCount})` : ""}</span>
      </button>
    </nav>
  );
};
