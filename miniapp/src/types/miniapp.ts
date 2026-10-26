/**
 * TypeScript types matching backend schemas in app/schemas/miniapp.py
 */

export interface MiniAppUser {
  id: number;
  telegram_id: number;
  phone: string | null;
  first_name: string | null;
  last_name: string | null;
  username: string | null;
  language: string;
  role: string;
}

export interface MiniAppPropertyMedia {
  id: number;
  file_id: string;
  file_unique_id: string | null;
  media_type: string;
  order: number;
  url: string;
}

export interface MiniAppPropertySummary {
  id: number;
  title: string;
  deal_type: "sale" | "rent";
  property_type: string;
  price_usd: number;
  price_formatted: string;
  rooms: number | null;
  area_sqm: number | null;
  floor: number | null;
  total_floors: number | null;
  district: string | null;
  address: string | null;
  latitude: number | null;
  longitude: number | null;
  has_coordinates: boolean;
  is_favorite: boolean;
  cover_url: string;
  media_count: number;
  created_at: string;
}

export interface MiniAppPropertyDetail extends MiniAppPropertySummary {
  description: string | null;
  condition: string | null;
  furniture: boolean | null;
  cadastre_number: string | null;
  cadastre_verified: boolean;
  is_owner: boolean;
  media: MiniAppPropertyMedia[];
}

export interface MiniAppPropertyListResponse {
  items: MiniAppPropertySummary[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface MiniAppMapProperty {
  id: number;
  latitude: number | string;
  longitude: number | string;
  price: number | string | null;
  currency: string | null;
  rooms: number | null;
  property_type: string;
  listing_type: string;
  title: string;
  district: string | null;
  thumbnail_url: string | null;
}

export interface MiniAppFavoriteResponse {
  property_id: number;
  is_favorite: boolean;
  total_favorites: number;
  message: string;
}

export interface MiniAppViewingRequestInput {
  scheduled_date: string;
  preferred_time: string;
  customer_comment?: string | null;
}

export interface MiniAppViewingRequestResponse {
  id: number;
  property_id: number;
  customer_id: number;
  broker_id: number | null;
  scheduled_date: string;
  preferred_time: string;
  status: string;
  created_at: string;
  message: string;
}

export interface MiniAppBrokerContactInput {
  comment?: string | null;
}

export interface MiniAppBrokerContactResponse {
  lead_id: number;
  property_id: number;
  broker_id: number | null;
  status: string;
  created_at: string;
  message: string;
}

export interface PropertyFilterParams {
  deal_type?: "sale" | "rent";
  property_type?: string;
  rooms?: number;
  min_price?: number;
  max_price?: number;
  district?: string;
  page?: number;
  page_size?: number;
}
