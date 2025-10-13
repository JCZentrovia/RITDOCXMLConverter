import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { FormsModule, ReactiveFormsModule, FormBuilder, FormGroup } from '@angular/forms';
import { Subscription, interval, debounceTime, distinctUntilChanged } from 'rxjs';
import { ManuscriptService, ManuscriptResponse, ManuscriptListResponse, ManuscriptStatistics } from '../shared/services/manuscript.service';
import { ErrorHandlerService } from '../shared/services/error-handler.service';
import { DownloadService, DownloadRequest } from '../shared/services/download.service';
import { NavigationComponent } from '../shared/components/navigation/navigation.component';
import { FileUploadComponent, FileUploadConfig } from '../shared/components/file-upload/file-upload.component';
import { LoadingComponent } from '../shared/components/loading/loading.component';
import { ConfirmationDialogComponent } from '../shared/components/confirmation-dialog/confirmation-dialog.component';
import { DownloadDialogComponent, DownloadOptions } from '../shared/components/download-dialog/download-dialog.component';

@Component({
  selector: 'app-manuscripts',
  standalone: true,
  imports: [CommonModule, RouterModule, FormsModule, ReactiveFormsModule, NavigationComponent, FileUploadComponent, LoadingComponent, ConfirmationDialogComponent, DownloadDialogComponent],
  template: `
    <div class="min-h-screen bg-gray-50">
      <app-navigation></app-navigation>

      <main class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div class="px-4 py-6 sm:px-0">
          <!-- Header with Statistics -->
          <div class="mb-8">
            <div class="sm:flex sm:items-center sm:justify-between mb-6">
              <div>
                <h1 class="text-3xl font-bold text-gray-900">Manuscripts</h1>
                <p class="mt-1 text-sm text-gray-600">
                  Manage your PDF manuscripts and track processing status
                </p>
              </div>
              <div class="mt-4 sm:mt-0 flex space-x-3">
                <button
                  type="button"
                  class="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                  (click)="refreshManuscripts()"
                  [disabled]="isLoading"
                >
                  <svg class="-ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Refresh
                </button>
                <button
                  type="button"
                  class="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                  (click)="openUploadModal()"
                >
                  <svg class="-ml-1 mr-2 h-5 w-5" stroke="currentColor" fill="none" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                  </svg>
                  Upload Manuscript
                </button>
              </div>
            </div>

            <!-- Statistics Cards -->
            <div class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4 mb-6" *ngIf="statistics">
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
                        <dt class="text-sm font-medium text-gray-500 truncate">Total</dt>
                        <dd class="text-lg font-medium text-gray-900">{{ statistics.total }}</dd>
                      </dl>
                    </div>
                  </div>
                </div>
              </div>

              <div class="bg-white overflow-hidden shadow rounded-lg">
                <div class="p-5">
                  <div class="flex items-center">
                    <div class="flex-shrink-0">
                      <svg class="h-6 w-6 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    </div>
                    <div class="ml-5 w-0 flex-1">
                      <dl>
                        <dt class="text-sm font-medium text-gray-500 truncate">Processing</dt>
                        <dd class="text-lg font-medium text-gray-900">{{ statistics.processing }}</dd>
                      </dl>
                    </div>
                  </div>
                </div>
              </div>

              <div class="bg-white overflow-hidden shadow rounded-lg">
                <div class="p-5">
                  <div class="flex items-center">
                    <div class="flex-shrink-0">
                      <svg class="h-6 w-6 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    </div>
                    <div class="ml-5 w-0 flex-1">
                      <dl>
                        <dt class="text-sm font-medium text-gray-500 truncate">Completed</dt>
                        <dd class="text-lg font-medium text-gray-900">{{ statistics.completed }}</dd>
                      </dl>
                    </div>
                  </div>
                </div>
              </div>

              <div class="bg-white overflow-hidden shadow rounded-lg">
                <div class="p-5">
                  <div class="flex items-center">
                    <div class="flex-shrink-0">
                      <svg class="h-6 w-6 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    </div>
                    <div class="ml-5 w-0 flex-1">
                      <dl>
                        <dt class="text-sm font-medium text-gray-500 truncate">Failed</dt>
                        <dd class="text-lg font-medium text-gray-900">{{ statistics.failed }}</dd>
                      </dl>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Enhanced Filters and Search -->
          <div class="bg-white shadow rounded-lg mb-6">
            <div class="px-4 py-5 sm:p-6">
              <form [formGroup]="filterForm" class="space-y-4">
                <div class="grid grid-cols-1 gap-4 sm:grid-cols-6">
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
                        formControlName="search"
                        class="focus:ring-indigo-500 focus:border-indigo-500 block w-full pl-10 sm:text-sm border-gray-300 rounded-md"
                        placeholder="Search by filename..."
                      />
                      <div class="absolute inset-y-0 right-0 pr-3 flex items-center" *ngIf="filterForm.get('search')?.value">
                        <button
                          type="button"
                          (click)="clearSearch()"
                          class="text-gray-400 hover:text-gray-500"
                        >
                          <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  </div>

                  <!-- Status Filter -->
                  <div>
                    <label for="status" class="block text-sm font-medium text-gray-700">Status</label>
                    <select
                      id="status"
                      formControlName="status"
                      class="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
                    >
                      <option value="">All Status</option>
                      <option value="pending">Pending</option>
                      <option value="processing">Processing</option>
                      <option value="complete">Complete</option>
                      <option value="failed">Failed</option>
                    </select>
                  </div>

                  <!-- Sort -->
                  <div>
                    <label for="sort" class="block text-sm font-medium text-gray-700">Sort by</label>
                    <select
                      id="sort"
                      formControlName="sortBy"
                      class="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
                    >
                      <option value="upload_date_desc">Newest First</option>
                      <option value="upload_date_asc">Oldest First</option>
                      <option value="name_asc">Name A-Z</option>
                      <option value="name_desc">Name Z-A</option>
                      <option value="status_asc">Status</option>
                    </select>
                  </div>

                  <!-- Items per page -->
                  <div>
                    <label for="pageSize" class="block text-sm font-medium text-gray-700">Per Page</label>
                    <select
                      id="pageSize"
                      formControlName="pageSize"
                      class="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md"
                    >
                      <option value="10">10</option>
                      <option value="25">25</option>
                      <option value="50">50</option>
                      <option value="100">100</option>
                    </select>
                  </div>

                  <!-- Actions -->
                  <div class="flex items-end space-x-2">
                    <button
                      type="button"
                      (click)="resetFilters()"
                      class="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                    >
                      Clear
                    </button>
                  </div>
                </div>

                <!-- Bulk Actions -->
                <div class="flex items-center justify-between pt-4 border-t border-gray-200" *ngIf="selectedManuscripts.size > 0">
                  <div class="flex items-center">
                    <span class="text-sm text-gray-700">
                      {{ selectedManuscripts.size }} {{ selectedManuscripts.size === 1 ? 'item' : 'items' }} selected
                    </span>
                  </div>
                  <div class="flex space-x-2">
                    <button
                      type="button"
                      (click)="bulkDownload()"
                      class="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                    >
                      <svg class="-ml-0.5 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      Download PDF
                    </button>
                    <button
                      type="button"
                      (click)="bulkDownloadXML()"
                      class="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                    >
                      <svg class="-ml-0.5 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      Download DOCX
                    </button>
                    <button
                      type="button"
                      (click)="bulkDelete()"
                      class="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                    >
                      <svg class="-ml-0.5 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                      Delete Selected
                    </button>
                    <button
                      type="button"
                      (click)="clearSelection()"
                      class="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                    >
                      Clear Selection
                    </button>
                  </div>
                </div>
              </form>
            </div>
          </div>

          <!-- Enhanced Manuscript List -->
          <div class="bg-white shadow rounded-lg">
            <!-- Loading State -->
            <div *ngIf="isLoading" class="p-8 text-center">
              <app-loading [size]="'lg'" [message]="'Loading manuscripts...'"></app-loading>
            </div>

            <!-- Empty State -->
            <div *ngIf="!isLoading && manuscripts.length === 0" class="text-center py-12">
              <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <h3 class="mt-2 text-sm font-medium text-gray-900">No manuscripts</h3>
              <p class="mt-1 text-sm text-gray-500">Get started by uploading your first PDF manuscript.</p>
              <div class="mt-6">
                <button
                  type="button"
                  (click)="openUploadModal()"
                  class="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                >
                  <svg class="-ml-1 mr-2 h-5 w-5" stroke="currentColor" fill="none" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                  </svg>
                  Upload Manuscript
                </button>
              </div>
            </div>

            <!-- Manuscript Table -->
            <div *ngIf="!isLoading && manuscripts.length > 0">
              <!-- Table Header -->
              <div class="px-4 py-5 sm:p-6 border-b border-gray-200">
                <div class="flex items-center justify-between">
                  <div class="flex items-center">
                    <input
                      type="checkbox"
                      class="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                      [checked]="isAllSelected()"
                      [indeterminate]="isSomeSelected()"
                      (change)="toggleSelectAll()"
                    />
                    <span class="ml-3 text-sm font-medium text-gray-900">
                      {{ manuscripts.length }} {{ manuscripts.length === 1 ? 'manuscript' : 'manuscripts' }}
                    </span>
                  </div>
                  <div class="text-sm text-gray-500">
                    Showing {{ (currentPage - 1) * pageSize + 1 }} to {{ Math.min(currentPage * pageSize, totalItems) }} of {{ totalItems }} results
                  </div>
                </div>
              </div>

              <!-- Manuscript Items -->
              <div class="divide-y divide-gray-200">
                <div
                  *ngFor="let manuscript of manuscripts; trackBy: trackByManuscript"
                  class="px-4 py-4 sm:px-6 hover:bg-gray-50 transition-colors duration-150"
                  [class.bg-blue-50]="selectedManuscripts.has(manuscript.id)"
                >
                  <div class="flex items-center space-x-4">
                    <!-- Checkbox -->
                    <input
                      type="checkbox"
                      class="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                      [checked]="selectedManuscripts.has(manuscript.id)"
                      (change)="toggleManuscriptSelection(manuscript.id)"
                    />

                    <!-- File Icon -->
                    <div class="flex-shrink-0">
                      <svg class="h-10 w-10 text-red-500" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20Z" />
                      </svg>
                    </div>

                    <!-- Manuscript Info -->
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center justify-between">
                        <div class="flex-1">
                          <p class="text-sm font-medium text-gray-900 truncate">
                            {{ manuscript.file_name }}
                          </p>
                          <div class="mt-1 flex items-center space-x-4 text-sm text-gray-500">
                            <span>Uploaded {{ manuscript.upload_date | date:'short' }}</span>
                            <span class="flex items-center">
                              <svg class="flex-shrink-0 mr-1.5 h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                              </svg>
                              PDF Document
                            </span>
                            <span *ngIf="manuscript.processing_completed_at" class="flex items-center">
                              <svg class="flex-shrink-0 mr-1.5 h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                              Completed {{ manuscript.processing_completed_at | date:'short' }}
                            </span>
                          </div>
                        </div>

                        <!-- Status and Actions -->
                        <div class="flex items-center space-x-4">
                          <!-- Status Badge -->
                          <span [ngClass]="getStatusClass(manuscript.status)" class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium">
                            {{ manuscript.status | titlecase }}
                          </span>

                          <!-- Actions -->
                          <div class="flex items-center space-x-2">
                            <!-- Download Button -->
                            <button
                              *ngIf="manuscript.status === 'complete'"
                              type="button"
                              class="inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-colors duration-200"
                              (click)="downloadManuscript(manuscript)"
                              title="Download converted DOCX file"
                            >
                              <svg class="-ml-0.5 mr-1.5 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-4-4m4 4l4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                              Download
                            </button>
                            
                            <!-- Disabled Download Button -->
                            <button
                              *ngIf="manuscript.status !== 'complete'"
                              type="button"
                              class="inline-flex items-center px-3 py-1.5 border border-gray-300 text-xs font-medium rounded-md text-gray-400 bg-gray-100 cursor-not-allowed"
                              disabled
                              title="Download available when processing is complete"
                            >
                              <svg class="-ml-0.5 mr-1.5 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-4-4m4 4l4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                              Download
                            </button>

                            <!-- Retry Button -->
                            <button
                              *ngIf="manuscript.status === 'failed'"
                              type="button"
                              class="inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded text-yellow-700 bg-yellow-100 hover:bg-yellow-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-yellow-500"
                              (click)="retryProcessing(manuscript)"
                            >
                              <svg class="-ml-0.5 mr-1 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                              </svg>
                              Retry
                            </button>

                            <!-- Delete Button -->
                            <button
                              type="button"
                              class="inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded text-red-700 bg-red-100 hover:bg-red-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                              (click)="deleteManuscript(manuscript)"
                            >
                              <svg class="-ml-0.5 mr-1 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                              </svg>
                              Delete
                            </button>
                          </div>
                        </div>
                      </div>

                      <!-- Error Message -->
                      <div *ngIf="manuscript.status === 'failed' && manuscript.error_message" class="mt-2 p-2 bg-red-50 rounded-md">
                        <div class="flex">
                          <svg class="h-4 w-4 text-red-400 mt-0.5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          <p class="text-xs text-red-700">{{ manuscript.error_message }}</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Pagination -->
              <div class="bg-white px-4 py-3 border-t border-gray-200 sm:px-6" *ngIf="totalPages > 1">
                <div class="flex items-center justify-between">
                  <div class="flex-1 flex justify-between sm:hidden">
                    <button
                      type="button"
                      (click)="previousPage()"
                      [disabled]="currentPage === 1"
                      class="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Previous
                    </button>
                    <button
                      type="button"
                      (click)="nextPage()"
                      [disabled]="currentPage === totalPages"
                      class="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Next
                    </button>
                  </div>
                  <div class="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
                    <div>
                      <p class="text-sm text-gray-700">
                        Showing
                        <span class="font-medium">{{ (currentPage - 1) * pageSize + 1 }}</span>
                        to
                        <span class="font-medium">{{ Math.min(currentPage * pageSize, totalItems) }}</span>
                        of
                        <span class="font-medium">{{ totalItems }}</span>
                        results
                      </p>
                    </div>
                    <div>
                      <nav class="relative z-0 inline-flex rounded-md shadow-sm -space-x-px" aria-label="Pagination">
                        <button
                          type="button"
                          (click)="previousPage()"
                          [disabled]="currentPage === 1"
                          class="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          <span class="sr-only">Previous</span>
                          <svg class="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clip-rule="evenodd" />
                          </svg>
                        </button>

                        <button
                          *ngFor="let page of getPageNumbers()"
                          type="button"
                          (click)="goToPage(page)"
                          [class]="page === currentPage ? 'bg-indigo-50 border-indigo-500 text-indigo-600' : 'bg-white border-gray-300 text-gray-500 hover:bg-gray-50'"
                          class="relative inline-flex items-center px-4 py-2 border text-sm font-medium"
                        >
                          {{ page }}
                        </button>

                        <button
                          type="button"
                          (click)="nextPage()"
                          [disabled]="currentPage === totalPages"
                          class="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          <span class="sr-only">Next</span>
                          <svg class="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
                          </svg>
                        </button>
                      </nav>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Upload Modal -->
          <div 
            *ngIf="showUploadModal" 
            class="fixed inset-0 z-50 overflow-y-auto"
            aria-labelledby="modal-title" 
            role="dialog" 
            aria-modal="true"
          >
            <div class="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
              <!-- Background overlay -->
              <div 
                class="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" 
                aria-hidden="true"
                (click)="closeUploadModal()"
              ></div>

              <!-- Modal panel -->
              <div class="inline-block align-bottom bg-white rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full sm:p-6">
                <div class="sm:flex sm:items-start">
                  <div class="w-full">
                    <!-- Modal Header -->
                    <div class="flex items-center justify-between mb-4">
                      <h3 class="text-lg leading-6 font-medium text-gray-900" id="modal-title">
                        Upload Manuscript
                      </h3>
                      <button
                        type="button"
                        class="bg-white rounded-md text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                        (click)="closeUploadModal()"
                      >
                        <span class="sr-only">Close</span>
                        <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>

                    <!-- File Upload Component -->
                    <app-file-upload
                      [config]="uploadConfig"
                      (fileUploaded)="onFileUploaded($event)"
                      (uploadProgress)="onUploadProgress($event)"
                      (uploadError)="onUploadError($event)"
                    ></app-file-upload>

                    <!-- Modal Footer -->
                    <div class="mt-6 flex justify-end">
                      <button
                        type="button"
                        class="inline-flex justify-center px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                        (click)="closeUploadModal()"
                      >
                        Close
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Download Dialog -->
          <app-download-dialog
            *ngIf="showDownloadDialog"
            [manuscript]="selectedManuscriptForDownload"
            (download)="onDownloadWithOptions($event)"
            (cancel)="closeDownloadDialog()"
          ></app-download-dialog>

          <!-- Confirmation Dialog -->
          <app-confirmation-dialog
            [isOpen]="showConfirmDialog"
            [title]="confirmDialog.title"
            [message]="confirmDialog.message"
            [confirmText]="confirmDialog.confirmText"
            [cancelText]="confirmDialog.cancelText"
            [type]="confirmDialog.type"
            (confirmed)="onConfirmAction()"
            (cancelled)="onCancelAction()"
          ></app-confirmation-dialog>
        </div>
      </main>

    </div>
  `
})
export class ManuscriptsComponent implements OnInit, OnDestroy {
  // Data properties
  manuscripts: ManuscriptResponse[] = [];
  statistics: ManuscriptStatistics | null = null;
  selectedManuscripts = new Set<string>();
  
