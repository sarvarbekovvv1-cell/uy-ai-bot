import React, { useEffect, useState, useCallback } from "react";
import { Header } from "./components/Header";
import { BottomNav } from "./components/BottomNav";
import { ListPage } from "./pages/ListPage";
import { MapPage } from "./pages/MapPage";
import { DetailPage } from "./pages/DetailPage";
import { FavoritesPage } from "./pages/FavoritesPage";
import { api } from "./api/client";
import {
  getTelegramWebApp,
  initTelegramWebApp,
} from "./telegram/webapp";
import type { MiniAppUser, PropertyFilterParams } from "./types/miniapp";

export const App: React.FC = () => {
  const [tab, setTab] = useState<"list" | "map" | "favorites">("list");
  const [selectedPropertyId, setSelectedPropertyId] = useState<number | null>(null);
  const [user, setUser] = useState<MiniAppUser | null>(null);
  const [favoritesCount, setFavoritesCount] = useState<number>(0);
  const [filters, setFilters] = useState<PropertyFilterParams>({});
  const [isFilterOpen, setIsFilterOpen] = useState<boolean>(false);

  // Initialize Telegram WebApp
  useEffect(() => {
    initTelegramWebApp();
  }, []);

  // Fetch current user and favorites count
  const refreshUserAndFavorites = useCallback(() => {
    api
      .getMe()
      .then((u) => setUser(u))
      .catch(() => {
        // Dev fallback or offline
      });

    api
      .getFavorites()
      .then((favs) => setFavoritesCount(favs.length))
      .catch(() => {
        // Dev fallback
      });
  }, []);

  useEffect(() => {
    refreshUserAndFavorites();
  }, [refreshUserAndFavorites]);

  // Telegram WebApp BackButton handling
  useEffect(() => {
    const tg = getTelegramWebApp();
    if (!tg) return;

    const handleBack = () => {
      if (selectedPropertyId !== null) {
        setSelectedPropertyId(null);
      } else if (tab !== "list") {
        setTab("list");
      }
    };

    if (selectedPropertyId !== null || tab !== "list") {
      tg.BackButton.show();
      tg.BackButton.onClick(handleBack);
    } else {
      tg.BackButton.hide();
      tg.BackButton.offClick(handleBack);
    }

    return () => {
      tg.BackButton.offClick(handleBack);
    };
  }, [selectedPropertyId, tab]);

  const activeFilterCount = Object.keys(filters).filter(
    (k) => filters[k as keyof PropertyFilterParams] !== undefined
  ).length;

  return (
    <div className="app-layout">
      <Header
        user={user}
        currentTab={selectedPropertyId ? "detail" : tab}
        onOpenFilter={() => setIsFilterOpen(true)}
        activeFilterCount={activeFilterCount}
        onBack={() => setSelectedPropertyId(null)}
      />

      <main className="app-main">
        {selectedPropertyId !== null ? (
          <DetailPage
            propertyId={selectedPropertyId}
            onFavoritesUpdated={refreshUserAndFavorites}
          />
        ) : tab === "list" ? (
          <ListPage
            filters={filters}
            onFilterChange={setFilters}
            onSelectProperty={(id) => setSelectedPropertyId(id)}
            isFilterOpen={isFilterOpen}
            onCloseFilter={() => setIsFilterOpen(false)}
            onFavoritesUpdated={refreshUserAndFavorites}
          />
        ) : tab === "map" ? (
          <MapPage onSelectProperty={(id) => setSelectedPropertyId(id)} />
        ) : (
          <FavoritesPage
            onSelectProperty={(id) => setSelectedPropertyId(id)}
            onFavoritesUpdated={refreshUserAndFavorites}
          />
        )}
      </main>

      {selectedPropertyId === null && (
        <BottomNav
          currentTab={tab}
          onTabChange={(newTab) => {
            setTab(newTab);
            window.scrollTo({ top: 0, behavior: "smooth" });
          }}
          favoritesCount={favoritesCount}
        />
      )}
    </div>
  );
};
export default App;
