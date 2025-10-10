import { Injectable } from '@angular/core';
import { HttpClient, HttpEventType, HttpHeaders } from '@angular/common/http';
import { Observable, BehaviorSubject, Subject, throwError } from 'rxjs';
import { map, catchError, tap } from 'rxjs/operators';
import { ManuscriptService, ManuscriptResponse, DownloadUrlResponse } from './manuscript.service';
import { ErrorHandlerService } from './error-handler.service';

export interface DownloadProgress {
  id: string;
  fileName: string;
  fileType: 'pdf' | 'xml';
  progress: number;
  status: 'pending' | 'downloading' | 'completed' | 'failed' | 'cancelled';
  downloadedBytes: number;
  totalBytes: number;
  speed: number; // bytes per second
  timeRemaining: number; // seconds
  error?: string;
  startTime: number;
  endTime?: number;
}

export interface DownloadRequest {
  manuscriptId: string;
  fileName: string;
  fileType: 'pdf' | 'xml';
  priority?: number;
}

export interface DownloadHistory {
  id: string;
  manuscriptId: string;
  fileName: string;
  fileType: 'pdf' | 'xml';
  downloadDate: Date;
  fileSize: number;
  duration: number; // milliseconds
  status: 'completed' | 'failed';
  error?: string;
}

@Injectable({
  providedIn: 'root'
})
export class DownloadService {
  private activeDownloads = new Map<string, DownloadProgress>();
  private downloadQueue: DownloadRequest[] = [];
  private downloadHistory: DownloadHistory[] = [];
  private maxConcurrentDownloads = 3;
  private currentDownloads = 0;

  // Observables for reactive updates
  private downloadsSubject = new BehaviorSubject<DownloadProgress[]>([]);
  private historySubject = new BehaviorSubject<DownloadHistory[]>([]);
  private queueSubject = new BehaviorSubject<DownloadRequest[]>([]);

  public downloads$ = this.downloadsSubject.asObservable();
  public history$ = this.historySubject.asObservable();
  public queue$ = this.queueSubject.asObservable();

  // Download completion events
  private downloadCompleteSubject = new Subject<DownloadProgress>();
  public downloadComplete$ = this.downloadCompleteSubject.asObservable();

  constructor(
    private http: HttpClient,
    private manuscriptService: ManuscriptService,
    private errorHandler: ErrorHandlerService
  ) {
    this.loadDownloadHistory();
  }

  /**
   * Start a single file download
   */
  downloadFile(manuscriptId: string, fileName: string, fileType: 'pdf' | 'xml' = 'pdf'): Observable<DownloadProgress> {
    const downloadId = this.generateDownloadId();
    const request: DownloadRequest = {
      manuscriptId,
      fileName,
      fileType,
      priority: 1
    };

    // Add to queue
    this.addToQueue(request, downloadId);
    
    // Process queue
    this.processQueue();

    // Return observable for this specific download
    return this.downloads$.pipe(
      map(downloads => downloads.find(d => d.id === downloadId)),
      map(download => download!)
    );
  }

  /**
   * Start multiple file downloads (batch download)
   */
  downloadMultipleFiles(requests: DownloadRequest[]): Observable<DownloadProgress[]> {
    const downloadIds: string[] = [];

    requests.forEach(request => {
      const downloadId = this.generateDownloadId();
      downloadIds.push(downloadId);
      this.addToQueue(request, downloadId);
    });

    this.processQueue();

    // Return observable for these specific downloads
    return this.downloads$.pipe(
      map(downloads => downloads.filter(d => downloadIds.includes(d.id)))
    );
  }

  /**
   * Cancel a download
   */
  cancelDownload(downloadId: string): void {
    const download = this.activeDownloads.get(downloadId);
    if (download) {
      download.status = 'cancelled';
      download.endTime = Date.now();
      this.activeDownloads.delete(downloadId);
      this.currentDownloads--;
      this.updateDownloadsSubject();
      this.processQueue(); // Process next in queue
    }

    // Remove from queue if it's there
    this.downloadQueue = this.downloadQueue.filter(req => 
      this.getRequestId(req) !== downloadId
    );
    this.queueSubject.next([...this.downloadQueue]);
  }

  /**
   * Cancel all downloads
   */
  cancelAllDownloads(): void {
    // Cancel active downloads
    this.activeDownloads.forEach((download, id) => {
      this.cancelDownload(id);
    });

    // Clear queue
    this.downloadQueue = [];
    this.queueSubject.next([]);
  }

