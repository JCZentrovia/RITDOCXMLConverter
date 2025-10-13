import { Component, Input, Output, EventEmitter, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ManuscriptResponse } from '../../services/manuscript.service';

export interface DownloadOptions {
  fileType: 'pdf' | 'xml';
}

@Component({
  selector: 'app-download-dialog',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="fixed inset-0 z-50 overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
      <div class="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
        <!-- Background overlay -->
        <div 
          class="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" 
          aria-hidden="true"
          (click)="onCancel()"
        ></div>

        <!-- Modal panel -->
        <div class="inline-block align-bottom bg-white rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full sm:p-6">
          <div class="sm:flex sm:items-start">
            <div class="w-full">
              <!-- Modal Header -->
              <div class="flex items-center justify-between mb-6">
                <div class="flex items-center space-x-3">
                  <div class="mx-auto flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-blue-100">
                    <svg class="h-6 w-6 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <div>
                    <h3 class="text-lg leading-6 font-medium text-gray-900" id="modal-title">
                      Download Options
                    </h3>
                    <p class="text-sm text-gray-500">
                      Choose download format and options for "{{ manuscript?.file_name }}"
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  class="bg-white rounded-md text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                  (click)="onCancel()"
                >
                  <span class="sr-only">Close</span>
                  <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <!-- File Type Selection -->
              <div class="mb-6">
                <label class="text-base font-medium text-gray-900">File Format</label>
                <p class="text-sm leading-5 text-gray-500 mb-4">Select the format you want to download</p>
                <fieldset class="space-y-3">
                  <div class="relative flex items-start">
                    <div class="flex items-center h-5">
                      <input
                        id="pdf-format"
                        name="fileType"
                        type="radio"
                        value="pdf"
                        [(ngModel)]="downloadOptions.fileType"
                        class="focus:ring-indigo-500 h-4 w-4 text-indigo-600 border-gray-300"
                      />
                    </div>
                    <div class="ml-3 text-sm">
                      <label for="pdf-format" class="font-medium text-gray-700 cursor-pointer">
                        <div class="flex items-center space-x-3">
                          <svg class="w-6 h-6 text-red-500" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20Z" />
                          </svg>
                          <div>
                            <div class="font-medium text-gray-900">PDF (Original)</div>
                            <div class="text-gray-500">Download the original PDF file</div>
                          </div>
                        </div>
                      </label>
                    </div>
                  </div>

                  <div class="relative flex items-start">
                    <div class="flex items-center h-5">
                      <input
                        id="Xml-format"
                        name="fileType"
                        type="radio"
                        value="xml"
                        [(ngModel)]="downloadOptions.fileType"
                        class="focus:ring-indigo-500 h-4 w-4 text-indigo-600 border-gray-300"
                        [disabled]="!isXmlAvailable"
                      />
                    </div>
                    <div class="ml-3 text-sm">
                      <label for="xml-format" class="font-medium text-gray-700 cursor-pointer" [class.opacity-50]="!isXmlAvailable">
                        <div class="flex items-center space-x-3">
                          <svg class="w-6 h-6 text-blue-500" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20Z" />
                          </svg>
                          <div>
                            <div class="font-medium text-gray-900">Converted XML File</div>
                            <div class="text-gray-500">
                              {{ isXmlAvailable ? 'Converted XML document' : 'Conversion in progress or not available' }}
                            </div>
                          </div>
                        </div>
                      </label>
                    </div>
                  </div>
                </fieldset>
              </div>


              <!-- File Information -->
              <div class="mb-6 p-4 bg-gray-50 rounded-lg">
                <h4 class="text-sm font-medium text-gray-900 mb-2">File Information</h4>
                <div class="space-y-1 text-sm text-gray-600">
                  <div class="flex justify-between">
                    <span>Status:</span>
                    <span class="font-medium" [ngClass]="getStatusClass(manuscript?.status || '')">
                      {{ manuscript?.status | titlecase }}
                    </span>
                  </div>
                  <div class="flex justify-between">
                    <span>Uploaded:</span>
                    <span>{{ manuscript?.upload_date | date:'short' }}</span>
                  </div>
                  <div class="flex justify-between" *ngIf="manuscript?.processing_completed_at">
                    <span>Processed:</span>
                    <span>{{ manuscript?.processing_completed_at | date:'short' }}</span>
                  </div>
                  <div class="flex justify-between" *ngIf="getEstimatedFileSize() > 0">
                    <span>Estimated Size:</span>
                    <span>{{ formatBytes(getEstimatedFileSize()) }}</span>
                  </div>
                </div>
              </div>

              <!-- Action Buttons -->
              <div class="flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-3 space-y-3 space-y-reverse sm:space-y-0">
                <button
                  type="button"
                  (click)="onCancel()"
                  class="w-full sm:w-auto inline-flex justify-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  (click)="onDownload()"
                  [disabled]="!canDownload()"
                  class="w-full sm:w-auto inline-flex justify-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <svg class="-ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  Download {{ downloadOptions.fileType.toUpperCase() }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `
})
export class DownloadDialogComponent implements OnInit {
  @Input() manuscript: ManuscriptResponse | null = null;

  @Output() download = new EventEmitter<DownloadOptions>();
  @Output() cancel = new EventEmitter<void>();

  downloadOptions: DownloadOptions = {
    fileType: 'pdf'
  };

  ngOnInit(): void {
    // Set default file type based on availability
    if (this.manuscript) {
      this.downloadOptions.fileType = this.isXmlAvailable ? 'xml' : 'pdf';
    }
  }

  get isXmlAvailable(): boolean {
    return this.manuscript?.status === 'complete';
  }

  canDownload(): boolean {
    if (!this.manuscript) return false;
    
    if (this.downloadOptions.fileType === 'pdf') {
      return true; // PDF is always available
    }
    
    if (this.downloadOptions.fileType === 'xml') {
      return this.isXmlAvailable;
    }
    
    return false;
  }

  getEstimatedFileSize(): number {
    if (!this.manuscript) return 0;
    
    // Estimate file sizes based on type
    const baseSize = 1024 * 1024; // 1MB base estimate
    
    if (this.downloadOptions.fileType === 'pdf') {
      return baseSize * 2; // PDFs are typically larger
    } else if (this.downloadOptions.fileType === 'xml') {
      return baseSize * 0.8; // XML files are typically smaller
    }
    
    return baseSize;
  }

  onDownload(): void {
    if (this.canDownload()) {
      this.download.emit({ ...this.downloadOptions });
    }
  }

  onCancel(): void {
    this.cancel.emit();
  }

  // Utility Methods
  getStatusClass(status: string): string {
    switch (status.toLowerCase()) {
      case 'pending':
        return 'text-yellow-600';
      case 'processing':
        return 'text-blue-600';
      case 'complete':
        return 'text-green-600';
      case 'failed':
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  }

  formatBytes(bytes: number): string {
    if (bytes === 0) return '0 B';
    
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }
}
