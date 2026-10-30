/**
 * UyAI Admin API Client with CSRF token management and typed endpoints.
 */

import type {
  AuditEventItem,
  BrokerPhoneSettingItem,
  BrokerPhoneSettingUpdateInput,
  BrokerWorkloadItem,
  CRMOutboxEventItem,
  DashboardKPIs,
  KaizenCycleItem,
  KaizenOverview,
  KaizenRecommendationItem,
  LeadDetail,
  LeadItem,
  LoginResponse,
  PaginatedResponse,
  PaymentCardSettingItem,
  PaymentCardSettingUpdateInput,
  PropertyCreateInput,
  PropertyDetail,
  PropertyListItem,
  StaffUser,
  UserItem,
  ValuationOrderItem,
  ViewingItem,
} from "../types";

let currentCsrfToken: string | null = null;

export type UnauthorizedHandler = (status: number, message?: string) => void;
let onUnauthorizedCallback: UnauthorizedHandler | null = null;

export function setOnUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  onUnauthorizedCallback = handler;
}

export function setCsrfToken(token: string | null): void {
  currentCsrfToken = token;
}

export function getCsrfToken(): string | null {
  return currentCsrfToken;
}

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  isRetry = false
): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers || {});

  if (!headers.has("Content-Type") && options.body && typeof options.body === "string") {
    headers.set("Content-Type", "application/json");
  }

  // Inject CSRF token on mutating requests
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    if (currentCsrfToken) {
      headers.set("X-CSRF-Token", currentCsrfToken);
    }
  }

  let response: Response;
  try {
    response = await fetch(path, {
      ...options,
      headers,
      credentials: "include",
    });
  } catch (err) {
    throw new ApiError(
      "Server bilan bog‘lanib bo‘lmadi. Qayta urinib ko‘ring.",
      0,
      err
    );
  }

  // Handle centralized 401: clear token and notify session listener (unless it's a login attempt)
  if (response.status === 401) {
    currentCsrfToken = null;
    if (
      !path.includes("/api/admin/v1/auth/login") &&
      !path.includes("/api/admin/v1/auth/logout")
    ) {
      onUnauthorizedCallback?.(401, "Sessiya tugagan. Qayta kiring.");
    }
  }

  const contentType = response.headers.get("content-type");
  let body: unknown = null;
  if (contentType && contentType.includes("application/json")) {
    try {
      body = await response.json();
    } catch {
      body = null;
    }
  }

  // Handle 403 CSRF failure: attempt single refresh via /auth/me and retry mutating request once
  const isCsrfError =
    response.status === 403 &&
    body &&
    typeof body === "object" &&
    "detail" in body &&
    typeof (body as { detail: unknown }).detail === "string" &&
    (body as { detail: string }).detail.toLowerCase().includes("csrf");

  if (isCsrfError && !isRetry && ["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    try {
      const meRes = await fetch("/api/admin/v1/auth/me", {
        credentials: "include",
      });
      if (meRes.ok) {
        const meData = await meRes.json();
        if (meData?.csrf_token) {
          setCsrfToken(meData.csrf_token);
          return await request<T>(path, options, true);
        }
      }
    } catch {
      // Fall through to standard error throw below
    }
  }

  // Handle 429 rate limiting with friendly message
  if (response.status === 429) {
    throw new ApiError(
      "Juda ko‘p urinish. Birozdan keyin qayta urinib ko‘ring.",
      429,
      body
    );
  }

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    if (body && typeof body === "object" && "detail" in body) {
      const detail = (body as { detail: unknown }).detail;
      if (typeof detail === "string") {
        message = detail;
      } else if (Array.isArray(detail) && detail[0]?.msg) {
        message = String(detail[0].msg);
      }
    }
    throw new ApiError(message, response.status, body);
  }

  return body as T;
}

