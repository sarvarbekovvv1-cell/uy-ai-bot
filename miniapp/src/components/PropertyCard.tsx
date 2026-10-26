import React from "react";
import type { MiniAppPropertySummary } from "../types/miniapp";
import { formatArea, formatFloor, formatRooms, getDealTypeLabel } from "../utils/format";
import { triggerHaptic } from "../telegram/webapp";

interface PropertyCardProps {
  property: MiniAppPropertySummary;
  onClick: () => void;
  onToggleFavorite: (e: React.MouseEvent) => void;
}

export const PropertyCard: React.FC<PropertyCardProps> = ({
  property,
  onClick,
  onToggleFavorite,
}) => {
  const handleFav = (e: React.MouseEvent) => {
    e.stopPropagation();
    triggerHaptic("medium");
    onToggleFavorite(e);
  };

  return (
    <div className="property-card" onClick={onClick}>
      <div className="card-media">
        <img
          src={property.cover_url}
          alt={property.title}
          className="card-image"
          loading="lazy"
          onError={(e) => {
            (e.target as HTMLImageElement).src =
              "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='400' height='260' fill='%23e5e7eb'><rect width='400' height='260'/><text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle' fill='%239ca3af' font-size='20' font-family='sans-serif'>UyAI</text></svg>";
          }}
        />
        <div className={`deal-badge ${property.deal_type}`}>
          {getDealTypeLabel(property.deal_type)}
        </div>
        <button
          className="favorite-btn"
          onClick={handleFav}
          aria-label={property.is_favorite ? "Remove favorite" : "Add favorite"}
        >
          {property.is_favorite ? "❤️" : "🤍"}
        </button>
      </div>

      <div className="card-body">
        <div className="card-price">{property.price_formatted}</div>
        <div className="card-title">{property.title}</div>
        <div className="card-specs">
          <span>{formatRooms(property.rooms)}</span>
          <span>•</span>
          <span>{formatArea(property.area_sqm)}</span>
          {property.floor && (
            <>
              <span>•</span>
              <span>{formatFloor(property.floor, property.total_floors)}</span>
            </>
          )}
        </div>
        <div className="card-address">
          📍 {property.district ? `${property.district}, ` : ""}
          {property.address || "Toshkent shahri"}
        </div>
      </div>
    </div>
  );
};
