import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { Subscription } from 'rxjs';
import { AdminService, UserListFilters, UserListResponse, AdminUserUpdate } from '../../shared/services/admin.service';
import { AuthService, User } from '../../shared/services/auth.service';
import { ErrorHandlerService } from '../../shared/services/error-handler.service';
import { NavigationComponent } from '../../shared/components/navigation/navigation.component';
import { LoadingComponent } from '../../shared/components/loading/loading.component';
import { ConfirmationDialogComponent } from '../../shared/components/confirmation-dialog/confirmation-dialog.component';

@Component({
  selector: 'app-user-management',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule, NavigationComponent, LoadingComponent, ConfirmationDialogComponent],
  template: `
    <div class="min-h-screen bg-gray-50">
      <app-navigation></app-navigation>

      <main class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div class="px-4 py-6 sm:px-0">
          <!-- Header -->
          <div class="sm:flex sm:items-center sm:justify-between mb-8">
            <div>
              <h1 class="text-3xl font-bold text-gray-900">User Management</h1>
              <p class="mt-1 text-sm text-gray-600">
                Manage user accounts, roles, and permissions
              </p>
            </div>
            <div class="mt-4 sm:mt-0 flex space-x-3">
              <button
                type="button"
                (click)="exportUsers()"
                [disabled]="isExporting"
                class="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
              >
                <svg class="-ml-1 mr-2 h-4 w-4" [class.animate-spin]="isExporting" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-4-4m4 4l4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {{ isExporting ? 'Exporting...' : 'Export Users' }}
              </button>
              
              <button
                type="button"
                *ngIf="selectedUsers.length > 0"
                (click)="showBulkActions = !showBulkActions"
                class="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
              >
                Bulk Actions ({{ selectedUsers.length }})
              </button>
            </div>
          </div>

          <!-- Filters -->
          <div class="bg-white shadow rounded-lg mb-6">
            <div class="px-4 py-5 sm:p-6">
              <div class="grid grid-cols-1 gap-4 sm:grid-cols-5">
                <!-- Search -->
                <div class="sm:col-span-2">
                  <label for="search" class="block text-sm font-medium text-gray-700">Search</label>
                  <div class="mt-1 relative rounded-md shadow-sm">
                    <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <svg class="h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                      </svg>
                    </div>
                    <input
                      type="text"
                      id="search"
                      [(ngModel)]="filters.search"
                      (input)="applyFilters()"
                      class="focus:ring-indigo-500 focus:border-indigo-500 block w-full pl-10 sm:text-sm border-gray-300 rounded-md"
                      placeholder="Search by email or name..."
                    />
                  </div>
                </div>

                <!-- Role Filter -->
                <div>
                  <label for="roleFilter" class="block text-sm font-medium text-gray-700">Role</label>
                  <select
                    id="roleFilter"
                    [(ngModel)]="filters.role"
                    (change)="applyFilters()"
                    class="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
                  >
                    <option value="">All Roles</option>
                    <option value="admin">Admin</option>
                    <option value="user">User</option>
                  </select>
                </div>

                <!-- Status Filter -->
                <div>
                  <label for="statusFilter" class="block text-sm font-medium text-gray-700">Status</label>
                  <select
                    id="statusFilter"
                    [(ngModel)]="filters.is_active"
                    (change)="applyFilters()"
                    class="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
                  >
                    <option [ngValue]="undefined">All Status</option>
                    <option [ngValue]="true">Active</option>
                    <option [ngValue]="false">Inactive</option>
                  </select>
                </div>

                <!-- Sort -->
                <div>
                  <label for="sortBy" class="block text-sm font-medium text-gray-700">Sort By</label>
                  <select
                    id="sortBy"
                    [(ngModel)]="filters.sort_by"
                    (change)="applyFilters()"
                    class="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
                  >
                    <option value="created_at">Created Date</option>
                    <option value="email">Email</option>
                    <option value="last_login">Last Login</option>
                    <option value="login_count">Login Count</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          <!-- Bulk Actions Panel -->
          <div *ngIf="showBulkActions && selectedUsers.length > 0" class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
            <div class="flex items-center justify-between">
              <div class="flex items-center">
                <svg class="h-5 w-5 text-blue-400 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span class="text-sm font-medium text-blue-800">{{ selectedUsers.length }} users selected</span>
              </div>
              <div class="flex space-x-2">
                <button
                  type="button"
                  (click)="bulkActivateUsers()"
                  [disabled]="isBulkProcessing"
                  class="inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded text-green-700 bg-green-100 hover:bg-green-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50"
                >
                  Activate
                </button>
                <button
                  type="button"
                  (click)="bulkDeactivateUsers()"
                  [disabled]="isBulkProcessing"
                  class="inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded text-yellow-700 bg-yellow-100 hover:bg-yellow-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-yellow-500 disabled:opacity-50"
                >
                  Deactivate
                </button>
                <button
                  type="button"
                  (click)="confirmBulkDelete()"
                  [disabled]="isBulkProcessing"
                  class="inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded text-red-700 bg-red-100 hover:bg-red-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50"
                >
                  Delete
                </button>
                <button
                  type="button"
                  (click)="clearSelection()"
                  class="inline-flex items-center px-3 py-1.5 border border-gray-300 text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                >
                  Clear
                </button>
              </div>
            </div>
          </div>

          <!-- Users Table -->
          <div class="bg-white shadow overflow-hidden sm:rounded-md">
            <!-- Loading State -->
            <div *ngIf="isLoading" class="p-6">
              <app-loading message="Loading users..." size="md"></app-loading>
            </div>

            <!-- Empty State -->
            <div *ngIf="!isLoading && (!userList || userList.users.length === 0)" class="text-center py-12">
              <svg class="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
                <path d="M34 40h10v-4a6 6 0 00-10.712-3.714M34 40H14m20 0v-4a9.971 9.971 0 00-.712-3.714M14 40H4v-4a6 6 0 0110.713-3.714M14 40v-4c0-1.313.253-2.566.713-3.714m0 0A10.003 10.003 0 0124 26c4.21 0 7.813 2.602 9.288 6.286M30 14a6 6 0 11-12 0 6 6 0 0112 0zm12 6a4 4 0 11-8 0 4 4 0 018 0zm-28 0a4 4 0 11-8 0 4 4 0 018 0z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
              <h3 class="mt-2 text-sm font-medium text-gray-900">No users found</h3>
              <p class="mt-1 text-sm text-gray-500">
                {{ filters.search || filters.role || filters.is_active !== undefined ? 'Try adjusting your search criteria.' : 'No users have been registered yet.' }}
              </p>
            </div>

            <!-- Users List -->
            <div *ngIf="!isLoading && userList && userList.users.length > 0">
              <!-- Table Header -->
              <div class="bg-gray-50 px-6 py-3 border-b border-gray-200">
                <div class="flex items-center">
                  <input
                    type="checkbox"
                    [checked]="isAllSelected()"
                    [indeterminate]="isPartiallySelected()"
                    (change)="toggleSelectAll()"
                    class="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                  />
                  <span class="ml-3 text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Select All ({{ userList.total }} total)
                  </span>
                </div>
              </div>

              <!-- User Rows -->
              <ul class="divide-y divide-gray-200">
                <li *ngFor="let user of userList.users" class="px-6 py-4 hover:bg-gray-50">
                  <div class="flex items-center justify-between">
                    <div class="flex items-center min-w-0 flex-1">
                      <input
                        type="checkbox"
                        [checked]="isUserSelected(user.id)"
                        (change)="toggleUserSelection(user.id)"
                        class="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                      />
                      
                      <div class="ml-4 min-w-0 flex-1">
                        <div class="flex items-center">
                          <div class="flex-shrink-0 h-10 w-10">
                            <div class="h-10 w-10 rounded-full bg-gray-300 flex items-center justify-center">
                              <span class="text-sm font-medium text-gray-700">
                                {{ getUserInitials(user) }}
                              </span>
                            </div>
                          </div>
                          
                          <div class="ml-4 min-w-0 flex-1">
                            <div class="flex items-center">
                              <p class="text-sm font-medium text-gray-900 truncate">
                                {{ getUserDisplayName(user) }}
                              </p>
                              <span [ngClass]="getRoleBadgeClass(user.role)" 
                                    class="ml-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium">
                                {{ user.role }}
                              </span>
                            </div>
                            <p class="text-sm text-gray-500 truncate">{{ user.email }}</p>
                            <div class="mt-1 flex items-center text-xs text-gray-500 space-x-4">
                              <span class="flex items-center">
                                <span [ngClass]="user.is_active ? 'text-green-600' : 'text-red-600'" class="font-medium">
                                  {{ user.is_active ? 'Active' : 'Inactive' }}
                                </span>
                              </span>
                              <span class="flex items-center">
                                <span [ngClass]="user.is_verified ? 'text-green-600' : 'text-yellow-600'" class="font-medium">
                                  {{ user.is_verified ? 'Verified' : 'Unverified' }}
                                </span>
                              </span>
                              <span>Joined {{ user.created_at | date:'shortDate' }}</span>
                              <span *ngIf="user.last_login">Last login {{ user.last_login | date:'short' }}</span>
                              <span *ngIf="user.login_count">{{ user.login_count }} logins</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                    
                    <div class="flex items-center space-x-2 ml-4">
                      <!-- Edit Button -->
                      <button
                        type="button"
                        (click)="editUser(user)"
                        class="inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded text-indigo-700 bg-indigo-100 hover:bg-indigo-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                      >
                        Edit
                      </button>

                      <!-- Toggle Status -->
                      <button
                        type="button"
                        (click)="toggleUserStatus(user)"
                        [ngClass]="user.is_active ? 'text-yellow-700 bg-yellow-100 hover:bg-yellow-200' : 'text-green-700 bg-green-100 hover:bg-green-200'"
                        class="inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded focus:outline-none focus:ring-2 focus:ring-offset-2"
                      >
                        {{ user.is_active ? 'Deactivate' : 'Activate' }}
                      </button>

                      <!-- Delete Button -->
                      <button
                        type="button"
                        (click)="confirmDeleteUser(user)"
                        class="inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded text-red-700 bg-red-100 hover:bg-red-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </li>
              </ul>

              <!-- Pagination -->
              <div *ngIf="userList.total_pages > 1" class="bg-white px-4 py-3 border-t border-gray-200 sm:px-6">
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
                      [disabled]="filters.page === userList.total_pages"
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
                        <span class="font-medium">{{ userList.total }}</span>
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
                          [disabled]="filters.page === userList.total_pages"
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

      <!-- Confirmation Dialog -->
      <app-confirmation-dialog
        [isOpen]="showDeleteConfirmation"
        [title]="deleteConfirmationTitle"
        [message]="deleteConfirmationMessage"
        [type]="'danger'"
        [confirmText]="'Delete'"
        [cancelText]="'Cancel'"
        [processingText]="'Deleting...'"
        [isProcessing]="isDeleting"
        (confirmed)="executeDelete()"
        (cancelled)="cancelDelete()"
      ></app-confirmation-dialog>
    </div>
  `
})
export class UserManagementComponent implements OnInit, OnDestroy {
  userList: UserListResponse | null = null;
  filters: UserListFilters = {
    page: 1,
    limit: 20,
    sort_by: 'created_at',
    sort_order: 'desc'
  };
  
