import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { Subscription } from 'rxjs';
import { AuthService, User } from '../shared/services/auth.service';
import { ErrorHandlerService } from '../shared/services/error-handler.service';
import { NavigationComponent } from '../shared/components/navigation/navigation.component';

interface AppSettings {
  theme: 'light' | 'dark' | 'auto';
  notifications: {
    email: boolean;
    browser: boolean;
    processing: boolean;
    marketing: boolean;
  };
  privacy: {
    profileVisible: boolean;
    activityVisible: boolean;
    analyticsEnabled: boolean;
  };
  preferences: {
    language: string;
    timezone: string;
    dateFormat: string;
    autoDownload: boolean;
  };
}

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [CommonModule, RouterModule, NavigationComponent],
  template: `
    <div class="min-h-screen bg-gray-50">
      <app-navigation></app-navigation>

      <main class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div class="px-4 py-6 sm:px-0">
          <!-- Header -->
          <div class="mb-8">
            <h1 class="text-3xl font-bold text-gray-900">Settings</h1>
            <p class="mt-1 text-sm text-gray-600">
              Manage your application preferences and account settings
            </p>
          </div>

          <div class="grid grid-cols-1 gap-6 lg:grid-cols-4">
            <!-- Settings Navigation -->
            <div class="lg:col-span-1">
              <nav class="space-y-1">
                <button
                  *ngFor="let section of settingSections"
                  type="button"
                  (click)="activeSection = section.id"
                  [class]="activeSection === section.id 
                    ? 'bg-indigo-50 border-indigo-500 text-indigo-700' 
                    : 'border-transparent text-gray-900 hover:bg-gray-50 hover:text-gray-900'"
                  class="group border-l-4 px-3 py-2 flex items-center text-sm font-medium w-full text-left"
                >
                  <span [innerHTML]="section.icon" class="mr-3 h-5 w-5 flex-shrink-0"></span>
                  {{ section.name }}
                </button>
              </nav>
            </div>

            <!-- Settings Content -->
            <div class="lg:col-span-3">



              <!-- Account Settings -->
              <div *ngIf="activeSection === 'account'" class="space-y-6">
                <!-- Account Information -->
                <div class="bg-white shadow rounded-lg">
                  <div class="px-4 py-5 sm:p-6">
                    <h3 class="text-lg leading-6 font-medium text-gray-900 mb-4">
                      Account Information
                    </h3>
                    
                    <dl class="grid grid-cols-1 gap-x-4 gap-y-6 sm:grid-cols-2">
                      <div>
                        <dt class="text-sm font-medium text-gray-500">Email</dt>
                        <dd class="mt-1 text-sm text-gray-900">{{ currentUser?.email }}</dd>
                      </div>
                      <div>
                        <dt class="text-sm font-medium text-gray-500">Member since</dt>
                        <dd class="mt-1 text-sm text-gray-900">{{ currentUser?.created_at | date:'longDate' }}</dd>
                      </div>
                    </dl>

                    <div class="mt-6">
                      <button
                        type="button"
                        routerLink="/profile"
                        class="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                      >
                        Edit Profile
                      </button>
                    </div>
                  </div>
                </div>

                <!-- Danger Zone -->
                <div class="bg-white shadow rounded-lg">
                  <div class="px-4 py-5 sm:p-6">
                    <h3 class="text-lg leading-6 font-medium text-red-900 mb-4">
                      Danger Zone
                    </h3>
                    
                    <div class="space-y-4">
                      <div class="border border-red-200 rounded-md p-4">
                        <div class="flex justify-between items-start">
                          <div>
                            <h4 class="text-sm font-medium text-red-900">Delete Account</h4>
                            <p class="mt-1 text-sm text-red-700">
                              Permanently delete your account and all associated data. This action cannot be undone.
                            </p>
                          </div>
                          <button
                            type="button"
                            (click)="confirmDeleteAccount()"
                            class="ml-4 inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                          >
                            Delete Account
                          </button>
                        </div>
                      </div>
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
export class SettingsComponent implements OnInit, OnDestroy {
  currentUser: User | null = null;
  activeSection = 'account';
  
  
  private subscription?: Subscription;

  settingSections = [
    {
      id: 'account',
      name: 'Account',
      icon: '<svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>'
    }
  ];

  constructor(
    private authService: AuthService,
    private errorHandler: ErrorHandlerService
  ) {}

  ngOnInit(): void {
    this.subscription = this.authService.currentUser$.subscribe(user => {
      this.currentUser = user;
    });
  }

  ngOnDestroy(): void {
    if (this.subscription) {
      this.subscription.unsubscribe();
    }
  }


  confirmDeleteAccount(): void {
    const confirmation = confirm(
      'Are you sure you want to delete your account? This action cannot be undone and will permanently delete all your data including manuscripts.'
    );
    
    if (confirmation) {
      const doubleConfirmation = confirm(
        'This is your final warning. Deleting your account will permanently remove all your data. Type "DELETE" to confirm.'
      );
      
      if (doubleConfirmation) {
        this.errorHandler.showError('Account deletion functionality will be implemented in a future update');
      }
    }
  }
}
