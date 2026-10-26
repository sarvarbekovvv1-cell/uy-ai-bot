/**
 * Utility functions for formatting numbers, currency, dates, labels, coordinates, and map configs
 */

export const DEFAULT_TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
export const DEFAULT_TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

export function getMapTileConfig(): { url: string; attribution: string } {
  const customUrl =
    typeof import.meta !== "undefined" && import.meta.env?.VITE_MAP_TILE_URL;
  const customAttribution =
    typeof import.meta !== "undefined" && import.meta.env?.VITE_MAP_TILE_ATTRIBUTION;

  return {
    url:
      customUrl && typeof customUrl === "string" && customUrl.trim() !== ""
        ? customUrl.trim()
        : DEFAULT_TILE_URL,
    attribution:
      customAttribution &&
      typeof customAttribution === "string" &&
      customAttribution.trim() !== ""
        ? customAttribution.trim()
        : DEFAULT_TILE_ATTRIBUTION,
  };
}

/**
 * Safely format property price for USD and UZS currencies.
 * Handles Decimal strings ("75000.00"), numbers (75000), null, undefined, NaN.
 * Never returns undefined, NaN, or [object Object].
 */
export function formatPropertyPrice(
  price: number | string | null | undefined,
  currency: string | null | undefined = "USD"
): string {
  if (price === null || price === undefined) {
    return "Narx ko‘rsatilmagan";
  }

  const str = String(price).trim();
  if (
    str === "" ||
    str.toLowerCase() === "nan" ||
    str.toLowerCase() === "null" ||
    str.toLowerCase() === "undefined"
  ) {
    return "Narx ko‘rsatilmagan";
  }

  // Parse numeric value
  const num =
    typeof price === "number" ? price : parseFloat(str.replace(/[^\d.-]/g, ""));
  if (!Number.isFinite(num) || isNaN(num) || num < 0) {
    return "Narx ko‘rsatilmagan";
  }

  const curr = (currency || "USD").toUpperCase();

  if (curr === "UZS") {
    if (num >= 1_000_000_000) {
      const billions = num / 1_000_000_000;
      const formatted = Number.isInteger(billions)
        ? billions.toString()
        : billions.toFixed(1).replace(/\.0$/, "");
      return `${formatted} mlrd so‘m`;
    }
    if (num >= 1_000_000) {
      const millions = num / 1_000_000;
      const formatted = Number.isInteger(millions)
        ? millions.toString()
        : millions.toFixed(1).replace(/\.0$/, "");
      return `${formatted} mln so‘m`;
    }
    const intStr = Math.round(num)
      .toString()
      .replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    return `${intStr} so‘m`;
  }

  // USD (and unknown currencies)
  const intVal = Math.round(num);
  const spaced = intVal.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  if (curr === "USD") {
    return `$${spaced}`;
  }
  return `${spaced} ${curr}`;
}

export function formatPrice(usd: number): string {
  return formatPropertyPrice(usd, "USD");
}

export function isValidCoordinate(lat: unknown, lng: unknown): boolean {
  if (lat === null || lat === undefined || lng === null || lng === undefined) {
    return false;
  }
  const latStr = String(lat).trim();
  const lngStr = String(lng).trim();
  if (
    latStr === "" ||
    lngStr === "" ||
    latStr.toLowerCase() === "nan" ||
    lngStr.toLowerCase() === "nan"
  ) {
    return false;
  }

  const latNum = typeof lat === "number" ? lat : parseFloat(latStr);
  const lngNum = typeof lng === "number" ? lng : parseFloat(lngStr);

  if (!Number.isFinite(latNum) || !Number.isFinite(lngNum)) {
    return false;
  }

  return latNum >= -90 && latNum <= 90 && lngNum >= -180 && lngNum <= 180;
}

export function formatArea(sqm: number | null): string {
  if (sqm === null || sqm === undefined) return "—";
  return `${sqm} m²`;
}

export function formatRooms(rooms: number | null): string {
  if (rooms === null || rooms === undefined) return "—";
  return `${rooms} xona`;
}

export function formatFloor(floor: number | null, total: number | null): string {
  if (floor === null) return "—";
  if (total) return `${floor}/${total}-qavat`;
  return `${floor}-qavat`;
}

export function getDealTypeLabel(dealType: string): string {
  return dealType === "rent" ? "Ijara" : "Sotuv";
}

export function getPropertyTypeLabel(ptype: string): string {
  switch (ptype) {
    case "apartment":
      return "Kvartira";
    case "house":
      return "Hovli / Uy";
    case "commercial":
      return "Tijorat maydoni";
    case "land":
      return "Yer uchastkasi";
    default:
      return ptype;
  }
}

export function getConditionLabel(cond: string | null): string {
  if (!cond) return "—";
  switch (cond) {
    case "euro":
      return "Yevro ta’mir";
    case "good":
      return "Yaxshi";
    case "medium":
      return "O‘rta";
    case "rough":
      return "Qora suvoq";
    case "needs_repair":
      return "Ta’mirtalab";
    default:
      return cond;
  }
}
