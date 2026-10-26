/**
 * Utility functions for UI formatting and masking in Admin Panel.
 */

export function formatPrice(price: number | string, currency: string = "USD"): string {
  const num = typeof price === "number" ? price : parseFloat(price);
  if (isNaN(num)) return `0 ${currency}`;
  return `${Math.round(num).toLocaleString("en-US")} ${currency}`;
}

export function maskPhone(phone: string | null | undefined): string {
  if (!phone) return "—";
  const clean = phone.replace(/[^\d+]/g, "");
  if (clean.length < 7) return phone;
  // +998 90 123 45 67 -> +998 90 *** ** 67
  const prefix = clean.slice(0, 7);
  const suffix = clean.slice(-2);
  return `${prefix} *** ** ${suffix}`;
}

export function getStageBadgeColor(stage: string): { bg: string; text: string } {
  switch (stage) {
    case "won":
      return { bg: "rgba(16, 185, 129, 0.2)", text: "#34d399" };
    case "lost":
      return { bg: "rgba(239, 68, 68, 0.2)", text: "#f87171" };
    case "negotiation":
      return { bg: "rgba(139, 92, 246, 0.2)", text: "#c084fc" };
    case "viewing_scheduled":
      return { bg: "rgba(6, 182, 212, 0.2)", text: "#22d3ee" };
    case "qualified":
      return { bg: "rgba(245, 158, 11, 0.2)", text: "#fbbf24" };
    case "contacted":
      return { bg: "rgba(59, 130, 246, 0.2)", text: "#93c5fd" };
    default:
      return { bg: "rgba(100, 116, 139, 0.2)", text: "#cbd5e1" };
  }
}

export function getStatusBadgeColor(status: string): { bg: string; text: string } {
  switch (status) {
    case "approved":
    case "succeeded":
    case "completed":
      return { bg: "rgba(16, 185, 129, 0.2)", text: "#34d399" };
    case "pending_approval":
    case "pending":
      return { bg: "rgba(245, 158, 11, 0.2)", text: "#fbbf24" };
    case "rejected":
    case "failed":
    case "cancelled":
      return { bg: "rgba(239, 68, 68, 0.2)", text: "#f87171" };
    default:
      return { bg: "rgba(100, 116, 139, 0.2)", text: "#cbd5e1" };
  }
}
