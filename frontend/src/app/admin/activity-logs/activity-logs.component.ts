import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { Subscription } from 'rxjs';
import { AdminService, ActivityLogFilters, ActivityLogResponse, ActivityLog } from '../../shared/services/admin.service';
import { AuthService } from '../../shared/services/auth.service';
import { ErrorHandlerService } from '../../shared/services/error-handler.service';
import { NavigationComponent } from '../../shared/components/navigation/navigation.component';
import { LoadingComponent } from '../../shared/components/loading/loading.component';

@Component({
  selector: 'app-activity-logs',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule, NavigationComponent, LoadingComponent],
  template: `
    <div class="min-h-screen bg-gray-50">
      <app-navigation></app-navigation>

      <main class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div class="px-4 py-6 sm:px-0">
          <!-- Header -->
          <div class="sm:flex sm:items-center sm:justify-between mb-8">
            <div>
              <h1 class="text-3xl font-bold text-gray-900">Activity Logs</h1>
              <p class="mt-1 text-sm text-gray-600">
                Monitor user activities and system events
              </p>
            </div>
            <div class="mt-4 sm:mt-0 flex space-x-3">
              <button
                type="button"
                (click)="exportLogs()"
                [disabled]="isExporting"
                class="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
              >
                <svg class="-ml-1 mr-2 h-4 w-4" [class.animate-spin]="isExporting" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-4-4m4 4l4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {{ isExporting ? 'Exporting...' : 'Export Logs' }}
              </button>
              
              <button
                type="button"
                (click)="refreshLogs()"
                [disabled]="isLoading"
                class="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
              >
                <svg class="-ml-1 mr-2 h-4 w-4" [class.animate-spin]="isLoading" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Refresh
              </button>
            </div>
          </div>

          <!-- Filters -->
          <div class="bg-white shadow rounded-lg mb-6">
            <div class="px-4 py-5 sm:p-6">
              <div class="grid grid-cols-1 gap-4 sm:grid-cols-6">
                <!-- Activity Type Filter -->
                <div class="sm:col-span-2">
                  <label for="activityType" class="block text-sm font-medium text-gray-700">Activity Type</label>
                  <select
                    id="activityType"
                    [(ngModel)]="filters.activity_type"
                    (change)="applyFilters()"
                    class="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
                  >
                    <option value="">All Activities</option>
                    <option value="login">Login</option>
                    <option value="logout">Logout</option>
                    <option value="register">Registration</option>
                    <option value="profile_update">Profile Update</option>
                    <option value="password_change">Password Change</option>
                    <option value="manuscript_upload">Manuscript Upload</option>
                    <option value="manuscript_download">Manuscript Download</option>
                    <option value="manuscript_delete">Manuscript Delete</option>
                    <option value="admin_action">Admin Action</option>
                  </select>
                </div>

                <!-- User Filter -->
                <div class="sm:col-span-2">
                  <label for="userFilter" class="block text-sm font-medium text-gray-700">User ID</label>
                  <input
                    type="text"
                    id="userFilter"
                    [(ngModel)]="filters.user_id"
                    (input)="applyFilters()"
                    class="mt-1 focus:ring-indigo-500 focus:border-indigo-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                    placeholder="Enter user ID..."
                  />
                </div>

                <!-- Date Range -->
                <div>
                  <label for="startDate" class="block text-sm font-medium text-gray-700">Start Date</label>
                  <input
                    type="date"
                    id="startDate"
                    [(ngModel)]="filters.start_date"
                    (change)="applyFilters()"
                    class="mt-1 focus:ring-indigo-500 focus:border-indigo-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                  />
                </div>

                <div>
                  <label for="endDate" class="block text-sm font-medium text-gray-700">End Date</label>
                  <input
                    type="date"
                    id="endDate"
                    [(ngModel)]="filters.end_date"
                    (change)="applyFilters()"
                    class="mt-1 focus:ring-indigo-500 focus:border-indigo-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                  />
                </div>
              </div>

              <div class="mt-4 flex justify-between items-center">
                <div class="text-sm text-gray-500">
                  <span *ngIf="activityList">
                    Showing {{ activityList.activities.length }} of {{ activityList.total }} activities
                  </span>
                </div>
                <button
                  type="button"
                  (click)="clearFilters()"
                  class="text-sm text-indigo-600 hover:text-indigo-500 font-medium"
                >
                  Clear Filters
                </button>
              </div>
            </div>
          </div>

          <!-- Activity Timeline -->
          <div class="bg-white shadow overflow-hidden sm:rounded-md">
            <!-- Loading State -->
            <div *ngIf="isLoading" class="p-6">
              <app-loading message="Loading activity logs..." size="md"></app-loading>
            </div>

            <!-- Empty State -->
            <div *ngIf="!isLoading && (!activityList || activityList.activities.length === 0)" class="text-center py-12">
              <svg class="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
                <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
              <h3 class="mt-2 text-sm font-medium text-gray-900">No activity logs found</h3>
              <p class="mt-1 text-sm text-gray-500">
                {{ hasActiveFilters() ? 'Try adjusting your filter criteria.' : 'No activities have been logged yet.' }}
              </p>
            </div>

            <!-- Activity List -->
            <div *ngIf="!isLoading && activityList && activityList.activities.length > 0">
              <div class="flow-root">
                <ul class="-mb-8">
                  <li *ngFor="let activity of activityList.activities; let i = index">
                    <div class="relative pb-8">
                      <!-- Timeline line -->
                      <span 
                        *ngIf="i !== activityList!.activities.length - 1" 
                        class="absolute top-4 left-4 -ml-px h-full w-0.5 bg-gray-200"
                      ></span>
                      
                      <div class="relative flex space-x-3 px-6 py-4 hover:bg-gray-50">
                        <!-- Activity Icon -->
                        <div>
                          <span [ngClass]="getActivityIconClass(activity.activity_type)" 
                                class="h-8 w-8 rounded-full flex items-center justify-center ring-8 ring-white">
                            <div [innerHTML]="getActivityIcon(activity.activity_type)" class="h-5 w-5"></div>
                          </span>
                        </div>
                        
                        <!-- Activity Content -->
                        <div class="min-w-0 flex-1 pt-1.5 flex justify-between space-x-4">
                          <div class="min-w-0 flex-1">
                            <p class="text-sm text-gray-500">
                              <span class="font-medium text-gray-900">{{ activity.user_email }}</span>
                              {{ activity.description }}
                            </p>
                            
                            <!-- Activity Details -->
                            <div class="mt-2 text-xs text-gray-500 space-y-1">
                              <div class="flex items-center space-x-4">
                                <span class="flex items-center">
                                  <svg class="mr-1 h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                                  </svg>
                                  {{ activity.timestamp | date:'short' }}
                                </span>
                                
                                <span class="flex items-center" *ngIf="activity.ip_address">
                                  <svg class="mr-1 h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 01-9-9m9 9H3m9 9v-9m0-9v9" />
                                  </svg>
                                  {{ activity.ip_address }}
                                </span>
                                
                                <span [ngClass]="getActivityTypeClass(activity.activity_type)" 
                                      class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium">
                                  {{ formatActivityType(activity.activity_type) }}
                                </span>
                              </div>
                              
                              <!-- User Agent (truncated) -->
                              <div *ngIf="activity.user_agent" class="flex items-center">
                                <svg class="mr-1 h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                                </svg>
                                <span class="truncate max-w-md">{{ activity.user_agent }}</span>
                              </div>
                              
                              <!-- Metadata -->
                              <div *ngIf="activity.metadata && hasVisibleMetadata(activity.metadata)" class="mt-2">
                                <button
                                  type="button"
                                  (click)="toggleMetadata(activity.id)"
                                  class="text-indigo-600 hover:text-indigo-500 text-xs font-medium"
                                >
                                  {{ isMetadataExpanded(activity.id) ? 'Hide' : 'Show' }} Details
                                </button>
                                
                                <div *ngIf="isMetadataExpanded(activity.id)" class="mt-2 bg-gray-50 rounded-md p-3">
                                  <pre class="text-xs text-gray-700 whitespace-pre-wrap">{{ formatMetadata(activity.metadata) }}</pre>
                                </div>
                              </div>
                            </div>
                          </div>
                          
                          <!-- Activity ID -->
                          <div class="text-right text-xs text-gray-400">
                            <p>ID: {{ activity.id.substring(0, 8) }}...</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </li>
                </ul>
              </div>

              <!-- Pagination -->
              <div *ngIf="activityList.total_pages > 1" class="bg-white px-4 py-3 border-t border-gray-200 sm:px-6">
                <div class="flex items-center justify-between">
                  <div class="flex-1 flex justify-between sm:hidden">
                    <button
                      type="button"
                      (click)="previousPage()"
                      [disabled]="filters.page === 1"
                      class="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
                    >
                      Previous
                    </button>
                    <button
                      type="button"
                      (click)="nextPage()"
                      [disabled]="filters.page === activityList.total_pages"
                      class="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
                    >
                      Next
                    </button>
                  </div>
                  <div class="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
                    <div>
                      <p class="text-sm text-gray-700">
                        Showing
                        <span class="font-medium">{{ getStartIndex() }}</span>
                        to
                        <span class="font-medium">{{ getEndIndex() }}</span>
                        of
                        <span class="font-medium">{{ activityList.total }}</span>
                        results
                      </p>
                    </div>
                    <div>
                      <nav class="relative z-0 inline-flex rounded-md shadow-sm -space-x-px">
                        <button
                          type="button"
                          (click)="previousPage()"
                          [disabled]="filters.page === 1"
                          class="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
                        >
                          Previous
                        </button>
                        <button
                          type="button"
                          (click)="nextPage()"
                          [disabled]="filters.page === activityList.total_pages"
                          class="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
                        >
                          Next
                        </button>
                      </nav>
                    </div>
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
export class ActivityLogsComponent implements OnInit, OnDestroy {
  activityList: ActivityLogResponse | null = null;
  filters: ActivityLogFilters = {
    page: 1,
    limit: 50
  };
  
  expandedMetadata: Set<string> = new Set();
  
  isLoading = false;
  isExporting = false;
  
  private subscriptions: Subscription[] = [];

  constructor(
    private adminService: AdminService,
    private authService: AuthService,
    private errorHandler: ErrorHandlerService
  ) {}

  ngOnInit(): void {
    this.loadActivityLogs();
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(sub => sub.unsubscribe());
  }

  loadActivityLogs(): void {
    this.isLoading = true;
    this.subscriptions.push(
      this.adminService.getAllUserActivities(this.filters).subscribe({
        next: (activityList) => {
          this.activityList = activityList;
          this.isLoading = false;
        },
        error: (error) => {
          this.errorHandler.showError(error);
          this.isLoading = false;
        }
      })
    );
  }

  applyFilters(): void {
    this.filters.page = 1; // Reset to first page
    this.loadActivityLogs();
  }

  clearFilters(): void {
    this.filters = {
      page: 1,
      limit: 50
    };
    this.loadActivityLogs();
  }

  refreshLogs(): void {
    this.loadActivityLogs();
  }

  hasActiveFilters(): boolean {
    return !!(this.filters.activity_type || this.filters.user_id || this.filters.start_date || this.filters.end_date);
  }

  // Export
  exportLogs(): void {
    this.isExporting = true;
    this.subscriptions.push(
      this.adminService.exportActivityLogs().subscribe({
        next: (blob) => {
          // Create download link
          const url = window.URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = `activity-logs-export-${new Date().toISOString().split('T')[0]}.csv`;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          window.URL.revokeObjectURL(url);
          
          this.errorHandler.showSuccess('Activity logs exported successfully');
          this.isExporting = false;
        },
        error: (error) => {
          this.errorHandler.showError(error);
          this.isExporting = false;
        }
      })
    );
  }

  // Pagination
  previousPage(): void {
    if (this.filters.page && this.filters.page > 1) {
      this.filters.page--;
      this.loadActivityLogs();
    }
  }

  nextPage(): void {
    if (this.filters.page && this.activityList && this.filters.page < this.activityList.total_pages) {
      this.filters.page++;
      this.loadActivityLogs();
    }
  }

  getStartIndex(): number {
    if (!this.activityList || !this.filters.page || !this.filters.limit) return 0;
    return (this.filters.page - 1) * this.filters.limit + 1;
  }

  getEndIndex(): number {
    if (!this.activityList || !this.filters.page || !this.filters.limit) return 0;
    const end = this.filters.page * this.filters.limit;
    return Math.min(end, this.activityList.total);
  }

  // Metadata handling
  toggleMetadata(activityId: string): void {
    if (this.expandedMetadata.has(activityId)) {
      this.expandedMetadata.delete(activityId);
    } else {
      this.expandedMetadata.add(activityId);
    }
  }

  isMetadataExpanded(activityId: string): boolean {
    return this.expandedMetadata.has(activityId);
  }

  hasVisibleMetadata(metadata: any): boolean {
    return metadata && Object.keys(metadata).length > 0;
  }

  formatMetadata(metadata: any): string {
    return JSON.stringify(metadata, null, 2);
  }

  // Activity type formatting
  formatActivityType(activityType: string): string {
    return activityType.split('_').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
  }

  getActivityTypeClass(activityType: string): string {
    switch (activityType) {
      case 'login':
        return 'bg-green-100 text-green-800';
      case 'logout':
        return 'bg-gray-100 text-gray-800';
      case 'register':
        return 'bg-blue-100 text-blue-800';
      case 'profile_update':
        return 'bg-indigo-100 text-indigo-800';
      case 'password_change':
        return 'bg-yellow-100 text-yellow-800';
      case 'manuscript_upload':
        return 'bg-purple-100 text-purple-800';
      case 'manuscript_download':
        return 'bg-teal-100 text-teal-800';
      case 'manuscript_delete':
        return 'bg-red-100 text-red-800';
      case 'admin_action':
        return 'bg-orange-100 text-orange-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  }

  getActivityIconClass(activityType: string): string {
    switch (activityType) {
      case 'login':
        return 'bg-green-500';
      case 'logout':
        return 'bg-gray-500';
      case 'register':
        return 'bg-blue-500';
      case 'profile_update':
        return 'bg-indigo-500';
      case 'password_change':
        return 'bg-yellow-500';
      case 'manuscript_upload':
        return 'bg-purple-500';
      case 'manuscript_download':
        return 'bg-teal-500';
      case 'manuscript_delete':
        return 'bg-red-500';
      case 'admin_action':
        return 'bg-orange-500';
      default:
        return 'bg-gray-500';
    }
  }

  getActivityIcon(activityType: string): string {
    const icons = {
      login: '<svg fill="white" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" /></svg>',
      logout: '<svg fill="white" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>',
      register: '<svg fill="white" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" /></svg>',
      profile_update: '<svg fill="white" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>',
      password_change: '<svg fill="white" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>',
      manuscript_upload: '<svg fill="white" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" /></svg>',
      manuscript_download: '<svg fill="white" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-4-4m4 4l4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>',
      manuscript_delete: '<svg fill="white" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>',
      admin_action: '<svg fill="white" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>'
    };
    
    return icons[activityType as keyof typeof icons] || icons.admin_action;
  }
}
