import { Component, OnInit, OnDestroy, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subscription, interval } from 'rxjs';
import { AdminService, UserStatistics } from '../../services/admin.service';
import { ErrorHandlerService } from '../../services/error-handler.service';

export interface ChartDataPoint {
  label: string;
  value: number;
  color?: string;
}

export interface TimeSeriesDataPoint {
  timestamp: string;
  value: number;
  label?: string;
}

export interface AnalyticsMetric {
  id: string;
  title: string;
  value: number;
  change: number;
  changeType: 'increase' | 'decrease' | 'neutral';
  format: 'number' | 'percentage' | 'currency' | 'time';
  icon: string;
  color: string;
}

@Component({
  selector: 'app-analytics-dashboard',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="space-y-6">
      <!-- Key Metrics -->
      <div class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <div 
          *ngFor="let metric of keyMetrics"
          class="bg-white overflow-hidden shadow rounded-lg"
        >
          <div class="p-5">
            <div class="flex items-center">
              <div class="flex-shrink-0">
                <div 
                  class="w-8 h-8 rounded-md flex items-center justify-center"
                  [style.background-color]="metric.color + '20'"
                >
                  <div 
                    [innerHTML]="metric.icon" 
                    class="h-5 w-5"
                    [style.color]="metric.color"
                  ></div>
                </div>
              </div>
              <div class="ml-5 w-0 flex-1">
                <dl>
                  <dt class="text-sm font-medium text-gray-500 truncate">{{ metric.title }}</dt>
                  <dd class="text-lg font-medium text-gray-900">{{ formatMetricValue(metric) }}</dd>
                </dl>
              </div>
            </div>
            
            <!-- Change Indicator -->
            <div class="mt-4 flex items-center">
              <div 
                class="flex items-center text-sm"
                [ngClass]="getChangeClass(metric.changeType)"
              >
                <svg 
                  *ngIf="metric.changeType === 'increase'" 
                  class="w-4 h-4 mr-1" 
                  fill="currentColor" 
                  viewBox="0 0 24 24"
                >
                  <path d="M7 14l5-5 5 5H7z"/>
                </svg>
                <svg 
                  *ngIf="metric.changeType === 'decrease'" 
                  class="w-4 h-4 mr-1" 
                  fill="currentColor" 
                  viewBox="0 0 24 24"
                >
                  <path d="M7 10l5 5 5-5H7z"/>
                </svg>
                <span class="font-medium">{{ getAbsoluteValue(metric.change) }}%</span>
              </div>
              <span class="ml-2 text-sm text-gray-500">vs last period</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Charts Row -->
      <div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <!-- Processing Status Chart -->
        <div class="bg-white shadow rounded-lg p-6">
          <h3 class="text-lg font-medium text-gray-900 mb-4">Processing Status Distribution</h3>
          <div class="flex items-center justify-center">
            <div class="relative w-48 h-48">
              <!-- Donut Chart -->
              <svg class="w-48 h-48 transform -rotate-90" viewBox="0 0 100 100">
                <circle
                  cx="50"
                  cy="50"
                  r="40"
                  stroke="#f3f4f6"
                  stroke-width="8"
                  fill="none"
                />
                <circle
                  *ngFor="let segment of donutChartSegments; let i = index"
                  cx="50"
                  cy="50"
                  r="40"
                  [attr.stroke]="segment.color"
                  stroke-width="8"
                  fill="none"
                  [attr.stroke-dasharray]="segment.dashArray"
                  [attr.stroke-dashoffset]="segment.dashOffset"
                  class="transition-all duration-500"
                />
              </svg>
              
              <!-- Center Text -->
              <div class="absolute inset-0 flex items-center justify-center">
                <div class="text-center">
                  <div class="text-2xl font-bold text-gray-900">{{ getTotalManuscripts() }}</div>
                  <div class="text-sm text-gray-500">Total</div>
                </div>
              </div>
            </div>
          </div>
          
          <!-- Legend -->
          <div class="mt-4 grid grid-cols-2 gap-2">
            <div 
              *ngFor="let item of processingStatusData"
              class="flex items-center"
            >
              <div 
                class="w-3 h-3 rounded-full mr-2"
                [style.background-color]="item.color"
              ></div>
              <span class="text-sm text-gray-600">{{ item.label }}: {{ item.value }}</span>
            </div>
          </div>
        </div>

        <!-- Activity Timeline -->
        <div class="bg-white shadow rounded-lg p-6">
          <h3 class="text-lg font-medium text-gray-900 mb-4">Activity Timeline (Last 7 Days)</h3>
          <div class="h-48">
            <!-- Simple Line Chart -->
            <div class="relative h-full">
              <svg class="w-full h-full" viewBox="0 0 400 200">
                <!-- Grid Lines -->
                <defs>
                  <pattern id="grid" width="40" height="20" patternUnits="userSpaceOnUse">
                    <path d="M 40 0 L 0 0 0 20" fill="none" stroke="#f3f4f6" stroke-width="1"/>
                  </pattern>
                </defs>
                <rect width="100%" height="100%" fill="url(#grid)" />
                
                <!-- Chart Line -->
                <polyline
                  [attr.points]="getTimelineChartPoints()"
                  fill="none"
                  stroke="#3b82f6"
                  stroke-width="2"
                  class="transition-all duration-500"
                />
                
                <!-- Data Points -->
                <circle
                  *ngFor="let point of timelineChartPoints"
                  [attr.cx]="point.x"
                  [attr.cy]="point.y"
                  r="4"
                  fill="#3b82f6"
                  class="hover:r-6 transition-all duration-200 cursor-pointer"
                  [attr.data-value]="point.value"
                />
              </svg>
              
              <!-- Y-Axis Labels -->
              <div class="absolute left-0 top-0 h-full flex flex-col justify-between text-xs text-gray-500 -ml-8">
                <span>{{ getMaxTimelineValue() }}</span>
                <span>{{ getFloorValue(getMaxTimelineValue() / 2) }}</span>
                <span>0</span>
              </div>
              
              <!-- X-Axis Labels -->
              <div class="absolute bottom-0 left-0 w-full flex justify-between text-xs text-gray-500 -mb-6">
                <span *ngFor="let point of timelineData">{{ formatTimelineDate(point.timestamp) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Detailed Statistics -->
      <div class="bg-white shadow rounded-lg">
        <div class="px-6 py-4 border-b border-gray-200">
          <h3 class="text-lg font-medium text-gray-900">Detailed Statistics</h3>
        </div>
        <div class="p-6">
          <div class="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            <!-- User Statistics -->
            <div>
              <h4 class="text-sm font-medium text-gray-900 mb-3">User Metrics</h4>
              <div class="space-y-2">
                <div class="flex justify-between text-sm">
                  <span class="text-gray-600">Total Users</span>
                  <span class="font-medium">{{ statistics?.total_users || 0 }}</span>
                </div>
                <div class="flex justify-between text-sm">
                  <span class="text-gray-600">Active Users</span>
                  <span class="font-medium text-green-600">{{ statistics?.active_users || 0 }}</span>
                </div>
                <div class="flex justify-between text-sm">
                  <span class="text-gray-600">Admin Users</span>
                  <span class="font-medium text-purple-600">{{ statistics?.admin_users || 0 }}</span>
                </div>
                <div class="flex justify-between text-sm">
                  <span class="text-gray-600">Recent Registrations</span>
                  <span class="font-medium text-blue-600">{{ statistics?.recent_registrations || 0 }}</span>
                </div>
              </div>
            </div>

            <!-- Processing Statistics -->
            <div>
              <h4 class="text-sm font-medium text-gray-900 mb-3">Processing Metrics</h4>
              <div class="space-y-2">
                <div class="flex justify-between text-sm">
                  <span class="text-gray-600">Total Manuscripts</span>
                  <span class="font-medium">{{ statistics?.total_manuscripts || 0 }}</span>
                </div>
                <div class="flex justify-between text-sm">
                  <span class="text-gray-600">Processing</span>
                  <span class="font-medium text-yellow-600">{{ statistics?.processing_manuscripts || 0 }}</span>
                </div>
                <div class="flex justify-between text-sm">
                  <span class="text-gray-600">Completed</span>
                  <span class="font-medium text-green-600">{{ statistics?.completed_manuscripts || 0 }}</span>
                </div>
                <div class="flex justify-between text-sm">
                  <span class="text-gray-600">Failed</span>
                  <span class="font-medium text-red-600">{{ statistics?.failed_manuscripts || 0 }}</span>
                </div>
              </div>
            </div>

            <!-- Performance Statistics -->
            <div>
              <h4 class="text-sm font-medium text-gray-900 mb-3">Performance Metrics</h4>
              <div class="space-y-2">
                <div class="flex justify-between text-sm">
                  <span class="text-gray-600">Avg Processing Time</span>
                  <span class="font-medium">{{ statistics?.avg_processing_time_minutes || 0 }}min</span>
                </div>
                <div class="flex justify-between text-sm">
                  <span class="text-gray-600">Storage Used</span>
                  <span class="font-medium">{{ formatStorage(statistics?.storage_used_mb || 0) }}</span>
                </div>
                <div class="flex justify-between text-sm">
                  <span class="text-gray-600">Today's Manuscripts</span>
                  <span class="font-medium text-blue-600">{{ statistics?.manuscripts_today || 0 }}</span>
                </div>
                <div class="flex justify-between text-sm">
                  <span class="text-gray-600">This Week</span>
                  <span class="font-medium text-indigo-600">{{ statistics?.manuscripts_this_week || 0 }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Real-time Updates -->
      <div *ngIf="showRealTimeUpdates" class="bg-white shadow rounded-lg p-6">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-medium text-gray-900">Real-time Activity</h3>
          <div class="flex items-center text-sm text-gray-500">
            <div class="w-2 h-2 bg-green-400 rounded-full mr-2 animate-pulse"></div>
            Live
          </div>
        </div>
        
        <div class="space-y-3">
          <div 
            *ngFor="let activity of recentActivities"
            class="flex items-center justify-between py-2 border-b border-gray-100 last:border-b-0"
          >
            <div class="flex items-center">
              <div 
                class="w-2 h-2 rounded-full mr-3"
                [ngClass]="getActivityColor(activity.type)"
              ></div>
              <span class="text-sm text-gray-900">{{ activity.description }}</span>
            </div>
            <span class="text-xs text-gray-500">{{ getRelativeTime(activity.timestamp) }}</span>
          </div>
        </div>
      </div>
    </div>
  `
})
export class AnalyticsDashboardComponent implements OnInit, OnDestroy {
  @Input() showRealTimeUpdates = true;
  @Input() refreshInterval = 30000; // 30 seconds

  statistics: UserStatistics | null = null;
  keyMetrics: AnalyticsMetric[] = [];
  processingStatusData: ChartDataPoint[] = [];
  timelineData: TimeSeriesDataPoint[] = [];
  donutChartSegments: any[] = [];
  timelineChartPoints: any[] = [];
  recentActivities: any[] = [];

  private subscriptions: Subscription[] = [];

  constructor(
    private adminService: AdminService,
    private errorHandler: ErrorHandlerService
  ) {}

  ngOnInit(): void {
    this.loadAnalyticsData();
    this.setupRealTimeUpdates();
    this.generateMockTimelineData();
    this.generateMockActivities();
  }

  ngOnDestroy(): void {
    this.subscriptions.forEach(sub => sub.unsubscribe());
  }

  private loadAnalyticsData(): void {
    this.subscriptions.push(
      this.adminService.getUserStatistics().subscribe({
        next: (stats) => {
          this.statistics = stats;
          this.updateKeyMetrics();
          this.updateProcessingStatusChart();
        },
        error: (error) => {
          this.errorHandler.showError('Failed to load analytics data');
        }
      })
    );
  }

  private setupRealTimeUpdates(): void {
    if (this.refreshInterval > 0) {
      this.subscriptions.push(
        interval(this.refreshInterval).subscribe(() => {
          this.loadAnalyticsData();
        })
      );
    }
  }

  private updateKeyMetrics(): void {
    if (!this.statistics) return;

    this.keyMetrics = [
      {
        id: 'total_users',
        title: 'Total Users',
        value: this.statistics.total_users,
        change: 12.5,
        changeType: 'increase',
        format: 'number',
        icon: '<svg fill="currentColor" viewBox="0 0 24 24"><path d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z"/></svg>',
        color: '#3b82f6'
      },
      {
        id: 'manuscripts_processed',
        title: 'Manuscripts Processed',
        value: this.statistics.completed_manuscripts,
        change: 8.2,
        changeType: 'increase',
        format: 'number',
        icon: '<svg fill="currentColor" viewBox="0 0 24 24"><path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>',
        color: '#10b981'
      },
      {
        id: 'processing_time',
        title: 'Avg Processing Time',
        value: this.statistics.avg_processing_time_minutes,
        change: -5.1,
        changeType: 'decrease',
        format: 'time',
        icon: '<svg fill="currentColor" viewBox="0 0 24 24"><path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
        color: '#f59e0b'
      },
      {
        id: 'success_rate',
        title: 'Success Rate',
        value: this.calculateSuccessRate(),
        change: 2.3,
        changeType: 'increase',
        format: 'percentage',
        icon: '<svg fill="currentColor" viewBox="0 0 24 24"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
        color: '#8b5cf6'
      }
    ];
  }

  private updateProcessingStatusChart(): void {
    if (!this.statistics) return;

    this.processingStatusData = [
      { label: 'Completed', value: this.statistics.completed_manuscripts, color: '#10b981' },
      { label: 'Processing', value: this.statistics.processing_manuscripts, color: '#3b82f6' },
      { label: 'Failed', value: this.statistics.failed_manuscripts, color: '#ef4444' },
      { label: 'Pending', value: Math.max(0, this.statistics.total_manuscripts - this.statistics.completed_manuscripts - this.statistics.processing_manuscripts - this.statistics.failed_manuscripts), color: '#6b7280' }
    ];

    this.generateDonutChartSegments();
  }

  private generateDonutChartSegments(): void {
    const total = this.getTotalManuscripts();
    let cumulativePercentage = 0;
    const circumference = 2 * Math.PI * 40; // radius = 40

    this.donutChartSegments = this.processingStatusData.map(item => {
      const percentage = total > 0 ? (item.value / total) * 100 : 0;
      const dashArray = `${(percentage / 100) * circumference} ${circumference}`;
      const dashOffset = -cumulativePercentage * circumference / 100;
      
      cumulativePercentage += percentage;
      
      return {
        ...item,
        percentage,
        dashArray,
        dashOffset
      };
    });
  }

  private generateMockTimelineData(): void {
    const now = new Date();
    this.timelineData = [];
    
    for (let i = 6; i >= 0; i--) {
      const date = new Date(now);
      date.setDate(date.getDate() - i);
      
      this.timelineData.push({
        timestamp: date.toISOString(),
        value: Math.floor(Math.random() * 50) + 10,
        label: date.toLocaleDateString('en-US', { weekday: 'short' })
      });
    }
    
    this.generateTimelineChartPoints();
  }

  private generateTimelineChartPoints(): void {
    const maxValue = this.getMaxTimelineValue();
    const width = 400;
    const height = 200;
    const padding = 20;
    
    this.timelineChartPoints = this.timelineData.map((point, index) => {
      const x = padding + (index * (width - 2 * padding)) / (this.timelineData.length - 1);
      const y = height - padding - ((point.value / maxValue) * (height - 2 * padding));
      
      return {
        x,
        y,
        value: point.value,
        timestamp: point.timestamp
      };
    });
  }

  private generateMockActivities(): void {
    const activities = [
      { type: 'upload', description: 'New manuscript uploaded by user@example.com' },
      { type: 'completed', description: 'Processing completed for document.pdf' },
      { type: 'user', description: 'New user registration: john.doe@example.com' },
      { type: 'failed', description: 'Processing failed for large-document.pdf' },
      { type: 'download', description: 'Document downloaded by admin@example.com' }
    ];

    this.recentActivities = activities.map((activity, index) => ({
      ...activity,
      timestamp: new Date(Date.now() - index * 60000).toISOString()
    }));
  }

  // Helper methods
  formatMetricValue(metric: AnalyticsMetric): string {
    switch (metric.format) {
      case 'percentage':
        return `${metric.value}%`;
      case 'currency':
        return `$${metric.value.toLocaleString()}`;
      case 'time':
        return `${metric.value}min`;
      default:
        return metric.value.toLocaleString();
    }
  }

  getChangeClass(changeType: string): string {
    switch (changeType) {
      case 'increase':
        return 'text-green-600';
      case 'decrease':
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  }

  getTotalManuscripts(): number {
    return this.processingStatusData.reduce((sum, item) => sum + item.value, 0);
  }

  getMaxTimelineValue(): number {
    return Math.max(...this.timelineData.map(point => point.value));
  }

  getTimelineChartPoints(): string {
    return this.timelineChartPoints.map(point => `${point.x},${point.y}`).join(' ');
  }

  formatTimelineDate(timestamp: string): string {
    return new Date(timestamp).toLocaleDateString('en-US', { weekday: 'short' });
  }

  formatStorage(mb: number): string {
    if (mb < 1024) {
      return `${mb.toFixed(1)} MB`;
    } else {
      return `${(mb / 1024).toFixed(1)} GB`;
    }
  }

  calculateSuccessRate(): number {
    if (!this.statistics) return 0;
    const total = this.statistics.completed_manuscripts + this.statistics.failed_manuscripts;
    return total > 0 ? Math.round((this.statistics.completed_manuscripts / total) * 100) : 0;
  }

  getActivityColor(type: string): string {
    const colors = {
      upload: 'bg-blue-400',
      completed: 'bg-green-400',
      user: 'bg-purple-400',
      failed: 'bg-red-400',
      download: 'bg-yellow-400'
    };
    return colors[type as keyof typeof colors] || 'bg-gray-400';
  }

  getRelativeTime(timestamp: string): string {
    const now = new Date();
    const time = new Date(timestamp);
    const diffInSeconds = Math.floor((now.getTime() - time.getTime()) / 1000);

    if (diffInSeconds < 60) {
      return 'Just now';
    } else if (diffInSeconds < 3600) {
      const minutes = Math.floor(diffInSeconds / 60);
      return `${minutes}m ago`;
    } else if (diffInSeconds < 86400) {
      const hours = Math.floor(diffInSeconds / 3600);
      return `${hours}h ago`;
    } else {
      const days = Math.floor(diffInSeconds / 86400);
      return `${days}d ago`;
    }
  }

  getAbsoluteValue(value: number): number {
    return Math.abs(value);
  }

  getFloorValue(value: number): number {
    return Math.floor(value);
  }
}
