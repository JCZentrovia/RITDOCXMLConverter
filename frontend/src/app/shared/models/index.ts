export interface User {
  id: string;
  email: string;
  created_at?: string;
}

export interface Manuscript {
  id: string;
  user_id: string;
  file_name: string;
  upload_date: string;
  status: 'pending' | 'processing' | 'complete';
  pdf_s3_key: string;
  docx_s3_key?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface ApiResponse<T> {
  data: T;
  message?: string;
  status: number;
}

export interface UploadProgress {
  loaded: number;
  total: number;
  percentage: number;
}
