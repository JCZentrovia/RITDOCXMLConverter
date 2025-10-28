import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { Subscription } from 'rxjs';
import { AuthService, User } from '../shared/services/auth.service';
import { ManuscriptService, ManuscriptResponse, ManuscriptStatistics } from '../shared/services/manuscript.service';
import { ErrorHandlerService } from '../shared/services/error-handler.service';
import { NavigationComponent } from '../shared/components/navigation/navigation.component';
import { FileUploadComponent, FileUploadConfig } from '../shared/components/file-upload/file-upload.component';
//import { switchMap } from 'rxjs/operators';
import { HttpClient } from '@angular/common/http';
import { switchMap } from 'rxjs';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterModule, NavigationComponent, FileUploadComponent],
  template: `
    <div class="min-h-screen bg-gray-50">
      <!-- Navigation -->
      <app-navigation></app-navigation>

      <!-- Main Content -->
      <main class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <!-- Welcome Section -->
        <div class="px-4 py-6 sm:px-0">
          <div class="mb-8">
            <h1 class="text-3xl font-bold text-gray-900">
              Welcome back, {{ getUserDisplayName() }}!
            </h1>
            <p class="mt-1 text-sm text-gray-600">
              Manage your manuscripts and track processing status
            </p>
          </div>

          <!-- Stats Cards -->
          <div class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4 mb-8">
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
                      <dt class="text-sm font-medium text-gray-500 truncate">Total Manuscripts</dt>
                      <dd class="text-lg font-medium text-gray-900">{{ statistics?.total || 0 }}</dd>
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
                      <dd class="text-lg font-medium text-gray-900">{{ statistics?.processing || 0 }}</dd>
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
                      <dd class="text-lg font-medium text-gray-900">{{ statistics?.completed || 0 }}</dd>
                    </dl>
                  </div>
                </div>
              </div>
            </div>

          </div>

          <!-- Quick Actions -->
          <div class="bg-white shadow rounded-lg mb-8">
            <div class="px-4 py-5 sm:p-6">
              <h3 class="text-lg leading-6 font-medium text-gray-900 mb-4">Quick Actions</h3>
              <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <button
                  type="button"
                  class="relative block w-full border-2 border-gray-300 border-dashed rounded-lg p-6 text-center hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                  (click)="openUploadModal()"
                >
                  <svg class="mx-auto h-8 w-8 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
                    <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
                  </svg>
                  <span class="mt-2 block text-sm font-medium text-gray-900">Upload New Manuscript</span>
                  <span class="mt-1 block text-xs text-gray-500">PDF files up to 10MB</span>
                </button>

                <button
                  type="button"
                  routerLink="/manuscripts"
                  class="relative block w-full border-2 border-gray-300 border-dashed rounded-lg p-6 text-center hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                >
                  <svg class="mx-auto h-8 w-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                  </svg>
                  <span class="mt-2 block text-sm font-medium text-gray-900">View All Manuscripts</span>
                  <span class="mt-1 block text-xs text-gray-500">Manage your documents</span>
                </button>

              </div>
            </div>
          </div>

          <!-- Recent Manuscripts -->
          <div class="bg-white shadow rounded-lg">
            <div class="px-4 py-5 sm:p-6">
              <h3 class="text-lg leading-6 font-medium text-gray-900 mb-4">Recent Manuscripts</h3>
              
              <div *ngIf="isLoading" class="text-center py-4">
                <div class="inline-flex items-center">
                  <svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-gray-500" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Loading manuscripts...
                </div>
              </div>

              <div *ngIf="!isLoading && manuscripts.length === 0" class="text-center py-8">
                <svg class="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
                  <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
                </svg>
                <h3 class="mt-2 text-sm font-medium text-gray-900">No manuscripts</h3>
                <p class="mt-1 text-sm text-gray-500">Get started by uploading your first manuscript.</p>
                <div class="mt-6">
                  <button
                    type="button"
                    class="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                    (click)="triggerFileUpload()"
                  >
                    <svg class="-ml-1 mr-2 h-5 w-5" stroke="currentColor" fill="none" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                    </svg>
                    Upload Manuscript
                  </button>
                </div>
              </div>

              <div *ngIf="!isLoading && manuscripts.length > 0" class="overflow-hidden">
                <ul class="divide-y divide-gray-200">
                  <li *ngFor="let manuscript of getRecentManuscripts()" class="py-4">
                    <div class="flex items-center space-x-4">
                      <div class="flex-shrink-0">
                        <svg class="h-8 w-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                      </div>
                      <div class="flex-1 min-w-0">
                        <p class="text-sm font-medium text-gray-900 truncate">
                          {{ manuscript.file_name || 'Untitled Document' }}
                        </p>
                        <p class="text-sm text-gray-500">
                          Uploaded {{ manuscript.upload_date | date:'short' }}
                        </p>
                      </div>
                      <div class="flex items-center space-x-2">
                        <span [ngClass]="getStatusClass(manuscript.status)" class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium">
                          {{ manuscript.status }}
                        </span>
                        <button
                          *ngIf="manuscript.status === 'complete'"
                          class="inline-flex items-center px-3 py-1 border border-transparent text-xs font-medium rounded text-indigo-700 bg-indigo-100 hover:bg-indigo-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                          (click)="downloadManuscript(manuscript)"
                        >
                          <svg class="-ml-0.5 mr-1 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-4-4m4 4l4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          Download
                        </button>
                      </div>
                    </div>
                  </li>
                </ul>
                
                <div *ngIf="manuscripts.length > 5" class="mt-6">
                  <button
                    type="button"
                    routerLink="/manuscripts"
                    class="w-full flex justify-center items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                  >
                    View all {{ manuscripts.length }} manuscripts
                    <svg class="ml-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

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

      <!-- Hidden file input (legacy) -->
      <input
        #fileInput
        type="file"
        class="hidden"
        accept=".pdf"
        (change)="onFileSelected($event)"
      />
    </div>
  `
})
export class DashboardComponent implements OnInit, OnDestroy {
  manuscripts: ManuscriptResponse[] = [];
  statistics: ManuscriptStatistics | null = null;
  currentUser: User | null = null;
  isLoading = false;
  showUploadModal = false;
  
