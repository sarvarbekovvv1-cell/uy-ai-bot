import { beforeEach, describe, expect, it, vi } from "vitest";
import { adminApi, setCsrfToken } from "../api/client";
import type {
  KaizenCycleItem,
  KaizenOverview,
  KaizenRecommendationItem,
} from "../types";

describe("Admin Kaizen API & Frontend Integration", () => {
  beforeEach(() => {
    setCsrfToken("test_csrf_token");
    vi.restoreAllMocks();
  });

  it("fetches kaizen overview with days and date filters", async () => {
    const mockOverview: KaizenOverview = {
      date_from: "2026-10-01T00:00:00Z",
      date_to: "2026-10-26T23:59:59Z",
      lead_funnel: {
        total_leads: 12,
        new_leads: 3,
        contacted_leads: 3,
        qualified_leads: 2,
        viewing_scheduled_leads: 2,
        negotiation_leads: 1,
        won_leads: 1,
        lost_leads: 0,
        active_leads: 11,
        conversion_rates: {
          overall_win_rate: 8.3,
          lead_to_contacted_rate: 100.0,
          contacted_to_qualified_rate: 66.7,
          qualified_to_viewing_rate: 100.0,
          viewing_to_negotiation_rate: 50.0,
          negotiation_to_won_rate: 100.0,
        },
      },
      response_time: {
        sample_size: 5,
        average_seconds: 420.0,
        median_seconds: 360.0,
        p90_seconds: 720.0,
        average_minutes: 7.0,
        median_minutes: 6.0,
        p90_minutes: 12.0,
        insufficient_data: false,
      },
      viewings: {
        total_viewings: 8,
        pending: 1,
        accepted: 1,
        rejected: 0,
        cancelled: 1,
        completed: 5,
        completion_rate: 62.5,
        cancellation_rate: 12.5,
        viewing_to_won_rate: 20.0,
      },
      properties: {
        total_properties: 20,
        approved: 15,
        moderation_backlog: 3,
        submitted: 2,
        under_review: 1,
        rejected: 2,
        archived: 0,
        sold: 0,
        rented: 0,
        by_listing_type: {},
        by_property_type: {},
        top_districts: {},
      },
      brokers: {
        total_active_brokers: 4,
        total_overdue_followups: 0,
        brokers: [],
      },
      crm_health: {
        pending_events: 0,
        processing_events: 0,
        succeeded_events: 49,
        failed_events: 1,
        permanent_failed_events: 0,
        sync_success_rate: 98.0,
      },
    };

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => mockOverview,
    });
    vi.stubGlobal("fetch", mockFetch);

    const result = await adminApi.getKaizenOverview({ days: 30 });

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [path] = mockFetch.mock.calls[0];
    expect(path).toContain("/api/admin/v1/kaizen/overview?days=30");
    expect(result.lead_funnel.total_leads).toBe(12);
    expect(result.lead_funnel.conversion_rates.overall_win_rate).toBe(8.3);
    expect(result.response_time.insufficient_data).toBe(false);
  });

  it("handles custom date range params in getKaizenOverview", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => ({
        date_from: "2026-10-01",
        date_to: "2026-10-15",
        lead_funnel: { total_leads: 0, conversion_rates: {} },
        response_time: { insufficient_data: true },
        viewings: {},
        properties: {},
        brokers: {},
        crm_health: {},
      }),
    });
    vi.stubGlobal("fetch", mockFetch);

    await adminApi.getKaizenOverview({
      date_from: "2026-10-01",
      date_to: "2026-10-15",
    });

    const [path] = mockFetch.mock.calls[0];
    expect(path).toContain("date_from=2026-10-01");
    expect(path).toContain("date_to=2026-10-15");
  });

  it("creates a new PDCA cycle via POST /kaizen/cycles with CSRF header", async () => {
    const mockCreatedCycle: KaizenCycleItem = {
      id: 101,
      title: "Improve lead conversion rate",
      description: "Focus on qualified leads",
      status: "draft",
      metric_key: "overall_win_rate",
      baseline_value: 8.5,
      target_value: 15.0,
      observed_value: null,
      unit: "%",
      date_from: null,
      date_to: null,
      plan_text: null,
      do_text: null,
      check_text: null,
      act_text: null,
      baseline_snapshot_json: null,
      check_snapshot_json: null,
      outcome: null,
      created_by_name: "Super Admin",
      created_at: "2026-10-26T16:00:00Z",
      started_at: null,
      checking_at: null,
      completed_at: null,
      cancelled_at: null,
    };

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => mockCreatedCycle,
    });
    vi.stubGlobal("fetch", mockFetch);

    const result = await adminApi.createKaizenCycle({
      title: "Improve lead conversion rate",
      metric_key: "overall_win_rate",
      target_value: 15.0,
      description: "Focus on qualified leads",
    });

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [path, init] = mockFetch.mock.calls[0];
    expect(path).toBe("/api/admin/v1/kaizen/cycles");
    expect(init.method).toBe("POST");
    expect(result.id).toBe(101);
    expect(result.baseline_value).toBe(8.5);
    expect(result.status).toBe("draft");
  });

  it("progresses cycle through PLAN -> START -> CHECK -> COMPLETE", async () => {
    const cycleMock: KaizenCycleItem = {
      id: 101,
      title: "Cycle 101",
      description: null,
      status: "planned",
      metric_key: "overall_win_rate",
      baseline_value: 10.0,
      target_value: 20.0,
      observed_value: null,
      unit: "%",
      date_from: null,
      date_to: null,
      plan_text: "Action plan",
      do_text: null,
      check_text: null,
      act_text: null,
      baseline_snapshot_json: null,
      check_snapshot_json: null,
      outcome: null,
      created_by_name: "Super Admin",
      created_at: "2026-10-26T16:00:00Z",
      started_at: null,
      checking_at: null,
      completed_at: null,
      cancelled_at: null,
    };

    const mockFetch = vi
      .fn()
      // 1. plan
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({ ...cycleMock, status: "planned" }),
      })
      // 2. start
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({ ...cycleMock, status: "active" }),
      })
      // 3. check
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({
          cycle: { ...cycleMock, status: "checking", observed_value: 18.0 },
          delta: 8.0,
          progress_towards_target_pct: 80.0,
          snapshot: {},
        }),
      })
      // 4. complete
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({ ...cycleMock, status: "completed", outcome: "successful" }),
      });

    vi.stubGlobal("fetch", mockFetch);

    // 1. plan
    const planned = await adminApi.planKaizenCycle(101, { plan_text: "Action plan" });
    expect(planned.status).toBe("planned");

    // 2. start
    const started = await adminApi.startKaizenCycle(101, "Execution started");
    expect(started.status).toBe("active");

    // 3. check
    const checked = await adminApi.checkKaizenCycle(101, "Measured at mid-sprint");
    expect(checked.cycle.status).toBe("checking");
    expect(checked.delta).toBe(8.0);
    expect(checked.progress_towards_target_pct).toBe(80.0);

    // 4. complete
    const completed = await adminApi.completeKaizenCycle(101, "successful", "Standardized");
    expect(completed.status).toBe("completed");
    expect(completed.outcome).toBe("successful");
  });

  it("handles recommendation generation and review", async () => {
    const mockRecs: KaizenRecommendationItem[] = [
      {
        id: 50,
        category: "conversion",
        title: "Lid konversiyasini oshirish",
        description: "Win rate 8.3%",
        evidence_json: "{}",
        recommendation_text: "Kvalifikatsiyani kuchaytiring",
        confidence: 0.9,
        severity: "warning",
        metric_key: "overall_win_rate",
        status: "new",
        generated_at: "2026-10-26T16:00:00Z",
        reviewed_at: null,
        linked_cycle_id: null,
      },
    ];

    const mockFetch = vi
      .fn()
      // generate
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => mockRecs,
      })
      // review
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({ ...mockRecs[0], status: "accepted" }),
      });

    vi.stubGlobal("fetch", mockFetch);

    const generated = await adminApi.generateKaizenRecommendations({ use_ai: true });
    expect(generated.length).toBe(1);
    expect(generated[0].metric_key).toBe("overall_win_rate");

    const reviewed = await adminApi.reviewKaizenRecommendation(50, "accept");
    expect(reviewed.status).toBe("accepted");
  });
});