  // UI state
  isLoading = false;
  showUploadModal = false;
  showConfirmDialog = false;
  showDownloadDialog = false;
  selectedManuscriptForDownload: ManuscriptResponse | null = null;
  
  // Pagination
  currentPage = 1;
  pageSize = 25;
  totalItems = 0;
  totalPages = 0;
  
  // Filter form
  filterForm: FormGroup;
  
  // Upload configuration
  uploadConfig: FileUploadConfig = {
    maxFileSize: 10 * 1024 * 1024, // 10MB
    allowedTypes: ['application/pdf'],
    multiple: false,
    dragAndDrop: true,
    autoUpload: true
  };
  
  // Confirmation dialog
  confirmDialog = {
    title: '',
    message: '',
    confirmText: 'Confirm',
    cancelText: 'Cancel',
    type: 'warning' as 'info' | 'warning' | 'danger',
    action: null as (() => void) | null
  };
  
  // Real-time updates
  private subscriptions: Subscription[] = [];
  private refreshInterval?: Subscription;

  constructor(
    private manuscriptService: ManuscriptService,
    private errorHandler: ErrorHandlerService,
    private downloadService: DownloadService,
    private formBuilder: FormBuilder
  ) {
    this.filterForm = this.formBuilder.group({
      search: [''],
      status: [''],
      sortBy: ['upload_date_desc'],
      pageSize: [25]
    });
  }

