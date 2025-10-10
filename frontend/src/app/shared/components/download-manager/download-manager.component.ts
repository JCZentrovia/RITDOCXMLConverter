import { Component, OnInit, OnDestroy, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subscription } from 'rxjs';
import { DownloadService, DownloadProgress, DownloadHistory, DownloadRequest } from '../../services/download.service';

@Component({
  selector: 'app-download-manager',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="download-manager" [class.expanded]="isExpanded">
      <!-- Download Manager Header -->
      <div class="download-header" (click)="toggleExpanded()">
        <div class="flex items-center space-x-3">
          <div class="download-icon">
            <svg class="w-5 h-5 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div class="download-info">
            <h3 class="text-sm font-medium text-gray-900">Downloads</h3>
            <p class="text-xs text-gray-500" *ngIf="activeDownloads.length > 0">
              {{ activeDownloads.length }} active • {{ queuedDownloads.length }} queued
            </p>
            <p class="text-xs text-gray-500" *ngIf="activeDownloads.length === 0 && queuedDownloads.length === 0">
              No active downloads
            </p>
          </div>
        </div>
        
        <div class="flex items-center space-x-2">
          <!-- Overall Progress -->
          <div class="overall-progress" *ngIf="activeDownloads.length > 0">
            <div class="w-16 bg-gray-200 rounded-full h-2">
              <div 
                class="bg-indigo-600 h-2 rounded-full transition-all duration-300"
                [style.width.%]="getOverallProgress()"
              ></div>
            </div>
          </div>
          
          <!-- Expand/Collapse Button -->
          <button
            type="button"
            class="text-gray-400 hover:text-gray-500 transition-colors"
          >
            <svg 
              class="w-4 h-4 transition-transform duration-200"
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

      <!-- Download Manager Content -->
      <div class="download-content" *ngIf="isExpanded">
        <!-- Active Downloads -->
        <div class="download-section" *ngIf="activeDownloads.length > 0">
          <div class="section-header">
            <h4 class="text-xs font-medium text-gray-700 uppercase tracking-wide">Active Downloads</h4>
            <button
              type="button"
              (click)="cancelAllDownloads()"
              class="text-xs text-red-600 hover:text-red-700"
            >
              Cancel All
            </button>
          </div>
          
          <div class="download-list">
            <div 
              *ngFor="let download of activeDownloads; trackBy: trackByDownload"
              class="download-item"
            >
              <!-- Download Info -->
              <div class="download-item-header">
                <div class="flex items-center space-x-3 flex-1 min-w-0">
                  <!-- File Type Icon -->
                  <div class="file-type-icon">
                    <svg *ngIf="download.fileType === 'pdf'" class="w-6 h-6 text-red-500" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20Z" />
                    </svg>
                    <svg *ngIf="download.fileType === 'xml'" class="w-6 h-6 text-blue-500" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20Z" />
                    </svg>
                  </div>
                  
                  <!-- File Info -->
                  <div class="flex-1 min-w-0">
                    <p class="text-sm font-medium text-gray-900 truncate">{{ download.fileName }}</p>
                    <div class="flex items-center space-x-2 text-xs text-gray-500">
                      <span class="status-badge" [ngClass]="getStatusClass(download.status)">
                        {{ download.status | titlecase }}
                      </span>
                      <span *ngIf="download.status === 'downloading'">
                        {{ formatBytes(download.downloadedBytes) }} / {{ formatBytes(download.totalBytes) }}
                      </span>
                      <span *ngIf="download.status === 'downloading' && download.speed > 0">
                        {{ formatBytes(download.speed) }}/s
                      </span>
                      <span *ngIf="download.status === 'downloading' && download.timeRemaining > 0">
                        {{ formatTime(download.timeRemaining) }} remaining
                      </span>
                    </div>
                  </div>
                </div>

                <!-- Actions -->
                <div class="download-actions">
                  <button
                    *ngIf="download.status === 'downloading'"
                    type="button"
                    (click)="cancelDownload(download.id)"
                    class="action-button text-red-600 hover:text-red-700"
                    title="Cancel download"
                  >
                    <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                  
                  <button
                    *ngIf="download.status === 'failed'"
                    type="button"
                    (click)="retryDownload(download.id)"
                    class="action-button text-blue-600 hover:text-blue-700"
                    title="Retry download"
                  >
                    <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                  </button>
                </div>
              </div>

              <!-- Progress Bar -->
              <div class="download-progress" *ngIf="download.status === 'downloading'">
                <div class="progress-track">
                  <div 
                    class="progress-fill"
                    [style.width.%]="download.progress"
                  ></div>
                </div>
                <span class="progress-text">{{ download.progress }}%</span>
              </div>

              <!-- Error Message -->
              <div class="error-message" *ngIf="download.status === 'failed' && download.error">
                <svg class="w-4 h-4 text-red-500 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {{ download.error }}
              </div>
            </div>
          </div>
        </div>

        <!-- Download Queue -->
        <div class="download-section" *ngIf="queuedDownloads.length > 0">
          <div class="section-header">
            <h4 class="text-xs font-medium text-gray-700 uppercase tracking-wide">Queue ({{ queuedDownloads.length }})</h4>
          </div>
          
          <div class="queue-list">
            <div 
              *ngFor="let request of queuedDownloads; let i = index; trackBy: trackByRequest"
              class="queue-item"
            >
              <div class="flex items-center space-x-3">
                <span class="queue-position">{{ i + 1 }}</span>
                <div class="flex-1 min-w-0">
                  <p class="text-sm text-gray-900 truncate">{{ request.fileName }}</p>
                  <p class="text-xs text-gray-500">{{ request.fileType.toUpperCase() }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Download History -->
        <div class="download-section" *ngIf="showHistory && downloadHistory.length > 0">
          <div class="section-header">
            <h4 class="text-xs font-medium text-gray-700 uppercase tracking-wide">Recent Downloads</h4>
            <button
              type="button"
              (click)="clearHistory()"
              class="text-xs text-red-600 hover:text-red-700"
            >
              Clear History
            </button>
          </div>
          
          <div class="history-list">
            <div 
              *ngFor="let item of getRecentHistory(); trackBy: trackByHistory"
              class="history-item"
            >
              <div class="flex items-center space-x-3">
                <div class="history-status" [ngClass]="getHistoryStatusClass(item.status)">
                  <svg *ngIf="item.status === 'completed'" class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                  </svg>
                  <svg *ngIf="item.status === 'failed'" class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </div>
                <div class="flex-1 min-w-0">
                  <p class="text-sm text-gray-900 truncate">{{ item.fileName }}</p>
                  <div class="flex items-center space-x-2 text-xs text-gray-500">
                    <span>{{ item.downloadDate | date:'short' }}</span>
                    <span *ngIf="item.fileSize > 0">{{ formatBytes(item.fileSize) }}</span>
                    <span *ngIf="item.duration > 0">{{ formatDuration(item.duration) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Download Statistics -->
        <div class="download-section" *ngIf="showStatistics">
          <div class="section-header">
            <h4 class="text-xs font-medium text-gray-700 uppercase tracking-wide">Statistics</h4>
          </div>
          
          <div class="statistics-grid">
            <div class="stat-item">
              <span class="stat-value">{{ statistics.totalDownloads }}</span>
              <span class="stat-label">Total</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ statistics.completedDownloads }}</span>
              <span class="stat-label">Completed</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ formatBytes(statistics.totalDataDownloaded) }}</span>
              <span class="stat-label">Downloaded</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ formatBytes(statistics.averageDownloadSpeed) }}/s</span>
              <span class="stat-label">Avg Speed</span>
            </div>
          </div>
        </div>

        <!-- Empty State -->
        <div class="empty-state" *ngIf="activeDownloads.length === 0 && queuedDownloads.length === 0 && downloadHistory.length === 0">
          <svg class="w-8 h-8 text-gray-400 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <p class="text-sm text-gray-500 text-center">No downloads yet</p>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .download-manager {
      @apply bg-white border border-gray-200 rounded-lg shadow-sm;
      position: fixed;
      bottom: 20px;
      right: 20px;
      width: 400px;
      max-height: 600px;
      z-index: 1000;
      transition: all 0.3s ease;
    }

    .download-manager:not(.expanded) {
      max-height: 60px;
    }

    .download-header {
      @apply p-4 border-b border-gray-200 cursor-pointer hover:bg-gray-50 transition-colors;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .download-content {
      @apply max-h-96 overflow-y-auto;
    }

    .download-section {
      @apply p-4 border-b border-gray-100 last:border-b-0;
    }

    .section-header {
      @apply flex items-center justify-between mb-3;
    }

    .download-list, .queue-list, .history-list {
      @apply space-y-3;
    }

    .download-item {
      @apply space-y-2;
    }

    .download-item-header {
      @apply flex items-center space-x-3;
    }

    .download-actions {
      @apply flex items-center space-x-1;
    }

    .action-button {
      @apply p-1 rounded-full hover:bg-gray-100 transition-colors;
    }

    .download-progress {
      @apply flex items-center space-x-3;
    }

    .progress-track {
      @apply flex-1 bg-gray-200 rounded-full h-2;
    }

    .progress-fill {
      @apply bg-indigo-600 h-2 rounded-full transition-all duration-300;
    }

    .progress-text {
      @apply text-xs font-medium text-gray-700 w-10 text-right;
    }

    .error-message {
      @apply flex items-center text-xs text-red-600 bg-red-50 p-2 rounded;
    }

    .status-badge {
      @apply px-2 py-0.5 rounded-full text-xs font-medium;
    }

    .status-badge.pending {
      @apply bg-yellow-100 text-yellow-800;
    }

    .status-badge.downloading {
      @apply bg-blue-100 text-blue-800;
    }

    .status-badge.completed {
      @apply bg-green-100 text-green-800;
    }

    .status-badge.failed {
      @apply bg-red-100 text-red-800;
    }

    .queue-item, .history-item {
      @apply p-2 bg-gray-50 rounded;
    }

    .queue-position {
      @apply w-6 h-6 bg-gray-200 rounded-full flex items-center justify-center text-xs font-medium text-gray-600;
    }

    .history-status {
      @apply w-4 h-4 rounded-full flex items-center justify-center;
    }

    .history-status.completed {
      @apply bg-green-100 text-green-600;
    }

    .history-status.failed {
      @apply bg-red-100 text-red-600;
    }

    .statistics-grid {
      @apply grid grid-cols-2 gap-3;
    }

    .stat-item {
      @apply text-center p-2 bg-gray-50 rounded;
    }

    .stat-value {
      @apply block text-sm font-medium text-gray-900;
    }

    .stat-label {
      @apply block text-xs text-gray-500;
    }

    .empty-state {
      @apply p-8 text-center;
    }

    .overall-progress {
      @apply flex items-center;
    }
  `]
})
export class DownloadManagerComponent implements OnInit, OnDestroy {
  @Input() showHistory = true;
  @Input() showStatistics = true;
  @Input() autoExpand = true;

  @Output() downloadComplete = new EventEmitter<DownloadProgress>();
  @Output() downloadFailed = new EventEmitter<DownloadProgress>();

  activeDownloads: DownloadProgress[] = [];
  queuedDownloads: DownloadRequest[] = [];
  downloadHistory: DownloadHistory[] = [];
  statistics = {
    totalDownloads: 0,
    completedDownloads: 0,
    failedDownloads: 0,
    totalDataDownloaded: 0,
    averageDownloadSpeed: 0
  };

  isExpanded = false;

  private subscriptions: Subscription[] = [];

  constructor(private downloadService: DownloadService) {}

  ngOnInit(): void {
    // Subscribe to download updates
    this.subscriptions.push(
      this.downloadService.downloads$.subscribe(downloads => {
        this.activeDownloads = downloads;
        
        // Auto-expand when downloads start
        if (this.autoExpand && downloads.length > 0 && !this.isExpanded) {
          this.isExpanded = true;
        }
      })
    );

    this.subscriptions.push(
      this.downloadService.queue$.subscribe(queue => {
        this.queuedDownloads = queue;
      })
    );

    this.subscriptions.push(
      this.downloadService.history$.subscribe(history => {
        this.downloadHistory = history;
      })
    );

    this.subscriptions.push(
      this.downloadService.downloadComplete$.subscribe(download => {
        this.downloadComplete.emit(download);
      })
    );

    // Update statistics
    this.updateStatistics();
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(sub => sub.unsubscribe());
  }

  toggleExpanded(): void {
    this.isExpanded = !this.isExpanded;
  }

  cancelDownload(downloadId: string): void {
    this.downloadService.cancelDownload(downloadId);
  }

  cancelAllDownloads(): void {
    this.downloadService.cancelAllDownloads();
  }

  retryDownload(downloadId: string): void {
    this.downloadService.retryDownload(downloadId);
  }

  clearHistory(): void {
    this.downloadService.clearDownloadHistory();
  }

  getOverallProgress(): number {
    if (this.activeDownloads.length === 0) return 0;
    
    const totalProgress = this.activeDownloads.reduce((sum, download) => sum + download.progress, 0);
    return Math.round(totalProgress / this.activeDownloads.length);
  }

  getRecentHistory(): DownloadHistory[] {
    return this.downloadHistory.slice(0, 5); // Show last 5 downloads
  }

  private updateStatistics(): void {
    this.statistics = this.downloadService.getDownloadStatistics();
  }

  // Utility Methods
  getStatusClass(status: string): string {
    return status.toLowerCase();
  }

  getHistoryStatusClass(status: string): string {
    return status.toLowerCase();
  }

  formatBytes(bytes: number): string {
    if (bytes === 0) return '0 B';
    
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  formatTime(seconds: number): string {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${Math.round(seconds / 3600)}h`;
  }

  formatDuration(milliseconds: number): string {
    const seconds = Math.round(milliseconds / 1000);
    return this.formatTime(seconds);
  }

  // TrackBy Functions
  trackByDownload(index: number, download: DownloadProgress): string {
    return download.id;
  }

  trackByRequest(index: number, request: DownloadRequest): string {
    return `${request.manuscriptId}-${request.fileType}`;
  }

  trackByHistory(index: number, item: DownloadHistory): string {
    return item.id;
  }
}
