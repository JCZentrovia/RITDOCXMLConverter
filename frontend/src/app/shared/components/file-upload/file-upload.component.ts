import { Component, Input, Output, EventEmitter, OnInit, OnDestroy, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subscription } from 'rxjs';
import { ManuscriptService, UploadProgress } from '../../services/manuscript.service';
import { ErrorHandlerService } from '../../services/error-handler.service';

export interface FileUploadConfig {
  maxFileSize?: number; // in bytes
  allowedTypes?: string[];
  multiple?: boolean;
  dragAndDrop?: boolean;
  showPreview?: boolean;
  autoUpload?: boolean;
}

export interface UploadedFile {
  file: File;
  progress: number;
  status: 'pending' | 'uploading' | 'completed' | 'error';
  manuscriptId?: string;
  error?: string;
  preview?: string;
}

@Component({
  selector: 'app-file-upload',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="file-upload-container">
      <!-- Upload Area -->
      <div 
        class="upload-area"
        [class.drag-over]="isDragOver"
        [class.disabled]="disabled"
        (click)="triggerFileSelect()"
        (dragover)="onDragOver($event)"
        (dragleave)="onDragLeave($event)"
        (drop)="onDrop($event)"
      >
        <!-- Hidden File Input -->
        <input
          #fileInput
          type="file"
          class="hidden"
          [accept]="acceptedTypes"
          [multiple]="config.multiple"
          (change)="onFileSelected($event)"
        />

        <!-- Upload Content -->
        <div class="upload-content">
          <!-- Icon -->
          <div class="upload-icon">
            <svg class="w-12 h-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </div>

          <!-- Text -->
          <div class="upload-text">
            <p class="text-lg font-medium text-gray-900">
              {{ isDragOver ? 'Drop files here' : 'Upload PDF files' }}
            </p>
            <p class="text-sm text-gray-500 mt-1">
              {{ config.dragAndDrop ? 'Drag and drop files here, or click to browse' : 'Click to browse files' }}
            </p>
            <p class="text-xs text-gray-400 mt-2">
              Large files are supported. Upload time depends on your network.
            </p>
          </div>

          <!-- Upload Button -->
          <button
            type="button"
            class="upload-button"
            [disabled]="disabled"
          >
            <svg class="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
            Choose Files
          </button>
        </div>
      </div>

      <!-- File List -->
      <div *ngIf="uploadedFiles.length > 0" class="file-list">
        <h3 class="text-sm font-medium text-gray-900 mb-3">
          {{ uploadedFiles.length === 1 ? '1 file' : uploadedFiles.length + ' files' }}
        </h3>
        
        <div class="space-y-3">
          <div 
            *ngFor="let uploadedFile of uploadedFiles; trackBy: trackByFile"
            class="file-item"
          >
            <!-- File Info -->
            <div class="file-info">
              <!-- File Icon -->
              <div class="file-icon">
                <svg class="w-8 h-8 text-red-500" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20Z" />
                </svg>
              </div>

              <!-- File Details -->
              <div class="file-details">
                <div class="file-name">{{ uploadedFile.file.name }}</div>
                <div class="file-meta">
                  {{ formatFileSize(uploadedFile.file.size) }} • 
                  {{ getStatusText(uploadedFile.status) }}
                </div>
              </div>

              <!-- Actions -->
              <div class="file-actions">
                <!-- Remove Button -->
                <button
                  *ngIf="uploadedFile.status === 'pending' || uploadedFile.status === 'error'"
                  type="button"
                  (click)="removeFile(uploadedFile)"
                  class="action-button text-red-600 hover:text-red-700"
                  title="Remove file"
                >
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>

                <!-- Retry Button -->
                <button
                  *ngIf="uploadedFile.status === 'error'"
                  type="button"
                  (click)="retryUpload(uploadedFile)"
                  class="action-button text-blue-600 hover:text-blue-700 ml-2"
                  title="Retry upload"
                >
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                </button>

                <!-- Success Icon -->
                <div
                  *ngIf="uploadedFile.status === 'completed'"
                  class="text-green-600"
                  title="Upload completed"
                >
                  <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
              </div>
            </div>

            <!-- Progress Bar -->
            <div *ngIf="uploadedFile.status === 'uploading'" class="progress-bar">
              <div class="progress-track">
                <div 
                  class="progress-fill"
                  [style.width.%]="uploadedFile.progress"
                ></div>
              </div>
              <div class="progress-text">{{ uploadedFile.progress }}%</div>
            </div>

            <!-- Error Message -->
            <div *ngIf="uploadedFile.status === 'error' && uploadedFile.error" class="error-message">
              <svg class="w-4 h-4 text-red-500 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {{ uploadedFile.error }}
            </div>
          </div>
        </div>

        <!-- Upload All Button -->
        <div *ngIf="!config.autoUpload && hasPendingFiles()" class="upload-all-section">
          <button
            type="button"
            (click)="uploadAllFiles()"
            class="upload-all-button"
            [disabled]="isUploading"
          >
            <svg class="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            Upload {{ getPendingFilesCount() }} {{ getPendingFilesCount() === 1 ? 'file' : 'files' }}
          </button>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .file-upload-container {
      @apply w-full;
    }

    .upload-area {
      @apply border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer transition-colors duration-200;
    }

    .upload-area:hover:not(.disabled) {
      @apply border-gray-400 bg-gray-50;
    }

    .upload-area.drag-over {
      @apply border-blue-500 bg-blue-50;
    }

    .upload-area.disabled {
      @apply cursor-not-allowed opacity-50;
    }

    .upload-content {
      @apply flex flex-col items-center space-y-4;
    }

    .upload-icon {
      @apply flex items-center justify-center;
    }

    .upload-text {
      @apply text-center;
    }

    .upload-button {
      @apply inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed;
    }

    .file-list {
      @apply mt-6 p-4 bg-gray-50 rounded-lg;
    }

    .file-item {
      @apply bg-white rounded-lg p-4 border border-gray-200;
    }

    .file-info {
      @apply flex items-center space-x-3;
    }

    .file-icon {
      @apply flex-shrink-0;
    }

    .file-details {
      @apply flex-1 min-w-0;
    }

    .file-name {
      @apply text-sm font-medium text-gray-900 truncate;
    }

    .file-meta {
      @apply text-xs text-gray-500;
    }

    .file-actions {
      @apply flex items-center space-x-1;
    }

    .action-button {
      @apply p-1 rounded-full hover:bg-gray-100 transition-colors duration-150;
    }

    .progress-bar {
      @apply mt-3 flex items-center space-x-3;
    }

    .progress-track {
      @apply flex-1 bg-gray-200 rounded-full h-2;
    }

    .progress-fill {
      @apply bg-blue-600 h-2 rounded-full transition-all duration-300;
    }

    .progress-text {
      @apply text-xs font-medium text-gray-700 w-10 text-right;
    }

    .error-message {
      @apply mt-2 flex items-center text-xs text-red-600 bg-red-50 p-2 rounded;
    }

    .upload-all-section {
      @apply mt-4 pt-4 border-t border-gray-200;
    }

    .upload-all-button {
      @apply inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed;
    }

    .hidden {
      display: none;
    }
  `]
})
export class FileUploadComponent implements OnInit, OnDestroy {
  @Input() config: FileUploadConfig = {
    maxFileSize: 100 * 1024 * 1024, // 100MB
    allowedTypes: ['application/pdf'],
    multiple: false,
    dragAndDrop: true,
    showPreview: false,
    autoUpload: true
  };

  @Input() disabled = false;

  @Output() fileUploaded = new EventEmitter<{ file: File; manuscriptId: string }>();
  @Output() uploadProgress = new EventEmitter<{ file: File; progress: number }>();
  @Output() uploadError = new EventEmitter<{ file: File; error: string }>();
  @Output() filesChanged = new EventEmitter<UploadedFile[]>();

  @ViewChild('fileInput') fileInput!: ElementRef<HTMLInputElement>;

  uploadedFiles: UploadedFile[] = [];
  isDragOver = false;
  isUploading = false;

  private subscriptions: Subscription[] = [];

  constructor(
    private manuscriptService: ManuscriptService,
    private errorHandler: ErrorHandlerService
  ) {}

  ngOnInit(): void {
    // Set default config values
    this.config = {
      maxFileSize: 100 * 1024 * 1024, // 100MB
      allowedTypes: ['application/pdf'],
      multiple: false,
      dragAndDrop: true,
      showPreview: false,
      autoUpload: true,
      ...this.config
    };
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(sub => sub.unsubscribe());
  }

  get acceptedTypes(): string {
    return this.config.allowedTypes?.join(',') || '.pdf';
  }

  // File Selection
  triggerFileSelect(): void {
    if (!this.disabled) {
      this.fileInput.nativeElement.click();
    }
  }

  onFileSelected(event: Event): void {
    const target = event.target as HTMLInputElement;
    const files = target.files;
    
    if (files) {
      this.handleFiles(Array.from(files));
    }
    
    // Reset input value to allow selecting the same file again
    target.value = '';
  }

  // Drag and Drop
  onDragOver(event: DragEvent): void {
    if (!this.config.dragAndDrop || this.disabled) return;
    
    event.preventDefault();
    event.stopPropagation();
    this.isDragOver = true;
  }

  onDragLeave(event: DragEvent): void {
    if (!this.config.dragAndDrop || this.disabled) return;
    
    event.preventDefault();
    event.stopPropagation();
    this.isDragOver = false;
  }

  onDrop(event: DragEvent): void {
    if (!this.config.dragAndDrop || this.disabled) return;
    
    event.preventDefault();
    event.stopPropagation();
    this.isDragOver = false;

    const files = event.dataTransfer?.files;
    if (files) {
      this.handleFiles(Array.from(files));
    }
  }

  // File Handling
  private handleFiles(files: File[]): void {
    // Validate file count
    if (!this.config.multiple && files.length > 1) {
      this.errorHandler.showError('Only one file can be uploaded at a time');
      return;
    }

    // Validate and add files
    for (const file of files) {
      if (this.validateFile(file)) {
        const uploadedFile: UploadedFile = {
          file,
          progress: 0,
          status: 'pending'
        };

        this.uploadedFiles.push(uploadedFile);

        // Auto-upload if enabled
        if (this.config.autoUpload) {
          this.uploadFile(uploadedFile);
        }
      }
    }

    this.filesChanged.emit(this.uploadedFiles);
  }

  private validateFile(file: File): boolean {
    // Check file type
    if (this.config.allowedTypes && !this.config.allowedTypes.includes(file.type)) {
      this.errorHandler.showError(`File type ${file.type} is not allowed. Only PDF files are supported.`);
      return false;
    }

    // No hard client-side size cap; warn if very large
    const veryLargeThreshold = 500 * 1024 * 1024; // 500MB
    if (file.size > veryLargeThreshold) {
      this.errorHandler.showWarning(
        `Large file detected (${this.formatFileSize(file.size)}). Upload may take a while depending on your network.`
      );
    }

    // Check if file already exists
    if (this.uploadedFiles.some(uf => uf.file.name === file.name && uf.file.size === file.size)) {
      this.errorHandler.showError(`File "${file.name}" has already been added`);
      return false;
    }

    return true;
  }

  // Upload Operations
  private uploadFile(uploadedFile: UploadedFile): void {
    uploadedFile.status = 'uploading';
    uploadedFile.progress = 0;
    this.isUploading = true;

    const subscription = this.manuscriptService.uploadManuscript(uploadedFile.file).subscribe({
      next: (progress: UploadProgress) => {
        if (progress.type === 'progress' && progress.progress !== undefined) {
          uploadedFile.progress = progress.progress;
          this.uploadProgress.emit({ file: uploadedFile.file, progress: progress.progress });
        } else if (progress.type === 'complete') {
          uploadedFile.status = 'completed';
          uploadedFile.progress = 100;
          uploadedFile.manuscriptId = (progress as any).manuscript_id;
          
          this.fileUploaded.emit({ 
            file: uploadedFile.file, 
            manuscriptId: uploadedFile.manuscriptId! 
          });
          
          this.errorHandler.showSuccess(`File "${uploadedFile.file.name}" uploaded successfully`);
        }
      },
      error: (error) => {
        uploadedFile.status = 'error';
        uploadedFile.error = error.message || 'Upload failed';
        this.uploadError.emit({ file: uploadedFile.file, error: uploadedFile.error || 'Unknown error' });
        this.errorHandler.showError(`Failed to upload "${uploadedFile.file.name}": ${uploadedFile.error}`);
      },
      complete: () => {
        this.isUploading = this.uploadedFiles.some(uf => uf.status === 'uploading');
      }
    });

    this.subscriptions.push(subscription);
  }

  uploadAllFiles(): void {
    const pendingFiles = this.uploadedFiles.filter(uf => uf.status === 'pending');
    pendingFiles.forEach(uploadedFile => this.uploadFile(uploadedFile));
  }

  retryUpload(uploadedFile: UploadedFile): void {
    uploadedFile.error = undefined;
    this.uploadFile(uploadedFile);
  }

  removeFile(uploadedFile: UploadedFile): void {
    const index = this.uploadedFiles.indexOf(uploadedFile);
    if (index > -1) {
      this.uploadedFiles.splice(index, 1);
      this.filesChanged.emit(this.uploadedFiles);
    }
  }

  // Helper Methods
  hasPendingFiles(): boolean {
    return this.uploadedFiles.some(uf => uf.status === 'pending');
  }

  getPendingFilesCount(): number {
    return this.uploadedFiles.filter(uf => uf.status === 'pending').length;
  }

  getStatusText(status: string): string {
    switch (status) {
      case 'pending': return 'Ready to upload';
      case 'uploading': return 'Uploading...';
      case 'completed': return 'Upload complete';
      case 'error': return 'Upload failed';
      default: return 'Unknown';
    }
  }

  formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  trackByFile(index: number, uploadedFile: UploadedFile): string {
    return `${uploadedFile.file.name}-${uploadedFile.file.size}`;
  }
}
