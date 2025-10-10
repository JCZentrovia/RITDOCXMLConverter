import { Component, OnInit, OnDestroy, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { Subscription } from 'rxjs';
import { RealtimeService, UserNotification } from '../../services/realtime.service';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-notification-center',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div class="relative">
      <!-- Notification Bell -->
      <button
        type="button"
        (click)="toggleNotificationPanel()"
        class="relative p-2 text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 rounded-full"
        [class.text-indigo-600]="hasUnreadNotifications"
      >
        <span class="sr-only">View notifications</span>
        <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-5 5v-5zM11 19H6a2 2 0 01-2-2V7a2 2 0 012-2h5m5 0v5" />
        </svg>
        
        <!-- Notification Badge -->
        <span 
          *ngIf="unreadCount > 0" 
          class="absolute -top-0.5 -right-0.5 h-4 w-4 bg-red-500 text-white text-xs font-medium rounded-full flex items-center justify-center"
        >
          {{ unreadCount > 99 ? '99+' : unreadCount }}
        </span>
        
        <!-- Pulse Animation for New Notifications -->
        <span 
          *ngIf="hasNewNotification" 
          class="absolute -top-0.5 -right-0.5 h-4 w-4 bg-red-500 rounded-full animate-ping"
        ></span>
      </button>

      <!-- Notification Panel -->
      <div 
        *ngIf="isNotificationPanelOpen"
        class="absolute right-0 mt-2 w-80 bg-white rounded-md shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none z-50"
        (click)="$event.stopPropagation()"
      >
        <!-- Header -->
        <div class="px-4 py-3 border-b border-gray-200">
          <div class="flex items-center justify-between">
            <h3 class="text-sm font-medium text-gray-900">Notifications</h3>
            <div class="flex items-center space-x-2">
              <button
                *ngIf="unreadCount > 0"
                type="button"
                (click)="markAllAsRead()"
                class="text-xs text-indigo-600 hover:text-indigo-500 font-medium"
              >
                Mark all read
              </button>
              <button
                type="button"
                (click)="closeNotificationPanel()"
                class="text-gray-400 hover:text-gray-500"
              >
                <span class="sr-only">Close</span>
                <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        <!-- Notifications List -->
        <div class="max-h-96 overflow-y-auto">
          <!-- Loading State -->
          <div *ngIf="isLoading" class="px-4 py-8 text-center">
            <div class="inline-flex items-center">
              <svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-gray-500" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span class="text-sm text-gray-500">Loading notifications...</span>
            </div>
          </div>

          <!-- Empty State -->
          <div *ngIf="!isLoading && notifications.length === 0" class="px-4 py-8 text-center">
            <svg class="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
              <path d="M34 40h10v-4a6 6 0 00-10.712-3.714M34 40H14m20 0v-4a9.971 9.971 0 00-.712-3.714M14 40H4v-4a6 6 0 0110.713-3.714M14 40v-4c0-1.313.253-2.566.713-3.714m0 0A10.003 10.003 0 0124 26c4.21 0 7.813 2.602 9.288 6.286M30 14a6 6 0 11-12 0 6 6 0 0112 0zm12 6a4 4 0 11-8 0 4 4 0 018 0zm-28 0a4 4 0 11-8 0 4 4 0 018 0z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <h3 class="mt-2 text-sm font-medium text-gray-900">No notifications</h3>
            <p class="mt-1 text-sm text-gray-500">You're all caught up!</p>
          </div>

          <!-- Notification Items -->
          <div *ngIf="!isLoading && notifications.length > 0" class="divide-y divide-gray-200">
            <div 
              *ngFor="let notification of notifications; trackBy: trackByNotificationId"
              class="px-4 py-3 hover:bg-gray-50 cursor-pointer transition-colors duration-150"
              [class.bg-blue-50]="!notification.read"
              (click)="handleNotificationClick(notification)"
            >
              <div class="flex items-start space-x-3">
                <!-- Notification Icon -->
                <div class="flex-shrink-0 mt-0.5">
                  <div 
                    class="h-8 w-8 rounded-full flex items-center justify-center"
                    [ngClass]="getNotificationIconClass(notification.type)"
                  >
                    <div [innerHTML]="getNotificationIcon(notification.type)" class="h-4 w-4"></div>
                  </div>
                </div>

                <!-- Notification Content -->
                <div class="flex-1 min-w-0">
                  <div class="flex items-center justify-between">
                    <p class="text-sm font-medium text-gray-900 truncate">
                      {{ notification.title }}
                    </p>
                    <div class="flex items-center space-x-2">
                      <span class="text-xs text-gray-500">
                        {{ getRelativeTime(notification.created_at) }}
                      </span>
                      <div 
                        *ngIf="!notification.read" 
                        class="w-2 h-2 bg-blue-500 rounded-full"
                      ></div>
                    </div>
                  </div>
                  
                  <p class="text-sm text-gray-600 mt-1">
                    {{ notification.message }}
                  </p>
                  
                  <!-- Action Button -->
                  <div *ngIf="notification.action_url && notification.action_text" class="mt-2">
                    <button
                      type="button"
                      (click)="handleActionClick(notification, $event)"
                      class="text-xs text-indigo-600 hover:text-indigo-500 font-medium"
                    >
                      {{ notification.action_text }}
                    </button>
                  </div>
                </div>

                <!-- Dismiss Button -->
                <div class="flex-shrink-0">
                  <button
                    type="button"
                    (click)="dismissNotification(notification, $event)"
                    class="text-gray-400 hover:text-gray-500 opacity-0 group-hover:opacity-100 transition-opacity duration-150"
                  >
                    <span class="sr-only">Dismiss</span>
                    <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <div *ngIf="notifications.length > 0" class="px-4 py-3 border-t border-gray-200">
          <button
            type="button"
            routerLink="/notifications"
            (click)="closeNotificationPanel()"
            class="w-full text-center text-sm text-indigo-600 hover:text-indigo-500 font-medium"
          >
            View all notifications
          </button>
        </div>
      </div>

      <!-- Backdrop -->
      <div 
        *ngIf="isNotificationPanelOpen"
        class="fixed inset-0 z-40"
        (click)="closeNotificationPanel()"
      ></div>
    </div>
  `
})
export class NotificationCenterComponent implements OnInit, OnDestroy {
  notifications: UserNotification[] = [];
  unreadCount = 0;
  hasUnreadNotifications = false;
  hasNewNotification = false;
  isNotificationPanelOpen = false;
  isLoading = false;

  private subscriptions: Subscription[] = [];
  private newNotificationTimer?: any;

  constructor(
    private realtimeService: RealtimeService,
    private authService: AuthService
  ) {}

  ngOnInit(): void {
    this.loadNotifications();
    this.subscribeToRealtimeNotifications();
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(sub => sub.unsubscribe());
    if (this.newNotificationTimer) {
      clearTimeout(this.newNotificationTimer);
    }
  }

  @HostListener('document:keydown.escape', ['$event'])
  onEscapeKey(event: Event): void {
    if (this.isNotificationPanelOpen) {
      this.closeNotificationPanel();
    }
  }

  private loadNotifications(): void {
    this.isLoading = true;
    
    // Subscribe to unread notifications from realtime service
    this.subscriptions.push(
      this.realtimeService.unreadNotifications.subscribe(notifications => {
        this.notifications = notifications;
        this.unreadCount = notifications.length;
        this.hasUnreadNotifications = this.unreadCount > 0;
        this.isLoading = false;
      })
    );
  }

  private subscribeToRealtimeNotifications(): void {
    // Subscribe to new notifications
    this.subscriptions.push(
      this.realtimeService.notifications.subscribe(notification => {
        // Show new notification indicator
        this.hasNewNotification = true;
        
        // Clear the indicator after 3 seconds
        if (this.newNotificationTimer) {
          clearTimeout(this.newNotificationTimer);
        }
        this.newNotificationTimer = setTimeout(() => {
          this.hasNewNotification = false;
        }, 3000);

        // Show browser notification if permission granted
        this.showBrowserNotification(notification);
      })
    );
  }

  private showBrowserNotification(notification: UserNotification): void {
    if ('Notification' in window && Notification.permission === 'granted') {
      const browserNotification = new Notification(notification.title, {
        body: notification.message,
        icon: '/assets/icons/notification-icon.png',
        badge: '/assets/icons/badge-icon.png',
        tag: notification.id,
        requireInteraction: notification.type === 'error'
      });

      browserNotification.onclick = () => {
        window.focus();
        this.handleNotificationClick(notification);
        browserNotification.close();
      };

      // Auto-close after 5 seconds for non-error notifications
      if (notification.type !== 'error') {
        setTimeout(() => browserNotification.close(), 5000);
      }
    }
  }

  toggleNotificationPanel(): void {
    this.isNotificationPanelOpen = !this.isNotificationPanelOpen;
    
    // Request notification permission if not already granted
    if (this.isNotificationPanelOpen && 'Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }

  closeNotificationPanel(): void {
    this.isNotificationPanelOpen = false;
  }

  markAllAsRead(): void {
    this.realtimeService.markAllNotificationsAsRead();
  }

  handleNotificationClick(notification: UserNotification): void {
    // Mark as read
    if (!notification.read) {
      this.realtimeService.markNotificationAsRead(notification.id);
    }

    // Navigate to action URL if available
    if (notification.action_url) {
      // This would typically use Router.navigate()
      // For now, we'll just close the panel
      this.closeNotificationPanel();
    }
  }

  handleActionClick(notification: UserNotification, event: Event): void {
    event.stopPropagation();
    this.handleNotificationClick(notification);
  }

  dismissNotification(notification: UserNotification, event: Event): void {
    event.stopPropagation();
    this.realtimeService.markNotificationAsRead(notification.id);
  }

  trackByNotificationId(index: number, notification: UserNotification): string {
    return notification.id;
  }

  getNotificationIconClass(type: string): string {
    switch (type) {
      case 'success':
        return 'bg-green-100 text-green-600';
      case 'error':
        return 'bg-red-100 text-red-600';
      case 'warning':
        return 'bg-yellow-100 text-yellow-600';
      case 'info':
      default:
        return 'bg-blue-100 text-blue-600';
    }
  }

  getNotificationIcon(type: string): string {
    const icons = {
      success: '<svg fill="currentColor" viewBox="0 0 24 24"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
      error: '<svg fill="currentColor" viewBox="0 0 24 24"><path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"/></svg>',
      warning: '<svg fill="currentColor" viewBox="0 0 24 24"><path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"/></svg>',
      info: '<svg fill="currentColor" viewBox="0 0 24 24"><path d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>'
    };
    
    return icons[type as keyof typeof icons] || icons.info;
  }

  getRelativeTime(timestamp: string): string {
    const now = new Date();
    const time = new Date(timestamp);
    const diffInSeconds = Math.floor((now.getTime() - time.getTime()) / 1000);

    if (diffInSeconds < 60) {
      return 'Just now';
    } else if (diffInSeconds < 3600) {
      const minutes = Math.floor(diffInSeconds / 60);
      return `${minutes}m ago`;
    } else if (diffInSeconds < 86400) {
      const hours = Math.floor(diffInSeconds / 3600);
      return `${hours}h ago`;
    } else if (diffInSeconds < 604800) {
      const days = Math.floor(diffInSeconds / 86400);
      return `${days}d ago`;
    } else {
      return time.toLocaleDateString();
    }
  }
}
