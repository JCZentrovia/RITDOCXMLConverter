import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-confirmation-dialog',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div *ngIf="isOpen" class="fixed inset-0 z-50 overflow-y-auto">
      <!-- Backdrop -->
      <div 
        class="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
        (click)="onCancel()"
      ></div>
      
      <!-- Dialog -->
      <div class="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
        <div class="relative transform overflow-hidden rounded-lg bg-white px-4 pb-4 pt-5 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg sm:p-6">
          <!-- Icon -->
          <div class="mx-auto flex h-12 w-12 items-center justify-center rounded-full" [ngClass]="iconBackgroundClass">
            <div [innerHTML]="iconSvg" [ngClass]="iconClass" class="h-6 w-6"></div>
          </div>
          
          <!-- Content -->
          <div class="mt-3 text-center sm:mt-5">
            <h3 class="text-base font-semibold leading-6 text-gray-900">
              {{ title }}
            </h3>
            <div class="mt-2">
              <p class="text-sm text-gray-500">
                {{ message }}
              </p>
            </div>
          </div>
          
          <!-- Actions -->
          <div class="mt-5 sm:mt-6 sm:grid sm:grid-flow-row-dense sm:grid-cols-2 sm:gap-3">
            <button
              type="button"
              (click)="onConfirm()"
              [disabled]="isProcessing"
              [ngClass]="confirmButtonClass"
              class="inline-flex w-full justify-center rounded-md px-3 py-2 text-sm font-semibold shadow-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 sm:col-start-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span *ngIf="isProcessing" class="mr-2">
                <svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              </span>
              {{ isProcessing ? processingText : confirmText }}
            </button>
            
            <button
              type="button"
              (click)="onCancel()"
              [disabled]="isProcessing"
              class="mt-3 inline-flex w-full justify-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 sm:col-start-1 sm:mt-0 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {{ cancelText }}
            </button>
          </div>
        </div>
      </div>
    </div>
  `
})
export class ConfirmationDialogComponent {
  @Input() isOpen: boolean = false;
  @Input() title: string = 'Confirm Action';
  @Input() message: string = 'Are you sure you want to proceed?';
  @Input() confirmText: string = 'Confirm';
  @Input() cancelText: string = 'Cancel';
  @Input() processingText: string = 'Processing...';
  @Input() type: 'danger' | 'warning' | 'info' = 'danger';
  @Input() isProcessing: boolean = false;

  @Output() confirmed = new EventEmitter<void>();
  @Output() cancelled = new EventEmitter<void>();

  get iconBackgroundClass(): string {
    const classes = {
      danger: 'bg-red-100',
      warning: 'bg-yellow-100',
      info: 'bg-blue-100'
    };
    return classes[this.type];
  }

  get iconClass(): string {
    const classes = {
      danger: 'text-red-600',
      warning: 'text-yellow-600', 
      info: 'text-blue-600'
    };
    return classes[this.type];
  }

  get iconSvg(): string {
    const icons = {
      danger: '<svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" /></svg>',
      warning: '<svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" /></svg>',
      info: '<svg fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>'
    };
    return icons[this.type];
  }

  get confirmButtonClass(): string {
    const classes = {
      danger: 'bg-red-600 text-white hover:bg-red-500 focus-visible:outline-red-600',
      warning: 'bg-yellow-600 text-white hover:bg-yellow-500 focus-visible:outline-yellow-600',
      info: 'bg-blue-600 text-white hover:bg-blue-500 focus-visible:outline-blue-600'
    };
    return classes[this.type];
  }

  onConfirm(): void {
    if (!this.isProcessing) {
      this.confirmed.emit();
    }
  }

  onCancel(): void {
    if (!this.isProcessing) {
      this.cancelled.emit();
    }
  }
}
