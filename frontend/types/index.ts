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
