import { Component, Input, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subscription } from 'rxjs';
import { RealtimeService, ManuscriptStatusUpdate } from '../../services/realtime.service';

export interface ProcessingStep {
  id: string;
  name: string;
  description: string;
  status: 'pending' | 'in-progress' | 'completed' | 'failed';
  progress?: number;
  startTime?: Date;
  endTime?: Date;
  error?: string;
}

@Component({
  selector: 'app-progress-tracker',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
      <!-- Header -->
      <div class="flex items-center justify-between mb-6">
        <div>
          <h3 class="text-lg font-medium text-gray-900">Processing Progress</h3>
          <p class="text-sm text-gray-500 mt-1">
            {{ manuscriptName || 'Document' }} • {{ getOverallStatusText() }}
          </p>
        </div>
        
        <!-- Overall Progress -->
        <div class="text-right">
          <div class="text-2xl font-bold" [ngClass]="getOverallProgressClass()">
            {{ getOverallProgress() }}%
          </div>
          <div class="text-xs text-gray-500">Complete</div>
        </div>
      </div>

      <!-- Overall Progress Bar -->
      <div class="mb-6">
        <div class="flex items-center justify-between text-sm text-gray-600 mb-2">
          <span>Overall Progress</span>
          <span>{{ getOverallProgress() }}%</span>
        </div>
        <div class="w-full bg-gray-200 rounded-full h-2">
          <div 
            class="h-2 rounded-full transition-all duration-500 ease-out"
            [ngClass]="getOverallProgressBarClass()"
            [style.width.%]="getOverallProgress()"
          ></div>
        </div>
      </div>

      <!-- Processing Steps -->
      <div class="space-y-4">
        <div 
          *ngFor="let step of processingSteps; let i = index"
          class="flex items-start space-x-4"
        >
          <!-- Step Icon -->
          <div class="flex-shrink-0 mt-1">
            <div 
              class="w-8 h-8 rounded-full flex items-center justify-center border-2 transition-all duration-300"
              [ngClass]="getStepIconClass(step)"
            >
              <!-- Pending -->
              <div *ngIf="step.status === 'pending'" class="w-3 h-3 rounded-full bg-gray-300"></div>
              
              <!-- In Progress -->
              <div *ngIf="step.status === 'in-progress'" class="w-4 h-4">
                <svg class="animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              </div>
              
              <!-- Completed -->
              <div *ngIf="step.status === 'completed'" class="w-4 h-4">
                <svg class="text-green-600" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
              </div>
              
              <!-- Failed -->
              <div *ngIf="step.status === 'failed'" class="w-4 h-4">
                <svg class="text-red-600" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M6 18L18 6M6 6l12 12"/>
                </svg>
              </div>
            </div>
          </div>

          <!-- Step Content -->
          <div class="flex-1 min-w-0">
            <div class="flex items-center justify-between">
              <h4 class="text-sm font-medium text-gray-900">{{ step.name }}</h4>
              <span 
                class="text-xs px-2 py-1 rounded-full font-medium"
                [ngClass]="getStepStatusClass(step.status)"
              >
                {{ getStepStatusText(step.status) }}
              </span>
            </div>
            
            <p class="text-sm text-gray-600 mt-1">{{ step.description }}</p>
            
            <!-- Step Progress Bar -->
            <div *ngIf="step.status === 'in-progress' && step.progress !== undefined" class="mt-2">
              <div class="flex items-center justify-between text-xs text-gray-500 mb-1">
                <span>Step Progress</span>
                <span>{{ step.progress }}%</span>
              </div>
              <div class="w-full bg-gray-200 rounded-full h-1">
                <div 
                  class="bg-blue-500 h-1 rounded-full transition-all duration-300"
                  [style.width.%]="step.progress"
                ></div>
              </div>
            </div>
            
            <!-- Error Message -->
            <div *ngIf="step.status === 'failed' && step.error" class="mt-2">
              <div class="bg-red-50 border border-red-200 rounded-md p-2">
                <p class="text-xs text-red-700">{{ step.error }}</p>
              </div>
            </div>
            
            <!-- Timing Information -->
            <div *ngIf="step.startTime || step.endTime" class="mt-2 text-xs text-gray-500">
              <span *ngIf="step.startTime">Started: {{ step.startTime | date:'short' }}</span>
              <span *ngIf="step.startTime && step.endTime" class="mx-2">•</span>
              <span *ngIf="step.endTime">Completed: {{ step.endTime | date:'short' }}</span>
              <span *ngIf="step.startTime && step.endTime" class="ml-2">
                ({{ getDuration(step.startTime, step.endTime) }})
              </span>
            </div>
          </div>

          <!-- Connector Line -->
          <div 
            *ngIf="i < processingSteps.length - 1" 
            class="absolute left-8 mt-8 w-0.5 h-6 bg-gray-200"
            [ngClass]="{'bg-blue-300': isStepConnected(i)}"
          ></div>
        </div>
      </div>

      <!-- Action Buttons -->
      <div *ngIf="showActions" class="mt-6 flex items-center justify-between pt-4 border-t border-gray-200">
        <div class="flex space-x-3">
          <button
            *ngIf="canRetry"
            type="button"
            (click)="onRetry()"
            class="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
          >
            <svg class="-ml-0.5 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Retry Processing
          </button>
          
          <button
            *ngIf="canCancel"
            type="button"
            (click)="onCancel()"
            class="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
          >
            <svg class="-ml-0.5 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
            Cancel Processing
          </button>
        </div>
        
        <button
          *ngIf="isCompleted"
          type="button"
          (click)="onDownload()"
          class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
        >
          <svg class="-ml-0.5 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-4-4m4 4l4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Download Result
        </button>
      </div>
    </div>
  `,
  styles: [`
    .absolute {
      position: absolute;
    }
  `]
})
export class ProgressTrackerComponent implements OnInit, OnDestroy {
  @Input() manuscriptId?: string;
  @Input() manuscriptName?: string;
  @Input() showActions = true;
  
  processingSteps: ProcessingStep[] = [
    {
      id: 'upload',
      name: 'File Upload',
      description: 'Uploading file to processing server',
      status: 'completed'
    },
    {
      id: 'validation',
      name: 'File Validation',
      description: 'Validating file format and structure',
      status: 'completed'
    },
    {
      id: 'extraction',
      name: 'Content Extraction',
      description: 'Extracting text and formatting from PDF',
      status: 'in-progress',
      progress: 65
    },
    {
      id: 'conversion',
      name: 'Format Conversion',
      description: 'Converting to Word document format',
      status: 'pending'
    },
    {
      id: 'optimization',
      name: 'Document Optimization',
      description: 'Optimizing layout and formatting',
      status: 'pending'
    },
    {
      id: 'finalization',
      name: 'Finalization',
      description: 'Preparing final document for download',
      status: 'pending'
    }
  ];

  private subscriptions: Subscription[] = [];

  constructor(private realtimeService: RealtimeService) {}

  ngOnInit(): void {
    this.subscribeToManuscriptUpdates();
    this.simulateProgress();
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(sub => sub.unsubscribe());
  }

  private subscribeToManuscriptUpdates(): void {
    if (this.manuscriptId) {
      this.subscriptions.push(
        this.realtimeService.manuscriptUpdates.subscribe(update => {
          if (update.manuscript_id === this.manuscriptId) {
            this.updateProgressFromStatus(update);
          }
        })
      );
    }
  }

  private updateProgressFromStatus(update: ManuscriptStatusUpdate): void {
    switch (update.status) {
      case 'processing':
        this.updateProcessingProgress(update.progress || 0);
        break;
      case 'completed':
        this.markAllStepsCompleted();
        break;
      case 'failed':
        this.markCurrentStepFailed(update.error_message);
        break;
    }
  }

  private updateProcessingProgress(overallProgress: number): void {
    // Distribute progress across steps
    const stepsCount = this.processingSteps.length;
    const progressPerStep = 100 / stepsCount;
    
    this.processingSteps.forEach((step, index) => {
      const stepStartProgress = index * progressPerStep;
      const stepEndProgress = (index + 1) * progressPerStep;
      
      if (overallProgress >= stepEndProgress) {
        step.status = 'completed';
        step.progress = 100;
        step.endTime = new Date();
      } else if (overallProgress > stepStartProgress) {
        step.status = 'in-progress';
        step.progress = Math.round(((overallProgress - stepStartProgress) / progressPerStep) * 100);
        if (!step.startTime) {
          step.startTime = new Date();
        }
      } else {
        step.status = 'pending';
      }
    });
  }

  private markAllStepsCompleted(): void {
    this.processingSteps.forEach(step => {
      step.status = 'completed';
      step.progress = 100;
      if (!step.endTime) {
        step.endTime = new Date();
      }
    });
  }

  private markCurrentStepFailed(error?: string): void {
    const currentStep = this.processingSteps.find(step => step.status === 'in-progress');
    if (currentStep) {
      currentStep.status = 'failed';
      currentStep.error = error || 'Processing failed';
      currentStep.endTime = new Date();
    }
  }

  // Simulate progress for demonstration
  private simulateProgress(): void {
    if (!this.manuscriptId) {
      // Simulate progress updates
      let currentProgress = 0;
      const interval = setInterval(() => {
        currentProgress += Math.random() * 15;
        if (currentProgress >= 100) {
          currentProgress = 100;
          clearInterval(interval);
        }
        this.updateProcessingProgress(currentProgress);
      }, 2000);

      // Clean up on destroy
      this.subscriptions.push({
        unsubscribe: () => clearInterval(interval)
      } as Subscription);
    }
  }

  getOverallProgress(): number {
    const completedSteps = this.processingSteps.filter(step => step.status === 'completed').length;
    const inProgressSteps = this.processingSteps.filter(step => step.status === 'in-progress');
    
    let progress = (completedSteps / this.processingSteps.length) * 100;
    
    if (inProgressSteps.length > 0) {
      const inProgressStep = inProgressSteps[0];
      const stepProgress = (inProgressStep.progress || 0) / 100;
      progress += (stepProgress / this.processingSteps.length) * 100;
    }
    
    return Math.round(progress);
  }

  getOverallStatusText(): string {
    const failedSteps = this.processingSteps.filter(step => step.status === 'failed');
    if (failedSteps.length > 0) {
      return 'Processing Failed';
    }
    
    const completedSteps = this.processingSteps.filter(step => step.status === 'completed');
    if (completedSteps.length === this.processingSteps.length) {
      return 'Processing Complete';
    }
    
    const inProgressSteps = this.processingSteps.filter(step => step.status === 'in-progress');
    if (inProgressSteps.length > 0) {
      return `Processing: ${inProgressSteps[0].name}`;
    }
    
    return 'Waiting to Start';
  }

  getOverallProgressClass(): string {
    const progress = this.getOverallProgress();
    if (progress === 100) {
      return 'text-green-600';
    } else if (progress > 0) {
      return 'text-blue-600';
    } else {
      return 'text-gray-500';
    }
  }

  getOverallProgressBarClass(): string {
    const progress = this.getOverallProgress();
    const hasFailed = this.processingSteps.some(step => step.status === 'failed');
    
    if (hasFailed) {
      return 'bg-red-500';
    } else if (progress === 100) {
      return 'bg-green-500';
    } else {
      return 'bg-blue-500';
    }
  }

  getStepIconClass(step: ProcessingStep): string {
    switch (step.status) {
      case 'completed':
        return 'border-green-500 bg-green-50';
      case 'in-progress':
        return 'border-blue-500 bg-blue-50';
      case 'failed':
        return 'border-red-500 bg-red-50';
      default:
        return 'border-gray-300 bg-gray-50';
    }
  }

  getStepStatusClass(status: string): string {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'in-progress':
        return 'bg-blue-100 text-blue-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  }

  getStepStatusText(status: string): string {
    switch (status) {
      case 'completed':
        return 'Completed';
      case 'in-progress':
        return 'In Progress';
      case 'failed':
        return 'Failed';
      default:
        return 'Pending';
    }
  }

  isStepConnected(index: number): boolean {
    const currentStep = this.processingSteps[index];
    const nextStep = this.processingSteps[index + 1];
    
    return currentStep.status === 'completed' || 
           (currentStep.status === 'in-progress' && nextStep?.status !== 'pending');
  }

  getDuration(startTime: Date, endTime: Date): string {
    const durationMs = endTime.getTime() - startTime.getTime();
    const seconds = Math.floor(durationMs / 1000);
    
    if (seconds < 60) {
      return `${seconds}s`;
    } else if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60);
      return `${minutes}m ${seconds % 60}s`;
    } else {
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      return `${hours}h ${minutes}m`;
    }
  }

  get canRetry(): boolean {
    return this.processingSteps.some(step => step.status === 'failed');
  }

  get canCancel(): boolean {
    return this.processingSteps.some(step => step.status === 'in-progress');
  }

  get isCompleted(): boolean {
    return this.processingSteps.every(step => step.status === 'completed');
  }

  onRetry(): void {
    // Reset failed steps to pending
    this.processingSteps.forEach(step => {
      if (step.status === 'failed') {
        step.status = 'pending';
        step.error = undefined;
        step.startTime = undefined;
        step.endTime = undefined;
        step.progress = undefined;
      }
    });
    
    // Restart simulation
    this.simulateProgress();
  }

  onCancel(): void {
    // Mark in-progress steps as pending
    this.processingSteps.forEach(step => {
      if (step.status === 'in-progress') {
        step.status = 'pending';
        step.progress = undefined;
        step.startTime = undefined;
      }
    });
  }

  onDownload(): void {
    // Emit download event or handle download logic
    console.log('Download requested for manuscript:', this.manuscriptId);
  }
}