  /**
   * Retry a failed download
   */
  retryDownload(downloadId: string): void {
    const downloads = this.downloadsSubject.value;
    const failedDownload = downloads.find(d => d.id === downloadId && d.status === 'failed');
    
    if (failedDownload) {
      const request: DownloadRequest = {
        manuscriptId: downloadId.split('-')[0], // Extract manuscript ID
        fileName: failedDownload.fileName,
        fileType: failedDownload.fileType
      };
      
      this.addToQueue(request, downloadId);
      this.processQueue();
    }
  }

  /**
   * Get download history
   */
  getDownloadHistory(): DownloadHistory[] {
    return [...this.downloadHistory];
  }

  /**
   * Clear download history
   */
  clearDownloadHistory(): void {
    this.downloadHistory = [];
    this.historySubject.next([]);
    this.saveDownloadHistory();
  }

  /**
   * Get active downloads
   */
  getActiveDownloads(): DownloadProgress[] {
    return Array.from(this.activeDownloads.values());
  }

  /**
   * Get download statistics
   */
  getDownloadStatistics(): {
    totalDownloads: number;
    completedDownloads: number;
    failedDownloads: number;
    totalDataDownloaded: number; // bytes
    averageDownloadSpeed: number; // bytes per second
  } {
    const completed = this.downloadHistory.filter(h => h.status === 'completed');
    const failed = this.downloadHistory.filter(h => h.status === 'failed');
    
    const totalDataDownloaded = completed.reduce((sum, h) => sum + h.fileSize, 0);
    const totalDuration = completed.reduce((sum, h) => sum + h.duration, 0);
    const averageDownloadSpeed = totalDuration > 0 ? (totalDataDownloaded / (totalDuration / 1000)) : 0;

    return {
      totalDownloads: this.downloadHistory.length,
      completedDownloads: completed.length,
      failedDownloads: failed.length,
      totalDataDownloaded,
      averageDownloadSpeed
    };
  }

  /**
   * Private Methods
   */

  private addToQueue(request: DownloadRequest, downloadId: string): void {
    // Create download progress entry
    const downloadProgress: DownloadProgress = {
      id: downloadId,
      fileName: request.fileName,
      fileType: request.fileType,
      progress: 0,
      status: 'pending',
      downloadedBytes: 0,
      totalBytes: 0,
      speed: 0,
      timeRemaining: 0,
      startTime: Date.now()
    };

    this.activeDownloads.set(downloadId, downloadProgress);
    
    // Add to queue
    this.downloadQueue.push(request);
    this.downloadQueue.sort((a, b) => (b.priority || 0) - (a.priority || 0));
    
    this.updateDownloadsSubject();
    this.queueSubject.next([...this.downloadQueue]);
  }

  private processQueue(): void {
    while (this.currentDownloads < this.maxConcurrentDownloads && this.downloadQueue.length > 0) {
      const request = this.downloadQueue.shift()!;
      this.startDownload(request);
    }
    this.queueSubject.next([...this.downloadQueue]);
  }

  private startDownload(request: DownloadRequest): void {
    this.currentDownloads++;
    const downloadId = this.getRequestId(request);
    const download = this.activeDownloads.get(downloadId);
    
    if (!download) return;

    download.status = 'downloading';
    download.startTime = Date.now();
    this.updateDownloadsSubject();

    // Get download URL from manuscript service
    this.manuscriptService.getDownloadUrl(request.manuscriptId, request.fileType)
      .pipe(
        catchError(error => {
          this.handleDownloadError(downloadId, error);
          return throwError(error);
        })
      )
      .subscribe({
        next: (response: DownloadUrlResponse) => {
          this.downloadFromUrl(downloadId, response.download_url, response.file_name);
        },
        error: (error) => {
          this.handleDownloadError(downloadId, error);
        }
      });
  }

