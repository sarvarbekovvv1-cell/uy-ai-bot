/**
 * UyAI Admin API Client with CSRF token management and typed endpoints.
 */

import type {
  AuditEventItem,
  BrokerWorkloadItem,
  CRMOutboxEventItem,
  DashboardKPIs,
  LeadDetail,
  LeadItem,
  LoginResponse,
  PaginatedResponse,
  PropertyDetail,
  PropertyListItem,
  StaffUser,
  UserItem,
  ViewingItem,
} from "../types";

let currentCsrfToken: string | null = null;

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

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
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

  const response = await fetch(path, {
    ...options,
    headers,
    credentials: "include",
  });

  if (response.status === 401) {
    currentCsrfToken = null;
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
    const res = await request<LoginResponse>("/api/admin/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    setCsrfToken(res.csrf_token);
    return res;
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
};
