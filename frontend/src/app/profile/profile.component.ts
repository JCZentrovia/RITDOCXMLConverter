import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { Subscription } from 'rxjs';
import { AuthService, User, UserProfileUpdate, PasswordChangeRequest } from '../shared/services/auth.service';
import { ErrorHandlerService } from '../shared/services/error-handler.service';
import { NavigationComponent } from '../shared/components/navigation/navigation.component';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterModule, NavigationComponent],
  template: `
    <div class="min-h-screen bg-gray-50">
      <app-navigation></app-navigation>

      <main class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div class="px-4 py-6 sm:px-0">
          <!-- Header -->
          <div class="mb-8">
            <h1 class="text-3xl font-bold text-gray-900">Profile Settings</h1>
            <p class="mt-1 text-sm text-gray-600">
              Manage your account information and preferences
            </p>
          </div>

          <div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <!-- Profile Information -->
            <div class="lg:col-span-2">
              <div class="bg-white shadow rounded-lg">
                <div class="px-4 py-5 sm:p-6">
                  <h3 class="text-lg leading-6 font-medium text-gray-900 mb-4">
                    Profile Information
                  </h3>
                  
                  <form [formGroup]="profileForm" (ngSubmit)="updateProfile()">
                    <div class="grid grid-cols-1 gap-6 sm:grid-cols-2">
                      <!-- Email -->
                      <div class="sm:col-span-2">
                        <label for="email" class="block text-sm font-medium text-gray-700">
                          Email address
                        </label>
                        <div class="mt-1">
                          <input
                            type="email"
                            id="email"
                            formControlName="email"
                            class="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md"
                            [class.border-red-300]="profileForm.get('email')?.invalid && profileForm.get('email')?.touched"
                          />
                          <div *ngIf="profileForm.get('email')?.invalid && profileForm.get('email')?.touched" 
                               class="mt-1 text-sm text-red-600">
                            <div *ngIf="profileForm.get('email')?.errors?.['required']">Email is required</div>
                            <div *ngIf="profileForm.get('email')?.errors?.['email']">Please enter a valid email</div>
                          </div>
                        </div>
                      </div>

                      <!-- First Name -->
                      <div>
                        <label for="firstName" class="block text-sm font-medium text-gray-700">
                          First name
                        </label>
                        <div class="mt-1">
                          <input
                            type="text"
                            id="firstName"
                            formControlName="first_name"
                            class="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md"
                            [class.border-red-300]="profileForm.get('first_name')?.invalid && profileForm.get('first_name')?.touched"
                          />
                          <div *ngIf="profileForm.get('first_name')?.invalid && profileForm.get('first_name')?.touched" 
                               class="mt-1 text-sm text-red-600">
                            <div *ngIf="profileForm.get('first_name')?.errors?.['minlength']">First name must be at least 1 character</div>
                            <div *ngIf="profileForm.get('first_name')?.errors?.['maxlength']">First name cannot exceed 50 characters</div>
                          </div>
                        </div>
                      </div>

                      <!-- Last Name -->
                      <div>
                        <label for="lastName" class="block text-sm font-medium text-gray-700">
                          Last name
                        </label>
                        <div class="mt-1">
                          <input
                            type="text"
                            id="lastName"
                            formControlName="last_name"
                            class="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md"
                            [class.border-red-300]="profileForm.get('last_name')?.invalid && profileForm.get('last_name')?.touched"
                          />
                          <div *ngIf="profileForm.get('last_name')?.invalid && profileForm.get('last_name')?.touched" 
                               class="mt-1 text-sm text-red-600">
                            <div *ngIf="profileForm.get('last_name')?.errors?.['minlength']">Last name must be at least 1 character</div>
                            <div *ngIf="profileForm.get('last_name')?.errors?.['maxlength']">Last name cannot exceed 50 characters</div>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div class="mt-6">
                      <button
                        type="submit"
                        [disabled]="profileForm.invalid || isUpdatingProfile"
                        class="inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <span *ngIf="isUpdatingProfile" class="mr-2">
                          <svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                        </span>
                        {{ isUpdatingProfile ? 'Updating...' : 'Update Profile' }}
                      </button>
                    </div>
                  </form>
                </div>
              </div>

              <!-- Change Password -->
              <div class="bg-white shadow rounded-lg mt-6">
                <div class="px-4 py-5 sm:p-6">
                  <h3 class="text-lg leading-6 font-medium text-gray-900 mb-4">
                    Change Password
                  </h3>
                  
                  <form [formGroup]="passwordForm" (ngSubmit)="changePassword()">
                    <div class="space-y-6">
                      <!-- Current Password -->
                      <div>
                        <label for="currentPassword" class="block text-sm font-medium text-gray-700">
                          Current password
                        </label>
                        <div class="mt-1">
                          <input
                            type="password"
                            id="currentPassword"
                            formControlName="current_password"
                            class="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md"
                            [class.border-red-300]="passwordForm.get('current_password')?.invalid && passwordForm.get('current_password')?.touched"
                          />
                          <div *ngIf="passwordForm.get('current_password')?.invalid && passwordForm.get('current_password')?.touched" 
                               class="mt-1 text-sm text-red-600">
                            <div *ngIf="passwordForm.get('current_password')?.errors?.['required']">Current password is required</div>
                          </div>
                        </div>
                      </div>

                      <!-- New Password -->
                      <div>
                        <label for="newPassword" class="block text-sm font-medium text-gray-700">
                          New password
                        </label>
                        <div class="mt-1">
                          <input
                            type="password"
                            id="newPassword"
                            formControlName="new_password"
                            class="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md"
                            [class.border-red-300]="passwordForm.get('new_password')?.invalid && passwordForm.get('new_password')?.touched"
                          />
                          <div *ngIf="passwordForm.get('new_password')?.invalid && passwordForm.get('new_password')?.touched" 
                               class="mt-1 text-sm text-red-600">
                            <div *ngIf="passwordForm.get('new_password')?.errors?.['required']">New password is required</div>
                            <div *ngIf="passwordForm.get('new_password')?.errors?.['minlength']">Password must be at least 6 characters</div>
                          </div>
                        </div>
                      </div>

                      <!-- Confirm Password -->
                      <div>
                        <label for="confirmPassword" class="block text-sm font-medium text-gray-700">
                          Confirm new password
                        </label>
                        <div class="mt-1">
                          <input
                            type="password"
                            id="confirmPassword"
                            formControlName="confirm_password"
                            class="shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md"
                            [class.border-red-300]="passwordForm.get('confirm_password')?.invalid && passwordForm.get('confirm_password')?.touched"
                          />
                          <div *ngIf="passwordForm.get('confirm_password')?.invalid && passwordForm.get('confirm_password')?.touched" 
                               class="mt-1 text-sm text-red-600">
                            <div *ngIf="passwordForm.get('confirm_password')?.errors?.['required']">Please confirm your password</div>
                            <div *ngIf="passwordForm.get('confirm_password')?.errors?.['passwordMismatch']">Passwords do not match</div>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div class="mt-6">
                      <button
                        type="submit"
                        [disabled]="passwordForm.invalid || isChangingPassword"
                        class="inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <span *ngIf="isChangingPassword" class="mr-2">
                          <svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                        </span>
                        {{ isChangingPassword ? 'Changing...' : 'Change Password' }}
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            </div>

            <!-- Account Information Sidebar -->
            <div class="lg:col-span-1">
              <div class="bg-white shadow rounded-lg">
                <div class="px-4 py-5 sm:p-6">
                  <h3 class="text-lg leading-6 font-medium text-gray-900 mb-4">
                    Account Information
                  </h3>
                  
                  <dl class="space-y-4">
                    <div>
                      <dt class="text-sm font-medium text-gray-500">Account Status</dt>
                      <dd class="mt-1">
                        <span [ngClass]="currentUser?.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'" 
                              class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium">
                          {{ currentUser?.is_active ? 'Active' : 'Inactive' }}
                        </span>
                      </dd>
                    </div>

                    <div>
                      <dt class="text-sm font-medium text-gray-500">Email Verification</dt>
                      <dd class="mt-1">
                        <span [ngClass]="currentUser?.is_verified ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'" 
                              class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium">
                          {{ currentUser?.is_verified ? 'Verified' : 'Unverified' }}
                        </span>
                      </dd>
                    </div>


                    <div>
                      <dt class="text-sm font-medium text-gray-500">Member Since</dt>
                      <dd class="mt-1 text-sm text-gray-900">{{ currentUser?.created_at | date:'longDate' }}</dd>
                    </div>



                  </dl>
                </div>
              </div>

              <!-- Quick Actions -->
              <div class="bg-white shadow rounded-lg mt-6">
                <div class="px-4 py-5 sm:p-6">
                  <h3 class="text-lg leading-6 font-medium text-gray-900 mb-4">
                    Quick Actions
                  </h3>
                  
                  <div class="space-y-3">
                    <button
                      type="button"
                      routerLink="/dashboard"
                      class="w-full inline-flex justify-center items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                    >
                      <svg class="-ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2H5a2 2 0 00-2-2z" />
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5a2 2 0 012-2h4a2 2 0 012 2v2H8V5z" />
                      </svg>
                      Go to Dashboard
                    </button>

                    <button
                      type="button"
                      routerLink="/manuscripts"
                      class="w-full inline-flex justify-center items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                    >
                      <svg class="-ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      View Manuscripts
                    </button>

                    <button
                      type="button"
                      (click)="refreshProfile()"
                      [disabled]="isRefreshing"
                      class="w-full inline-flex justify-center items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
                    >
                      <svg class="-ml-1 mr-2 h-4 w-4" [class.animate-spin]="isRefreshing" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                      {{ isRefreshing ? 'Refreshing...' : 'Refresh Profile' }}
                    </button>
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
export class ProfileComponent implements OnInit, OnDestroy {
  currentUser: User | null = null;
  profileForm: FormGroup;
  passwordForm: FormGroup;
  
  isUpdatingProfile = false;
  isChangingPassword = false;
  isRefreshing = false;
  
  private subscription?: Subscription;

  constructor(
    private fb: FormBuilder,
    private authService: AuthService,
    private errorHandler: ErrorHandlerService
  ) {
    this.profileForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      first_name: ['', [Validators.minLength(1), Validators.maxLength(50)]],
      last_name: ['', [Validators.minLength(1), Validators.maxLength(50)]]
    });

    this.passwordForm = this.fb.group({
      current_password: ['', [Validators.required]],
      new_password: ['', [Validators.required, Validators.minLength(6)]],
      confirm_password: ['', [Validators.required]]
    }, { validators: this.passwordMatchValidator });
  }

  ngOnInit(): void {
    this.subscription = this.authService.currentUser$.subscribe(user => {
      this.currentUser = user;
      if (user) {
        this.profileForm.patchValue({
          email: user.email,
          first_name: user.first_name || '',
          last_name: user.last_name || ''
        });
      }
    });

    // Load fresh profile data
    this.refreshProfile();
  }

  ngOnDestroy(): void {
    if (this.subscription) {
      this.subscription.unsubscribe();
    }
  }

  passwordMatchValidator(form: FormGroup) {
    const newPassword = form.get('new_password');
    const confirmPassword = form.get('confirm_password');
    
    if (newPassword && confirmPassword && newPassword.value !== confirmPassword.value) {
      confirmPassword.setErrors({ passwordMismatch: true });
    } else if (confirmPassword?.errors?.['passwordMismatch']) {
      delete confirmPassword.errors['passwordMismatch'];
      if (Object.keys(confirmPassword.errors).length === 0) {
        confirmPassword.setErrors(null);
      }
    }
    
    return null;
  }

  updateProfile(): void {
    if (this.profileForm.valid) {
      this.isUpdatingProfile = true;
      
      const profileData: UserProfileUpdate = this.profileForm.value;
      
      this.authService.updateProfile(profileData).subscribe({
        next: (user: User) => {
          this.errorHandler.showSuccess('Profile updated successfully');
          this.isUpdatingProfile = false;
        },
        error: (error: any) => {
          this.errorHandler.showError(error);
          this.isUpdatingProfile = false;
        }
      });
    }
  }

  changePassword(): void {
    if (this.passwordForm.valid) {
      this.isChangingPassword = true;
      
      const passwordData: PasswordChangeRequest = this.passwordForm.value;
      
      this.authService.changePassword(passwordData).subscribe({
        next: () => {
          this.errorHandler.showSuccess('Password changed successfully');
          this.passwordForm.reset();
          this.isChangingPassword = false;
        },
        error: (error: any) => {
          this.errorHandler.showError(error);
          this.isChangingPassword = false;
        }
      });
    }
  }

  refreshProfile(): void {
    this.isRefreshing = true;
    
    this.authService.getCurrentUserProfile().subscribe({
      next: (user: User) => {
        this.errorHandler.showSuccess('Profile refreshed');
        this.isRefreshing = false;
      },
      error: (error: any) => {
        this.errorHandler.showError(error);
        this.isRefreshing = false;
      }
    });
  }
}
