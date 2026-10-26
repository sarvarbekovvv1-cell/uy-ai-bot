import React, { useEffect, useState, useCallback, useRef } from "react";
import { api } from "../api/client";
import type {
  MiniAppPropertySummary,
  PropertyFilterParams,
} from "../types/miniapp";
import { PropertyCard } from "../components/PropertyCard";
import { FilterModal } from "../components/FilterModal";

interface ListPageProps {
  filters: PropertyFilterParams;
  onFilterChange: (filters: PropertyFilterParams) => void;
  onSelectProperty: (id: number) => void;
  isFilterOpen: boolean;
  onCloseFilter: () => void;
  onFavoritesUpdated: () => void;
}

export const ListPage: React.FC<ListPageProps> = ({
  filters,
  onFilterChange,
  onSelectProperty,
  isFilterOpen,
  onCloseFilter,
  onFavoritesUpdated,
}) => {
  const [properties, setProperties] = useState<MiniAppPropertySummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [page, setPage] = useState<number>(1);
  const [hasMore, setHasMore] = useState<boolean>(false);
  const [loadingMore, setLoadingMore] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const requestSeqRef = useRef<number>(0);

  const loadProperties = useCallback(async (pageNum: number, isInitial = false) => {
    const currentSeq = ++requestSeqRef.current;
    if (isInitial) setLoading(true);
    else setLoadingMore(true);
    setError(null);
    try {
      const res = await api.getProperties({ ...filters, page: pageNum, page_size: 10 });
      if (currentSeq !== requestSeqRef.current) return;
      if (pageNum === 1) {
        setProperties(res.items);
      } else {
        setProperties((prev) => [...prev, ...res.items]);
      }
      setHasMore(res.has_more);
      setPage(res.page);
    } catch {
      if (currentSeq !== requestSeqRef.current) return;
      setError("Mulklarni yuklashda xatolik yuz berdi");
    } finally {
      if (currentSeq === requestSeqRef.current) {
        setLoading(false);
        setLoadingMore(false);
      }
    }
  }, [filters]);

  useEffect(() => {
    loadProperties(1, true);
  }, [loadProperties]);

  const handleToggleFavorite = async (property: MiniAppPropertySummary) => {
    try {
      if (property.is_favorite) {
        await api.removeFavorite(property.id);
      } else {
        await api.addFavorite(property.id);
      }
      setProperties((prev) =>
        prev.map((p) =>
          p.id === property.id ? { ...p, is_favorite: !p.is_favorite } : p
        )
      );
      onFavoritesUpdated();
    } catch {
      // Toggle failure
    }
  };

  return (
    <div className="list-page">
      <FilterModal
        isOpen={isFilterOpen}
        onClose={onCloseFilter}
        filters={filters}
        onApply={onFilterChange}
      />

      {loading ? (
        <div className="property-feed">
          {[1, 2, 3].map((n) => (
            <div
              key={n}
              style={{
                height: "280px",
                backgroundColor: "var(--card-bg)",
                borderRadius: "12px",
                opacity: 0.6,
                animation: "pulse 1.5s infinite",
              }}
            />
          ))}
        </div>
      ) : error ? (
        <div className="empty-state">
          <div className="empty-icon">⚠️</div>
          <p>{error}</p>
          <button
            className="primary-btn"
            style={{ marginTop: "16px", maxWidth: "200px" }}
            onClick={() => loadProperties(1, true)}
          >
            Qayta urinish
          </button>
        </div>
      ) : properties.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">🏠</div>
          <h3>Mulk topilmadi</h3>
          <p style={{ marginTop: "6px", fontSize: "13px" }}>
            Tanlangan filtrlarga mos ko‘chmas mulk mavjud emas. Filtrlarni o‘zgartirib ko‘ring.
          </p>
        </div>
      ) : (
        <div className="property-feed">
          {properties.map((p) => (
            <PropertyCard
              key={p.id}
              property={p}
              onClick={() => onSelectProperty(p.id)}
              onToggleFavorite={() => handleToggleFavorite(p)}
            />
          ))}

          {hasMore && (
            <button
              className="secondary-btn"
              style={{ width: "100%", marginTop: "8px" }}
              disabled={loadingMore}
              onClick={() => loadProperties(page + 1)}
            >
              {loadingMore ? "Yuklanmoqda..." : "Yana ko‘rsatish"}
            </button>
          )}
        </div>
      )}
    </div>
  );
};