export const adminApi = {
  // --- Auth ---
  async login(username: string, password: string): Promise<LoginResponse> {
    try {
      const res = await request<LoginResponse>("/api/admin/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      setCsrfToken(res.csrf_token);
      return res;
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        throw new ApiError("Login yoki parol noto‘g‘ri.", 401, err.data);
      }
      throw err;
    }
  },

  async logout(): Promise<void> {
    try {
      await request<{ status: string }>("/api/admin/v1/auth/logout", {
        method: "POST",
      });
    } finally {
      setCsrfToken(null);
    }
  },

  async getMe(): Promise<StaffUser> {
    return request<StaffUser>("/api/admin/v1/auth/me");
  },

  async updateUsername(newUsername: string): Promise<StaffUser> {
    return request<StaffUser>("/api/admin/v1/auth/username", {
      method: "PATCH",
      body: JSON.stringify({ new_username: newUsername }),
    });
  },

  async updatePassword(
    currentPassword: string,
    newPassword: string,
    newPasswordConfirm: string
  ): Promise<{ status: string; message: string }> {
    return request<{ status: string; message: string }>("/api/admin/v1/auth/password", {
      method: "POST",
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
        new_password_confirm: newPasswordConfirm,
      }),
    });
  },

  // --- Dashboard ---
  async getDashboardKPIs(): Promise<DashboardKPIs> {
    return request<DashboardKPIs>("/api/admin/v1/dashboard/kpis");
  },

  // --- Properties ---
  async listProperties(params: {
    page?: number;
    page_size?: number;
    status?: string;
    property_type?: string;
    district?: string;
    search?: string;
    sort_by?: string;
    sort_order?: string;
  } = {}): Promise<PaginatedResponse<PropertyListItem>> {
    const q = new URLSearchParams();
    if (params.page) q.set("page", String(params.page));
    if (params.page_size) q.set("page_size", String(params.page_size));
    if (params.status) q.set("status", params.status);
    if (params.property_type) q.set("property_type", params.property_type);
    if (params.district) q.set("district", params.district);
    if (params.search) q.set("search", params.search);
    if (params.sort_by) q.set("sort_by", params.sort_by);
    if (params.sort_order) q.set("sort_order", params.sort_order);
    return request<PaginatedResponse<PropertyListItem>>(`/api/admin/v1/properties?${q.toString()}`);
  },

  async getProperty(id: number): Promise<PropertyDetail> {
    return request<PropertyDetail>(`/api/admin/v1/properties/${id}`);
  },

  async approveProperty(id: number): Promise<{ status: string; message: string }> {
    return request<{ status: string; message: string }>(`/api/admin/v1/properties/${id}/approve`, {
      method: "POST",
    });
  },

  async rejectProperty(id: number, reason: string): Promise<{ status: string; message: string }> {
    return request<{ status: string; message: string }>(`/api/admin/v1/properties/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
  },

  async archiveProperty(id: number): Promise<{ status: string; message: string }> {
    return request<{ status: string; message: string }>(`/api/admin/v1/properties/${id}/archive`, {
      method: "POST",
    });
  },

  // --- Users ---
  async listUsers(params: {
    page?: number;
    page_size?: number;
    role?: string;
    search?: string;
  } = {}): Promise<PaginatedResponse<UserItem>> {
    const q = new URLSearchParams();
    if (params.page) q.set("page", String(params.page));
    if (params.page_size) q.set("page_size", String(params.page_size));
    if (params.role) q.set("role", params.role);
    if (params.search) q.set("search", params.search);
    return request<PaginatedResponse<UserItem>>(`/api/admin/v1/users?${q.toString()}`);
  },

  async updateUserRoles(userId: number, roles: string[]): Promise<UserItem> {
    return request<UserItem>(`/api/admin/v1/users/${userId}/roles`, {
      method: "PUT",
      body: JSON.stringify({ roles }),
    });
  },

  // --- Brokers ---
  async listBrokers(): Promise<BrokerWorkloadItem[]> {
    return request<BrokerWorkloadItem[]>("/api/admin/v1/brokers");
  },

  // --- Leads ---
  async listLeads(params: {
    page?: number;
    page_size?: number;
    stage?: string;
    broker_id?: number;
    search?: string;
  } = {}): Promise<PaginatedResponse<LeadItem>> {
    const q = new URLSearchParams();
    if (params.page) q.set("page", String(params.page));
    if (params.page_size) q.set("page_size", String(params.page_size));
    if (params.stage) q.set("stage", params.stage);
    if (params.broker_id) q.set("broker_id", String(params.broker_id));
    if (params.search) q.set("search", params.search);
    return request<PaginatedResponse<LeadItem>>(`/api/admin/v1/leads?${q.toString()}`);
  },

  async getLead(id: number): Promise<LeadDetail> {
    return request<LeadDetail>(`/api/admin/v1/leads/${id}`);
  },

  async updateLeadStage(id: number, target_stage: string): Promise<{ status: string; stage: string }> {
    return request<{ status: string; stage: string }>(`/api/admin/v1/leads/${id}/stage`, {
      method: "PATCH",
      body: JSON.stringify({ target_stage }),
    });
  },

  async assignLead(id: number, broker_user_id: number): Promise<{ status: string; broker_id: number }> {
    return request<{ status: string; broker_id: number }>(`/api/admin/v1/leads/${id}/assign`, {
      method: "POST",
      body: JSON.stringify({ broker_user_id }),
    });
  },

  async addLeadNote(id: number, note_text: string): Promise<{ status: string; note_id: number }> {
    return request<{ status: string; note_id: number }>(`/api/admin/v1/leads/${id}/notes`, {
      method: "POST",
      body: JSON.stringify({ note_text }),
    });
  },

  // --- Viewings ---
  async listViewings(params: {
    page?: number;
    page_size?: number;
    status?: string;
    broker_id?: number;
  } = {}): Promise<PaginatedResponse<ViewingItem>> {
    const q = new URLSearchParams();
    if (params.page) q.set("page", String(params.page));
    if (params.page_size) q.set("page_size", String(params.page_size));
    if (params.status) q.set("status", params.status);
    if (params.broker_id) q.set("broker_id", String(params.broker_id));
    return request<PaginatedResponse<ViewingItem>>(`/api/admin/v1/viewings?${q.toString()}`);
  },

  async acceptViewing(id: number): Promise<{ status: string; message: string }> {
    return request<{ status: string; message: string }>(`/api/admin/v1/viewings/${id}/accept`, {
      method: "POST",
    });
  },

  async rejectViewing(id: number, reason: string): Promise<{ status: string; message: string }> {
    return request<{ status: string; message: string }>(`/api/admin/v1/viewings/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ notes: reason }),
    });
  },

  async completeViewing(id: number, outcome: string, notes?: string): Promise<{ status: string; message: string }> {
    return request<{ status: string; message: string }>(`/api/admin/v1/viewings/${id}/complete`, {
      method: "POST",
      body: JSON.stringify({ outcome, notes }),
    });
  },

  async cancelViewing(id: number, reason: string): Promise<{ status: string; message: string }> {
    return request<{ status: string; message: string }>(`/api/admin/v1/viewings/${id}/cancel`, {
      method: "POST",
      body: JSON.stringify({ notes: reason }),
    });
  },

  // --- CRM Outbox ---
  async listCRMOutbox(params: {
    page?: number;
    page_size?: number;
    status?: string;
  } = {}): Promise<PaginatedResponse<CRMOutboxEventItem>> {
    const q = new URLSearchParams();
    if (params.page) q.set("page", String(params.page));
    if (params.page_size) q.set("page_size", String(params.page_size));
    if (params.status) q.set("status", params.status);
    return request<PaginatedResponse<CRMOutboxEventItem>>(`/api/admin/v1/crm/outbox?${q.toString()}`);
  },

  async retryCRMEvent(id: number): Promise<{ status: string; message: string }> {
    return request<{ status: string; message: string }>(`/api/admin/v1/crm/outbox/${id}/retry`, {
      method: "POST",
    });
  },

  // --- Audit Trail ---
  async listAuditEvents(params: {
    page?: number;
    page_size?: number;
    action?: string;
  } = {}): Promise<PaginatedResponse<AuditEventItem>> {
    const q = new URLSearchParams();
    if (params.page) q.set("page", String(params.page));
    if (params.page_size) q.set("page_size", String(params.page_size));
    if (params.action) q.set("action", params.action);
    return request<PaginatedResponse<AuditEventItem>>(`/api/admin/v1/audit?${q.toString()}`);
  },

  // --- Property Creation (Phase 12) ---
  async uploadPropertyMedia(
    file: File
  ): Promise<{ media_unique_id: string; file_type: string; safe_url: string }> {
    return request<{ media_unique_id: string; file_type: string; safe_url: string }>(
      "/api/admin/v1/properties/upload-media",
      {
        method: "POST",
        headers: {
          "Content-Type": file.type || "image/jpeg",
        },
        body: file,
      }
    );
  },

  async createProperty(data: PropertyCreateInput): Promise<PropertyDetail> {
    return request<PropertyDetail>("/api/admin/v1/properties", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  // --- Kaizen / PDCA (Phase 12) ---
  async getKaizenOverview(params: {
    days?: number;
    date_from?: string;
    date_to?: string;
  } = {}): Promise<KaizenOverview> {
    const q = new URLSearchParams();
    if (params.days) q.set("days", String(params.days));
    if (params.date_from) q.set("date_from", params.date_from);
    if (params.date_to) q.set("date_to", params.date_to);
    return request<KaizenOverview>(`/api/admin/v1/kaizen/overview?${q.toString()}`);
  },

  async listKaizenCycles(params: {
    status?: string;
    metric_key?: string;
    page?: number;
    page_size?: number;
  } = {}): Promise<PaginatedResponse<KaizenCycleItem>> {
    const q = new URLSearchParams();
    if (params.status) q.set("status", params.status);
    if (params.metric_key) q.set("metric_key", params.metric_key);
    if (params.page) q.set("page", String(params.page));
    if (params.page_size) q.set("page_size", String(params.page_size));
    return request<PaginatedResponse<KaizenCycleItem>>(`/api/admin/v1/kaizen/cycles?${q.toString()}`);
  },

  async getKaizenCycle(id: number): Promise<KaizenCycleItem> {
    return request<KaizenCycleItem>(`/api/admin/v1/kaizen/cycles/${id}`);
  },

  async createKaizenCycle(data: {
    title: string;
    metric_key: string;
    target_value?: number;
    description?: string;
    date_from?: string;
    date_to?: string;
    plan_text?: string;
    recommendation_id?: number;
  }): Promise<KaizenCycleItem> {
    return request<KaizenCycleItem>("/api/admin/v1/kaizen/cycles", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async planKaizenCycle(
    id: number,
    data: {
      plan_text: string;
      target_value?: number;
      date_from?: string;
      date_to?: string;
    }
  ): Promise<KaizenCycleItem> {
    return request<KaizenCycleItem>(`/api/admin/v1/kaizen/cycles/${id}/plan`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async startKaizenCycle(id: number, do_text?: string): Promise<KaizenCycleItem> {
    return request<KaizenCycleItem>(`/api/admin/v1/kaizen/cycles/${id}/start`, {
      method: "POST",
      body: JSON.stringify({ do_text }),
    });
  },

  async checkKaizenCycle(
    id: number,
    check_text?: string
  ): Promise<{
    cycle: KaizenCycleItem;
    delta: number | null;
    progress_towards_target_pct: number | null;
    snapshot: Record<string, unknown>;
  }> {
    return request<{
      cycle: KaizenCycleItem;
      delta: number | null;
      progress_towards_target_pct: number | null;
      snapshot: Record<string, unknown>;
    }>(`/api/admin/v1/kaizen/cycles/${id}/check`, {
      method: "POST",
      body: JSON.stringify({ check_text }),
    });
  },

  async completeKaizenCycle(
    id: number,
    outcome: "successful" | "partially_successful" | "unsuccessful",
    act_text?: string
  ): Promise<KaizenCycleItem> {
    return request<KaizenCycleItem>(`/api/admin/v1/kaizen/cycles/${id}/complete`, {
      method: "POST",
      body: JSON.stringify({ outcome, act_text }),
    });
  },

  async cancelKaizenCycle(id: number, reason?: string): Promise<KaizenCycleItem> {
    return request<KaizenCycleItem>(`/api/admin/v1/kaizen/cycles/${id}/cancel`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
  },

  async listKaizenRecommendations(params: {
    status?: string;
    category?: string;
    page?: number;
    page_size?: number;
  } = {}): Promise<PaginatedResponse<KaizenRecommendationItem>> {
    const q = new URLSearchParams();
    if (params.status) q.set("status", params.status);
    if (params.category) q.set("category", params.category);
    if (params.page) q.set("page", String(params.page));
    if (params.page_size) q.set("page_size", String(params.page_size));
    return request<PaginatedResponse<KaizenRecommendationItem>>(
      `/api/admin/v1/kaizen/recommendations?${q.toString()}`
    );
  },

  async generateKaizenRecommendations(params: {
    date_from?: string;
    date_to?: string;
    use_ai?: boolean;
  } = {}): Promise<KaizenRecommendationItem[]> {
    return request<KaizenRecommendationItem[]>("/api/admin/v1/kaizen/recommendations/generate", {
      method: "POST",
      body: JSON.stringify(params),
    });
  },

  async reviewKaizenRecommendation(
    id: number,
    action: "accept" | "dismiss"
  ): Promise<KaizenRecommendationItem> {
    return request<KaizenRecommendationItem>(
      `/api/admin/v1/kaizen/recommendations/${id}/review`,
      {
        method: "POST",
        body: JSON.stringify({ action }),
      }
    );
  },

  async getPaymentSettings(): Promise<PaymentCardSettingItem> {
    return request<PaymentCardSettingItem>("/api/admin/v1/payment-settings");
  },

  async updatePaymentSettings(
    data: PaymentCardSettingUpdateInput
  ): Promise<PaymentCardSettingItem> {
    return request<PaymentCardSettingItem>("/api/admin/v1/payment-settings", {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  // --- System Settings (Professional Broker Phone) ---
  async getBrokerPhone(): Promise<BrokerPhoneSettingItem> {
    return request<BrokerPhoneSettingItem>("/api/admin/v1/system-settings/broker-phone");
  },

  async updateBrokerPhone(
    data: BrokerPhoneSettingUpdateInput
  ): Promise<BrokerPhoneSettingItem> {
    return request<BrokerPhoneSettingItem>("/api/admin/v1/system-settings/broker-phone", {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  // --- Valuation Orders & Receipt Verification ---
  async listValuationOrders(params: {
    page?: number;
    page_size?: number;
    payment_status?: string;
    valuation_status?: string;
  } = {}): Promise<PaginatedResponse<ValuationOrderItem>> {
    const q = new URLSearchParams();
    if (params.page) q.set("page", String(params.page));
    if (params.page_size) q.set("page_size", String(params.page_size));
    if (params.payment_status) q.set("payment_status", params.payment_status);
    if (params.valuation_status) q.set("valuation_status", params.valuation_status);
    return request<PaginatedResponse<ValuationOrderItem>>(
      `/api/admin/v1/valuation-orders?${q.toString()}`
    );
  },

  async getValuationOrder(orderId: string): Promise<ValuationOrderItem> {
    return request<ValuationOrderItem>(`/api/admin/v1/valuation-orders/${orderId}`);
  },

  async approveValuationOrder(
    orderId: string,
    notes?: string
  ): Promise<{ status: string; order_id: string; payment_status: string }> {
    return request<{ status: string; order_id: string; payment_status: string }>(
      `/api/admin/v1/valuation-orders/${orderId}/approve`,
      {
        method: "POST",
        body: JSON.stringify({ notes }),
      }
    );
  },

  async rejectValuationOrder(
    orderId: string,
    reason: string
  ): Promise<{ status: string; order_id: string; payment_status: string }> {
    return request<{ status: string; order_id: string; payment_status: string }>(
      `/api/admin/v1/valuation-orders/${orderId}/reject`,
      {
        method: "POST",
        body: JSON.stringify({ reason }),
      }
    );
  },
};
