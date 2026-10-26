/**
 * UyAI Mini App API Client
 */

import { getInitData } from "../telegram/webapp";
import type {
  MiniAppBrokerContactInput,
  MiniAppBrokerContactResponse,
  MiniAppFavoriteResponse,
  MiniAppMapProperty,
  MiniAppPropertyDetail,
  MiniAppPropertyListResponse,
  MiniAppPropertySummary,
  MiniAppUser,
  MiniAppViewingRequestInput,
  MiniAppViewingRequestResponse,
  PropertyFilterParams,
} from "../types/miniapp";

const API_BASE = "/api/miniapp/v1";

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, message: string, data?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const initData = getInitData();
  const headers = new Headers(options.headers || {});

  // Bypass localtunnel reminder screen
  headers.set("Bypass-Tunnel-Reminder", "true");

  if (initData) {
    headers.set("Authorization", `tma ${initData}`);
    headers.set("X-Telegram-Init-Data", initData);
  } else {
    // Development fallback header when testing directly in browser outside Telegram
    headers.set("X-Dev-Telegram-Id", "1");
  }

  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`;
    let data: unknown = null;
    try {
      data = await response.json();
      if (typeof data === "object" && data !== null && "detail" in data) {
        errorDetail = String((data as { detail: unknown }).detail);
      }
    } catch {
      // Body not JSON
    }
    throw new ApiError(response.status, errorDetail, data);
  }

  return (await response.json()) as T;
}

export const api = {
  getMe: (): Promise<MiniAppUser> => request<MiniAppUser>("/me"),

  getProperties: (params: PropertyFilterParams = {}): Promise<MiniAppPropertyListResponse> => {
    const searchParams = new URLSearchParams();
    if (params.deal_type) {
      searchParams.set("listing_type", params.deal_type);
      searchParams.set("deal_type", params.deal_type);
    }
    if (params.property_type) searchParams.set("property_type", params.property_type);
    if (params.rooms !== undefined && params.rooms > 0)
      searchParams.set("rooms", String(params.rooms));
    if (params.min_price !== undefined) searchParams.set("min_price", String(params.min_price));
    if (params.max_price !== undefined) searchParams.set("max_price", String(params.max_price));
    if (params.district) searchParams.set("district", params.district);
    if (params.page !== undefined) searchParams.set("page", String(params.page));
    if (params.page_size !== undefined) searchParams.set("page_size", String(params.page_size));

    const qs = searchParams.toString();
    return request<MiniAppPropertyListResponse>(`/properties${qs ? `?${qs}` : ""}`);
  },

  getPropertyDetail: (id: number): Promise<MiniAppPropertyDetail> =>
    request<MiniAppPropertyDetail>(`/properties/${id}`),

  getFavorites: (): Promise<MiniAppPropertySummary[]> =>
    request<MiniAppPropertySummary[]>("/favorites"),

  addFavorite: (propertyId: number): Promise<MiniAppFavoriteResponse> =>
    request<MiniAppFavoriteResponse>(`/favorites/${propertyId}`, { method: "POST" }),

  removeFavorite: (propertyId: number): Promise<MiniAppFavoriteResponse> =>
    request<MiniAppFavoriteResponse>(`/favorites/${propertyId}`, { method: "DELETE" }),

  getMapProperties: (bounds?: {
    min_lat?: number;
    max_lat?: number;
    min_lng?: number;
    max_lng?: number;
  }): Promise<MiniAppMapProperty[]> => {
    const searchParams = new URLSearchParams();
    if (bounds?.min_lat !== undefined) searchParams.set("min_lat", String(bounds.min_lat));
    if (bounds?.max_lat !== undefined) searchParams.set("max_lat", String(bounds.max_lat));
    if (bounds?.min_lng !== undefined) searchParams.set("min_lng", String(bounds.min_lng));
    if (bounds?.max_lng !== undefined) searchParams.set("max_lng", String(bounds.max_lng));

    const qs = searchParams.toString();
    return request<MiniAppMapProperty[]>(`/map/properties${qs ? `?${qs}` : ""}`);
  },

  createViewingRequest: (
    propertyId: number,
    input: MiniAppViewingRequestInput
  ): Promise<MiniAppViewingRequestResponse> =>
    request<MiniAppViewingRequestResponse>(`/properties/${propertyId}/viewing-request`, {
      method: "POST",
      body: JSON.stringify(input),
    }),

  createBrokerContact: (
    propertyId: number,
    input: MiniAppBrokerContactInput
  ): Promise<MiniAppBrokerContactResponse> =>
    request<MiniAppBrokerContactResponse>(`/properties/${propertyId}/broker-contact`, {
      method: "POST",
      body: JSON.stringify(input),
    }),
};
