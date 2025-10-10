import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { Subscription, interval } from 'rxjs';
import { AdminService, UserStatistics, SystemHealth } from '../../shared/services/admin.service';
import { AuthService, User } from '../../shared/services/auth.service';
import { ErrorHandlerService } from '../../shared/services/error-handler.service';
import { NavigationComponent } from '../../shared/components/navigation/navigation.component';
import { LoadingComponent } from '../../shared/components/loading/loading.component';

@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  imports: [CommonModule, RouterModule, NavigationComponent, LoadingComponent],
  template: `
    <div class="min-h-screen bg-gray-50">
      <app-navigation></app-navigation>

      <main class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div class="px-4 py-6 sm:px-0">
          <!-- Header -->
          <div class="mb-8">
            <h1 class="text-3xl font-bold text-gray-900">Admin Dashboard</h1>
            <p class="mt-1 text-sm text-gray-600">
              System overview and administrative controls
            </p>
          </div>

          <!-- Access Control Check -->
          <div *ngIf="!isAdmin" class="bg-red-50 border border-red-200 rounded-md p-4 mb-6">
            <div class="flex">
              <div class="flex-shrink-0">
                <svg class="h-5 w-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
              </div>
              <div class="ml-3">
                <h3 class="text-sm font-medium text-red-800">Access Denied</h3>
                <p class="mt-1 text-sm text-red-700">
                  You do not have administrator privileges to access this page.
                </p>
              </div>
            </div>
          </div>

          <!-- Admin Content -->
          <div *ngIf="isAdmin">
            <!-- System Health Status -->
            <div class="mb-6">
              <div class="bg-white shadow rounded-lg p-6">
                <div class="flex items-center justify-between mb-4">
                  <h3 class="text-lg leading-6 font-medium text-gray-900">System Health</h3>
                  <button
                    type="button"
                    (click)="refreshSystemHealth()"
                    [disabled]="isRefreshingHealth"
                    class="inline-flex items-center px-3 py-1.5 border border-gray-300 shadow-sm text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
                  >
                    <svg class="h-4 w-4 mr-1" [class.animate-spin]="isRefreshingHealth" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    Refresh
                  </button>
                </div>

                <div *ngIf="isLoadingHealth" class="flex justify-center py-8">
                  <app-loading message="Loading system health..." size="md"></app-loading>
                </div>

                <div *ngIf="!isLoadingHealth && systemHealth" class="grid grid-cols-1 gap-4 sm:grid-cols-3">
                  <!-- Overall Status -->
                  <div class="bg-gray-50 rounded-lg p-4">
                    <div class="flex items-center">
                      <div class="flex-shrink-0">
                        <div class="w-3 h-3 rounded-full" [ngClass]="getHealthStatusColor(systemHealth.status)"></div>
                      </div>
                      <div class="ml-3">
                        <p class="text-sm font-medium text-gray-900 capitalize">{{ systemHealth.status }}</p>
                        <p class="text-xs text-gray-500">Overall Status</p>
                      </div>
                    </div>
                  </div>

                  <!-- MongoDB Status -->
                  <div class="bg-gray-50 rounded-lg p-4">
                    <div class="flex items-center">
                      <div class="flex-shrink-0">
                        <div class="w-3 h-3 rounded-full" [ngClass]="getServiceStatusColor(systemHealth.services.mongodb.status)"></div>
                      </div>
                      <div class="ml-3">
                        <p class="text-sm font-medium text-gray-900 capitalize">{{ systemHealth.services.mongodb.status }}</p>
                        <p class="text-xs text-gray-500">MongoDB</p>
                      </div>
                    </div>
                  </div>

                  <!-- S3 Status -->
                  <div class="bg-gray-50 rounded-lg p-4">
                    <div class="flex items-center">
                      <div class="flex-shrink-0">
                        <div class="w-3 h-3 rounded-full" [ngClass]="getServiceStatusColor(systemHealth.services.s3.status)"></div>
                      </div>
                      <div class="ml-3">
                        <p class="text-sm font-medium text-gray-900 capitalize">{{ systemHealth.services.s3.status }}</p>
                        <p class="text-xs text-gray-500">AWS S3</p>
                      </div>
                    </div>
                  </div>
                </div>

                <div *ngIf="!isLoadingHealth && systemHealth" class="mt-4 text-xs text-gray-500">
                  Last updated: {{ systemHealth.timestamp | date:'short' }} | 
                  Version: {{ systemHealth.version }} | 
                  Environment: {{ systemHealth.system.environment }}
                </div>
              </div>
            </div>

            <!-- Statistics Overview -->
            <div class="mb-6">
              <div *ngIf="isLoadingStats" class="bg-white shadow rounded-lg p-6">
                <app-loading message="Loading statistics..." size="md"></app-loading>
              </div>

              <div *ngIf="!isLoadingStats && statistics" class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
                <!-- User Statistics -->
                <div class="bg-white overflow-hidden shadow rounded-lg">
                  <div class="p-5">
                    <div class="flex items-center">
                      <div class="flex-shrink-0">
                        <svg class="h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z" />
                        </svg>
                      </div>
                      <div class="ml-5 w-0 flex-1">
                        <dl>
                          <dt class="text-sm font-medium text-gray-500 truncate">Total Users</dt>
                          <dd class="text-lg font-medium text-gray-900">{{ statistics.total_users }}</dd>
                        </dl>
                      </div>
                    </div>
                    <div class="mt-3">
                      <div class="flex items-center text-sm">
                        <span class="text-green-600 font-medium">{{ statistics.active_users }}</span>
                        <span class="text-gray-500 ml-1">active</span>
                        <span class="text-gray-400 mx-1">•</span>
                        <span class="text-blue-600 font-medium">{{ statistics.verified_users }}</span>
                        <span class="text-gray-500 ml-1">verified</span>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Recent Activity -->
                <div class="bg-white overflow-hidden shadow rounded-lg">
                  <div class="p-5">
                    <div class="flex items-center">
                      <div class="flex-shrink-0">
                        <svg class="h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                        </svg>
                      </div>
                      <div class="ml-5 w-0 flex-1">
                        <dl>
                          <dt class="text-sm font-medium text-gray-500 truncate">Recent Registrations</dt>
                          <dd class="text-lg font-medium text-gray-900">{{ statistics.recent_registrations }}</dd>
                        </dl>
                      </div>
                    </div>
                    <div class="mt-3">
                      <div class="flex items-center text-sm">
                        <span class="text-indigo-600 font-medium">{{ statistics.recent_logins }}</span>
                        <span class="text-gray-500 ml-1">recent logins</span>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Manuscript Statistics -->
                <div class="bg-white overflow-hidden shadow rounded-lg">
                  <div class="p-5">
                    <div class="flex items-center">
                      <div class="flex-shrink-0">
                        <svg class="h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                      </div>
                      <div class="ml-5 w-0 flex-1">
                        <dl>
                          <dt class="text-sm font-medium text-gray-500 truncate">Total Manuscripts</dt>
                          <dd class="text-lg font-medium text-gray-900">{{ statistics.total_manuscripts }}</dd>
                        </dl>
                      </div>
                    </div>
                    <div class="mt-3">
                      <div class="flex items-center text-sm">
                        <span class="text-yellow-600 font-medium">{{ statistics.processing_manuscripts }}</span>
                        <span class="text-gray-500 ml-1">processing</span>
                        <span class="text-gray-400 mx-1">•</span>
                        <span class="text-green-600 font-medium">{{ statistics.completed_manuscripts }}</span>
                        <span class="text-gray-500 ml-1">completed</span>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Storage & Performance -->
                <div class="bg-white overflow-hidden shadow rounded-lg">
                  <div class="p-5">
                    <div class="flex items-center">
                      <div class="flex-shrink-0">
                        <svg class="h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                        </svg>
                      </div>
                      <div class="ml-5 w-0 flex-1">
                        <dl>
                          <dt class="text-sm font-medium text-gray-500 truncate">Storage Used</dt>
                          <dd class="text-lg font-medium text-gray-900">{{ formatStorage(statistics.storage_used_mb) }}</dd>
                        </dl>
                      </div>
                    </div>
                    <div class="mt-3">
                      <div class="flex items-center text-sm">
                        <span class="text-purple-600 font-medium">{{ statistics.avg_processing_time_minutes }}min</span>
                        <span class="text-gray-500 ml-1">avg processing</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Quick Actions -->
            <div class="mb-6">
              <div class="bg-white shadow rounded-lg p-6">
                <h3 class="text-lg leading-6 font-medium text-gray-900 mb-4">Quick Actions</h3>
                <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <button
                    type="button"
                    routerLink="/admin/users"
                    class="inline-flex items-center justify-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                  >
                    <svg class="-ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z" />
                    </svg>
                    Manage Users
                  </button>

                  <button
                    type="button"
                    routerLink="/admin/activities"
                    class="inline-flex items-center justify-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                  >
                    <svg class="-ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                    Activity Logs
                  </button>

                  <button
                    type="button"
                    routerLink="/admin/system"
                    class="inline-flex items-center justify-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                  >
                    <svg class="-ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    System Settings
                  </button>

                  <button
                    type="button"
                    (click)="exportData()"
                    [disabled]="isExporting"
                    class="inline-flex items-center justify-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
                  >
                    <svg class="-ml-1 mr-2 h-4 w-4" [class.animate-spin]="isExporting" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-4-4m4 4l4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    {{ isExporting ? 'Exporting...' : 'Export Data' }}
                  </button>
                </div>
              </div>
            </div>

            <!-- Recent Activity Summary -->
            <div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <!-- Recent Users -->
              <div class="bg-white shadow rounded-lg">
                <div class="px-4 py-5 sm:p-6">
                  <h3 class="text-lg leading-6 font-medium text-gray-900 mb-4">Recent User Activity</h3>
                  <div class="text-center py-8 text-gray-500">
                    <svg class="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
                      <path d="M34 40h10v-4a6 6 0 00-10.712-3.714M34 40H14m20 0v-4a9.971 9.971 0 00-.712-3.714M14 40H4v-4a6 6 0 0110.713-3.714M14 40v-4c0-1.313.253-2.566.713-3.714m0 0A10.003 10.003 0 0124 26c4.21 0 7.813 2.602 9.288 6.286M30 14a6 6 0 11-12 0 6 6 0 0112 0zm12 6a4 4 0 11-8 0 4 4 0 018 0zm-28 0a4 4 0 11-8 0 4 4 0 018 0z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
                    </svg>
                    <p class="mt-2 text-sm">Recent user activity will be displayed here</p>
                    <button
                      type="button"
                      routerLink="/admin/users"
                      class="mt-2 text-indigo-600 hover:text-indigo-500 text-sm font-medium"
                    >
                      View all users →
                    </button>
                  </div>
                </div>
              </div>

              <!-- System Alerts -->
              <div class="bg-white shadow rounded-lg">
                <div class="px-4 py-5 sm:p-6">
                  <h3 class="text-lg leading-6 font-medium text-gray-900 mb-4">System Alerts</h3>
                  <div class="text-center py-8 text-gray-500">
                    <svg class="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
                      <path d="M34 40h10v-4a6 6 0 00-10.712-3.714M34 40H14m20 0v-4a9.971 9.971 0 00-.712-3.714M14 40H4v-4a6 6 0 0110.713-3.714M14 40v-4c0-1.313.253-2.566.713-3.714m0 0A10.003 10.003 0 0124 26c4.21 0 7.813 2.602 9.288 6.286M30 14a6 6 0 11-12 0 6 6 0 0112 0zm12 6a4 4 0 11-8 0 4 4 0 018 0zm-28 0a4 4 0 11-8 0 4 4 0 018 0z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
                    </svg>
                    <p class="mt-2 text-sm">No system alerts at this time</p>
                    <p class="text-xs text-gray-400">System is running normally</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  `
})
export class AdminDashboardComponent implements OnInit, OnDestroy {
  currentUser: User | null = null;
  isAdmin = false;
  
