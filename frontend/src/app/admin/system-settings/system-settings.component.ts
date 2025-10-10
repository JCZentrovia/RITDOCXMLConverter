import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { Subscription } from 'rxjs';
import { AdminService, SystemHealth } from '../../shared/services/admin.service';
import { AuthService } from '../../shared/services/auth.service';
import { ErrorHandlerService } from '../../shared/services/error-handler.service';
import { NavigationComponent } from '../../shared/components/navigation/navigation.component';
import { LoadingComponent } from '../../shared/components/loading/loading.component';

interface SystemSettings {
  maintenance_mode: boolean;
  registration_enabled: boolean;
  max_file_size_mb: number;
  allowed_file_types: string[];
  session_timeout_minutes: number;
  max_concurrent_uploads: number;
  processing_queue_size: number;
  email_notifications_enabled: boolean;
  backup_enabled: boolean;
  backup_frequency_hours: number;
  log_retention_days: number;
  rate_limiting_enabled: boolean;
  max_requests_per_minute: number;
}

@Component({
  selector: 'app-system-settings',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterModule, NavigationComponent, LoadingComponent],
  template: `
    <div class="min-h-screen bg-gray-50">
      <app-navigation></app-navigation>

      <main class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div class="px-4 py-6 sm:px-0">
          <!-- Header -->
          <div class="mb-8">
            <h1 class="text-3xl font-bold text-gray-900">System Settings</h1>
            <p class="mt-1 text-sm text-gray-600">
              Configure system-wide settings and maintenance options
            </p>
          </div>

          <!-- System Status -->
          <div class="mb-6">
            <div class="bg-white shadow rounded-lg p-6">
              <div class="flex items-center justify-between mb-4">
                <h3 class="text-lg leading-6 font-medium text-gray-900">System Status</h3>
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

              <div *ngIf="isLoadingHealth" class="flex justify-center py-4">
                <app-loading message="Loading system status..." size="sm"></app-loading>
              </div>

              <div *ngIf="!isLoadingHealth && systemHealth" class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
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

                <div class="bg-gray-50 rounded-lg p-4">
                  <div class="flex items-center">
                    <div class="flex-shrink-0">
                      <div class="w-3 h-3 rounded-full" [ngClass]="getServiceStatusColor(systemHealth.services.mongodb.status)"></div>
                    </div>
                    <div class="ml-3">
                      <p class="text-sm font-medium text-gray-900">{{ systemHealth.services.mongodb.status }}</p>
                      <p class="text-xs text-gray-500">Database</p>
                    </div>
                  </div>
                </div>

                <div class="bg-gray-50 rounded-lg p-4">
                  <div class="flex items-center">
                    <div class="flex-shrink-0">
                      <div class="w-3 h-3 rounded-full" [ngClass]="getServiceStatusColor(systemHealth.services.s3.status)"></div>
                    </div>
                    <div class="ml-3">
                      <p class="text-sm font-medium text-gray-900">{{ systemHealth.services.s3.status }}</p>
                      <p class="text-xs text-gray-500">File Storage</p>
                    </div>
                  </div>
                </div>

                <div class="bg-gray-50 rounded-lg p-4">
                  <div class="flex items-center">
                    <div class="flex-shrink-0">
                      <div class="w-3 h-3 rounded-full bg-blue-400"></div>
                    </div>
                    <div class="ml-3">
                      <p class="text-sm font-medium text-gray-900">{{ systemHealth.version }}</p>
                      <p class="text-xs text-gray-500">Version</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Settings Forms -->
          <div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <!-- General Settings -->
            <div class="bg-white shadow rounded-lg">
              <div class="px-4 py-5 sm:p-6">
                <h3 class="text-lg leading-6 font-medium text-gray-900 mb-4">General Settings</h3>
                
                <form [formGroup]="generalForm" (ngSubmit)="saveGeneralSettings()">
                  <div class="space-y-4">
                    <!-- Maintenance Mode -->
                    <div class="flex items-start">
                      <div class="flex items-center h-5">
                        <input
                          id="maintenance-mode"
                          type="checkbox"
                          formControlName="maintenance_mode"
                          class="focus:ring-indigo-500 h-4 w-4 text-indigo-600 border-gray-300 rounded"
                        />
                      </div>
                      <div class="ml-3 text-sm">
                        <label for="maintenance-mode" class="font-medium text-gray-700">
                          Maintenance Mode
                        </label>
                        <p class="text-gray-500">Temporarily disable user access for maintenance</p>
                      </div>
                    </div>

                    <!-- Registration Enabled -->
                    <div class="flex items-start">
                      <div class="flex items-center h-5">
                        <input
                          id="registration-enabled"
                          type="checkbox"
                          formControlName="registration_enabled"
                          class="focus:ring-indigo-500 h-4 w-4 text-indigo-600 border-gray-300 rounded"
                        />
                      </div>
                      <div class="ml-3 text-sm">
                        <label for="registration-enabled" class="font-medium text-gray-700">
                          User Registration
                        </label>
                        <p class="text-gray-500">Allow new users to register accounts</p>
                      </div>
                    </div>

                    <!-- Session Timeout -->
                    <div>
                      <label for="session-timeout" class="block text-sm font-medium text-gray-700">
                        Session Timeout (minutes)
                      </label>
                      <input
                        type="number"
                        id="session-timeout"
                        formControlName="session_timeout_minutes"
                        min="5"
                        max="1440"
                        class="mt-1 focus:ring-indigo-500 focus:border-indigo-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                      />
                    </div>
                  </div>

                  <div class="mt-6">
                    <button
                      type="submit"
                      [disabled]="generalForm.invalid || isSavingGeneral"
                      class="inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
                    >
                      {{ isSavingGeneral ? 'Saving...' : 'Save General Settings' }}
                    </button>
                  </div>
                </form>
              </div>
            </div>

            <!-- File Upload Settings -->
            <div class="bg-white shadow rounded-lg">
              <div class="px-4 py-5 sm:p-6">
                <h3 class="text-lg leading-6 font-medium text-gray-900 mb-4">File Upload Settings</h3>
                
                <form [formGroup]="uploadForm" (ngSubmit)="saveUploadSettings()">
                  <div class="space-y-4">
                    <!-- Max File Size -->
                    <div>
                      <label for="max-file-size" class="block text-sm font-medium text-gray-700">
                        Maximum File Size (MB)
                      </label>
                      <input
                        type="number"
                        id="max-file-size"
                        formControlName="max_file_size_mb"
                        min="1"
                        max="100"
                        class="mt-1 focus:ring-indigo-500 focus:border-indigo-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                      />
                    </div>

                    <!-- Max Concurrent Uploads -->
                    <div>
                      <label for="max-concurrent-uploads" class="block text-sm font-medium text-gray-700">
                        Max Concurrent Uploads
                      </label>
                      <input
                        type="number"
                        id="max-concurrent-uploads"
                        formControlName="max_concurrent_uploads"
                        min="1"
                        max="10"
                        class="mt-1 focus:ring-indigo-500 focus:border-indigo-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                      />
                    </div>

                    <!-- Processing Queue Size -->
                    <div>
                      <label for="processing-queue-size" class="block text-sm font-medium text-gray-700">
                        Processing Queue Size
                      </label>
                      <input
                        type="number"
                        id="processing-queue-size"
                        formControlName="processing_queue_size"
                        min="1"
                        max="100"
                        class="mt-1 focus:ring-indigo-500 focus:border-indigo-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                      />
                    </div>
                  </div>

                  <div class="mt-6">
                    <button
                      type="submit"
                      [disabled]="uploadForm.invalid || isSavingUpload"
                      class="inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
                    >
                      {{ isSavingUpload ? 'Saving...' : 'Save Upload Settings' }}
                    </button>
                  </div>
                </form>
              </div>
            </div>

            <!-- Security Settings -->
            <div class="bg-white shadow rounded-lg">
              <div class="px-4 py-5 sm:p-6">
                <h3 class="text-lg leading-6 font-medium text-gray-900 mb-4">Security Settings</h3>
                
                <form [formGroup]="securityForm" (ngSubmit)="saveSecuritySettings()">
                  <div class="space-y-4">
                    <!-- Rate Limiting -->
                    <div class="flex items-start">
                      <div class="flex items-center h-5">
                        <input
                          id="rate-limiting"
                          type="checkbox"
                          formControlName="rate_limiting_enabled"
                          class="focus:ring-indigo-500 h-4 w-4 text-indigo-600 border-gray-300 rounded"
                        />
                      </div>
                      <div class="ml-3 text-sm">
                        <label for="rate-limiting" class="font-medium text-gray-700">
                          Rate Limiting
                        </label>
                        <p class="text-gray-500">Enable API rate limiting protection</p>
                      </div>
                    </div>

                    <!-- Max Requests Per Minute -->
                    <div>
                      <label for="max-requests" class="block text-sm font-medium text-gray-700">
                        Max Requests Per Minute
                      </label>
                      <input
                        type="number"
                        id="max-requests"
                        formControlName="max_requests_per_minute"
                        min="10"
                        max="1000"
                        class="mt-1 focus:ring-indigo-500 focus:border-indigo-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                      />
                    </div>

                    <!-- Log Retention -->
                    <div>
                      <label for="log-retention" class="block text-sm font-medium text-gray-700">
                        Log Retention (days)
                      </label>
                      <input
                        type="number"
                        id="log-retention"
                        formControlName="log_retention_days"
                        min="7"
                        max="365"
                        class="mt-1 focus:ring-indigo-500 focus:border-indigo-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                      />
                    </div>
                  </div>

                  <div class="mt-6">
                    <button
                      type="submit"
                      [disabled]="securityForm.invalid || isSavingSecurity"
                      class="inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
                    >
                      {{ isSavingSecurity ? 'Saving...' : 'Save Security Settings' }}
                    </button>
                  </div>
                </form>
              </div>
            </div>

            <!-- Backup & Maintenance -->
            <div class="bg-white shadow rounded-lg">
              <div class="px-4 py-5 sm:p-6">
                <h3 class="text-lg leading-6 font-medium text-gray-900 mb-4">Backup & Maintenance</h3>
                
                <form [formGroup]="backupForm" (ngSubmit)="saveBackupSettings()">
                  <div class="space-y-4">
                    <!-- Email Notifications -->
                    <div class="flex items-start">
                      <div class="flex items-center h-5">
                        <input
                          id="email-notifications"
                          type="checkbox"
                          formControlName="email_notifications_enabled"
                          class="focus:ring-indigo-500 h-4 w-4 text-indigo-600 border-gray-300 rounded"
                        />
                      </div>
                      <div class="ml-3 text-sm">
                        <label for="email-notifications" class="font-medium text-gray-700">
                          Email Notifications
                        </label>
                        <p class="text-gray-500">Send system notifications via email</p>
                      </div>
                    </div>

                    <!-- Backup Enabled -->
                    <div class="flex items-start">
                      <div class="flex items-center h-5">
                        <input
                          id="backup-enabled"
                          type="checkbox"
                          formControlName="backup_enabled"
                          class="focus:ring-indigo-500 h-4 w-4 text-indigo-600 border-gray-300 rounded"
                        />
                      </div>
                      <div class="ml-3 text-sm">
                        <label for="backup-enabled" class="font-medium text-gray-700">
                          Automatic Backups
                        </label>
                        <p class="text-gray-500">Enable scheduled system backups</p>
                      </div>
                    </div>

                    <!-- Backup Frequency -->
                    <div>
                      <label for="backup-frequency" class="block text-sm font-medium text-gray-700">
                        Backup Frequency (hours)
                      </label>
                      <select
                        id="backup-frequency"
                        formControlName="backup_frequency_hours"
                        class="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
                      >
                        <option [ngValue]="1">Every Hour</option>
                        <option [ngValue]="6">Every 6 Hours</option>
                        <option [ngValue]="12">Every 12 Hours</option>
                        <option [ngValue]="24">Daily</option>
                        <option [ngValue]="168">Weekly</option>
                      </select>
                    </div>
                  </div>

                  <div class="mt-6 space-y-3">
                    <button
                      type="submit"
                      [disabled]="backupForm.invalid || isSavingBackup"
                      class="w-full inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
                    >
                      {{ isSavingBackup ? 'Saving...' : 'Save Backup Settings' }}
                    </button>

                    <button
                      type="button"
                      (click)="triggerManualBackup()"
                      [disabled]="isCreatingBackup"
                      class="w-full inline-flex justify-center py-2 px-4 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
                    >
                      <svg class="-ml-1 mr-2 h-4 w-4" [class.animate-spin]="isCreatingBackup" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                      </svg>
                      {{ isCreatingBackup ? 'Creating Backup...' : 'Create Manual Backup' }}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  `
})
export class SystemSettingsComponent implements OnInit, OnDestroy {
  systemHealth: SystemHealth | null = null;
  