  ngOnInit(): void {
    this.setupFormSubscriptions();
    this.loadData();
    this.startRealTimeUpdates();
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(sub => sub.unsubscribe());
    if (this.refreshInterval) {
      this.refreshInterval.unsubscribe();
    }
  }

  // Form and Filter Management
  private setupFormSubscriptions(): void {
    // Subscribe to form changes with debouncing
    this.subscriptions.push(
      this.filterForm.valueChanges
        .pipe(
          debounceTime(300),
          distinctUntilChanged()
        )
        .subscribe(() => {
          this.currentPage = 1; // Reset to first page when filters change
          this.loadManuscripts();
        })
    );
  }

  clearSearch(): void {
    this.filterForm.patchValue({ search: '' });
  }

  resetFilters(): void {
    this.filterForm.reset({
      search: '',
      status: '',
      sortBy: 'upload_date_desc',
      pageSize: 25
    });
    this.currentPage = 1;
  }

  // Data Loading
  loadData(): void {
    this.loadManuscripts();
    this.loadStatistics();
  }

  loadManuscripts(): void {
    this.isLoading = true;
    const formValue = this.filterForm.value;
    
    this.subscriptions.push(
      this.manuscriptService.getManuscripts(
        this.currentPage,
        formValue.pageSize,
        formValue.status
      ).subscribe({
        next: (response: ManuscriptListResponse) => {
          this.manuscripts = this.applyClientSideFilters(response.manuscripts);
          this.totalItems = response.total;
          this.pageSize = formValue.pageSize;
          this.totalPages = Math.ceil(this.totalItems / this.pageSize);
          this.isLoading = false;
        },
        error: (error) => {
          this.errorHandler.showError(error);
          this.isLoading = false;
        }
      })
    );
  }

