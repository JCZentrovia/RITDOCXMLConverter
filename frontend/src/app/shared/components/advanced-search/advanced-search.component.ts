import { Component, Input, Output, EventEmitter, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, FormGroup } from '@angular/forms';
import { FormsModule } from '@angular/forms';

export interface SearchFilter {
  field: string;
  operator: 'equals' | 'contains' | 'starts_with' | 'ends_with' | 'greater_than' | 'less_than' | 'between' | 'in' | 'not_in';
  value: any;
  label?: string;
}

export interface SearchField {
  key: string;
  label: string;
  type: 'text' | 'number' | 'date' | 'select' | 'multiselect' | 'boolean';
  options?: { value: any; label: string }[];
  operators?: string[];
}

export interface SearchQuery {
  filters: SearchFilter[];
  sort?: {
    field: string;
    direction: 'asc' | 'desc';
  };
  limit?: number;
  offset?: number;
}

@Component({
  selector: 'app-advanced-search',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, FormsModule],
  template: `
    <div class="bg-white border border-gray-200 rounded-lg shadow-sm">
      <!-- Header -->
      <div class="px-4 py-3 border-b border-gray-200 bg-gray-50 rounded-t-lg">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-medium text-gray-900">Advanced Search</h3>
          <div class="flex items-center space-x-2">
            <button
              type="button"
              (click)="addFilter()"
              class="inline-flex items-center px-2 py-1 border border-transparent text-xs font-medium rounded text-indigo-700 bg-indigo-100 hover:bg-indigo-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
            >
              <svg class="-ml-0.5 mr-1 h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
              Add Filter
            </button>
            <button
              type="button"
              (click)="clearAllFilters()"
              [disabled]="currentFilters.length === 0"
              class="inline-flex items-center px-2 py-1 border border-gray-300 text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Clear All
            </button>
            <button
              type="button"
              (click)="toggleExpanded()"
              class="inline-flex items-center px-2 py-1 border border-gray-300 text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
            >
              <svg 
                class="h-3 w-3 transition-transform duration-200"
                [class.rotate-180]="isExpanded"
                fill="none" 
                viewBox="0 0 24 24" 
                stroke="currentColor"
              >
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      <!-- Quick Search -->
      <div class="px-4 py-3 border-b border-gray-200">
        <div class="relative">
          <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <svg class="h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <input
            type="text"
            [(ngModel)]="quickSearchTerm"
            (input)="onQuickSearch()"
            class="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
            placeholder="Quick search..."
          />
          <div *ngIf="quickSearchTerm" class="absolute inset-y-0 right-0 pr-3 flex items-center">
            <button
              type="button"
              (click)="clearQuickSearch()"
              class="text-gray-400 hover:text-gray-500"
            >
              <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      <!-- Advanced Filters -->
      <div *ngIf="isExpanded" class="px-4 py-3 space-y-3">
        <!-- Active Filters -->
        <div *ngIf="currentFilters.length > 0" class="space-y-2">
          <div 
            *ngFor="let filter of currentFilters; let i = index"
            class="flex items-center space-x-2 p-2 bg-gray-50 rounded-md"
          >
            <!-- Field Selection -->
            <select
              [(ngModel)]="filter.field"
              (change)="onFilterFieldChange(i)"
              class="text-sm border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
            >
              <option value="">Select field...</option>
              <option *ngFor="let field of searchFields" [value]="field.key">
                {{ field.label }}
              </option>
            </select>

            <!-- Operator Selection -->
            <select
              [(ngModel)]="filter.operator"
              (change)="onFilterChange()"
              [disabled]="!filter.field"
              class="text-sm border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500 disabled:opacity-50"
            >
              <option *ngFor="let operator of getAvailableOperators(filter.field)" [value]="operator.value">
                {{ operator.label }}
              </option>
            </select>

            <!-- Value Input -->
            <div class="flex-1">
              <!-- Text Input -->
              <input
                *ngIf="getFieldType(filter.field) === 'text'"
                type="text"
                [(ngModel)]="filter.value"
                (input)="onFilterChange()"
                class="w-full text-sm border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
                placeholder="Enter value..."
              />

              <!-- Number Input -->
              <input
                *ngIf="getFieldType(filter.field) === 'number'"
                type="number"
                [(ngModel)]="filter.value"
                (input)="onFilterChange()"
                class="w-full text-sm border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
                placeholder="Enter number..."
              />

              <!-- Date Input -->
              <input
                *ngIf="getFieldType(filter.field) === 'date'"
                type="date"
                [(ngModel)]="filter.value"
                (change)="onFilterChange()"
                class="w-full text-sm border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
              />

              <!-- Select Input -->
              <select
                *ngIf="getFieldType(filter.field) === 'select'"
                [(ngModel)]="filter.value"
                (change)="onFilterChange()"
                class="w-full text-sm border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
              >
                <option value="">Select option...</option>
                <option *ngFor="let option of getFieldOptions(filter.field)" [value]="option.value">
                  {{ option.label }}
                </option>
              </select>

              <!-- Boolean Input -->
              <select
                *ngIf="getFieldType(filter.field) === 'boolean'"
                [(ngModel)]="filter.value"
                (change)="onFilterChange()"
                class="w-full text-sm border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
              >
                <option value="">Select...</option>
                <option [value]="true">Yes</option>
                <option [value]="false">No</option>
              </select>

              <!-- Between Input -->
              <div *ngIf="filter.operator === 'between'" class="flex space-x-2">
                <input
                  [type]="getFieldType(filter.field) === 'date' ? 'date' : 'number'"
                  [(ngModel)]="filter.value.from"
                  (input)="onFilterChange()"
                  class="flex-1 text-sm border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
                  placeholder="From..."
                />
                <input
                  [type]="getFieldType(filter.field) === 'date' ? 'date' : 'number'"
                  [(ngModel)]="filter.value.to"
                  (input)="onFilterChange()"
                  class="flex-1 text-sm border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
                  placeholder="To..."
                />
              </div>
            </div>

            <!-- Remove Filter -->
            <button
              type="button"
              (click)="removeFilter(i)"
              class="text-red-400 hover:text-red-500"
            >
              <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>

        <!-- Sorting -->
        <div class="border-t border-gray-200 pt-3">
          <h4 class="text-sm font-medium text-gray-900 mb-2">Sort By</h4>
          <div class="flex space-x-2">
            <select
              [(ngModel)]="sortField"
              (change)="onSortChange()"
              class="flex-1 text-sm border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
            >
              <option value="">No sorting</option>
              <option *ngFor="let field of searchFields" [value]="field.key">
                {{ field.label }}
              </option>
            </select>
            <select
              [(ngModel)]="sortDirection"
              (change)="onSortChange()"
              [disabled]="!sortField"
              class="text-sm border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500 disabled:opacity-50"
            >
              <option value="asc">Ascending</option>
              <option value="desc">Descending</option>
            </select>
          </div>
        </div>

        <!-- Actions -->
        <div class="border-t border-gray-200 pt-3 flex justify-between">
          <div class="flex space-x-2">
            <button
              type="button"
              (click)="saveSearch()"
              [disabled]="!hasActiveFilters()"
              class="inline-flex items-center px-3 py-1.5 border border-gray-300 text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <svg class="-ml-0.5 mr-1 h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
              </svg>
              Save Search
            </button>
            <button
              type="button"
              (click)="loadSavedSearch()"
              class="inline-flex items-center px-3 py-1.5 border border-gray-300 text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
            >
              <svg class="-ml-0.5 mr-1 h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-4-4m4 4l4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Load Saved
            </button>
          </div>
          
          <button
            type="button"
            (click)="applySearch()"
            class="inline-flex items-center px-4 py-1.5 border border-transparent text-xs font-medium rounded text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
          >
            Apply Search
          </button>
        </div>
      </div>

      <!-- Active Filters Summary -->
      <div *ngIf="!isExpanded && (hasActiveFilters() || quickSearchTerm)" class="px-4 py-2 bg-blue-50 border-t border-gray-200">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-2 text-sm text-blue-700">
            <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.707A1 1 0 013 7V4z" />
            </svg>
            <span>
              {{ getActiveFiltersCount() }} filter(s) active
              <span *ngIf="quickSearchTerm"> • Quick search: "{{ quickSearchTerm }}"</span>
            </span>
          </div>
          <button
            type="button"
            (click)="clearAllFilters()"
            class="text-xs text-blue-600 hover:text-blue-500 font-medium"
          >
            Clear all
          </button>
        </div>
      </div>
    </div>
  `
})
export class AdvancedSearchComponent implements OnInit {
  @Input() searchFields: SearchField[] = [];
  @Input() initialQuery?: SearchQuery;
  @Input() placeholder = 'Search...';
  
