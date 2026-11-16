/**
 * frontend/src/types/index.ts - Core TypeScript Data Definitions
 */

export interface ScoreBreakdown {
  service_relevance?: number;
  buying_intent?: number;
  requirement_clarity?: number;
  specific_features?: number;
  timeline_urgency?: number;
  [key: string]: number | undefined;
}

export interface Lead {
  id: number;
  business_name: string;
  requirement: string;
  source_name: string;
  source_url?: string;
  source_title?: string;
  publication_date?: string;
  location?: string;
  date_found?: string;
  category: string;
  buying_intent: 'Active' | 'Potential' | 'Unclear' | string;
  relevance: 'Relevant' | 'Not Relevant' | 'Pending' | string;
  summary?: string;
  evidence?: string;
  lead_score: number;
  priority: 'High' | 'Medium' | 'Low' | string;
  score_breakdown?: ScoreBreakdown;
  score_explanation?: string;
  status: 'processed' | 'unprocessed' | 'failed' | string;
  error_message?: string;
  is_exported: number;
  exported_at?: string;
  record_type?: 'live_discovery' | 'official_tender' | 'uploaded' | 'demo' | 'sample' | string;
  verification_status?:
    | 'official_tender'
    | 'source_domain_confirmed_tender_unverified'
    | 'unverified'
    | 'demo'
    | 'verified'
    | string;
  is_live_discovery?: boolean;
  provider_name?: string;
  source_domain?: string;
  discovered_at?: string;
  evidence_text?: string;
  search_query?: string;
  verified_at?: string;
  verification_notes?: string;
  created_at?: string;
  analyzed_at?: string;
  source_fetch_status?: string;
  source_page_type?: 'buyer_procurement' | 'seller_agency' | 'portfolio' | 'directory' | 'unknown' | string;
  source_verified_at?: string;
  source_evidence_snippet?: string;
}

export interface ServiceCategoryBreakdown {
  service_category: string;
  total_leads: number;
  high_priority_leads: number;
  medium_priority_leads: number;
  low_priority_leads: number;
}

export interface HighPriorityOpportunity {
  id: number;
  business_name: string;
  category: string;
  buying_intent: string;
  lead_score: number;
  relevance: string;
  priority: string;
  location?: string;
  date_found?: string;
  is_exported?: number;
  summary?: string;
}

export interface DashboardMetrics {
  total_records: number;
  processed_records: number;
  unprocessed_records: number;
  failed_records: number;
  relevant_opportunities: number;
  high_priority_leads: number;
  medium_priority_leads: number;
  low_priority_leads: number;
  active_intent_leads: number;
  potential_intent_leads: number;
  unclear_intent_leads: number;
  not_yet_exported: number;
  exported_leads?: number;
  verified_leads?: number;
  unverified_leads?: number;
  demo_leads?: number;
  discovered_leads?: number;
  category_counts: Record<string, number>;
  priority_counts: Record<string, number>;
  intent_counts: Record<string, number>;
  service_breakdown?: ServiceCategoryBreakdown[];
  high_priority_opportunities?: HighPriorityOpportunity[];
}

export interface HealthStatus {
  status: string;
  app_name: string;
  version: string;
  database_type: string;
  ai_providers: {
    openai_configured: boolean;
    gemini_configured: boolean;
    fallback_nlp_ready: boolean;
    active_preferred: string;
  };
  discovery?: {
    live_search_configured: boolean;
    provider?: string;
    active_provider?: string;
    configured_preference?: string;
    tavily_configured?: boolean;
    serper_configured?: boolean;
    operational?: boolean;
    live_search_executed?: boolean;
    mode: string;
    providers?: Record<string, any>;
  };
  stats: {
    total_records: number;
    processed_records: number;
    unprocessed_records: number;
  };
}

export interface DiscoveryQuery {
  location: string;
  category: string;
  service: string;
  auto_ingest?: boolean;
  auto_analyze?: boolean;
  limit?: number;
}

export interface DiscoveredLead {
  business_name: string;
  location: string;
  category: string;
  service: string;
  requirement: string;
  source_name: string;
  source_url: string;
  source_title?: string;
  publication_date?: string;
  date_found: string;
  verification_status?:
    | 'official_tender'
    | 'source_domain_confirmed_tender_unverified'
    | 'unverified'
    | 'demo'
    | 'verified'
    | string;
  verification_notes?: string;
  verified_at?: string;
  record_type?: 'live_discovery' | 'official_tender' | 'uploaded' | 'demo' | 'sample' | string;
  is_live_discovery?: boolean;
  provider_name?: string;
  source_domain?: string;
  discovered_at?: string;
  evidence_text?: string;
  search_query?: string;
  buying_intent?: string;
  relevance?: string;
  discovery_provider?: string;
  ingest_status?: 'ingested' | 'already_exists' | 'unprocessed' | string;
  id?: number;
  existing_lead_id?: number;
  lead_score?: number;
  priority?: string;
  score_breakdown?: any;
  score_explanation?: any;
  summary?: string;
  evidence?: string;
  analysis_status?: string;
  analysis_error?: string;
  source_fetch_status?: string;
  source_page_type?: string;
  source_verified_at?: string;
  source_evidence_snippet?: string;
}

export interface DiscoveryResult {
  candidates: DiscoveredLead[];
  stats: {
    mode?: 'static_benchmark' | 'live_search' | string;
    is_live_discovery?: boolean;
    live_provider_connected?: boolean;
    active_provider?: string;
    credit_exhausted?: boolean;
    notice?: string;
    query: {
      location: string;
      category: string;
      service: string;
    };
    total_matches: number;
    raw_results_count?: number;
    relevant_count?: number;
    unqualified_count?: number;
    unqualified_sample?: Array<{
      url: string;
      title: string;
      domain: string;
      organisation?: string;
      classification?: string;
      reason: string;
      evidence_snippet?: string;
    }>;
    queries_executed?: string[];
    search_query?: string;
    newly_ingested: number;
    duplicates_skipped: number;
    provider: string;
    status?: 'matches_found' | 'no_matches';
    message?: string;
    suggestions?: string[];
    auto_analyzed?: number;
  };
}

export interface LeadFilterState {
  search: string;
  category: string;
  priority: string;
  buying_intent: string;
  relevance: string;
  status: string;
  is_exported: string;
  record_type?: string;
  verification_status?: string;
  source_page_type?: string;
  is_live_discovery?: string;
  live_only?: boolean;
  order_by: string;
  page: number;
  page_size: number;
}
