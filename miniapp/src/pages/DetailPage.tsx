import React, { useEffect, useState } from "react";
import { api } from "../api/client";
import type { MiniAppPropertyDetail } from "../types/miniapp";
import {
  formatArea,
  formatFloor,
  formatRooms,
  getConditionLabel,
  getDealTypeLabel,
  getPropertyTypeLabel,
} from "../utils/format";
import { ViewingModal } from "../components/ViewingModal";
import { BrokerContactModal } from "../components/BrokerContactModal";
import { triggerHaptic } from "../telegram/webapp";

interface DetailPageProps {
  propertyId: number;
  onFavoritesUpdated: () => void;
}

export const DetailPage: React.FC<DetailPageProps> = ({
  propertyId,
  onFavoritesUpdated,
}) => {
  const [property, setProperty] = useState<MiniAppPropertyDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [activePhotoIdx, setActivePhotoIdx] = useState<number>(0);
  const [viewingModalOpen, setViewingModalOpen] = useState<boolean>(false);
  const [brokerModalOpen, setBrokerModalOpen] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    api
      .getPropertyDetail(propertyId)
      .then((data) => {
        if (isMounted) setProperty(data);
      })
      .catch(() => {
        // Handle error
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [propertyId]);

  const handleToggleFavorite = async () => {
    if (!property) return;
    try {
      if (property.is_favorite) {
        await api.removeFavorite(property.id);
      } else {
        await api.addFavorite(property.id);
      }
      setProperty((prev) => (prev ? { ...prev, is_favorite: !prev.is_favorite } : null));
      triggerHaptic("medium");
      onFavoritesUpdated();
    } catch {
      // Toggle failure
    }
  };

  const handleActionSuccess = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 5000);
  };

  if (loading) {
    return (
      <div className="detail-container">
        <div
          style={{
            height: "240px",
            backgroundColor: "var(--card-bg)",
            borderRadius: "12px",
            marginBottom: "16px",
          }}
        />
        <div style={{ height: "30px", backgroundColor: "var(--card-bg)", width: "60%" }} />
      </div>
    );
  }

  if (!property) {
    return (
      <div className="empty-state">
        <div className="empty-icon">❌</div>
        <p>Mulk topilmadi yoki o‘chirilgan</p>
      </div>
    );
  }

  const photos =
    property.media.length > 0
      ? property.media.map((m) => m.url)
      : [property.cover_url];

  return (
    <div className="detail-container">
      {toastMessage && (
        <div
          style={{
            backgroundColor: "#d1fae5",
            color: "#065f46",
            padding: "12px 14px",
            borderRadius: "8px",
            marginBottom: "16px",
            fontSize: "14px",
            fontWeight: 600,
          }}
        >
          ✅ {toastMessage}
        </div>
      )}

      {/* Gallery */}
      <div className="detail-gallery">
        <img
          src={photos[activePhotoIdx]}
          alt={property.title}
          className="gallery-image"
          onError={(e) => {
            (e.target as HTMLImageElement).src =
              "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='400' height='240' fill='%23111827'><text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle' fill='%236b7280' font-size='18' font-family='sans-serif'>UyAI Rasmi</text></svg>";
          }}
        />
        <div className={`deal-badge ${property.deal_type}`}>
          {getDealTypeLabel(property.deal_type)}
        </div>
        <button className="favorite-btn" onClick={handleToggleFavorite}>
          {property.is_favorite ? "❤️" : "🤍"}
        </button>

        {photos.length > 1 && (
          <div className="gallery-count">
            {activePhotoIdx + 1} / {photos.length}
          </div>
        )}
      </div>

      {/* Photo selector thumbnails */}
      {photos.length > 1 && (
        <div
          style={{
            display: "flex",
            gap: "8px",
            overflowX: "auto",
            marginBottom: "16px",
            paddingBottom: "4px",
          }}
        >
          {photos.map((src, idx) => (
            <img
              key={idx}
              src={src}
              alt=""
              style={{
                width: "56px",
                height: "56px",
                borderRadius: "8px",
                objectFit: "cover",
                border:
                  idx === activePhotoIdx ? "2px solid var(--btn-color)" : "1px solid transparent",
                cursor: "pointer",
              }}
              onClick={() => setActivePhotoIdx(idx)}
            />
          ))}
        </div>
      )}

      <div className="detail-price">{property.price_formatted}</div>
      <h1 className="detail-title">{property.title}</h1>

      <div style={{ display: "flex", gap: "8px", marginBottom: "16px", flexWrap: "wrap" }}>
        {property.cadastre_verified && (
          <span className="badge-tag badge-verified">✓ Kadastr tasdiqlangan</span>
        )}
        <span className="badge-tag" style={{ backgroundColor: "var(--secondary-bg)" }}>
          {getPropertyTypeLabel(property.property_type)}
        </span>
      </div>

      {/* Specs Grid */}
      <div className="specs-grid">
        <div className="spec-item">
          <div className="spec-label">Xonalar</div>
          <div className="spec-value">{formatRooms(property.rooms)}</div>
        </div>
        <div className="spec-item">
          <div className="spec-label">Maydoni</div>
          <div className="spec-value">{formatArea(property.area_sqm)}</div>
        </div>
        <div className="spec-item">
          <div className="spec-label">Qavat</div>
          <div className="spec-value">{formatFloor(property.floor, property.total_floors)}</div>
        </div>
        <div className="spec-item">
          <div className="spec-label">Ta’miri</div>
          <div className="spec-value">{getConditionLabel(property.condition)}</div>
        </div>
        <div className="spec-item">
          <div className="spec-label">Jihozlari</div>
          <div className="spec-value">
            {property.furniture === true
              ? "Mavjud"
              : property.furniture === false
              ? "Yo‘q"
              : "—"}
          </div>
        </div>
        <div className="spec-item">
          <div className="spec-label">Manzil</div>
          <div className="spec-value">
            {property.district ? `${property.district}` : "Toshkent"}
          </div>
        </div>
      </div>

      {/* Description */}
      {property.description && (
        <div style={{ marginBottom: "20px" }}>
          <h3 style={{ fontSize: "15px", fontWeight: "700", marginBottom: "8px" }}>
            Tavsif
          </h3>
          <div className="detail-description">{property.description}</div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="action-buttons">
        <button
          className="secondary-btn"
          onClick={() => {
            triggerHaptic("light");
            setBrokerModalOpen(true);
          }}
        >
          👨‍💼 Broker bilan bog‘lanish
        </button>
        <button
          className="primary-btn"
          onClick={() => {
            triggerHaptic("light");
            setViewingModalOpen(true);
          }}
        >
          📅 Ko‘rishga yozilish
        </button>
      </div>

      {/* Modals */}
      <ViewingModal
        propertyId={property.id}
        isOpen={viewingModalOpen}
        onClose={() => setViewingModalOpen(false)}
        onSuccess={handleActionSuccess}
      />

      <BrokerContactModal
        propertyId={property.id}
        isOpen={brokerModalOpen}
        onClose={() => setBrokerModalOpen(false)}
        onSuccess={handleActionSuccess}
      />
    </div>
  );
};