  private applyClientSideFilters(manuscripts: ManuscriptResponse[]): ManuscriptResponse[] {
    const formValue = this.filterForm.value;
    let filtered = [...manuscripts];

    // Apply search filter
    if (formValue.search) {
      const searchTerm = formValue.search.toLowerCase();
      filtered = filtered.filter(m => 
        m.file_name.toLowerCase().includes(searchTerm)
      );
    }

    // Apply sorting
    filtered.sort((a, b) => {
      switch (formValue.sortBy) {
        case 'upload_date_asc':
          return new Date(a.upload_date).getTime() - new Date(b.upload_date).getTime();
        case 'upload_date_desc':
          return new Date(b.upload_date).getTime() - new Date(a.upload_date).getTime();
        case 'name_asc':
          return a.file_name.localeCompare(b.file_name);
        case 'name_desc':
          return b.file_name.localeCompare(a.file_name);
        case 'status_asc':
          return a.status.localeCompare(b.status);
        default:
          return 0;
      }
    });

    return filtered;
  }

  loadStatistics(): void {
    this.subscriptions.push(
      this.manuscriptService.getStatistics().subscribe({
        next: (stats) => {
          this.statistics = stats;
        },
        error: (error) => {
          console.error('Failed to load statistics:', error);
        }
      })
    );
  }

