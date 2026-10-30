/**
 * UyAI Admin Panel TypeScript Interfaces
 */

export type AuthStatus =
  | "checking"
  | "authenticated"
  | "unauthenticated"
  | "expired"
  | "error";

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
  living_area?: number | null;
  floor?: number | null;
  total_floors?: number | null;
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
  telegram_id?: number | null;
  full_name?: string | null;
  first_name?: string | null;
  last_name?: string | null;
  username?: string | null;
  phone_masked?: string | null;
  role?: string | null;
  roles?: string[];
  active_leads_count?: number;
  pending_viewings_count?: number;
  viewings_count?: number;
  won_leads_count?: number;
  lost_leads_count?: number;
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

// -----------------------------------------------------------------------------
// Phase 12 Types: Property Creation & Kaizen / PDCA
// -----------------------------------------------------------------------------
export interface PropertyCreateInput {
  listing_type: "sale" | "rent";
  property_type: "apartment" | "house" | "commercial" | "land";
  title?: string;
  description?: string;
  region: string;
  district: string;
  address: string;
  latitude?: number;
  longitude?: number;
  rooms: number;
  total_area: number;
  living_area?: number;
  floor?: number;
  total_floors?: number;
  condition: "new" | "renovated" | "needs_renovation" | "shell";
  construction_type?: string;
  has_furniture?: boolean;
  cadastre_status?: "available" | "not_available" | "in_process" | "unknown";
  price: number;
  currency?: "USD" | "UZS";
  negotiable?: boolean;
  auto_approve?: boolean;
  media_unique_ids?: string[];
}

export interface KaizenLeadFunnel {
  total_leads: number;
  new_leads: number;
  contacted_leads: number;
  qualified_leads: number;
  viewing_scheduled_leads: number;
  negotiation_leads: number;
  won_leads: number;
  lost_leads: number;
  active_leads: number;
  conversion_rates: {
    overall_win_rate: number | null;
    lead_to_contacted_rate: number | null;
    contacted_to_qualified_rate: number | null;
    qualified_to_viewing_rate: number | null;
    viewing_to_negotiation_rate: number | null;
    negotiation_to_won_rate: number | null;
  };
}

export interface KaizenResponseTime {
  sample_size: number;
  average_seconds: number | null;
  median_seconds: number | null;
  p90_seconds: number | null;
  average_minutes: number | null;
  median_minutes: number | null;
  p90_minutes: number | null;
  insufficient_data: boolean;
}

export interface KaizenViewingsKPI {
  total_viewings: number;
  pending: number;
  accepted: number;
  rejected: number;
  cancelled: number;
  completed: number;
  completion_rate: number | null;
  cancellation_rate: number | null;
  viewing_to_won_rate: number | null;
}

export interface KaizenPropertiesKPI {
  total_properties: number;
  approved: number;
  moderation_backlog: number;
  submitted: number;
  under_review: number;
  rejected: number;
  archived: number;
  sold: number;
  rented: number;
  by_listing_type: Record<string, number>;
  by_property_type: Record<string, number>;
  top_districts: Record<string, number>;
}

export interface KaizenBrokerPerformance {
  broker_id: number;
  name: string;
  username: string | null;
  assigned_leads: number;
  active_leads: number;
  won_leads: number;
  lost_leads: number;
  win_rate: number | null;
  completed_viewings: number;
  overdue_followups: number;
}

export interface KaizenBrokersKPI {
  total_active_brokers: number;
  total_overdue_followups: number;
  brokers: KaizenBrokerPerformance[];
}

export interface KaizenCRMHealthKPI {
  pending_events: number;
  processing_events: number;
  succeeded_events: number;
  failed_events: number;
  permanent_failed_events: number;
  sync_success_rate: number | null;
}

export interface KaizenOverview {
  date_from: string;
  date_to: string;
  lead_funnel: KaizenLeadFunnel;
  response_time: KaizenResponseTime;
  viewings: KaizenViewingsKPI;
  properties: KaizenPropertiesKPI;
  brokers: KaizenBrokersKPI;
  crm_health: KaizenCRMHealthKPI;
}

export interface KaizenCycleItem {
  id: number;
  title: string;
  description: string | null;
  status: "draft" | "planned" | "active" | "checking" | "completed" | "cancelled";
  metric_key: string;
  baseline_value: number | null;
  target_value: number | null;
  observed_value: number | null;
  unit: string;
  date_from: string | null;
  date_to: string | null;
  plan_text: string | null;
  do_text: string | null;
  check_text: string | null;
  act_text: string | null;
  baseline_snapshot_json: string | null;
  check_snapshot_json: string | null;
  outcome: "successful" | "partially_successful" | "unsuccessful" | null;
  created_by_name: string | null;
  created_at: string;
  started_at: string | null;
  checking_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
}

export interface KaizenRecommendationItem {
  id: number;
  metric_key: string;
  category: string;
  title: string;
  description: string;
  evidence_json: string;
  recommendation_text: string;
  confidence: number;
  severity: "info" | "warning" | "critical";
  status: "new" | "accepted" | "dismissed" | "converted_to_cycle";
  generated_at: string;
  reviewed_at: string | null;
  linked_cycle_id: number | null;
}

export interface PaymentCardSettingItem {
  card_number: string;
  card_holder: string;
  basic_price_uzs: number;
  standard_price_uzs: number;
  premium_price_uzs: number;
  is_active: boolean;
  updated_at: string;
}

export interface PaymentCardSettingUpdateInput {
  card_number?: string;
  card_holder?: string;
  basic_price_uzs?: number;
  standard_price_uzs?: number;
  premium_price_uzs?: number;
  is_active?: boolean;
}

export interface BrokerPhoneSettingItem {
  broker_phone: string;
  updated_at?: string | null;
}

export interface BrokerPhoneSettingUpdateInput {
  broker_phone: string;
}

export interface ValuationOrderItem {
  id: number;
  order_id: string;
  user_id: number;
  telegram_id: number;
  amount_uzs: number;
  currency: string;
  package_type: string;
  payment_provider: string | null;
  provider_trans_id: string | null;
  payment_status: "pending" | "pending_verification" | "paid" | "rejected" | "failed" | "cancelled";
  valuation_status: "pending" | "processing" | "completed" | "failed";
  receipt_file_id: string | null;
  receipt_analysis: {
    verdict?: "likely_match" | "mismatch" | "uncertain";
    amount_uzs?: number;
    transaction_id?: string | null;
    recipient_card?: string | null;
    payment_system?: string;
    notes?: string;
  } | null;
  admin_notes: string | null;
  approved_by_user_id: number | null;
  reviewed_at: string | null;
  paid_at: string | null;
  created_at: string;
}

