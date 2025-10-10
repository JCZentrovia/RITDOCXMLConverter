import { Injectable, OnDestroy } from '@angular/core';
import { BehaviorSubject, Observable, Subject, interval, timer } from 'rxjs';
import { takeUntil, switchMap, catchError, retry, filter } from 'rxjs/operators';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import { AuthService } from './auth.service';
import { ErrorHandlerService } from './error-handler.service';

export interface RealtimeEvent {
  id: string;
  type: 'manuscript_status_update' | 'user_notification' | 'system_alert' | 'admin_notification';
  data: any;
  timestamp: string;
  user_id?: string;
}

export interface ManuscriptStatusUpdate {
  manuscript_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress?: number;
  error_message?: string;
  processing_started_at?: string;
  processing_completed_at?: string;
}

export interface UserNotification {
  id: string;
  title: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
  read: boolean;
  created_at: string;
  action_url?: string;
  action_text?: string;
}

export interface SystemAlert {
  id: string;
  level: 'info' | 'warning' | 'critical';
  title: string;
  message: string;
  component: string;
  timestamp: string;
  resolved: boolean;
}

@Injectable({
  providedIn: 'root'
})
export class RealtimeService implements OnDestroy {
  private destroy$ = new Subject<void>();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectInterval = 5000; // 5 seconds
  
  // Connection state
  private connectionState$ = new BehaviorSubject<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected');
  
  // Event streams
  private events$ = new Subject<RealtimeEvent>();
  private manuscriptUpdates$ = new Subject<ManuscriptStatusUpdate>();
  private notifications$ = new Subject<UserNotification>();
  private systemAlerts$ = new Subject<SystemAlert>();
  
  // Notification management
  private unreadNotifications$ = new BehaviorSubject<UserNotification[]>([]);
  private systemAlertsList$ = new BehaviorSubject<SystemAlert[]>([]);

  constructor(
    private http: HttpClient,
    private authService: AuthService,
    private errorHandler: ErrorHandlerService
  ) {
    this.initializeRealtimeConnection();
    this.setupEventHandlers();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
    this.disconnect();
  }

  // Public observables
  get connectionState(): Observable<string> {
    return this.connectionState$.asObservable();
  }

  get events(): Observable<RealtimeEvent> {
    return this.events$.asObservable();
  }

  get manuscriptUpdates(): Observable<ManuscriptStatusUpdate> {
    return this.manuscriptUpdates$.asObservable();
  }

  get notifications(): Observable<UserNotification> {
    return this.notifications$.asObservable();
  }

  get systemAlerts(): Observable<SystemAlert> {
    return this.systemAlerts$.asObservable();
  }

  get unreadNotifications(): Observable<UserNotification[]> {
    return this.unreadNotifications$.asObservable();
  }

  get systemAlertsList(): Observable<SystemAlert[]> {
    return this.systemAlertsList$.asObservable();
  }

  // Connection management
  private initializeRealtimeConnection(): void {
    // Simulate WebSocket connection with polling for now
    // In a real implementation, this would establish a WebSocket connection
    this.authService.currentUser$.pipe(
      takeUntil(this.destroy$),
      filter(user => !!user),
      switchMap(() => this.startPolling())
    ).subscribe();
  }

  private startPolling(): Observable<any> {
    this.connectionState$.next('connecting');
    
    return interval(2000).pipe( // Poll every 2 seconds
      takeUntil(this.destroy$),
      switchMap(() => this.pollForUpdates()),
      retry({
        count: this.maxReconnectAttempts,
        delay: (error, retryCount) => {
          this.reconnectAttempts = retryCount;
          this.connectionState$.next('error');
          return timer(this.reconnectInterval * retryCount);
        }
      }),
      catchError(error => {
        this.connectionState$.next('error');
        this.errorHandler.showError('Real-time connection failed');
        throw error;
      })
    );
  }

  private pollForUpdates(): Observable<any> {
    // Simulate polling for real-time updates
    return this.http.get(`${environment.apiUrl}/api/v1/realtime/events`).pipe(
      catchError(error => {
        if (error.status === 401) {
          // Token expired, let auth service handle it
          return [];
        }
        throw error;
      })
    );
  }

