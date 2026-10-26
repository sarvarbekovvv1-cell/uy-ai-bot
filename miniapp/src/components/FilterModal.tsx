import React, { useState } from "react";
import type { PropertyFilterParams } from "../types/miniapp";
import { triggerHaptic } from "../telegram/webapp";

interface FilterModalProps {
  isOpen: boolean;
  onClose: () => void;
  filters: PropertyFilterParams;
  onApply: (newFilters: PropertyFilterParams) => void;
}

const DISTRICTS = [
  "Barchasi",
  "Yunusobod",
  "Chilonzor",
  "Mirzo Ulug‘bek",
  "Yakkasaroy",
  "Mirobod",
  "Shayxontohur",
  "Olmazor",
  "Uchtepa",
  "Yashnobod",
  "Sergeli",
  "Bektemir",
  "Yangihayot",
];

export const FilterModal: React.FC<FilterModalProps> = ({
  isOpen,
  onClose,
  filters,
  onApply,
}) => {
  const [dealType, setDealType] = useState<"sale" | "rent" | "">(filters.deal_type || "");
  const [propertyType, setPropertyType] = useState<string>(filters.property_type || "");
  const [rooms, setRooms] = useState<number | undefined>(filters.rooms);
  const [minPrice, setMinPrice] = useState<string>(
    filters.min_price ? String(filters.min_price) : ""
  );
  const [maxPrice, setMaxPrice] = useState<string>(
    filters.max_price ? String(filters.max_price) : ""
  );
  const [district, setDistrict] = useState<string>(filters.district || "Barchasi");

  if (!isOpen) return null;

  const handleApply = () => {
    triggerHaptic("medium");
    onApply({
      deal_type: dealType ? dealType : undefined,
      property_type: propertyType ? propertyType : undefined,
      rooms: rooms && rooms > 0 ? rooms : undefined,
      min_price: minPrice ? Number(minPrice) : undefined,
      max_price: maxPrice ? Number(maxPrice) : undefined,
      district: district && district !== "Barchasi" ? district : undefined,
    });
    onClose();
  };

  const handleReset = () => {
    setDealType("");
    setPropertyType("");
    setRooms(undefined);
    setMinPrice("");
    setMaxPrice("");
    setDistrict("Barchasi");
    onApply({});
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">Qidiruv filtrlari</div>
          <button className="close-btn" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="form-group">
          <label className="form-label">Bitim turi</label>
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              type="button"
              className={`header-btn ${dealType === "" ? "active" : ""}`}
              style={{
                flex: 1,
                justifyContent: "center",
                backgroundColor: dealType === "" ? "var(--btn-color)" : "var(--secondary-bg)",
                color: dealType === "" ? "var(--btn-text-color)" : "var(--text-color)",
              }}
              onClick={() => setDealType("")}
            >
              Barchasi
            </button>
            <button
              type="button"
              className={`header-btn ${dealType === "sale" ? "active" : ""}`}
              style={{
                flex: 1,
                justifyContent: "center",
                backgroundColor: dealType === "sale" ? "var(--btn-color)" : "var(--secondary-bg)",
                color: dealType === "sale" ? "var(--btn-text-color)" : "var(--text-color)",
              }}
              onClick={() => setDealType("sale")}
            >
              Sotuv
            </button>
            <button
              type="button"
              className={`header-btn ${dealType === "rent" ? "active" : ""}`}
              style={{
                flex: 1,
                justifyContent: "center",
                backgroundColor: dealType === "rent" ? "var(--btn-color)" : "var(--secondary-bg)",
                color: dealType === "rent" ? "var(--btn-text-color)" : "var(--text-color)",
              }}
              onClick={() => setDealType("rent")}
            >
              Ijara
            </button>
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">Mulk turi</label>
          <select
            className="form-select"
            value={propertyType}
            onChange={(e) => setPropertyType(e.target.value)}
          >
            <option value="">Barchasi</option>
            <option value="apartment">Kvartira</option>
            <option value="house">Hovli / Uy</option>
            <option value="commercial">Tijorat maydoni</option>
            <option value="land">Yer uchastkasi</option>
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Xonalar soni</label>
          <div style={{ display: "flex", gap: "6px" }}>
            {[1, 2, 3, 4, 5].map((num) => (
              <button
                key={num}
                type="button"
                className="header-btn"
                style={{
                  flex: 1,
                  justifyContent: "center",
                  backgroundColor: rooms === num ? "var(--btn-color)" : "var(--secondary-bg)",
                  color: rooms === num ? "var(--btn-text-color)" : "var(--text-color)",
                }}
                onClick={() => setRooms(rooms === num ? undefined : num)}
              >
                {num === 5 ? "5+" : num}
              </button>
            ))}
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">Narx oralig‘i (USD)</label>
          <div style={{ display: "flex", gap: "8px" }}>
            <input
              type="number"
              placeholder="Dan"
              className="form-input"
              value={minPrice}
              onChange={(e) => setMinPrice(e.target.value)}
            />
            <input
              type="number"
              placeholder="Gacha"
              className="form-input"
              value={maxPrice}
              onChange={(e) => setMaxPrice(e.target.value)}
            />
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">Tuman</label>
          <select
            className="form-select"
            value={district}
            onChange={(e) => setDistrict(e.target.value)}
          >
            {DISTRICTS.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </div>

        <div className="action-buttons">
          <button className="secondary-btn" onClick={handleReset}>
            Tozalash
          </button>
          <button className="primary-btn" onClick={handleApply}>
            Ko‘rsatish
          </button>
        </div>
      </div>
    </div>
  );
};
