import { Injectable } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError, BehaviorSubject } from 'rxjs';

export interface ApiErrorResponse {
  success: boolean;
  message: string;
  error_code: string;
  details?: {
    request_id: string;
    path: string;
    method: string;
  };
}

export interface ApiError {
  message: string;
  status: number;
  errorCode?: string;
  requestId?: string;
  details?: any;
}

export interface NotificationMessage {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message: string;
  timestamp: Date;
  duration?: number;
}

@Injectable({
  providedIn: 'root'
})
export class ErrorHandlerService {
  private notificationsSubject = new BehaviorSubject<NotificationMessage[]>([]);
  public notifications$ = this.notificationsSubject.asObservable();
  
  handleError(error: HttpErrorResponse): Observable<never> {
    let errorMessage = 'An unknown error occurred';
    let errorCode = 'UNKNOWN_ERROR';
    let requestId: string | undefined;
    
    if (error.error instanceof ErrorEvent) {
      // Client-side error
      errorMessage = `Network Error: ${error.error.message}`;
      errorCode = 'NETWORK_ERROR';
    } else {
      // Server-side error with new API format
      const apiErrorResponse = error.error as ApiErrorResponse;
      
      if (apiErrorResponse && apiErrorResponse.message) {
        errorMessage = apiErrorResponse.message;
        errorCode = apiErrorResponse.error_code || 'SERVER_ERROR';
        requestId = apiErrorResponse.details?.request_id;
      } else {
        // Fallback for non-API errors
        switch (error.status) {
          case 400:
            errorMessage = 'Bad Request: Please check your input';
            errorCode = 'VALIDATION_ERROR';
            break;
          case 401:
            errorMessage = 'Authentication required. Please login again.';
            errorCode = 'UNAUTHORIZED';
            break;
          case 403:
            errorMessage = 'Access denied. You do not have permission.';
            errorCode = 'FORBIDDEN';
            break;
          case 404:
            errorMessage = 'Resource not found';
            errorCode = 'NOT_FOUND';
            break;
          case 408:
            errorMessage = 'Request timeout. Please try again.';
            errorCode = 'TIMEOUT_ERROR';
            break;
          case 500:
            errorMessage = 'Internal server error. Please try again later.';
            errorCode = 'INTERNAL_ERROR';
            break;
          case 503:
            errorMessage = 'Service temporarily unavailable. Please try again later.';
            errorCode = 'CONNECTION_ERROR';
            break;
          default:
            errorMessage = `Server Error: ${error.status}`;
            errorCode = 'SERVER_ERROR';
        }
      }
    }
    
    console.error('API Error:', {
      status: error.status,
      message: errorMessage,
      errorCode,
      requestId,
      fullError: error
    });
    
    const apiError: ApiError = {
      message: errorMessage,
      status: error.status,
      errorCode,
      requestId,
      details: error.error
    };
    
    return throwError(() => apiError);
  }
  
  showError(error: ApiError | string, title?: string): void {
    const message = typeof error === 'string' ? error : error.message;
    const errorTitle = title || 'Error';
    
    this.addNotification({
      type: 'error',
      title: errorTitle,
      message: message,
      duration: 5000
    });
  }
  
  showSuccess(message: string, title: string = 'Success'): void {
    this.addNotification({
      type: 'success',
      title,
      message,
      duration: 3000
    });
  }
  
  showWarning(message: string, title: string = 'Warning'): void {
    this.addNotification({
      type: 'warning',
      title,
      message,
      duration: 4000
    });
  }
  
  showInfo(message: string, title: string = 'Info'): void {
    this.addNotification({
      type: 'info',
      title,
      message,
      duration: 3000
    });
  }
  
  private addNotification(notification: Omit<NotificationMessage, 'id' | 'timestamp'>): void {
    const newNotification: NotificationMessage = {
      ...notification,
      id: this.generateId(),
      timestamp: new Date()
    };
    
    const currentNotifications = this.notificationsSubject.value;
    this.notificationsSubject.next([newNotification, ...currentNotifications]);
    
    // Auto-remove notification after duration
    if (notification.duration && notification.duration > 0) {
      setTimeout(() => {
        this.removeNotification(newNotification.id);
      }, notification.duration);
    }
  }
  
  removeNotification(id: string): void {
    const currentNotifications = this.notificationsSubject.value;
    const updatedNotifications = currentNotifications.filter(n => n.id !== id);
    this.notificationsSubject.next(updatedNotifications);
  }
  
  clearAllNotifications(): void {
    this.notificationsSubject.next([]);
  }
  
  private generateId(): string {
    return Math.random().toString(36).substr(2, 9);
  }
}
