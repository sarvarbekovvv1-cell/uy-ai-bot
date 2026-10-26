import React, { useEffect, useState, useCallback } from "react";
import { api } from "../api/client";
import type { MiniAppPropertySummary } from "../types/miniapp";
import { PropertyCard } from "../components/PropertyCard";

interface FavoritesPageProps {
  onSelectProperty: (id: number) => void;
  onFavoritesUpdated: () => void;
}

export const FavoritesPage: React.FC<FavoritesPageProps> = ({
  onSelectProperty,
  onFavoritesUpdated,
}) => {
  const [favorites, setFavorites] = useState<MiniAppPropertySummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const loadFavorites = useCallback(async () => {
    setLoading(true);
    try {
      const items = await api.getFavorites();
      setFavorites(items);
    } catch {
      // Handle error
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadFavorites();
  }, [loadFavorites]);

  const handleToggleFavorite = async (property: MiniAppPropertySummary) => {
    try {
      await api.removeFavorite(property.id);
      setFavorites((prev) => prev.filter((p) => p.id !== property.id));
      onFavoritesUpdated();
    } catch {
      // Toggle error
    }
  };

  if (loading) {
    return (
      <div className="property-feed">
        {[1, 2].map((n) => (
          <div
            key={n}
            style={{
              height: "260px",
              backgroundColor: "var(--card-bg)",
              borderRadius: "12px",
              opacity: 0.6,
            }}
          />
        ))}
      </div>
    );
  }

  if (favorites.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon">❤️</div>
        <h3>Saqlangan uylar yo‘q</h3>
        <p style={{ marginTop: "6px", fontSize: "13px" }}>
          Sizga yoqqan e’lonlarni yurakcha tugmasini bosib saqlab qo‘yishingiz mumkin.
        </p>
      </div>
    );
  }

  return (
    <div className="property-feed">
      {favorites.map((p) => (
        <PropertyCard
          key={p.id}
          property={{ ...p, is_favorite: true }}
          onClick={() => onSelectProperty(p.id)}
          onToggleFavorite={() => handleToggleFavorite(p)}
        />
      ))}
    </div>
  );
};