  @Output() searchChanged = new EventEmitter<SearchQuery>();
  @Output() quickSearchChanged = new EventEmitter<string>();

  isExpanded = false;
  quickSearchTerm = '';
  currentFilters: SearchFilter[] = [];
  sortField = '';
  sortDirection: 'asc' | 'desc' = 'asc';

  private defaultOperators = [
    { value: 'equals', label: 'Equals' },
    { value: 'contains', label: 'Contains' },
    { value: 'starts_with', label: 'Starts with' },
    { value: 'ends_with', label: 'Ends with' }
  ];

  private numberOperators = [
    { value: 'equals', label: 'Equals' },
    { value: 'greater_than', label: 'Greater than' },
    { value: 'less_than', label: 'Less than' },
    { value: 'between', label: 'Between' }
  ];

  private selectOperators = [
    { value: 'equals', label: 'Equals' },
    { value: 'in', label: 'In' },
    { value: 'not_in', label: 'Not in' }
  ];

  constructor(private fb: FormBuilder) {}

  ngOnInit(): void {
    if (this.initialQuery) {
      this.loadQuery(this.initialQuery);
    }
  }

  toggleExpanded(): void {
    this.isExpanded = !this.isExpanded;
  }

  addFilter(): void {
    this.currentFilters.push({
      field: '',
      operator: 'equals',
      value: ''
    });
  }

