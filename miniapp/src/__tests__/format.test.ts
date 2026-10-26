import { describe, it, expect } from "vitest";
import {
  DEFAULT_TILE_URL,
  formatArea,
  formatFloor,
  formatPrice,
  formatPropertyPrice,
  formatRooms,
  getConditionLabel,
  getDealTypeLabel,
  getMapTileConfig,
  getPropertyTypeLabel,
  isValidCoordinate,
} from "../utils/format";

describe("format utilities & price formatting", () => {
  it("formats USD prices from numbers and backend Decimal strings correctly", () => {
    // Exact examples from spec
    expect(formatPropertyPrice(75000, "USD")).toBe("$75 000");
    expect(formatPropertyPrice("75000.00", "USD")).toBe("$75 000");
    expect(formatPropertyPrice(120000, "USD")).toBe("$120 000");
    expect(formatPropertyPrice("120000", "USD")).toBe("$120 000");
    expect(formatPropertyPrice("92000.00", "USD")).toBe("$92 000");
  });

  it("formats UZS prices from numbers and backend Decimal strings correctly", () => {
    // Exact examples from spec: 850000000 → 850 mln so‘m
    expect(formatPropertyPrice(850000000, "UZS")).toBe("850 mln so‘m");
    expect(formatPropertyPrice("850000000.00", "UZS")).toBe("850 mln so‘m");
    expect(formatPropertyPrice(1500000000, "UZS")).toBe("1.5 mlrd so‘m");
    expect(formatPropertyPrice("2000000000.00", "UZS")).toBe("2 mlrd so‘m");
    expect(formatPropertyPrice(450000, "UZS")).toBe("450 000 so‘m");
  });

  it("gracefully falls back on missing, null, undefined, empty, or NaN prices", () => {
    expect(formatPropertyPrice(null)).toBe("Narx ko‘rsatilmagan");
    expect(formatPropertyPrice(undefined)).toBe("Narx ko‘rsatilmagan");
    expect(formatPropertyPrice("")).toBe("Narx ko‘rsatilmagan");
    expect(formatPropertyPrice("   ")).toBe("Narx ko‘rsatilmagan");
    expect(formatPropertyPrice("NaN")).toBe("Narx ko‘rsatilmagan");
    expect(formatPropertyPrice(NaN)).toBe("Narx ko‘rsatilmagan");
    expect(formatPropertyPrice("invalid_string")).toBe("Narx ko‘rsatilmagan");
    expect(formatPropertyPrice(-500)).toBe("Narx ko‘rsatilmagan");

    // Must never return undefined, NaN, or [object Object]
    const outputs = [
      formatPropertyPrice(null),
      formatPropertyPrice(undefined),
      formatPropertyPrice(""),
      formatPropertyPrice(NaN),
    ];
    for (const out of outputs) {
      expect(out).not.toContain("undefined");
      expect(out).not.toContain("NaN");
      expect(out).not.toContain("[object Object]");
    }
  });

  it("handles unknown or missing currency safely", () => {
    expect(formatPropertyPrice(50000, null)).toBe("$50 000");
    expect(formatPropertyPrice(50000, undefined)).toBe("$50 000");
    expect(formatPropertyPrice(50000, "EUR")).toBe("50 000 EUR");
  });

  it("retains backward-compatible formatPrice helper", () => {
    expect(formatPrice(75000)).toBe("$75 000");
  });

  it("formats area in sqm", () => {
    expect(formatArea(85.5)).toBe("85.5 m²");
    expect(formatArea(null)).toBe("—");
  });

  it("formats rooms", () => {
    expect(formatRooms(3)).toBe("3 xona");
    expect(formatRooms(null)).toBe("—");
  });

  it("formats floor info", () => {
    expect(formatFloor(4, 9)).toBe("4/9-qavat");
    expect(formatFloor(2, null)).toBe("2-qavat");
    expect(formatFloor(null, null)).toBe("—");
  });

  it("formats deal type labels", () => {
    expect(getDealTypeLabel("sale")).toBe("Sotuv");
    expect(getDealTypeLabel("rent")).toBe("Ijara");
  });

  it("formats property type labels", () => {
    expect(getPropertyTypeLabel("apartment")).toBe("Kvartira");
    expect(getPropertyTypeLabel("house")).toBe("Hovli / Uy");
    expect(getPropertyTypeLabel("commercial")).toBe("Tijorat maydoni");
    expect(getPropertyTypeLabel("land")).toBe("Yer uchastkasi");
  });

  it("formats condition labels", () => {
    expect(getConditionLabel("euro")).toBe("Yevro ta’mir");
    expect(getConditionLabel("rough")).toBe("Qora suvoq");
    expect(getConditionLabel(null)).toBe("—");
  });
});

describe("coordinate validation", () => {
  it("accepts valid numeric coordinates in range", () => {
    expect(isValidCoordinate(41.2995, 69.2401)).toBe(true);
    expect(isValidCoordinate(0, 0)).toBe(true);
    expect(isValidCoordinate(-90, -180)).toBe(true);
    expect(isValidCoordinate(90, 180)).toBe(true);
  });

  it("accepts valid string decimal coordinates from API", () => {
    expect(isValidCoordinate("41.2995000", "69.2401000")).toBe(true);
  });

  it("rejects missing, null, undefined, NaN, and invalid coordinates", () => {
    expect(isValidCoordinate(null, 69.24)).toBe(false);
    expect(isValidCoordinate(41.29, null)).toBe(false);
    expect(isValidCoordinate(undefined, undefined)).toBe(false);
    expect(isValidCoordinate("", "")).toBe(false);
    expect(isValidCoordinate("NaN", "69.24")).toBe(false);
    expect(isValidCoordinate(NaN, 69.24)).toBe(false);
    expect(isValidCoordinate(95, 69.24)).toBe(false); // lat > 90
    expect(isValidCoordinate(-91, 69.24)).toBe(false); // lat < -90
    expect(isValidCoordinate(41.29, 185)).toBe(false); // lng > 180
    expect(isValidCoordinate(41.29, -185)).toBe(false); // lng < -180
  });
});

describe("map tile configuration", () => {
  it("provides default OpenStreetMap tile URL and valid attribution", () => {
    const config = getMapTileConfig();
    expect(config.url).toBe(DEFAULT_TILE_URL);
    expect(config.url).toContain("tile.openstreetmap.org");
    expect(config.attribution).toContain("OpenStreetMap");

    // Prove default tile URL does not contain secrets or placeholders
    expect(config.url).not.toContain("API_KEY");
    expect(config.url).not.toContain("YOUR_API_KEY");
    expect(config.url).not.toContain("undefined");
    expect(config.url).not.toContain("placeholder");
  });
});
