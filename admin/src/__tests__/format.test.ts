import { describe, expect, it } from "vitest";
import {
  formatPrice,
  getStageBadgeColor,
  getStatusBadgeColor,
  maskPhone,
} from "../utils/format";

describe("Admin Formatting Utilities", () => {
  it("formats prices correctly in USD and UZS", () => {
    expect(formatPrice(75000, "USD")).toBe("75,000 USD");
    expect(formatPrice(1250000000, "UZS")).toBe("1,250,000,000 UZS");
    expect(formatPrice("85000.5", "USD")).toBe("85,001 USD");
    expect(formatPrice(NaN)).toBe("0 USD");
  });

  it("masks customer and staff phone numbers correctly for privacy", () => {
    expect(maskPhone("+998901234567")).toBe("+998901 *** ** 67");
    expect(maskPhone("+998935556677")).toBe("+998935 *** ** 77");
    expect(maskPhone(null)).toBe("—");
    expect(maskPhone(undefined)).toBe("—");
    expect(maskPhone("123")).toBe("123");
  });

  it("returns distinct badge colors for lead stages", () => {
    const won = getStageBadgeColor("won");
    expect(won.text).toBe("#34d399");

    const lost = getStageBadgeColor("lost");
    expect(lost.text).toBe("#f87171");

    const nego = getStageBadgeColor("negotiation");
    expect(nego.text).toBe("#c084fc");

    const defaultColor = getStageBadgeColor("unknown_stage");
    expect(defaultColor.text).toBe("#cbd5e1");
  });

  it("returns distinct badge colors for operational statuses", () => {
    const approved = getStatusBadgeColor("approved");
    expect(approved.text).toBe("#34d399");

    const pending = getStatusBadgeColor("pending_approval");
    expect(pending.text).toBe("#fbbf24");

    const failed = getStatusBadgeColor("failed");
    expect(failed.text).toBe("#f87171");
  });
});
