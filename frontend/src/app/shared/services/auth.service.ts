import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, tap, map } from 'rxjs';
import { Router } from '@angular/router';
import { environment } from '../../../environments/environment';

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
}

export interface APIResponse<T> {
  success: boolean;
  message: string;
  data: T;
  metadata?: {
    timestamp: string;
    request_id: string;
    processing_time: string;
    api_version: string;
  };
}

export interface LoginData {
  access_token: string;
  token_type: string;
  user: User;
}

export interface User {
  id: string;
  email: string;
  first_name?: string;
  last_name?: string;
  is_active: boolean;
  is_verified: boolean;
  role: string;
  created_at: string;
  last_login?: string;
  login_count: number;
  manuscript_count: number;
}

export interface UserProfileUpdate {
  email?: string;
  first_name?: string;
  last_name?: string;
}

export interface PasswordChangeRequest {
  current_password: string;
  new_password: string;
  confirm_password: string;
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private readonly TOKEN_KEY = 'manuscript_token';
  private readonly REFRESH_TOKEN_KEY = 'manuscript_refresh_token';
  private readonly USER_KEY = 'manuscript_user';
  
  private currentUserSubject = new BehaviorSubject<User | null>(this.getUserFromStorage());
  public currentUser$ = this.currentUserSubject.asObservable();

  private readonly apiUrl = `${environment.apiUrl}/api/v1`;

  constructor(
    private http: HttpClient,
    private router: Router
  ) {}

  register(credentials: RegisterRequest): Observable<User> {
    return this.http.post<APIResponse<any>>(`${this.apiUrl}/auth/register`, credentials)
      .pipe(
        map(response => {
          // Backend returns user info in APIResponse format for registration
          const userData = response.data;
          const user: User = {
            id: userData.id || '',
            email: userData.email || credentials.email,
            first_name: userData.first_name || '',
            last_name: userData.last_name || '',
            is_active: userData.is_active || true,
            is_verified: userData.is_verified || false,
            role: userData.role || 'user',
            created_at: userData.created_at || new Date().toISOString(),
            last_login: userData.last_login || '',
            login_count: userData.login_count || 0,
            manuscript_count: userData.manuscript_count || 0
          };
          console.log('User registered successfully:', user);
          return user;
        })
      );
  }

  login(credentials: LoginRequest): Observable<User> {
    return this.http.post<{access_token: string, token_type: string, expires_in: number}>(`${this.apiUrl}/auth/login`, credentials)
      .pipe(
        map(response => {
          // Backend returns token directly, not wrapped in APIResponse
          this.setToken(response.access_token);
          
          // Create a basic user object since backend doesn't return user info in login
          const user: User = {
            id: '', // Will be populated when we fetch user info
            email: credentials.email,
            first_name: '',
            last_name: '',
            is_active: true,
            is_verified: true,
            role: 'user',
            created_at: new Date().toISOString(),
            last_login: new Date().toISOString(),
            login_count: 1,
            manuscript_count: 0
          };
          
          this.setUser(user);
          this.currentUserSubject.next(user);
          
          // Fetch actual user info after login
          this.getCurrentUserInfo().subscribe(
            actualUser => {
              this.setUser(actualUser);
              this.currentUserSubject.next(actualUser);
            },
            error => console.warn('Could not fetch user info after login:', error)
          );
          
          return user;
        })
      );
  }

  logout(): Observable<any> {
    return this.http.post<APIResponse<any>>(`${this.apiUrl}/auth/logout`, {})
      .pipe(
        tap(() => {
          this.clearStorage();
          this.currentUserSubject.next(null);
          this.router.navigate(['/login']);
        })
      );
  }

  getCurrentUserInfo(): Observable<User> {
    return this.http.get<APIResponse<User>>(`${this.apiUrl}/auth/me`)
      .pipe(
        map(response => response.data),
        tap(user => {
          this.setUser(user);
          this.currentUserSubject.next(user);
        })
      );
  }

  getCurrentUserProfile(): Observable<User> {
    return this.http.get<APIResponse<User>>(`${this.apiUrl}/users/profile`)
      .pipe(
        map(response => response.data),
        tap(user => {
          this.setUser(user);
          this.currentUserSubject.next(user);
        })
      );
  }

  updateProfile(profileData: UserProfileUpdate): Observable<User> {
    return this.http.put<APIResponse<User>>(`${this.apiUrl}/users/profile`, profileData)
      .pipe(
        map(response => response.data),
        tap(user => {
          this.setUser(user);
          this.currentUserSubject.next(user);
        })
      );
  }

  changePassword(passwordData: PasswordChangeRequest): Observable<any> {
    return this.http.post<APIResponse<any>>(`${this.apiUrl}/users/change-password`, passwordData)
      .pipe(
        map(response => response.data)
      );
  }

  requestPasswordReset(email: string): Observable<any> {
    return this.http.post<APIResponse<any>>(`${this.apiUrl}/users/request-password-reset`, { email })
      .pipe(
        map(response => response.data)
      );
  }

  validateToken(): Observable<User> {
    return this.http.get<APIResponse<User>>(`${this.apiUrl}/auth/validate`)
      .pipe(
        map(response => response.data),
        tap(user => {
          this.setUser(user);
          this.currentUserSubject.next(user);
        })
      );
  }

  getToken(): string | null {
    return localStorage.getItem(this.TOKEN_KEY);
  }

  getCurrentUser(): User | null {
    return this.currentUserSubject.value;
  }

  isAuthenticated(): boolean {
    return !!this.getToken();
  }

  hasRole(role: string): boolean {
    const user = this.getCurrentUser();
    return user?.role === role;
  }

  isAdmin(): boolean {
    return this.hasRole('admin') || this.hasRole('super_admin');
  }

  getUserDisplayName(): string {
    const user = this.getCurrentUser();
    if (!user) return '';
    
    if (user.first_name && user.last_name) {
      return `${user.first_name} ${user.last_name}`;
    } else if (user.first_name) {
      return user.first_name;
    } else if (user.last_name) {
      return user.last_name;
    } else {
      return user.email;
    }
  }

  private setToken(token: string): void {
    localStorage.setItem(this.TOKEN_KEY, token);
  }

  private setUser(user: User): void {
    localStorage.setItem(this.USER_KEY, JSON.stringify(user));
  }

  private getUserFromStorage(): User | null {
    const userStr = localStorage.getItem(this.USER_KEY);
    return userStr ? JSON.parse(userStr) : null;
  }

  private clearStorage(): void {
    localStorage.removeItem(this.TOKEN_KEY);
    localStorage.removeItem(this.REFRESH_TOKEN_KEY);
    localStorage.removeItem(this.USER_KEY);
  }
}
