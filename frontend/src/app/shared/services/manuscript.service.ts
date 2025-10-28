import { Injectable } from '@angular/core';
import { HttpClient, HttpEventType } from '@angular/common/http';
import { Observable, map, switchMap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { APIResponse } from './auth.service';

export interface Manuscript {
  id: string;
  user_id: string;
  file_name: string;
  upload_date: string;
  status: 'pending' | 'processing' | 'complete' | 'failed';
  pdf_s3_key: string;
  docx_s3_key?: string;
  xml_s3_key?: string;
  file_size?: number;
  content_type: string;
  processing_started_at?: string;
  processing_completed_at?: string;
  error_message?: string;
  retry_count: number;
}

export interface ManuscriptResponse {
  id: string;
  file_name: string;
  status: 'pending' | 'processing' | 'complete' | 'failed';
  upload_date: string;
  processing_completed_at?: string;
  error_message?: string;
}

export interface ManuscriptListResponse {
  manuscripts: ManuscriptResponse[];
  total: number;
  page: number;
  size: number;
}

export interface UploadUrlRequest {
  file_name: string;
  file_size?: number;
  content_type: string;
}

export interface UploadUrlResponse {
  upload_url: string;
  manuscript_id: string;
  expires_in: number;
}

export interface DownloadUrlResponse {
  download_url: string;
  file_name: string;
  expires_in: number;
}

export interface ManuscriptStatistics {
  total: number;
  pending: number;
  processing: number;
  completed: number;
  failed: number;
}

export interface UploadProgress {
  type: 'progress' | 'complete' | 'error';
  progress?: number;
  error?: string;
}

@Injectable({
  providedIn: 'root'
})
export class ManuscriptService {
  private readonly apiUrl = `${environment.apiUrl}/api/v1`;

  constructor(private http: HttpClient) {}

  getManuscripts(page: number = 1, limit: number = 50, status?: string): Observable<ManuscriptListResponse> {
    let params = `?skip=${(page - 1) * limit}&limit=${limit}`;
    if (status) {
      params += `&status=${status}`;
    }
    
    return this.http.get<APIResponse<ManuscriptListResponse>>(`${this.apiUrl}/manuscripts/${params}`)
      .pipe(
        map(response => response.data)
      );
  }

  getManuscript(id: string): Observable<Manuscript> {
    return this.http.get<APIResponse<Manuscript>>(`${this.apiUrl}/manuscripts/${id}`)
      .pipe(
        map(response => response.data)
      );
  }

  uploadManuscript(file: File): Observable<UploadProgress> {
    // First get upload URL
    return this.getUploadUrl(file).pipe(
      switchMap(uploadResponse => {
        // Upload file to S3 and return progress
        return this.uploadToS3(uploadResponse.upload_url, file).pipe(
          switchMap((progress: UploadProgress) => {
            if (progress.type === 'complete') {
              // Confirm upload with backend
              return this.confirmUpload(uploadResponse.manuscript_id).pipe(
                map(() => ({ ...progress, manuscript_id: uploadResponse.manuscript_id }))
              );
            }
            return [progress];
          })
        );
      })
    );
  }

  getUploadUrl(file: File): Observable<UploadUrlResponse> {
    const request: UploadUrlRequest = {
      file_name: file.name,
      file_size: file.size,
      content_type: file.type || 'application/pdf'
    };
    
    return this.http.post<APIResponse<UploadUrlResponse>>(`${this.apiUrl}/manuscripts/upload-url`, request)
      .pipe(
        map(response => response.data)
      );
  }

  confirmUpload(manuscriptId: string): Observable<void> {
    return this.http.post<APIResponse<void>>(`${this.apiUrl}/manuscripts/${manuscriptId}/confirm-upload`, {})
      .pipe(
        map(response => response.data)
      );
  }

  getDownloadUrl(manuscriptId: string, fileType: 'pdf' | 'xml' = 'pdf'): Observable<DownloadUrlResponse> {
    return this.http.get<APIResponse<DownloadUrlResponse>>(`${this.apiUrl}/manuscripts/${manuscriptId}/download-url?file_type=${fileType}`)
      .pipe(
        map(response => response.data)
      );
  }

  deleteManuscript(manuscriptId: string): Observable<void> {
    return this.http.delete<APIResponse<void>>(`${this.apiUrl}/manuscripts/${manuscriptId}`)
      .pipe(
        map(response => response.data)
      );
  }

  getStatistics(): Observable<ManuscriptStatistics> {
    return this.http.get<APIResponse<ManuscriptStatistics>>(`${this.apiUrl}/manuscripts/statistics/overview`)
      .pipe(
        map(response => response.data)
      );
  }

  uploadToS3(uploadUrl: string, file: File): Observable<UploadProgress> {
    // Use XMLHttpRequest directly for better S3 compatibility
    return new Observable<UploadProgress>(observer => {
      const xhr = new XMLHttpRequest();

      // Ensure large files have ample time to upload
      xhr.timeout = 15 * 60 * 1000; // 15 minutes
      xhr.withCredentials = false; // S3 presigned URLs should not send credentials
      
      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          const progress = Math.round(100 * event.loaded / event.total);
          observer.next({ type: 'progress' as const, progress });
        }
      });
      
      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          observer.next({ type: 'complete' as const });
          observer.complete();
        } else {
          observer.error(new Error(`Upload failed with status ${xhr.status}: ${xhr.statusText}`));
        }
      });
      
      xhr.addEventListener('timeout', () => {
        observer.error(new Error('Upload timed out. Please try again.'));
      });

      xhr.addEventListener('abort', () => {
        observer.error(new Error('Upload was aborted.'));
      });

      xhr.addEventListener('error', () => {
        observer.error(new Error('Upload failed due to network error'));
      });

      xhr.addEventListener('error', () => {
        observer.error(new Error('Upload failed due to network error'));
      });
      
      xhr.open('PUT', uploadUrl);
      // Set Content-Type to match what backend expects
      xhr.setRequestHeader('Content-Type', file.type || 'application/pdf');
      xhr.send(file);
      
      // Return cleanup function
      return () => {
        xhr.abort();
      };
    });
  }
}