  refreshManuscripts(): void {
    this.loadData();
    this.errorHandler.showSuccess('Manuscripts refreshed');
  }

  // Real-time Updates
  private startRealTimeUpdates(): void {
    // Refresh data every 30 seconds for real-time updates
    this.refreshInterval = interval(30000).subscribe(() => {
      this.loadData();
    });
  }

  // Selection Management
  toggleManuscriptSelection(manuscriptId: string): void {
    if (this.selectedManuscripts.has(manuscriptId)) {
      this.selectedManuscripts.delete(manuscriptId);
    } else {
      this.selectedManuscripts.add(manuscriptId);
    }
  }

  toggleSelectAll(): void {
    if (this.isAllSelected()) {
      this.selectedManuscripts.clear();
    } else {
      this.manuscripts.forEach(m => this.selectedManuscripts.add(m.id));
    }
  }

  isAllSelected(): boolean {
    return this.manuscripts.length > 0 && 
           this.manuscripts.every(m => this.selectedManuscripts.has(m.id));
  }

  isSomeSelected(): boolean {
    return this.selectedManuscripts.size > 0 && !this.isAllSelected();
  }

  clearSelection(): void {
    this.selectedManuscripts.clear();
  }

  // Pagination
  previousPage(): void {
    if (this.currentPage > 1) {
      this.currentPage--;
      this.loadManuscripts();
    }
  }

