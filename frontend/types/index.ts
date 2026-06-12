export interface UserProfile {
  id: string
  email: string
  name: string | null
  subscription_tier: 'trial' | 'starter' | 'growth' | 'pro' | 'agency'
  subscription_status: 'trial' | 'active' | 'past_due' | 'cancelling' | 'cancelled'
  credits_balance: number
  credits_available: number
  trial_ends_at: string | null
  onboarding_completed: boolean
  store_count: number
}

export interface AuthResponse {
  user: UserProfile
  access_token: string
  refresh_token: string
  expires_in: number
}

export interface RegisterData {
  email: string
  name: string
  password: string
  timezone?: string
}

export interface Store {
  id: string
  etsy_shop_id: string
  shop_name: string
  shop_url: string | null
  icon_url: string | null
  currency_code: string
  status: string
  sync_status: 'idle' | 'syncing' | 'error' | string
  listing_count: number
  health_score: number | null
  health_computed_at: string | null
  agent_enabled: boolean
  agent_last_run_at: string | null
  last_synced_at: string | null
  created_at: string
}

export interface OAuthInitiate {
  oauth_url: string
  state: string
  expires_in: number
}

export interface ListingSummary {
  id: string
  etsy_listing_id: number
  title: string | null
  price_usd: string | null
  currency_code: string
  state: string
  main_image_url: string | null
  image_count: number
  views_count: number
  favorites_count: number
  sales_count: number
  seo_score: number | null
  image_score: number | null
  tags: string[]
  primary_category: string | null
  etsy_updated_at: string | null
  synced_at: string
}

export interface ListingsMeta {
  page: number
  per_page: number
  total: number
  total_pages: number
}

export interface ListingDetail extends ListingSummary {
  description: string | null
  materials: string[]
  original_price: string | null
  quantity: number | null
  is_customizable: boolean
  image_urls: string[]
  average_rating: string | null
  review_count: number
  seo_scored_at: string | null
  image_scored_at: string | null
  taxonomy_path: string[]
  etsy_created_at: string | null
  created_at: string
}

export interface SeoAnalysis {
  id: string
  run_id: string | null
  overall_score: number
  title_score: number | null
  tags_score: number | null
  description_score: number | null
  priority: 'critical' | 'high' | 'medium' | 'low'
  title_analysis: {
    current_title: string | null
    optimized_title: string | null
    primary_keyword: string | null
    keyword_position: string | null
    issues: string[]
    change_rationale: string | null
  }
  tags_analysis: {
    current_tags: string[]
    optimized_tags: string[]
    weak_tags: string[]
    missing_high_value_tags: string[]
    replacements: { remove: string; add: string; reason: string }[]
  }
  description_analysis: {
    issues: string[]
    recommended_additions: string[]
    first_paragraph_ok: boolean
  }
  estimated_traffic_lift_pct: number | null
  competitor_gap_summary: string | null
  from_cache: boolean
  model_used: string | null
  cost_usd: number | null
  created_at: string
}

export interface Optimization {
  id: string
  listing_id: string
  run_id: string | null
  type: 'title' | 'description' | 'tags' | 'price' | 'images'
  old_value: string | string[] | null
  new_value: string | string[]
  change_summary: string | null
  impact_estimate: Record<string, number> | null
  status: 'pending' | 'approved' | 'rejected' | 'applying' | 'applied' | 'failed'
  approved_at: string | null
  approved_by: string | null
  rejected_at: string | null
  rejection_reason: string | null
  applied_at: string | null
  etsy_update_status: string | null
  created_at: string
}

export interface AgentRunStatus {
  id: string
  store_id: string
  run_type: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress_pct: number
  current_phase: string | null
  result_summary: Record<string, unknown> | null
  error_message: string | null
  credits_reserved: number
  credits_used: number
}