  statistics: UserStatistics | null = null;
  systemHealth: SystemHealth | null = null;
  
  isLoadingStats = false;
  isLoadingHealth = false;
  isRefreshingHealth = false;
  isExporting = false;
  
  private subscriptions: Subscription[] = [];
  private healthRefreshInterval?: Subscription;

  constructor(
    private adminService: AdminService,
    private authService: AuthService,
    private errorHandler: ErrorHandlerService
  ) {}

  ngOnInit(): void {
    // Check if user is admin
    this.subscriptions.push(
      this.authService.currentUser$.subscribe(user => {
        this.currentUser = user;
        this.isAdmin = this.authService.isAdmin();
        
        if (this.isAdmin) {
          this.loadDashboardData();
          this.startHealthMonitoring();
        }
      })
    );
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(sub => sub.unsubscribe());
    if (this.healthRefreshInterval) {
      this.healthRefreshInterval.unsubscribe();
    }
  }

  private loadDashboardData(): void {
    this.loadStatistics();
    this.loadSystemHealth();
  }

  private loadStatistics(): void {
    this.isLoadingStats = true;
    this.subscriptions.push(
      this.adminService.getUserStatistics().subscribe({
        next: (stats) => {
          this.statistics = stats;
          this.isLoadingStats = false;
        },
        error: (error) => {
          this.errorHandler.showError(error);
          this.isLoadingStats = false;
        }
      })
    );
  }