  private setupEventHandlers(): void {
    // Handle incoming events
    this.events$.pipe(
      takeUntil(this.destroy$)
    ).subscribe(event => {
      this.handleRealtimeEvent(event);
    });

    // Simulate some real-time events for demonstration
    this.simulateRealtimeEvents();
  }

  private handleRealtimeEvent(event: RealtimeEvent): void {
    switch (event.type) {
      case 'manuscript_status_update':
        this.manuscriptUpdates$.next(event.data as ManuscriptStatusUpdate);
        this.createNotificationFromManuscriptUpdate(event.data);
        break;
      
      case 'user_notification':
        const notification = event.data as UserNotification;
        this.notifications$.next(notification);
        this.addUnreadNotification(notification);
        break;
      
      case 'system_alert':
        const alert = event.data as SystemAlert;
        this.systemAlerts$.next(alert);
        this.addSystemAlert(alert);
        break;
      
      case 'admin_notification':
        if (this.authService.isAdmin()) {
          const adminNotification = event.data as UserNotification;
          this.notifications$.next(adminNotification);
          this.addUnreadNotification(adminNotification);
        }
        break;
    }
  }

  private createNotificationFromManuscriptUpdate(update: ManuscriptStatusUpdate): void {
    let notification: UserNotification;
    
    switch (update.status) {
      case 'processing':
        notification = {
          id: `manuscript-${update.manuscript_id}-processing`,
          title: 'Processing Started',
          message: 'Your manuscript is now being processed',
          type: 'info',
          read: false,
          created_at: new Date().toISOString(),
          action_url: '/manuscripts',
          action_text: 'View Manuscripts'
        };
        break;
      
      case 'completed':
        notification = {
          id: `manuscript-${update.manuscript_id}-completed`,
          title: 'Processing Complete',
          message: 'Your manuscript has been successfully processed and is ready for download',
          type: 'success',
          read: false,
          created_at: new Date().toISOString(),
          action_url: '/manuscripts',
          action_text: 'Download Now'
        };
        break;
      
      case 'failed':
        notification = {
          id: `manuscript-${update.manuscript_id}-failed`,
          title: 'Processing Failed',
          message: update.error_message || 'An error occurred while processing your manuscript',
          type: 'error',
          read: false,
          created_at: new Date().toISOString(),
          action_url: '/manuscripts',
          action_text: 'View Details'
        };
        break;
      
      default:
        return;
    }
    
    this.notifications$.next(notification);
    this.addUnreadNotification(notification);
  }

  private addUnreadNotification(notification: UserNotification): void {
    const current = this.unreadNotifications$.value;
    const updated = [notification, ...current].slice(0, 50); // Keep only last 50
    this.unreadNotifications$.next(updated);
  }

  private addSystemAlert(alert: SystemAlert): void {
    const current = this.systemAlertsList$.value;
    const updated = [alert, ...current.filter(a => a.id !== alert.id)].slice(0, 20); // Keep only last 20
    this.systemAlertsList$.next(updated);
  }

  // Public methods
  connect(): void {
    if (this.connectionState$.value === 'disconnected') {
      this.initializeRealtimeConnection();
    }
  }

  disconnect(): void {
    this.connectionState$.next('disconnected');
    this.destroy$.next();
  }

  markNotificationAsRead(notificationId: string): void {
    const current = this.unreadNotifications$.value;
    const updated = current.filter(n => n.id !== notificationId);
    this.unreadNotifications$.next(updated);
    
    // Send to backend
    this.http.put(`${environment.apiUrl}/api/v1/notifications/${notificationId}/read`, {})
      .subscribe({
        error: (error) => this.errorHandler.showError('Failed to mark notification as read')
      });
  }

  markAllNotificationsAsRead(): void {
    this.unreadNotifications$.next([]);
    
    // Send to backend
    this.http.put(`${environment.apiUrl}/api/v1/notifications/mark-all-read`, {})
      .subscribe({
        error: (error) => this.errorHandler.showError('Failed to mark all notifications as read')
      });
  }

  dismissSystemAlert(alertId: string): void {
    const current = this.systemAlertsList$.value;
    const updated = current.filter(a => a.id !== alertId);
    this.systemAlertsList$.next(updated);
    
    // Send to backend
    this.http.put(`${environment.apiUrl}/api/v1/admin/alerts/${alertId}/dismiss`, {})
      .subscribe({
        error: (error) => this.errorHandler.showError('Failed to dismiss alert')
      });
  }