  nextPage(): void {
    if (this.currentPage < this.totalPages) {
      this.currentPage++;
      this.loadManuscripts();
    }
  }

  goToPage(page: number): void {
    if (page >= 1 && page <= this.totalPages) {
      this.currentPage = page;
      this.loadManuscripts();
    }
  }

  getPageNumbers(): number[] {
    const pages: number[] = [];
    const maxPages = 5; // Show maximum 5 page numbers
    const startPage = Math.max(1, this.currentPage - Math.floor(maxPages / 2));
    const endPage = Math.min(this.totalPages, startPage + maxPages - 1);

    for (let i = startPage; i <= endPage; i++) {
      pages.push(i);
    }

    return pages;
  }

  // File Upload
  openUploadModal(): void {
    this.showUploadModal = true;
  }

  closeUploadModal(): void {
    this.showUploadModal = false;
  }

  onFileUploaded(event: { file: File; manuscriptId: string }): void {
    this.errorHandler.showSuccess(`File "${event.file.name}" uploaded successfully`);
    this.loadData(); // Refresh data to show the new manuscript
    this.closeUploadModal();
  }

  onUploadProgress(event: { file: File; progress: number }): void {
    // Handle upload progress if needed for UI feedback
    console.log(`Upload progress for ${event.file.name}: ${event.progress}%`);
  }

