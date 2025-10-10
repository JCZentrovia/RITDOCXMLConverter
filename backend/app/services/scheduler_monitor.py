"""
Scheduler monitoring service for tracking scheduler health and performance.

This service provides comprehensive monitoring of the scheduler service,
including execution tracking, performance metrics, and health status.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import time
import threading

# Monitoring imports removed
from app.core.logging_config import LoggingContext, performance_logger

logger = logging.getLogger(__name__)

class SchedulerStatus(str, Enum):
    """Scheduler status enumeration."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    SHUTTING_DOWN = "shutting_down"

class ExecutionResult(str, Enum):
    """Execution result enumeration."""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"

@dataclass
class SchedulerExecution:
    """Scheduler execution record."""
    execution_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    result: Optional[ExecutionResult] = None
    tasks_processed: int = 0
    tasks_successful: int = 0
    tasks_failed: int = 0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SchedulerMetrics:
    """Scheduler performance metrics."""
    total_executions: int
    successful_executions: int
    failed_executions: int
    average_execution_time_seconds: float
    total_tasks_processed: int
    total_tasks_successful: int
    total_tasks_failed: int
    success_rate_percentage: float
    tasks_per_execution_avg: float
    uptime_seconds: float
    last_execution_time: Optional[datetime]
    next_scheduled_execution: Optional[datetime]