  // Simulate real-time events for demonstration
  private simulateRealtimeEvents(): void {
    // Simulate manuscript processing updates
    timer(5000, 15000).pipe(
      takeUntil(this.destroy$)
    ).subscribe(() => {
      if (Math.random() > 0.7) { // 30% chance
        this.simulateManuscriptUpdate();
      }
    });

    // Simulate system alerts
    timer(10000, 30000).pipe(
      takeUntil(this.destroy$)
    ).subscribe(() => {
      if (Math.random() > 0.8) { // 20% chance
        this.simulateSystemAlert();
      }
    });

    // Simulate user notifications
    timer(8000, 20000).pipe(
      takeUntil(this.destroy$)
    ).subscribe(() => {
      if (Math.random() > 0.6) { // 40% chance
        this.simulateUserNotification();
      }
    });
  }

  private simulateManuscriptUpdate(): void {
    const statuses = ['processing', 'completed', 'failed'] as const;
    const status = statuses[Math.floor(Math.random() * statuses.length)];
    
    const update: ManuscriptStatusUpdate = {
      manuscript_id: `manuscript-${Date.now()}`,
      status,
      progress: status === 'processing' ? Math.floor(Math.random() * 100) : undefined,
      error_message: status === 'failed' ? 'Conversion failed: Unsupported PDF format' : undefined,
      processing_started_at: status === 'processing' || status === 'completed' || status === 'failed' ? new Date().toISOString() : undefined,
      processing_completed_at: status === 'completed' ? new Date().toISOString() : undefined
    };

    const event: RealtimeEvent = {
      id: `event-${Date.now()}`,
      type: 'manuscript_status_update',
      data: update,
      timestamp: new Date().toISOString()
    };

    this.events$.next(event);
  }

  private simulateSystemAlert(): void {
    const alerts = [
      {
        level: 'warning' as const,
        title: 'High Processing Queue',
        message: 'Processing queue has reached 80% capacity',
        component: 'processing_service'
      },
      {
        level: 'info' as const,
        title: 'Scheduled Maintenance',
        message: 'System maintenance scheduled for tonight at 2:00 AM',
        component: 'system'
      },
      {
        level: 'critical' as const,
        title: 'Storage Space Low',
        message: 'Available storage space is below 10%',
        component: 's3_storage'
      }
    ];

    const alertTemplate = alerts[Math.floor(Math.random() * alerts.length)];
    
    const alert: SystemAlert = {
      id: `alert-${Date.now()}`,
      ...alertTemplate,
      timestamp: new Date().toISOString(),
      resolved: false
    };

    const event: RealtimeEvent = {
      id: `event-${Date.now()}`,
      type: 'system_alert',
      data: alert,
      timestamp: new Date().toISOString()
    };

    this.events$.next(event);
  }

  private simulateUserNotification(): void {
    const notifications = [
      {
        title: 'Welcome!',
        message: 'Welcome to the Manuscript Processor. Upload your first document to get started.',
        type: 'info' as const
      },
      {
        title: 'Processing Complete',
        message: 'Your document "Research Paper.pdf" has been successfully converted.',
        type: 'success' as const
      },
      {
        title: 'Account Updated',
        message: 'Your profile information has been updated successfully.',
        type: 'success' as const
      },
      {
        title: 'Storage Warning',
        message: 'You are approaching your storage limit. Consider deleting old files.',
        type: 'warning' as const
      }
    ];

    const notificationTemplate = notifications[Math.floor(Math.random() * notifications.length)];
    
    const notification: UserNotification = {
      id: `notification-${Date.now()}`,
      ...notificationTemplate,
      read: false,
      created_at: new Date().toISOString(),
      action_url: '/manuscripts',
      action_text: 'View Details'
    };

    const event: RealtimeEvent = {
      id: `event-${Date.now()}`,
      type: 'user_notification',
      data: notification,
      timestamp: new Date().toISOString()
    };

    this.events$.next(event);
  }

  // Connection status helpers
  isConnected(): boolean {
    return this.connectionState$.value === 'connected';
  }

  isConnecting(): boolean {
    return this.connectionState$.value === 'connecting';
  }

  hasConnectionError(): boolean {
    return this.connectionState$.value === 'error';
  }
}