  onUploadError(event: { file: File; error: string }): void {
    this.errorHandler.showError(`Failed to upload "${event.file.name}": ${event.error}`);
  }

  // Manuscript Actions
  downloadManuscript(manuscript: ManuscriptResponse): void {
    // Open download dialog for file type selection
    this.selectedManuscriptForDownload = manuscript;
    this.showDownloadDialog = true;
  }


  retryProcessing(manuscript: ManuscriptResponse): void {
    // This would trigger reprocessing on the backend
    this.errorHandler.showInfo('Retry processing functionality will be implemented in Phase 5');
  }

  deleteManuscript(manuscript: ManuscriptResponse): void {
    this.showConfirmationDialog(
      'Delete Manuscript',
      `Are you sure you want to delete "${manuscript.file_name}"? This action cannot be undone.`,
      'Delete',
      'Cancel',
      'danger',
      () => {
        this.manuscriptService.deleteManuscript(manuscript.id).subscribe({
          next: () => {
            this.errorHandler.showSuccess('Manuscript deleted successfully');
            this.manuscripts = this.manuscripts.filter(m => m.id !== manuscript.id);
            this.selectedManuscripts.delete(manuscript.id);
            
            // Update pagination counts immediately
            this.totalItems = Math.max(0, this.totalItems - 1);
            this.totalPages = Math.ceil(this.totalItems / this.pageSize);
            
            // If current page is now empty and not the first page, go to previous page
            if (this.manuscripts.length === 0 && this.currentPage > 1) {
              this.currentPage--;
              this.loadManuscripts(); // Reload to get manuscripts for the previous page
            }
            
            this.loadStatistics(); // Refresh statistics
          },
          error: (error) => {
            this.errorHandler.showError(error);
          }
        });
      }
    );
  }

  // Bulk Operations
  bulkDownload(): void {
    const selectedIds = Array.from(this.selectedManuscripts);
    const selectedManuscripts = this.manuscripts.filter(m => selectedIds.includes(m.id));

    if (selectedManuscripts.length === 0) {
      this.errorHandler.showWarning('No manuscripts selected for download');
      return;
    }

    // Create download requests for all selected manuscripts
    const downloadRequests: DownloadRequest[] = selectedManuscripts.map(manuscript => ({
      manuscriptId: manuscript.id,
      fileName: manuscript.file_name,
      fileType: 'pdf', // Default to PDF for bulk downloads
      priority: 1
    }));

    // Start batch download
    this.downloadService.downloadMultipleFiles(downloadRequests).subscribe({
      next: (downloads) => {
        this.errorHandler.showSuccess(`Started batch download for ${downloads.length} manuscripts`);
      },
      error: (error) => {
        this.errorHandler.showError(`Failed to start batch download: ${error.message}`);
      }
    });

    // Clear selection after starting downloads
    this.clearSelection();
  }

  bulkDownloadXML(): void {
    const selectedIds = Array.from(this.selectedManuscripts);
    const completedManuscripts = this.manuscripts.filter(
      m => selectedIds.includes(m.id) && m.status === 'complete'
    );

    if (completedManuscripts.length === 0) {
      this.errorHandler.showWarning('No completed manuscripts selected for xml download');
      return;
    }

    // Create xml download requests
    const downloadRequests: DownloadRequest[] = completedManuscripts.map(manuscript => ({
      manuscriptId: manuscript.id,
      fileName: manuscript.file_name.replace('.pdf', '.xml'),
      fileType: 'xml',
      priority: 1
    }));

    // Start batch XML download
    this.downloadService.downloadMultipleFiles(downloadRequests).subscribe({
      next: (downloads) => {
        this.errorHandler.showSuccess(`Started batch XML download for ${downloads.length} manuscripts`);
      },
      error: (error) => {
        this.errorHandler.showError(`Failed to start batch XML download: ${error.message}`);
      }
    });

    // Clear selection after starting downloads
    this.clearSelection();
  }