  private loadSystemHealth(): void {
    this.isLoadingHealth = true;
    this.subscriptions.push(
      this.adminService.getSystemHealth().subscribe({
        next: (health) => {
          this.systemHealth = health;
          this.isLoadingHealth = false;
        },
        error: (error) => {
          this.errorHandler.showError(error);
          this.isLoadingHealth = false;
        }
      })
    );
  }

  private startHealthMonitoring(): void {
    // Refresh health status every 30 seconds
    this.healthRefreshInterval = interval(30000).subscribe(() => {
      this.refreshSystemHealth();
    });
  }

  refreshSystemHealth(): void {
    this.isRefreshingHealth = true;
    this.subscriptions.push(
      this.adminService.getSystemHealth().subscribe({
        next: (health) => {
          this.systemHealth = health;
          this.isRefreshingHealth = false;
        },
        error: (error) => {
          this.errorHandler.showError(error);
          this.isRefreshingHealth = false;
        }
      })
    );
  }

  getHealthStatusColor(status: string): string {
    switch (status) {
      case 'healthy':
        return 'bg-green-400';
      case 'degraded':
        return 'bg-yellow-400';
      case 'unhealthy':
        return 'bg-red-400';
      default:
        return 'bg-gray-400';
    }
  }

  getServiceStatusColor(status: string): string {
    switch (status) {
      case 'connected':
        return 'bg-green-400';
      case 'access_denied':
        return 'bg-yellow-400';
      case 'error':
        return 'bg-red-400';
      default:
        return 'bg-gray-400';
    }
  }

  formatStorage(mb: number): string {
    if (mb < 1024) {
      return `${mb.toFixed(1)} MB`;
    } else if (mb < 1024 * 1024) {
      return `${(mb / 1024).toFixed(1)} GB`;
    } else {
      return `${(mb / (1024 * 1024)).toFixed(1)} TB`;
    }
  }

  exportData(): void {
    this.isExporting = true;
    
    // Simulate export process
    setTimeout(() => {
      this.errorHandler.showSuccess('Data export completed successfully');
      this.isExporting = false;
    }, 2000);
  }
}