  private downloadFromUrl(downloadId: string, url: string, fileName: string): void {
    const download = this.activeDownloads.get(downloadId);
    if (!download) return;

    const startTime = Date.now();
    let lastProgressTime = startTime;
    let lastDownloadedBytes = 0;

    this.http.get(url, {
      observe: 'events',
      reportProgress: true,
      responseType: 'blob'
    }).pipe(
      catchError(error => {
        this.handleDownloadError(downloadId, error);
        return throwError(error);
      })
    ).subscribe({
      next: (event) => {
        if (event.type === HttpEventType.DownloadProgress && event.total) {
          const now = Date.now();
          const timeDiff = (now - lastProgressTime) / 1000; // seconds
          const bytesDiff = event.loaded - lastDownloadedBytes;
          
          // Calculate speed (bytes per second)
          const speed = timeDiff > 0 ? bytesDiff / timeDiff : 0;
          
          // Calculate time remaining
          const remainingBytes = event.total - event.loaded;
          const timeRemaining = speed > 0 ? remainingBytes / speed : 0;

          download.progress = Math.round((event.loaded / event.total) * 100);
          download.downloadedBytes = event.loaded;
          download.totalBytes = event.total;
          download.speed = speed;
          download.timeRemaining = timeRemaining;

          // Update tracking variables
          lastProgressTime = now;
          lastDownloadedBytes = event.loaded;

          this.updateDownloadsSubject();
        } else if (event.type === HttpEventType.Response) {
          // Download completed
          this.handleDownloadComplete(downloadId, event.body as Blob, fileName);
        }
      },
      error: (error) => {
        this.handleDownloadError(downloadId, error);
      }
    });
  }

  private handleDownloadComplete(downloadId: string, blob: Blob, fileName: string): void {
    const download = this.activeDownloads.get(downloadId);
    if (!download) return;

    download.status = 'completed';
    download.progress = 100;
    download.endTime = Date.now();
    
    // Trigger browser download
    this.triggerBrowserDownload(blob, fileName);
    
    // Add to history
    const historyEntry: DownloadHistory = {
      id: downloadId,
      manuscriptId: downloadId.split('-')[0],
      fileName: download.fileName,
      fileType: download.fileType,
      downloadDate: new Date(),
      fileSize: download.totalBytes,
      duration: download.endTime - download.startTime,
      status: 'completed'
    };
    
    this.downloadHistory.unshift(historyEntry);
    this.historySubject.next([...this.downloadHistory]);
    this.saveDownloadHistory();

    // Emit completion event
    this.downloadCompleteSubject.next(download);
    
    // Clean up and process next
    this.activeDownloads.delete(downloadId);
    this.currentDownloads--;
    this.updateDownloadsSubject();
    this.processQueue();

    this.errorHandler.showSuccess(`Download completed: ${fileName}`);
  }

  private handleDownloadError(downloadId: string, error: any): void {
    const download = this.activeDownloads.get(downloadId);
    if (!download) return;

    download.status = 'failed';
    download.error = error.message || 'Download failed';
    download.endTime = Date.now();

    // Add to history
    const historyEntry: DownloadHistory = {
      id: downloadId,
      manuscriptId: downloadId.split('-')[0],
      fileName: download.fileName,
      fileType: download.fileType,
      downloadDate: new Date(),
      fileSize: download.totalBytes,
      duration: download.endTime! - download.startTime,
      status: 'failed',
      error: download.error
    };
    
    this.downloadHistory.unshift(historyEntry);
    this.historySubject.next([...this.downloadHistory]);
    this.saveDownloadHistory();

    this.currentDownloads--;
    this.updateDownloadsSubject();
    this.processQueue();

    this.errorHandler.showError(`Download failed: ${download.fileName} - ${download.error}`);
  }

  private triggerBrowserDownload(blob: Blob, fileName: string): void {
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  }

  private updateDownloadsSubject(): void {
    this.downloadsSubject.next(Array.from(this.activeDownloads.values()));
  }

  private generateDownloadId(): string {
    return `download-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  private getRequestId(request: DownloadRequest): string {
    return `${request.manuscriptId}-${request.fileType}-${Date.now()}`;
  }

  private loadDownloadHistory(): void {
    try {
      const stored = localStorage.getItem('manuscript-download-history');
      if (stored) {
        this.downloadHistory = JSON.parse(stored).map((h: any) => ({
          ...h,
          downloadDate: new Date(h.downloadDate)
        }));
        this.historySubject.next([...this.downloadHistory]);
      }
    } catch (error) {
      console.error('Failed to load download history:', error);
    }
  }

  private saveDownloadHistory(): void {
    try {
      // Keep only last 100 downloads
      const historyToSave = this.downloadHistory.slice(0, 100);
      localStorage.setItem('manuscript-download-history', JSON.stringify(historyToSave));
    } catch (error) {
      console.error('Failed to save download history:', error);
    }
  }
}