  bulkDelete(): void {
    const selectedIds = Array.from(this.selectedManuscripts);
    const selectedManuscripts = this.manuscripts.filter(m => selectedIds.includes(m.id));

    this.showConfirmationDialog(
      'Delete Multiple Manuscripts',
      `Are you sure you want to delete ${selectedIds.length} manuscripts? This action cannot be undone.`,
      'Delete All',
      'Cancel',
      'danger',
      () => {
        // Delete each selected manuscript
        const deletePromises = selectedIds.map(id => 
          this.manuscriptService.deleteManuscript(id).toPromise()
        );

        Promise.all(deletePromises).then(() => {
          this.errorHandler.showSuccess(`${selectedIds.length} manuscripts deleted successfully`);
          this.manuscripts = this.manuscripts.filter(m => !selectedIds.includes(m.id));
          this.selectedManuscripts.clear();
          
          // Update pagination counts immediately
          this.totalItems = Math.max(0, this.totalItems - selectedIds.length);
          this.totalPages = Math.ceil(this.totalItems / this.pageSize);
          
          // If current page is now empty and not the first page, go to previous page
          if (this.manuscripts.length === 0 && this.currentPage > 1) {
            this.currentPage--;
            this.loadManuscripts(); // Reload to get manuscripts for the previous page
          }
          
          this.loadStatistics(); // Refresh statistics
        }).catch(error => {
          this.errorHandler.showError('Some manuscripts could not be deleted');
        });
      }
    );
  }

  // Confirmation Dialog
  private showConfirmationDialog(
    title: string,
    message: string,
    confirmText: string,
    cancelText: string,
    type: 'info' | 'warning' | 'danger',
    action: () => void
  ): void {
    this.confirmDialog = {
      title,
      message,
      confirmText,
      cancelText,
      type,
      action
    };
    this.showConfirmDialog = true;
  }

  onConfirmAction(): void {
    if (this.confirmDialog.action) {
      this.confirmDialog.action();
    }
    this.showConfirmDialog = false;
  }

  onCancelAction(): void {
    this.showConfirmDialog = false;
  }

  // Download Dialog Methods
  closeDownloadDialog(): void {
    this.showDownloadDialog = false;
    this.selectedManuscriptForDownload = null;
  }

/*  onDownloadWithOptions(options: DownloadOptions): void {
  if (!this.selectedManuscriptForDownload) return;
  const m = this.selectedManuscriptForDownload;

  const fileName = options.fileType === 'xml'
    ? m.file_name.replace(/\.pdf$/i, '.xml')
    : m.file_name;

  this.downloadService.downloadFile(m.id, fileName, options.fileType).subscribe();
  this.closeDownloadDialog();
}*/
  onDownloadWithOptions(options: DownloadOptions): void {
    if (!this.selectedManuscriptForDownload) return;

    const manuscript = this.selectedManuscriptForDownload;
    
    // Use the same approach as the direct download button
    this.manuscriptService.getDownloadUrl(manuscript.id, options.fileType).subscribe({
      next: (response) => {
        // Create a temporary link and trigger download
        const link = document.createElement('a');
        link.href = response.download_url;
        link.download = options.fileType === 'xml' 
          ? manuscript.file_name?.replace('.pdf', '.xml') || 'manuscript.xml'
          : manuscript.file_name || 'manuscript.pdf';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        this.errorHandler.showSuccess('Download started');
      },
      error: (error: any) => {
        this.errorHandler.showError(error);
      }
    });
  }


  // Utility Methods
  getStatusClass(status: string): string {
    switch (status.toLowerCase()) {
      case 'pending':
        return 'bg-yellow-100 text-yellow-800';
      case 'processing':
        return 'bg-blue-100 text-blue-800';
      case 'complete':
        return 'bg-green-100 text-green-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  }

  trackByManuscript(index: number, manuscript: ManuscriptResponse): string {
    return manuscript.id;
  }

  // Math utility for template
  Math = Math;
}