class SchedulerMonitor:
    """Comprehensive scheduler monitoring service."""
    
    def __init__(self):
        self.status = SchedulerStatus.STOPPED
        self.start_time: Optional[datetime] = None
        self.executions: List[SchedulerExecution] = []
        self.max_executions_history = 1000
        self.current_execution: Optional[SchedulerExecution] = None
        self.error_count = 0
        self.last_error: Optional[str] = None
        self.last_error_time: Optional[datetime] = None
        self.health_check_interval = 30  # seconds
        self.performance_thresholds = {
            "max_execution_time_seconds": 300,  # 5 minutes
            "max_failure_rate_percentage": 20,  # 20%
            "max_consecutive_failures": 5
        }
        self.consecutive_failures = 0
        self._lock = threading.Lock()
        
        logger.info("Scheduler monitor initialized")
    
    def start_monitoring(self) -> None:
        """Start scheduler monitoring."""
        with self._lock:
            if self.status == SchedulerStatus.RUNNING:
                logger.warning("Scheduler monitor already running")
                return
            
            self.status = SchedulerStatus.STARTING
            self.start_time = datetime.utcnow()
            self.error_count = 0
            self.consecutive_failures = 0
            
            logger.info("Scheduler monitor started")
            self.status = SchedulerStatus.RUNNING
            
            # Alert creation removed
    
    def stop_monitoring(self) -> None:
        """Stop scheduler monitoring."""
        with self._lock:
            if self.status == SchedulerStatus.STOPPED:
                logger.warning("Scheduler monitor already stopped")
                return
            
            self.status = SchedulerStatus.SHUTTING_DOWN
            
            # Complete current execution if running
            if self.current_execution and not self.current_execution.end_time:
                self.current_execution.end_time = datetime.utcnow()
                self.current_execution.duration_seconds = (
                    self.current_execution.end_time - self.current_execution.start_time
                ).total_seconds()
                self.current_execution.result = ExecutionResult.CANCELLED
            
            self.status = SchedulerStatus.STOPPED
            
            logger.info("Scheduler monitor stopped")
            
            # Alert creation removed
    
    def start_execution(self, execution_id: str, metadata: Dict[str, Any] = None) -> SchedulerExecution:
        """Start tracking a scheduler execution."""
        with self._lock:
            if self.current_execution and not self.current_execution.end_time:
                logger.warning(f"Starting new execution {execution_id} while {self.current_execution.execution_id} is still running")
                self.end_execution(self.current_execution.execution_id, ExecutionResult.CANCELLED)
            
            execution = SchedulerExecution(
                execution_id=execution_id,
                start_time=datetime.utcnow(),
                metadata=metadata or {}
            )
            
            self.current_execution = execution
            
            logger.info(f"Started scheduler execution: {execution_id}")
            
            # Record performance metric
            performance_monitor.record_metric(
                "scheduler_execution_start",
                1,
                "count",
                {"execution_id": execution_id}
            )
            
            return execution
    
    def end_execution(
        self, 
        execution_id: str, 
        result: ExecutionResult,
        tasks_processed: int = 0,
        tasks_successful: int = 0,
        tasks_failed: int = 0,
        error_message: Optional[str] = None
    ) -> Optional[SchedulerExecution]:
        """End tracking a scheduler execution."""
        with self._lock:
            if not self.current_execution or self.current_execution.execution_id != execution_id:
                logger.warning(f"No matching execution found for {execution_id}")
                return None
            
            execution = self.current_execution
            execution.end_time = datetime.utcnow()
            execution.duration_seconds = (execution.end_time - execution.start_time).total_seconds()
            execution.result = result
            execution.tasks_processed = tasks_processed
            execution.tasks_successful = tasks_successful
            execution.tasks_failed = tasks_failed
            execution.error_message = error_message
            
            # Add to history
            self.executions.append(execution)
            
            # Maintain history size
            if len(self.executions) > self.max_executions_history:
                self.executions = self.executions[-self.max_executions_history:]
            
            # Update error tracking
            if result == ExecutionResult.FAILURE:
                self.error_count += 1
                self.consecutive_failures += 1
                self.last_error = error_message
                self.last_error_time = execution.end_time
                
                # Alert creation removed
            else:
                self.consecutive_failures = 0
            
            # Alert creation removed
            
            self.current_execution = None
            
            logger.info(f"Ended scheduler execution: {execution_id} ({result.value}) in {execution.duration_seconds:.2f}s")
            
            # Record performance metrics
            performance_monitor.record_metric(
                "scheduler_execution_duration",
                execution.duration_seconds,
                "seconds",
                {"execution_id": execution_id, "result": result.value}
            )
            
            performance_monitor.record_metric(
                "scheduler_tasks_processed",
                tasks_processed,
                "count",
                {"execution_id": execution_id, "result": result.value}
            )
            
            # Log performance
            performance_logger.log_operation(
                operation="scheduler_execution",
                duration_ms=execution.duration_seconds * 1000,
                status=result.value,
                tasks_processed=tasks_processed,
                tasks_successful=tasks_successful,
                tasks_failed=tasks_failed
            )
            
            return execution
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get scheduler health status."""
        with self._lock:
            now = datetime.utcnow()
            uptime_seconds = (now - self.start_time).total_seconds() if self.start_time else 0
            
            # Calculate metrics
            metrics = self._calculate_metrics()
            
            # Determine health status
            health_status = "healthy"
            health_issues = []
            
            if self.status != SchedulerStatus.RUNNING:
                health_status = "unhealthy"
                health_issues.append(f"Scheduler status: {self.status.value}")
            
            if self.consecutive_failures >= self.performance_thresholds["max_consecutive_failures"]:
                health_status = "critical"
                health_issues.append(f"Too many consecutive failures: {self.consecutive_failures}")
            
            if metrics.success_rate_percentage < (100 - self.performance_thresholds["max_failure_rate_percentage"]):
                if health_status == "healthy":
                    health_status = "degraded"
                health_issues.append(f"Low success rate: {metrics.success_rate_percentage:.1f}%")
            
            # Check if scheduler is stuck
            if (self.current_execution and 
                (now - self.current_execution.start_time).total_seconds() > self.performance_thresholds["max_execution_time_seconds"]):
                health_status = "degraded"
                health_issues.append("Long-running execution detected")
            
            return {
                "status": self.status.value,
                "health_status": health_status,
                "health_issues": health_issues,
                "uptime_seconds": uptime_seconds,
                "current_execution": {
                    "execution_id": self.current_execution.execution_id,
                    "start_time": self.current_execution.start_time.isoformat(),
                    "duration_seconds": (now - self.current_execution.start_time).total_seconds()
                } if self.current_execution else None,
                "metrics": metrics.__dict__,
                "error_info": {
                    "total_errors": self.error_count,
                    "consecutive_failures": self.consecutive_failures,
                    "last_error": self.last_error,
                    "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None
                },
                "thresholds": self.performance_thresholds,
                "timestamp": now.isoformat()
            }
    
    def _calculate_metrics(self) -> SchedulerMetrics:
        """Calculate scheduler performance metrics."""
        if not self.executions:
            return SchedulerMetrics(
                total_executions=0,
                successful_executions=0,
                failed_executions=0,
                average_execution_time_seconds=0,
                total_tasks_processed=0,
                total_tasks_successful=0,
                total_tasks_failed=0,
                success_rate_percentage=0,
                tasks_per_execution_avg=0,
                uptime_seconds=(datetime.utcnow() - self.start_time).total_seconds() if self.start_time else 0,
                last_execution_time=None,
                next_scheduled_execution=None
            )
        
        total_executions = len(self.executions)
        successful_executions = sum(1 for e in self.executions if e.result == ExecutionResult.SUCCESS)
        failed_executions = sum(1 for e in self.executions if e.result == ExecutionResult.FAILURE)
        
        total_duration = sum(e.duration_seconds for e in self.executions if e.duration_seconds)
        average_execution_time = total_duration / total_executions if total_executions > 0 else 0
        
        total_tasks_processed = sum(e.tasks_processed for e in self.executions)
        total_tasks_successful = sum(e.tasks_successful for e in self.executions)
        total_tasks_failed = sum(e.tasks_failed for e in self.executions)
        
        success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 0
        tasks_per_execution = total_tasks_processed / total_executions if total_executions > 0 else 0
        
        last_execution_time = max(e.end_time for e in self.executions if e.end_time) if self.executions else None
        
        return SchedulerMetrics(
            total_executions=total_executions,
            successful_executions=successful_executions,
            failed_executions=failed_executions,
            average_execution_time_seconds=average_execution_time,
            total_tasks_processed=total_tasks_processed,
            total_tasks_successful=total_tasks_successful,
            total_tasks_failed=total_tasks_failed,
            success_rate_percentage=success_rate,
            tasks_per_execution_avg=tasks_per_execution,
            uptime_seconds=(datetime.utcnow() - self.start_time).total_seconds() if self.start_time else 0,
            last_execution_time=last_execution_time,
            next_scheduled_execution=None  # Will be set by scheduler
        )
    
    def get_execution_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get execution history."""
        with self._lock:
            recent_executions = self.executions[-limit:] if limit > 0 else self.executions
            
            return [
                {
                    "execution_id": e.execution_id,
                    "start_time": e.start_time.isoformat(),
                    "end_time": e.end_time.isoformat() if e.end_time else None,
                    "duration_seconds": e.duration_seconds,
                    "result": e.result.value if e.result else None,
                    "tasks_processed": e.tasks_processed,
                    "tasks_successful": e.tasks_successful,
                    "tasks_failed": e.tasks_failed,
                    "error_message": e.error_message,
                    "metadata": e.metadata
                }
                for e in reversed(recent_executions)
            ]
    
    def get_performance_trends(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance trends over the specified time period."""
        with self._lock:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            recent_executions = [
                e for e in self.executions 
                if e.start_time >= cutoff_time and e.end_time
            ]
            
            if not recent_executions:
                return {
                    "time_period_hours": hours,
                    "executions_count": 0,
                    "trends": {}
                }
            
            # Group by hour
            hourly_stats = {}
            for execution in recent_executions:
                hour_key = execution.start_time.replace(minute=0, second=0, microsecond=0)
                
                if hour_key not in hourly_stats:
                    hourly_stats[hour_key] = {
                        "executions": 0,
                        "successful": 0,
                        "failed": 0,
                        "total_duration": 0,
                        "tasks_processed": 0
                    }
                
                stats = hourly_stats[hour_key]
                stats["executions"] += 1
                stats["total_duration"] += execution.duration_seconds or 0
                stats["tasks_processed"] += execution.tasks_processed
                
                if execution.result == ExecutionResult.SUCCESS:
                    stats["successful"] += 1
                elif execution.result == ExecutionResult.FAILURE:
                    stats["failed"] += 1
            
            # Format trends
            trends = []
            for hour_key in sorted(hourly_stats.keys()):
                stats = hourly_stats[hour_key]
                avg_duration = stats["total_duration"] / stats["executions"] if stats["executions"] > 0 else 0
                success_rate = (stats["successful"] / stats["executions"] * 100) if stats["executions"] > 0 else 0
                
                trends.append({
                    "hour": hour_key.isoformat(),
                    "executions": stats["executions"],
                    "success_rate_percentage": success_rate,
                    "average_duration_seconds": avg_duration,
                    "tasks_processed": stats["tasks_processed"]
                })
            
            return {
                "time_period_hours": hours,
                "executions_count": len(recent_executions),
                "trends": trends
            }
    
    def update_thresholds(self, thresholds: Dict[str, Any]) -> None:
        """Update performance thresholds."""
        with self._lock:
            self.performance_thresholds.update(thresholds)
            logger.info(f"Updated scheduler performance thresholds: {thresholds}")

# Global scheduler monitor instance
scheduler_monitor = SchedulerMonitor()
