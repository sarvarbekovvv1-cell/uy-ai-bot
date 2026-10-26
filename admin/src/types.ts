/**
 * UyAI Admin Panel TypeScript Interfaces
 */

export interface StaffUser {
  id: number;
  telegram_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  phone: string | null;
  roles: string[];
  permissions: string[];
  csrf_token?: string | null;
}

export interface LoginResponse {
  user: StaffUser;
  csrf_token: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface DashboardKPIs {
  total_properties: number;
  pending_moderation_properties: number;
  approved_properties: number;
  total_leads: number;
  active_leads: number;
  won_leads: number;
  pending_viewings: number;
  crm_failed_events: number;
  crm_pending_events: number;
}

export interface PropertyListItem {
  id: number;
  title: string | null;
  property_type: string;
  listing_type: string;
  region: string;
  district: string;
  price: number;
  currency: string;
  rooms: number;
  total_area: number;
  status: string;
  created_at: string;
  approved_at: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
}

export interface PropertyMediaItem {
  id: number;
  file_type: string;
  safe_url: string;
  is_main: boolean;
}

export interface PropertyOwnerInfo {
  id: number;
  name: string;
  phone: string | null;
}

export interface PropertyDetail extends PropertyListItem {
  description: string | null;
  address: string;
  condition: string;
  construction_type: string | null;
  has_furniture: boolean;
  cadastre_status: string;
  negotiable: boolean;
  owner: PropertyOwnerInfo | null;
  media: PropertyMediaItem[];
}

export interface UserItem {
  id: number;
  telegram_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  phone_masked: string | null;
  language: string;
  is_active: boolean;
  roles: string[];
  created_at: string;
}

export interface BrokerWorkloadItem {
  id: number;
  telegram_id: number;
  full_name: string;
  username: string | null;
  phone_masked: string | null;
  roles: string[];
  active_leads_count: number;
  pending_viewings_count: number;
}

export interface LeadItem {
  id: number;
  customer_id: number;
  customer_name: string;
  customer_phone: string | null;
  property_id: number;
  property_title: string | null;
  stage: string;
  source: string;
  broker_id: number | null;
  broker_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface LeadNoteItem {
  id: number;
  author_name: string;
  note_text: string;
  created_at: string;
}

export interface LeadEventItem {
  id: number;
  event_type: string;
  from_stage: string | null;
  to_stage: string | null;
  actor_name: string | null;
  created_at: string;
}

export interface LeadDetail extends LeadItem {
  amo_crm_lead_id: string | null;
  notes: LeadNoteItem[];
  events: LeadEventItem[];
}

export interface ViewingItem {
  id: number;
  property_id: number;
  property_title: string | null;
  customer_id: number;
  customer_name: string;
  broker_id: number | null;
  broker_name: string | null;
  request_type: string;
  preferred_date: string | null;
  preferred_time: string | null;
  status: string;
  outcome: string | null;
  rejection_reason: string | null;
  created_at: string;
}

export interface CRMOutboxEventItem {
  id: number;
  provider: string;
  event_type: string;
  entity_type: string;
  entity_id: string;
  status: string;
  attempts: number;
  max_attempts: number;
  last_error_sanitized: string | null;
  created_at: string;
  updated_at: string;
}

export interface AuditEventItem {
  id: number;
  actor_user_id: number | null;
  actor_name: string | null;
  action: string;
  entity_type: string;
  entity_id: number | null;
  metadata_sanitized: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}
