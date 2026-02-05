// =============================================================================
// Auth Types
// =============================================================================

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  business_name: string;
  owner_name: string;
  email: string;
  password: string;
  phone: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user_type: "owner" | "technician" | "customer";
  user_id: string;
  user_name: string;
  business_id: string;
  business_name: string;
  role?: string;
}

export interface User {
  id: string;
  name: string;
  email: string;
  role: string;
  business_id: string;
  business_name: string;
}

// =============================================================================
// Dashboard Types
// =============================================================================

export interface DashboardStats {
  total_jobs_today: number;
  pending_jobs: number;
  in_progress_jobs: number;
  completed_today: number;
  total_technicians: number;
  active_technicians: number;
  total_customers: number;
  emergency_jobs: number;
}

// =============================================================================
// Job Types
// =============================================================================

export type JobStatus =
  | "pending"
  | "scheduled"
  | "dispatched"
  | "en_route"
  | "in_progress"
  | "completed"
  | "cancelled"
  | "awaiting_parts";

export type JobPriority = "low" | "normal" | "urgent" | "emergency";

export interface Job {
  id: string;
  confirmation_code: string;
  status: JobStatus;
  priority: JobPriority;
  service_type: string;
  description: string | null;
  customer_name: string | null;
  customer_phone: string | null;
  address: string | null;
  technician_name: string | null;
  technician_id: string | null;
  scheduled_date: string | null;
  scheduled_time_start: string | null;
  scheduled_time_end: string | null;
  created_at: string;
}

export interface JobFilters {
  status?: JobStatus;
  priority?: JobPriority;
  technician_id?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

// =============================================================================
// Technician Types
// =============================================================================

export interface Technician {
  id: string;
  name: string;
  phone: string;
  email: string | null;
  is_active: boolean;
  is_on_call: boolean;
  current_job_count: number;
}

export interface TechnicianCreate {
  name: string;
  email: string;
  phone: string;
  password: string;
}

// =============================================================================
// Customer Types
// =============================================================================

export interface Customer {
  id: string;
  name: string | null;
  phone: string;
  email: string | null;
  job_count: number;
  created_at: string;
}

// =============================================================================
// API Response Types
// =============================================================================

export interface ApiError {
  detail: string;
  errors?: Array<{
    field: string;
    message: string;
  }>;
}
