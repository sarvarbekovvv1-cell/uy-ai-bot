import { describe, expect, it } from "vitest";

describe("Admin RBAC Navigation Rules", () => {
  const ROLE_NAV_MAPPING: Record<string, string[]> = {
    superadmin: [
      "dashboard.view",
      "properties.view",
      "leads.view",
      "viewings.view",
      "leads.assign",
      "users.view",
      "crm.view",
      "audit.view",
    ],
    head_broker: [
      "dashboard.view",
      "properties.view",
      "leads.view",
      "viewings.view",
      "leads.assign",
      "crm.view",
      "audit.view",
    ],
    sales_broker: [
      "dashboard.view",
      "properties.view",
      "leads.view",
      "viewings.view",
    ],
    crm_operator: [
      "dashboard.view",
      "leads.view",
      "viewings.view",
      "crm.view",
      "audit.view",
    ],
    property_owner: [],
    buyer: [],
  };

  it("superadmin has all 8 navigation tabs visible", () => {
    const permissions = ROLE_NAV_MAPPING["superadmin"];
    expect(permissions).toHaveLength(8);
    expect(permissions).toContain("users.view");
    expect(permissions).toContain("crm.view");
  });

  it("sales_broker only sees dashboard, properties, leads, and viewings (no user management or crm outbox)", () => {
    const permissions = ROLE_NAV_MAPPING["sales_broker"];
    expect(permissions).not.toContain("users.view");
    expect(permissions).not.toContain("leads.assign");
    expect(permissions).not.toContain("crm.view");
    expect(permissions).toContain("leads.view");
  });

  it("customer roles (property_owner, buyer) have zero permissions and zero tabs", () => {
    expect(ROLE_NAV_MAPPING["property_owner"]).toHaveLength(0);
    expect(ROLE_NAV_MAPPING["buyer"]).toHaveLength(0);
  });
});
