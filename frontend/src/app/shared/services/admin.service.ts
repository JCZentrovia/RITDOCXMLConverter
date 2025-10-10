import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../../environments/environment';
import { User } from './auth.service';

export interface APIResponse<T> {
  success: boolean;
  message: string;
  data: T;
}

export interface UserListFilters {
  search?: string;
  role?: string;
  is_active?: boolean;
  is_verified?: boolean;
  page?: number;
  limit?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export interface UserListResponse {
  users: User[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

export interface UserStatistics {
  total_users: number;
  active_users: number;
  verified_users: number;
  admin_users: number;
  user_users: number;
  recent_registrations: number;
  recent_logins: number;
  total_manuscripts: number;
  manuscripts_today: number;
  manuscripts_this_week: number;
  manuscripts_this_month: number;
  processing_manuscripts: number;
  completed_manuscripts: number;
  failed_manuscripts: number;
  storage_used_mb: number;
  avg_processing_time_minutes: number;
}

export interface SystemHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  version: string;
  api_version: string;
  services: {
    mongodb: {
      status: string;
      database?: string;
      error?: string;
    };
    s3: {
      status: string;
      bucket?: string;
      region?: string;
      error?: string;
    };
  };
  system: {
    uptime: string;
    environment: string;
  };
}

export interface ActivityLog {
  id: string;
  user_id: string;
  user_email: string;
  activity_type: string;
  description: string;
  ip_address: string;
  user_agent: string;
  timestamp: string;
  metadata?: any;
}

export interface ActivityLogFilters {
  user_id?: string;
  activity_type?: string;
  start_date?: string;
  end_date?: string;
  page?: number;
  limit?: number;
}

export interface ActivityLogResponse {
  activities: ActivityLog[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

export interface AdminUserUpdate {
  role?: 'admin' | 'user';
  is_active?: boolean;
  is_verified?: boolean;
}

@Injectable({
  providedIn: 'root'
})
export class AdminService {
  private apiUrl = `${environment.apiUrl}/api/v1/admin`;

  constructor(private http: HttpClient) {}

  // User Management
  getUsers(filters: UserListFilters = {}): Observable<UserListResponse> {
    let params = new HttpParams();
    
    Object.keys(filters).forEach(key => {
      const value = (filters as any)[key];
      if (value !== undefined && value !== null && value !== '') {
        params = params.set(key, value.toString());
      }
    });

    return this.http.get<APIResponse<UserListResponse>>(`${this.apiUrl}/users`, { params })
      .pipe(map(response => response.data));
  }

  getUserById(userId: string): Observable<User> {
    return this.http.get<APIResponse<User>>(`${this.apiUrl}/users/${userId}`)
      .pipe(map(response => response.data));
  }

  updateUser(userId: string, updates: AdminUserUpdate): Observable<User> {
    return this.http.put<APIResponse<User>>(`${this.apiUrl}/users/${userId}`, updates)
      .pipe(map(response => response.data));
  }

  deleteUser(userId: string): Observable<void> {
    return this.http.delete<APIResponse<void>>(`${this.apiUrl}/users/${userId}`)
      .pipe(map(response => response.data));
  }

  // Statistics
  getUserStatistics(): Observable<UserStatistics> {
    return this.http.get<APIResponse<UserStatistics>>(`${this.apiUrl}/statistics`)
      .pipe(map(response => response.data));
  }

  // System Health
  getSystemHealth(): Observable<SystemHealth> {
    return this.http.get<SystemHealth>(`${environment.apiUrl}/health`);
  }

  // Activity Logs
  getActivityLogs(filters: ActivityLogFilters = {}): Observable<ActivityLogResponse> {
    let params = new HttpParams();
    
    Object.keys(filters).forEach(key => {
      const value = (filters as any)[key];
      if (value !== undefined && value !== null && value !== '') {
        params = params.set(key, value.toString());
      }
    });

    return this.http.get<APIResponse<ActivityLogResponse>>(`${this.apiUrl}/activities`, { params })
      .pipe(map(response => response.data));
  }

  getAllUserActivities(filters: ActivityLogFilters = {}): Observable<ActivityLogResponse> {
    let params = new HttpParams();
    
    Object.keys(filters).forEach(key => {
      const value = (filters as any)[key];
      if (value !== undefined && value !== null && value !== '') {
        params = params.set(key, value.toString());
      }
    });

    return this.http.get<APIResponse<ActivityLogResponse>>(`${this.apiUrl}/activities/all`, { params })
      .pipe(map(response => response.data));
  }

  // System Operations
  exportUserData(): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/export/users`, { 
      responseType: 'blob' 
    });
  }

  exportActivityLogs(): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/export/activities`, { 
      responseType: 'blob' 
    });
  }

  // Bulk Operations
  bulkUpdateUsers(userIds: string[], updates: AdminUserUpdate): Observable<void> {
    return this.http.put<APIResponse<void>>(`${this.apiUrl}/users/bulk`, {
      user_ids: userIds,
      updates
    }).pipe(map(response => response.data));
  }

  bulkDeleteUsers(userIds: string[]): Observable<void> {
    return this.http.delete<APIResponse<void>>(`${this.apiUrl}/users/bulk`, {
      body: { user_ids: userIds }
    }).pipe(map(response => response.data));
  }
}
