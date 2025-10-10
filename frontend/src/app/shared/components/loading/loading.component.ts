import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-loading',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div [ngClass]="containerClass" class="flex items-center justify-center">
      <div class="flex items-center space-x-2">
        <!-- Spinner -->
        <svg 
          [ngClass]="spinnerClass"
          class="animate-spin" 
          fill="none" 
          viewBox="0 0 24 24"
        >
          <circle 
            class="opacity-25" 
            cx="12" 
            cy="12" 
            r="10" 
            stroke="currentColor" 
            stroke-width="4"
          ></circle>
          <path 
            class="opacity-75" 
            fill="currentColor" 
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          ></path>
        </svg>
        
        <!-- Loading Text -->
        <span [ngClass]="textClass" *ngIf="showText">
          {{ message }}
        </span>
      </div>
    </div>
  `
})
export class LoadingComponent {
  @Input() message: string = 'Loading...';
  @Input() size: 'sm' | 'md' | 'lg' = 'md';
  @Input() color: 'primary' | 'secondary' | 'white' = 'primary';
  @Input() showText: boolean = true;
  @Input() fullScreen: boolean = false;

  get containerClass(): string {
    const base = this.fullScreen 
      ? 'fixed inset-0 bg-white bg-opacity-75 z-50' 
      : 'py-4';
    return base;
  }

  get spinnerClass(): string {
    const sizes = {
      sm: 'h-4 w-4',
      md: 'h-6 w-6', 
      lg: 'h-8 w-8'
    };

    const colors = {
      primary: 'text-indigo-600',
      secondary: 'text-gray-600',
      white: 'text-white'
    };

    return `${sizes[this.size]} ${colors[this.color]}`;
  }

  get textClass(): string {
    const colors = {
      primary: 'text-indigo-600',
      secondary: 'text-gray-600', 
      white: 'text-white'
    };

    return `text-sm font-medium ${colors[this.color]}`;
  }
}