  removeFilter(index: number): void {
    this.currentFilters.splice(index, 1);
    this.onFilterChange();
  }

  clearAllFilters(): void {
    this.currentFilters = [];
    this.quickSearchTerm = '';
    this.sortField = '';
    this.sortDirection = 'asc';
    this.emitSearchQuery();
  }

  onQuickSearch(): void {
    this.quickSearchChanged.emit(this.quickSearchTerm);
    this.emitSearchQuery();
  }

  clearQuickSearch(): void {
    this.quickSearchTerm = '';
    this.onQuickSearch();
  }

  onFilterFieldChange(index: number): void {
    const filter = this.currentFilters[index];
    const field = this.searchFields.find(f => f.key === filter.field);
    
    if (field) {
      // Reset operator and value when field changes
      const availableOperators = this.getAvailableOperators(filter.field);
      filter.operator = (availableOperators[0]?.value as any) || 'equals';
      filter.value = this.getDefaultValue(field.type);
    }
    
    this.onFilterChange();
  }

  onFilterChange(): void {
    this.emitSearchQuery();
  }

  onSortChange(): void {
    this.emitSearchQuery();
  }

  applySearch(): void {
    this.emitSearchQuery();
  }

  saveSearch(): void {
    const query = this.buildSearchQuery();
    const searchName = prompt('Enter a name for this search:');
    
    if (searchName) {
      const savedSearches = this.getSavedSearches();
      savedSearches[searchName] = query;
      localStorage.setItem('advanced_searches', JSON.stringify(savedSearches));
    }
  }

  loadSavedSearch(): void {
    const savedSearches = this.getSavedSearches();
    const searchNames = Object.keys(savedSearches);
    
    if (searchNames.length === 0) {
      alert('No saved searches found');
      return;
    }
    
    // Simple selection - in a real app, you'd use a proper dialog
    const selectedName = prompt(`Select a search:\n${searchNames.join('\n')}`);
    
    if (selectedName && savedSearches[selectedName]) {
      this.loadQuery(savedSearches[selectedName]);
    }
  }

  private loadQuery(query: SearchQuery): void {
    this.currentFilters = [...query.filters];
    this.sortField = query.sort?.field || '';
    this.sortDirection = query.sort?.direction || 'asc';
    this.emitSearchQuery();
  }

  private emitSearchQuery(): void {
    const query = this.buildSearchQuery();
    this.searchChanged.emit(query);
  }

  private buildSearchQuery(): SearchQuery {
    const validFilters = this.currentFilters.filter(f => 
      f.field && f.operator && (f.value !== '' && f.value !== null && f.value !== undefined)
    );

    const query: SearchQuery = {
      filters: validFilters
    };

    if (this.sortField) {
      query.sort = {
        field: this.sortField,
        direction: this.sortDirection
      };
    }

    return query;
  }

  private getSavedSearches(): any {
    const saved = localStorage.getItem('advanced_searches');
    return saved ? JSON.parse(saved) : {};
  }

  private getDefaultValue(type: string): any {
    switch (type) {
      case 'boolean':
        return false;
      case 'number':
        return 0;
      case 'date':
        return '';
      default:
        return '';
    }
  }

  // Helper methods for template
  getAvailableOperators(fieldKey: string): { value: string; label: string }[] {
    const field = this.searchFields.find(f => f.key === fieldKey);
    
    if (!field) return this.defaultOperators;
    
    if (field.operators) {
      return field.operators.map(op => {
        const found = [...this.defaultOperators, ...this.numberOperators, ...this.selectOperators]
          .find(o => o.value === op);
        return found || { value: op, label: op };
      });
    }

    switch (field.type) {
      case 'number':
      case 'date':
        return this.numberOperators;
      case 'select':
      case 'multiselect':
        return this.selectOperators;
      case 'boolean':
        return [{ value: 'equals', label: 'Equals' }];
      default:
        return this.defaultOperators;
    }
  }

  getFieldType(fieldKey: string): string {
    const field = this.searchFields.find(f => f.key === fieldKey);
    return field?.type || 'text';
  }

  getFieldOptions(fieldKey: string): { value: any; label: string }[] {
    const field = this.searchFields.find(f => f.key === fieldKey);
    return field?.options || [];
  }

  hasActiveFilters(): boolean {
    return this.currentFilters.some(f => 
      f.field && f.operator && (f.value !== '' && f.value !== null && f.value !== undefined)
    ) || !!this.quickSearchTerm || !!this.sortField;
  }

  getActiveFiltersCount(): number {
    let count = this.currentFilters.filter(f => 
      f.field && f.operator && (f.value !== '' && f.value !== null && f.value !== undefined)
    ).length;
    
    if (this.quickSearchTerm) count++;
    if (this.sortField) count++;
    
    return count;
  }
}
