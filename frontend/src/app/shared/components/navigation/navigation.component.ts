import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { Subscription } from 'rxjs';
import { AuthService, User } from '../../services/auth.service';
import { ErrorHandlerService } from '../../services/error-handler.service';

@Component({
  selector: 'app-navigation',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <nav class="bg-white shadow-lg">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between h-16">
          <!-- Logo and main navigation -->
          <div class="flex">
            <div class="flex-shrink-0 flex items-center">
              <h1 class="text-xl font-bold text-gray-900">
                <a routerLink="/dashboard" class="hover:text-indigo-600">
                  Manuscript Processor
                </a>
              </h1>
            </div>
            
            <!-- Main navigation links -->
            <div class="hidden sm:ml-6 sm:flex sm:space-x-8" *ngIf="currentUser">
              <a
                routerLink="/dashboard"
                routerLinkActive="border-indigo-500 text-gray-900"
                class="border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
              >
                Dashboard
              </a>
              
              <a
                routerLink="/manuscripts"
                routerLinkActive="border-indigo-500 text-gray-900"
                class="border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
              >
                Manuscripts
              </a>
              
              <a
                *ngIf="isAdmin"
                routerLink="/admin"
                routerLinkActive="border-indigo-500 text-gray-900"
                class="border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium"
              >
                Admin
              </a>
            </div>
          </div>

          <!-- User menu -->
          <div class="flex items-center space-x-4" *ngIf="currentUser">
            <div class="relative ml-3">
              <div>
                <button
                  type="button"
                  class="bg-white flex text-sm rounded-full focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                  (click)="toggleUserMenu()"
                  [attr.aria-expanded]="isUserMenuOpen"
                  aria-haspopup="true"
                >
                  <span class="sr-only">Open user menu</span>
                  <div class="h-8 w-8 rounded-full bg-indigo-500 flex items-center justify-center">
                    <span class="text-sm font-medium text-white">
                      {{ getUserInitials() }}
                    </span>
                  </div>
                </button>
              </div>

              <!-- User dropdown menu -->
              <div
                *ngIf="isUserMenuOpen"
                class="origin-top-right absolute right-0 mt-2 w-48 rounded-md shadow-lg py-1 bg-white ring-1 ring-black ring-opacity-5 focus:outline-none z-50"
                role="menu"
                aria-orientation="vertical"
                (clickOutside)="closeUserMenu()"
              >
                <div class="px-4 py-2 text-sm text-gray-700 border-b">
                  <div class="font-medium">{{ getUserDisplayName() }}</div>
                  <div class="text-gray-500">{{ currentUser.email }}</div>
                </div>
                
                <a
                  routerLink="/profile"
                  class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                  role="menuitem"
                  (click)="closeUserMenu()"
                >
                  Your Profile
                </a>
                
                <a
                  routerLink="/settings"
                  class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                  role="menuitem"
                  (click)="closeUserMenu()"
                >
                  Settings
                </a>
                
                <button
                  type="button"
                  class="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                  role="menuitem"
                  (click)="logout()"
                >
                  Sign out
                </button>
              </div>
            </div>
          </div>

          <!-- Mobile menu button -->
          <div class="flex items-center sm:hidden" *ngIf="currentUser">
            <button
              type="button"
              class="inline-flex items-center justify-center p-2 rounded-md text-gray-400 hover:text-gray-500 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-indigo-500"
              (click)="toggleMobileMenu()"
              [attr.aria-expanded]="isMobileMenuOpen"
            >
              <span class="sr-only">Open main menu</span>
              <!-- Hamburger icon -->
              <svg
                *ngIf="!isMobileMenuOpen"
                class="block h-6 w-6"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
              </svg>
              <!-- Close icon -->
              <svg
                *ngIf="isMobileMenuOpen"
                class="block h-6 w-6"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      <!-- Mobile menu -->
      <div class="sm:hidden" *ngIf="isMobileMenuOpen && currentUser">
        <div class="pt-2 pb-3 space-y-1">
          <a
            routerLink="/dashboard"
            routerLinkActive="bg-indigo-50 border-indigo-500 text-indigo-700"
            class="border-transparent text-gray-600 hover:bg-gray-50 hover:border-gray-300 hover:text-gray-800 block pl-3 pr-4 py-2 border-l-4 text-base font-medium"
            (click)="closeMobileMenu()"
          >
            Dashboard
          </a>
          
          <a
            routerLink="/manuscripts"
            routerLinkActive="bg-indigo-50 border-indigo-500 text-indigo-700"
            class="border-transparent text-gray-600 hover:bg-gray-50 hover:border-gray-300 hover:text-gray-800 block pl-3 pr-4 py-2 border-l-4 text-base font-medium"
            (click)="closeMobileMenu()"
          >
            Manuscripts
          </a>
          
          <a
            *ngIf="isAdmin"
            routerLink="/admin"
            routerLinkActive="bg-indigo-50 border-indigo-500 text-indigo-700"
            class="border-transparent text-gray-600 hover:bg-gray-50 hover:border-gray-300 hover:text-gray-800 block pl-3 pr-4 py-2 border-l-4 text-base font-medium"
            (click)="closeMobileMenu()"
          >
            Admin
          </a>
        </div>
        
        <div class="pt-4 pb-3 border-t border-gray-200">
          <div class="flex items-center px-4">
            <div class="flex-shrink-0">
              <div class="h-10 w-10 rounded-full bg-indigo-500 flex items-center justify-center">
                <span class="text-sm font-medium text-white">
                  {{ getUserInitials() }}
                </span>
              </div>
            </div>
            <div class="ml-3">
              <div class="text-base font-medium text-gray-800">{{ getUserDisplayName() }}</div>
              <div class="text-sm font-medium text-gray-500">{{ currentUser.email }}</div>
            </div>
          </div>
          
          <div class="mt-3 space-y-1">
            <a
              routerLink="/profile"
              class="block px-4 py-2 text-base font-medium text-gray-500 hover:text-gray-800 hover:bg-gray-100"
              (click)="closeMobileMenu()"
            >
              Your Profile
            </a>
            
            <a
              routerLink="/settings"
              class="block px-4 py-2 text-base font-medium text-gray-500 hover:text-gray-800 hover:bg-gray-100"
              (click)="closeMobileMenu()"
            >
              Settings
            </a>
            
            <button
              type="button"
              class="block w-full text-left px-4 py-2 text-base font-medium text-gray-500 hover:text-gray-800 hover:bg-gray-100"
              (click)="logout()"
            >
              Sign out
            </button>
          </div>
        </div>
      </div>
    </nav>
  `
})
export class NavigationComponent implements OnInit, OnDestroy {
  currentUser: User | null = null;
  isUserMenuOpen = false;
  isMobileMenuOpen = false;
  isAdmin = false;
  
  private subscription?: Subscription;

  constructor(
    private authService: AuthService,
    private errorHandler: ErrorHandlerService
  ) {}

  ngOnInit(): void {
    this.subscription = this.authService.currentUser$.subscribe(user => {
      this.currentUser = user;
      this.isAdmin = this.authService.isAdmin();
    });
  }

  ngOnDestroy(): void {
    if (this.subscription) {
      this.subscription.unsubscribe();
    }
  }

  toggleUserMenu(): void {
    this.isUserMenuOpen = !this.isUserMenuOpen;
  }

  closeUserMenu(): void {
    this.isUserMenuOpen = false;
  }

  toggleMobileMenu(): void {
    this.isMobileMenuOpen = !this.isMobileMenuOpen;
  }

  closeMobileMenu(): void {
    this.isMobileMenuOpen = false;
  }

  getUserDisplayName(): string {
    return this.authService.getUserDisplayName();
  }

  getUserInitials(): string {
    const displayName = this.getUserDisplayName();
    if (!displayName) return '?';
    
    const names = displayName.split(' ');
    if (names.length >= 2) {
      return (names[0][0] + names[1][0]).toUpperCase();
    } else {
      return displayName.substring(0, 2).toUpperCase();
    }
  }

  logout(): void {
    this.authService.logout().subscribe({
      next: () => {
        this.errorHandler.showSuccess('Logged out successfully');
      },
      error: (error) => {
        // Even if logout fails on server, clear local storage
        this.authService['clearStorage']();
        this.currentUser = null;
        this.errorHandler.showWarning('Logged out locally due to server error');
      }
    });
    
    this.closeUserMenu();
    this.closeMobileMenu();
  }
}