  generalForm!: FormGroup;
  uploadForm!: FormGroup;
  securityForm!: FormGroup;
  backupForm!: FormGroup;
  
  isLoadingHealth = false;
  isRefreshingHealth = false;
  isSavingGeneral = false;
  isSavingUpload = false;
  isSavingSecurity = false;
  isSavingBackup = false;
  isCreatingBackup = false;
  
  private subscriptions: Subscription[] = [];

  constructor(
    private fb: FormBuilder,
    private adminService: AdminService,
    private authService: AuthService,
    private errorHandler: ErrorHandlerService
  ) {
    this.initializeForms();
  }

  ngOnInit(): void {
    this.loadSystemHealth();
    this.loadSettings();
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(sub => sub.unsubscribe());
  }

  private initializeForms(): void {
    this.generalForm = this.fb.group({
      maintenance_mode: [false],
      registration_enabled: [true],
      session_timeout_minutes: [30, [Validators.required, Validators.min(5), Validators.max(1440)]]
    });

    this.uploadForm = this.fb.group({
      max_file_size_mb: [10, [Validators.required, Validators.min(1), Validators.max(100)]],
      max_concurrent_uploads: [3, [Validators.required, Validators.min(1), Validators.max(10)]],
      processing_queue_size: [10, [Validators.required, Validators.min(1), Validators.max(100)]]
    });

    this.securityForm = this.fb.group({
      rate_limiting_enabled: [true],
      max_requests_per_minute: [60, [Validators.required, Validators.min(10), Validators.max(1000)]],
      log_retention_days: [30, [Validators.required, Validators.min(7), Validators.max(365)]]
    });

    this.backupForm = this.fb.group({
      email_notifications_enabled: [true],
      backup_enabled: [true],
      backup_frequency_hours: [24, [Validators.required]]
    });
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

  private loadSettings(): void {
    // Load settings from localStorage or API
    const savedSettings = localStorage.getItem('system_settings');
    if (savedSettings) {
      const settings: SystemSettings = JSON.parse(savedSettings);
      
      this.generalForm.patchValue({
        maintenance_mode: settings.maintenance_mode,
        registration_enabled: settings.registration_enabled,
        session_timeout_minutes: settings.session_timeout_minutes
      });

      this.uploadForm.patchValue({
        max_file_size_mb: settings.max_file_size_mb,
        max_concurrent_uploads: settings.max_concurrent_uploads,
        processing_queue_size: settings.processing_queue_size
      });

      this.securityForm.patchValue({
        rate_limiting_enabled: settings.rate_limiting_enabled,
        max_requests_per_minute: settings.max_requests_per_minute,
        log_retention_days: settings.log_retention_days
      });

      this.backupForm.patchValue({
        email_notifications_enabled: settings.email_notifications_enabled,
        backup_enabled: settings.backup_enabled,
        backup_frequency_hours: settings.backup_frequency_hours
      });
    }
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

  saveGeneralSettings(): void {
    if (this.generalForm.valid) {
      this.isSavingGeneral = true;
      
      // Simulate API call
      setTimeout(() => {
        this.saveToStorage();
        this.errorHandler.showSuccess('General settings saved successfully');
        this.isSavingGeneral = false;
      }, 1000);
    }
  }

  saveUploadSettings(): void {
    if (this.uploadForm.valid) {
      this.isSavingUpload = true;
      
      // Simulate API call
      setTimeout(() => {
        this.saveToStorage();
        this.errorHandler.showSuccess('Upload settings saved successfully');
        this.isSavingUpload = false;
      }, 1000);
    }
  }

  saveSecuritySettings(): void {
    if (this.securityForm.valid) {
      this.isSavingSecurity = true;
      
      // Simulate API call
      setTimeout(() => {
        this.saveToStorage();
        this.errorHandler.showSuccess('Security settings saved successfully');
        this.isSavingSecurity = false;
      }, 1000);
    }
  }

  saveBackupSettings(): void {
    if (this.backupForm.valid) {
      this.isSavingBackup = true;
      
      // Simulate API call
      setTimeout(() => {
        this.saveToStorage();
        this.errorHandler.showSuccess('Backup settings saved successfully');
        this.isSavingBackup = false;
      }, 1000);
    }
  }

  triggerManualBackup(): void {
    this.isCreatingBackup = true;
    
    // Simulate backup creation
    setTimeout(() => {
      this.errorHandler.showSuccess('Manual backup created successfully');
      this.isCreatingBackup = false;
    }, 3000);
  }

  private saveToStorage(): void {
    const settings: SystemSettings = {
      ...this.generalForm.value,
      ...this.uploadForm.value,
      ...this.securityForm.value,
      ...this.backupForm.value,
      allowed_file_types: ['pdf'] // Static for now
    };
    
    localStorage.setItem('system_settings', JSON.stringify(settings));
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
}