  uploadConfig: FileUploadConfig = {
    maxFileSize: 100 * 1024 * 1024, // 100MB
    allowedTypes: ['application/pdf'],
    multiple: false,
    dragAndDrop: true,
    autoUpload: true
  };
  
  private subscriptions: Subscription[] = [];

  constructor(
    private authService: AuthService,
    private manuscriptService: ManuscriptService,
    private errorHandler: ErrorHandlerService,
    private http: HttpClient
  ) {}

  ngOnInit(): void {
    this.subscriptions.push(
      this.authService.currentUser$.subscribe(user => {
        this.currentUser = user;
      })
    );
    
    this.loadData();
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(sub => sub.unsubscribe());
  }

  loadData(): void {
    this.loadManuscripts();
    this.loadStatistics();
  }

  loadManuscripts(): void {
    this.isLoading = true;
    this.subscriptions.push(
      this.manuscriptService.getManuscripts(1, 10).subscribe({
        next: (response) => {
          this.manuscripts = response.manuscripts;
          this.isLoading = false;
        },
        error: (error) => {
          this.errorHandler.showError(error);
          this.isLoading = false;
        }
      })
    );
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

  getUserDisplayName(): string {
    return this.authService.getUserDisplayName();
  }

  getManuscriptsByStatus(status: string): ManuscriptResponse[] {
    return this.manuscripts.filter(m => m.status === status);
  }

  getRecentManuscripts(): ManuscriptResponse[] {
    return this.manuscripts
      .sort((a, b) => new Date(b.upload_date).getTime() - new Date(a.upload_date).getTime())
      .slice(0, 5);
  }

  // File Upload Event Handlers
  onFileUploaded(event: { file: File; manuscriptId: string }): void {
    this.errorHandler.showSuccess(`File "${event.file.name}" uploaded successfully`);
    this.loadData(); // Refresh data to show the new manuscript
  }

  onUploadProgress(event: { file: File; progress: number }): void {
    // Handle upload progress if needed for UI feedback
    console.log(`Upload progress for ${event.file.name}: ${event.progress}%`);
  }

  onUploadError(event: { file: File; error: string }): void {
    this.errorHandler.showError(`Failed to upload "${event.file.name}": ${event.error}`);
  }

  // Modal Management
  openUploadModal(): void {
    this.showUploadModal = true;
  }

  closeUploadModal(): void {
    this.showUploadModal = false;
  }

  // Legacy methods for backward compatibility
  triggerFileUpload(): void {
    this.openUploadModal();
  }

  onFileSelected(event: Event): void {
    // This method is kept for backward compatibility but not used with new upload component
    console.log('Legacy file selection method called');
  }

  getStatusClass(status: string): string {
    switch (status.toLowerCase()) {
      case 'pending':
        return 'bg-yellow-100 text-yellow-800';
      case 'processing':
        return 'bg-blue-100 text-blue-800';
      case 'completed':
      case 'complete':
        return 'bg-green-100 text-green-800';
      case 'failed':
      case 'error':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  }

  downloadManuscript(manuscript: ManuscriptResponse): void {
  this.manuscriptService.getDownloadUrl(manuscript.id, 'xml').pipe(
    switchMap(({ download_url }) =>
      this.http.get(download_url, { responseType: 'blob' }) // Observable<Blob>
    )
  ).subscribe({
    next: (blob: Blob) => {
      const fileName =
        manuscript.file_name?.replace(/\.pdf$/i, '.xml') ?? 'manuscript.xml';
     const blobUrl = URL.createObjectURL(blob);
     const a = document.createElement('a');
     a.href = blobUrl;
      a.download = fileName;
      document.body.appendChild(a);
     a.click();
      a.remove();
      URL.revokeObjectURL(blobUrl);

      this.errorHandler.showSuccess('Download started');
    },
    error: (err) => this.errorHandler.showError(err),
  });
}
  /*Commenting this out - as it was opening the xml in the same window and not downloading the xml file
  downloadManuscript(manuscript: ManuscriptResponse): void {
    this.manuscriptService.getDownloadUrl(manuscript.id, 'xml').subscribe({
      next: (response) => {
        // Create a temporary link and trigger download
        const link = document.createElement('a');
        link.href = response.download_url;
        link.download = manuscript.file_name?.replace('.pdf', 'xml') || 'manuscript.xml';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        this.errorHandler.showSuccess('Download started');
      },
      error: (error: any) => {
        this.errorHandler.showError(error);
      }
    });
  }*/
}