  selectedUsers: string[] = [];
  showBulkActions = false;
  
  isLoading = false;
  isExporting = false;
  isBulkProcessing = false;
  isDeleting = false;
  
  // Delete confirmation
  showDeleteConfirmation = false;
  deleteConfirmationTitle = '';
  deleteConfirmationMessage = '';
  pendingDeleteAction: (() => void) | null = null;
  
  private subscriptions: Subscription[] = [];

  constructor(
    private adminService: AdminService,
    private authService: AuthService,
    private errorHandler: ErrorHandlerService
  ) {}

  ngOnInit(): void {
    this.loadUsers();
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(sub => sub.unsubscribe());
  }

  loadUsers(): void {
    this.isLoading = true;
    this.subscriptions.push(
      this.adminService.getUsers(this.filters).subscribe({
        next: (userList) => {
          this.userList = userList;
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
    this.clearSelection();
    this.loadUsers();
  }

  // Selection methods
  isUserSelected(userId: string): boolean {
    return this.selectedUsers.includes(userId);
  }

  toggleUserSelection(userId: string): void {
    if (this.isUserSelected(userId)) {
      this.selectedUsers = this.selectedUsers.filter(id => id !== userId);
    } else {
      this.selectedUsers.push(userId);
    }
  }

  isAllSelected(): boolean {
    return this.userList ? this.selectedUsers.length === this.userList.users.length : false;
  }

  isPartiallySelected(): boolean {
    return this.selectedUsers.length > 0 && !this.isAllSelected();
  }

  toggleSelectAll(): void {
    if (this.isAllSelected()) {
      this.clearSelection();
    } else {
      this.selectedUsers = this.userList?.users.map(user => user.id) || [];
    }
  }

  clearSelection(): void {
    this.selectedUsers = [];
    this.showBulkActions = false;
  }

  // User actions
  editUser(user: User): void {
    // Navigate to user edit page or open modal
    this.errorHandler.showInfo('User editing functionality will be implemented');
  }

  toggleUserStatus(user: User): void {
    const updates: AdminUserUpdate = {
      is_active: !user.is_active
    };

    this.subscriptions.push(
      this.adminService.updateUser(user.id, updates).subscribe({
        next: (updatedUser) => {
          // Update the user in the list
          if (this.userList) {
            const index = this.userList.users.findIndex(u => u.id === user.id);
            if (index !== -1) {
              this.userList.users[index] = updatedUser;
            }
          }
          this.errorHandler.showSuccess(`User ${updatedUser.is_active ? 'activated' : 'deactivated'} successfully`);
        },
        error: (error) => {
          this.errorHandler.showError(error);
        }
      })
    );
  }

  confirmDeleteUser(user: User): void {
    this.deleteConfirmationTitle = 'Delete User';
    this.deleteConfirmationMessage = `Are you sure you want to delete ${this.getUserDisplayName(user)}? This action cannot be undone.`;
    this.pendingDeleteAction = () => this.deleteUser(user.id);
    this.showDeleteConfirmation = true;
  }

  private deleteUser(userId: string): void {
    this.isDeleting = true;
    this.subscriptions.push(
      this.adminService.deleteUser(userId).subscribe({
        next: () => {
          this.loadUsers(); // Reload the list
          this.errorHandler.showSuccess('User deleted successfully');
          this.isDeleting = false;
          this.showDeleteConfirmation = false;
        },
        error: (error) => {
          this.errorHandler.showError(error);
          this.isDeleting = false;
        }
      })
    );
  }

  // Bulk actions
  bulkActivateUsers(): void {
    this.isBulkProcessing = true;
    const updates: AdminUserUpdate = { is_active: true };
    
    this.subscriptions.push(
      this.adminService.bulkUpdateUsers(this.selectedUsers, updates).subscribe({
        next: () => {
          this.loadUsers();
          this.clearSelection();
          this.errorHandler.showSuccess('Users activated successfully');
          this.isBulkProcessing = false;
        },
        error: (error) => {
          this.errorHandler.showError(error);
          this.isBulkProcessing = false;
        }
      })
    );
  }

  bulkDeactivateUsers(): void {
    this.isBulkProcessing = true;
    const updates: AdminUserUpdate = { is_active: false };
    
    this.subscriptions.push(
      this.adminService.bulkUpdateUsers(this.selectedUsers, updates).subscribe({
        next: () => {
          this.loadUsers();
          this.clearSelection();
          this.errorHandler.showSuccess('Users deactivated successfully');
          this.isBulkProcessing = false;
        },
        error: (error) => {
          this.errorHandler.showError(error);
          this.isBulkProcessing = false;
        }
      })
    );
  }

  confirmBulkDelete(): void {
    this.deleteConfirmationTitle = 'Delete Multiple Users';
    this.deleteConfirmationMessage = `Are you sure you want to delete ${this.selectedUsers.length} users? This action cannot be undone.`;
    this.pendingDeleteAction = () => this.bulkDeleteUsers();
    this.showDeleteConfirmation = true;
  }

  private bulkDeleteUsers(): void {
    this.isDeleting = true;
    this.subscriptions.push(
      this.adminService.bulkDeleteUsers(this.selectedUsers).subscribe({
        next: () => {
          this.loadUsers();
          this.clearSelection();
          this.errorHandler.showSuccess('Users deleted successfully');
          this.isDeleting = false;
          this.showDeleteConfirmation = false;
        },
        error: (error) => {
          this.errorHandler.showError(error);
          this.isDeleting = false;
        }
      })
    );
  }

  // Export
  exportUsers(): void {
    this.isExporting = true;
    this.subscriptions.push(
      this.adminService.exportUserData().subscribe({
        next: (blob) => {
          // Create download link
          const url = window.URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = `users-export-${new Date().toISOString().split('T')[0]}.csv`;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          window.URL.revokeObjectURL(url);
          
          this.errorHandler.showSuccess('Users exported successfully');
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
      this.loadUsers();
    }
  }

  nextPage(): void {
    if (this.filters.page && this.userList && this.filters.page < this.userList.total_pages) {
      this.filters.page++;
      this.loadUsers();
    }
  }

  getStartIndex(): number {
    if (!this.userList || !this.filters.page || !this.filters.limit) return 0;
    return (this.filters.page - 1) * this.filters.limit + 1;
  }

  getEndIndex(): number {
    if (!this.userList || !this.filters.page || !this.filters.limit) return 0;
    const end = this.filters.page * this.filters.limit;
    return Math.min(end, this.userList.total);
  }

  // Confirmation dialog
  executeDelete(): void {
    if (this.pendingDeleteAction) {
      this.pendingDeleteAction();
      this.pendingDeleteAction = null;
    }
  }

  cancelDelete(): void {
    this.showDeleteConfirmation = false;
    this.pendingDeleteAction = null;
    this.isDeleting = false;
  }

  // Utility methods
  getUserDisplayName(user: User): string {
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

  getUserInitials(user: User): string {
    if (user.first_name && user.last_name) {
      return `${user.first_name.charAt(0)}${user.last_name.charAt(0)}`.toUpperCase();
    } else if (user.first_name) {
      return user.first_name.charAt(0).toUpperCase();
    } else if (user.last_name) {
      return user.last_name.charAt(0).toUpperCase();
    } else {
      return user.email.charAt(0).toUpperCase();
    }
  }

  getRoleBadgeClass(role: string): string {
    switch (role) {
      case 'admin':
        return 'bg-purple-100 text-purple-800';
      case 'user':
        return 'bg-blue-100 text-blue-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  }
}
