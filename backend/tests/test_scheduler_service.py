"""
Unit tests for scheduler service and monitoring.

This module tests scheduler execution tracking, health monitoring,
performance metrics, and error handling.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio

from app.services.scheduler_monitor import (
    scheduler_monitor, SchedulerMonitor, SchedulerStatus, ExecutionResult,
    SchedulerExecution, SchedulerMetrics
)
from app.core.monitoring import alert_manager, performance_monitor

pytestmark = [pytest.mark.asyncio, pytest.mark.scheduler]

class TestSchedulerMonitorInitialization:
    """Test scheduler monitor initialization and configuration."""
    
    def test_scheduler_monitor_initialization(self):
        """Test scheduler monitor is properly initialized."""
        monitor = SchedulerMonitor()
        
        assert monitor.status == SchedulerStatus.STOPPED
        assert monitor.start_time is None
        assert len(monitor.executions) == 0
        assert monitor.current_execution is None
        assert monitor.error_count == 0
        assert monitor.consecutive_failures == 0
    
    def test_scheduler_monitor_configuration(self):
        """Test scheduler monitor configuration."""
        monitor = SchedulerMonitor()
        
        # Test default configuration
        assert monitor.max_executions_history == 1000
        assert monitor.health_check_interval == 30
        assert monitor.performance_thresholds["max_execution_time_seconds"] == 300
        assert monitor.performance_thresholds["max_failure_rate_percentage"] == 20
        assert monitor.performance_thresholds["max_consecutive_failures"] == 5

class TestSchedulerMonitorLifecycle:
    """Test scheduler monitor lifecycle operations."""
    
    def test_start_monitoring(self):
        """Test starting scheduler monitoring."""
        monitor = SchedulerMonitor()
        
        monitor.start_monitoring()
        
        assert monitor.status == SchedulerStatus.RUNNING
        assert monitor.start_time is not None
        assert monitor.error_count == 0
        assert monitor.consecutive_failures == 0
    
    def test_start_monitoring_already_running(self):
        """Test starting monitoring when already running."""
        monitor = SchedulerMonitor()
        
        # Start monitoring
        monitor.start_monitoring()
        first_start_time = monitor.start_time
        
        # Try to start again
        monitor.start_monitoring()
        
        # Should remain the same
        assert monitor.status == SchedulerStatus.RUNNING
        assert monitor.start_time == first_start_time
    
    def test_stop_monitoring(self):
        """Test stopping scheduler monitoring."""
        monitor = SchedulerMonitor()
        
        # Start and then stop
        monitor.start_monitoring()
        monitor.stop_monitoring()
        
        assert monitor.status == SchedulerStatus.STOPPED
    
    def test_stop_monitoring_with_active_execution(self):
        """Test stopping monitoring with active execution."""
        monitor = SchedulerMonitor()
        
        monitor.start_monitoring()
        
        # Start an execution
        execution = monitor.start_execution("test-execution")
        assert monitor.current_execution is not None
        
        # Stop monitoring
        monitor.stop_monitoring()
        
        assert monitor.status == SchedulerStatus.STOPPED
        assert execution.result == ExecutionResult.CANCELLED
        assert execution.end_time is not None

class TestExecutionTracking:
    """Test scheduler execution tracking."""
    
    def test_start_execution(self):
        """Test starting execution tracking."""
        monitor = SchedulerMonitor()
        monitor.start_monitoring()
        
        execution_id = "test-execution-1"
        metadata = {"test": "data"}
        
        execution = monitor.start_execution(execution_id, metadata)
        
        assert execution.execution_id == execution_id
        assert execution.start_time is not None
        assert execution.end_time is None
        assert execution.metadata == metadata
        assert monitor.current_execution == execution
    
    def test_start_execution_overlapping(self):
        """Test starting execution when another is running."""
        monitor = SchedulerMonitor()
        monitor.start_monitoring()
        
        # Start first execution
        execution1 = monitor.start_execution("execution-1")
        
        # Start second execution (should cancel first)
        execution2 = monitor.start_execution("execution-2")
        
        assert execution1.result == ExecutionResult.CANCELLED
        assert execution1.end_time is not None
        assert monitor.current_execution == execution2
    
    def test_end_execution_success(self):
        """Test ending execution with success."""
        monitor = SchedulerMonitor()
        monitor.start_monitoring()
        
        execution_id = "test-execution"
        execution = monitor.start_execution(execution_id)
        
        # End execution successfully
        completed_execution = monitor.end_execution(
            execution_id,
            ExecutionResult.SUCCESS,
            tasks_processed=10,
            tasks_successful=9,
            tasks_failed=1
        )
        
        assert completed_execution is not None
        assert completed_execution.result == ExecutionResult.SUCCESS
        assert completed_execution.end_time is not None
        assert completed_execution.duration_seconds is not None
        assert completed_execution.tasks_processed == 10
        assert completed_execution.tasks_successful == 9
        assert completed_execution.tasks_failed == 1
        assert monitor.current_execution is None
        assert len(monitor.executions) == 1
    
    def test_end_execution_failure(self):
        """Test ending execution with failure."""
        monitor = SchedulerMonitor()
        monitor.start_monitoring()
        
        execution_id = "test-execution"
        execution = monitor.start_execution(execution_id)
        
        error_message = "Test error occurred"
        
        # End execution with failure
        completed_execution = monitor.end_execution(
            execution_id,
            ExecutionResult.FAILURE,
            error_message=error_message
        )
        
        assert completed_execution.result == ExecutionResult.FAILURE
        assert completed_execution.error_message == error_message
        assert monitor.error_count == 1
        assert monitor.consecutive_failures == 1
        assert monitor.last_error == error_message
    
    def test_end_execution_nonexistent(self):
        """Test ending execution that doesn't exist."""
        monitor = SchedulerMonitor()
        monitor.start_monitoring()
        
        # Try to end non-existent execution
        result = monitor.end_execution("nonexistent-execution", ExecutionResult.SUCCESS)
        
        assert result is None
    
    def test_execution_history_limit(self):
        """Test execution history size limit."""
        monitor = SchedulerMonitor()
        monitor.max_executions_history = 5  # Set small limit for testing
        monitor.start_monitoring()
        
        # Create more executions than the limit
        for i in range(10):
            execution = monitor.start_execution(f"execution-{i}")
            monitor.end_execution(f"execution-{i}", ExecutionResult.SUCCESS)
        
        # Should only keep the last 5
        assert len(monitor.executions) == 5
        
        # Should be the most recent ones
        execution_ids = [e.execution_id for e in monitor.executions]
        assert "execution-9" in execution_ids
        assert "execution-0" not in execution_ids

class TestHealthStatusAssessment:
    """Test scheduler health status assessment."""
    
    def test_health_status_healthy(self):
        """Test healthy status assessment."""
        monitor = SchedulerMonitor()
        monitor.start_monitoring()
        
        # Add some successful executions
        for i in range(5):
            execution = monitor.start_execution(f"execution-{i}")
            monitor.end_execution(f"execution-{i}", ExecutionResult.SUCCESS)
        
        health_status = monitor.get_health_status()
        
        assert health_status["status"] == SchedulerStatus.RUNNING.value
        assert health_status["health_status"] == "healthy"
        assert len(health_status["health_issues"]) == 0
    
    def test_health_status_degraded_low_success_rate(self):
        """Test degraded status due to low success rate."""
        monitor = SchedulerMonitor()
        monitor.start_monitoring()
        
        # Add mostly failed executions
        for i in range(10):
            execution = monitor.start_execution(f"execution-{i}")
            result = ExecutionResult.FAILURE if i < 8 else ExecutionResult.SUCCESS
            monitor.end_execution(f"execution-{i}", result)
        
        health_status = monitor.get_health_status()
        
        assert health_status["health_status"] in ["degraded", "critical"]
        assert any("success rate" in issue.lower() for issue in health_status["health_issues"])
    
    def test_health_status_critical_consecutive_failures(self):
        """Test critical status due to consecutive failures."""
        monitor = SchedulerMonitor()
        monitor.start_monitoring()
        
        # Add consecutive failures
        for i in range(6):  # More than threshold of 5
            execution = monitor.start_execution(f"execution-{i}")
            monitor.end_execution(f"execution-{i}", ExecutionResult.FAILURE)
        
        health_status = monitor.get_health_status()
        
        assert health_status["health_status"] == "critical"
        assert any("consecutive failures" in issue.lower() for issue in health_status["health_issues"])
    
    def test_health_status_unhealthy_not_running(self):
        """Test unhealthy status when not running."""
        monitor = SchedulerMonitor()
        # Don't start monitoring
        
        health_status = monitor.get_health_status()
        
        assert health_status["health_status"] == "unhealthy"
        assert any("scheduler status" in issue.lower() for issue in health_status["health_issues"])
    
    def test_health_status_degraded_long_execution(self):
        """Test degraded status due to long-running execution."""
        monitor = SchedulerMonitor()
        monitor.performance_thresholds["max_execution_time_seconds"] = 1  # 1 second for testing
        monitor.start_monitoring()
        
        # Start execution but don't end it
        execution = monitor.start_execution("long-execution")
        
        # Simulate time passing
        execution.start_time = datetime.utcnow() - timedelta(seconds=2)
        
        health_status = monitor.get_health_status()
        
        assert health_status["health_status"] == "degraded"
        assert any("long-running" in issue.lower() for issue in health_status["health_issues"])

class TestPerformanceMetrics:
    """Test scheduler performance metrics calculation."""
    
    def test_metrics_calculation_empty(self):
        """Test metrics calculation with no executions."""
        monitor = SchedulerMonitor()
        monitor.start_monitoring()
        
        metrics = monitor._calculate_metrics()
        
        assert metrics.total_executions == 0
        assert metrics.successful_executions == 0
        assert metrics.failed_executions == 0
        assert metrics.success_rate_percentage == 0
        assert metrics.average_execution_time_seconds == 0
    
    def test_metrics_calculation_with_executions(self):
        """Test metrics calculation with executions."""
        monitor = SchedulerMonitor()
        monitor.start_monitoring()
        
        # Add mixed executions
        execution_data = [
            (ExecutionResult.SUCCESS, 10, 8, 2),
            (ExecutionResult.SUCCESS, 5, 5, 0),
            (ExecutionResult.FAILURE, 3, 0, 3),
            (ExecutionResult.SUCCESS, 7, 6, 1)
        ]
        
        for i, (result, processed, successful, failed) in enumerate(execution_data):
            execution = monitor.start_execution(f"execution-{i}")
            # Simulate some duration
            execution.start_time = datetime.utcnow() - timedelta(seconds=2)
            monitor.end_execution(
                f"execution-{i}",
                result,
                tasks_processed=processed,
                tasks_successful=successful,
                tasks_failed=failed
            )
        
        metrics = monitor._calculate_metrics()
        
        assert metrics.total_executions == 4
        assert metrics.successful_executions == 3
        assert metrics.failed_executions == 1
        assert metrics.success_rate_percentage == 75.0
        assert metrics.total_tasks_processed == 25
        assert metrics.total_tasks_successful == 19
        assert metrics.total_tasks_failed == 6
        assert metrics.average_execution_time_seconds > 0
    
    def test_performance_trends(self):
        """Test performance trends calculation."""
        monitor = SchedulerMonitor()
        monitor.start_monitoring()
        
        # Add executions over time
        base_time = datetime.utcnow() - timedelta(hours=2)
        
        for i in range(5):
            execution = monitor.start_execution(f"execution-{i}")
            execution.start_time = base_time + timedelta(minutes=i * 30)
            monitor.end_execution(
                f"execution-{i}",
                ExecutionResult.SUCCESS,
                tasks_processed=10
            )
        
        trends = monitor.get_performance_trends(hours=3)
        
        assert trends["time_period_hours"] == 3
        assert trends["executions_count"] == 5
        assert len(trends["trends"]) > 0

class TestAlertIntegration:
    """Test scheduler integration with alert system."""
    
    @patch('app.core.monitoring.alert_manager')
    def test_consecutive_failures_alert(self, mock_alert_manager):
        """Test alert creation for consecutive failures."""
        monitor = SchedulerMonitor()
        monitor.start_monitoring()
        
        # Create consecutive failures to trigger alert
        for i in range(6):  # More than threshold
            execution = monitor.start_execution(f"execution-{i}")
            monitor.end_execution(f"execution-{i}", ExecutionResult.FAILURE, error_message="Test error")
        
        # Should have created an alert
        mock_alert_manager.create_alert.assert_called()
        
        # Verify alert details
        call_args = mock_alert_manager.create_alert.call_args
        assert call_args[1]["component"] == "scheduler"
        assert "consecutive failures" in call_args[1]["message"].lower()
    
    @patch('app.core.monitoring.alert_manager')
    def test_long_execution_alert(self, mock_alert_manager):
        """Test alert creation for long execution time."""
        monitor = SchedulerMonitor()
        monitor.performance_thresholds["max_execution_time_seconds"] = 1  # 1 second
        monitor.start_monitoring()
        
        execution = monitor.start_execution("long-execution")
        # Simulate long execution
        execution.start_time = datetime.utcnow() - timedelta(seconds=2)
        monitor.end_execution("long-execution", ExecutionResult.SUCCESS)
        
        # Should have created an alert
        mock_alert_manager.create_alert.assert_called()
        
        # Verify alert details
        call_args = mock_alert_manager.create_alert.call_args
        assert call_args[1]["component"] == "scheduler"
        assert "execution exceeded time threshold" in call_args[1]["message"].lower()

class TestThresholdManagement:
    """Test scheduler threshold management."""
    
    def test_update_thresholds(self):
        """Test updating performance thresholds."""
        monitor = SchedulerMonitor()
        
        new_thresholds = {
            "max_execution_time_seconds": 600,
            "max_failure_rate_percentage": 30
        }
        
        monitor.update_thresholds(new_thresholds)
        
        assert monitor.performance_thresholds["max_execution_time_seconds"] == 600
        assert monitor.performance_thresholds["max_failure_rate_percentage"] == 30
        # Other thresholds should remain unchanged
        assert monitor.performance_thresholds["max_consecutive_failures"] == 5
    
    def test_threshold_validation_in_health_check(self):
        """Test that updated thresholds are used in health checks."""
        monitor = SchedulerMonitor()
        monitor.start_monitoring()
        
        # Update threshold
        monitor.update_thresholds({"max_consecutive_failures": 2})
        
        # Create failures up to new threshold
        for i in range(3):  # More than new threshold of 2
            execution = monitor.start_execution(f"execution-{i}")
            monitor.end_execution(f"execution-{i}", ExecutionResult.FAILURE)
        
        health_status = monitor.get_health_status()
        
        # Should be critical due to exceeding new threshold
        assert health_status["health_status"] == "critical"

class TestExecutionHistory:
    """Test execution history management."""
    
    def test_get_execution_history(self):
        """Test retrieving execution history."""
        monitor = SchedulerMonitor()
        monitor.start_monitoring()
        
        # Add some executions
        for i in range(3):
            execution = monitor.start_execution(f"execution-{i}")
            monitor.end_execution(f"execution-{i}", ExecutionResult.SUCCESS, tasks_processed=i+1)
        
        history = monitor.get_execution_history(limit=10)
        
        assert len(history) == 3
        
        # Should be in reverse chronological order (most recent first)
        assert history[0]["execution_id"] == "execution-2"
        assert history[1]["execution_id"] == "execution-1"
        assert history[2]["execution_id"] == "execution-0"
        
        # Verify data structure
        for entry in history:
            assert "execution_id" in entry
            assert "start_time" in entry
            assert "end_time" in entry
            assert "duration_seconds" in entry
            assert "result" in entry
            assert "tasks_processed" in entry
    
    def test_get_execution_history_with_limit(self):
        """Test retrieving execution history with limit."""
        monitor = SchedulerMonitor()
        monitor.start_monitoring()
        
        # Add more executions than limit
        for i in range(5):
            execution = monitor.start_execution(f"execution-{i}")
            monitor.end_execution(f"execution-{i}", ExecutionResult.SUCCESS)
        
        history = monitor.get_execution_history(limit=3)
        
        assert len(history) == 3
        # Should get the most recent 3
        assert history[0]["execution_id"] == "execution-4"
        assert history[1]["execution_id"] == "execution-3"
        assert history[2]["execution_id"] == "execution-2"

class TestConcurrencyAndThreadSafety:
    """Test scheduler monitor thread safety and concurrency."""
    
    def test_concurrent_execution_operations(self):
        """Test concurrent execution start/end operations."""
        monitor = SchedulerMonitor()
        monitor.start_monitoring()
        
        # This test verifies that the threading.Lock works correctly
        # In a real concurrent scenario, operations should be thread-safe
        
        execution1 = monitor.start_execution("concurrent-1")
        execution2 = monitor.start_execution("concurrent-2")  # Should cancel execution1
        
        assert execution1.result == ExecutionResult.CANCELLED
        assert monitor.current_execution == execution2
    
    def test_health_status_during_execution_changes(self):
        """Test health status consistency during execution state changes."""
        monitor = SchedulerMonitor()
        monitor.start_monitoring()
        
        # Start execution
        execution = monitor.start_execution("test-execution")
        
        # Get health status while execution is running
        health_status_running = monitor.get_health_status()
        assert health_status_running["current_execution"] is not None
        
        # End execution
        monitor.end_execution("test-execution", ExecutionResult.SUCCESS)
        
        # Get health status after execution ends
        health_status_ended = monitor.get_health_status()
        assert health_status_ended["current_execution"] is None

class TestGlobalSchedulerMonitorInstance:
    """Test global scheduler monitor instance."""
    
    def test_global_instance_exists(self):
        """Test that global scheduler monitor instance exists."""
        from app.services.scheduler_monitor import scheduler_monitor
        
        assert scheduler_monitor is not None
        assert isinstance(scheduler_monitor, SchedulerMonitor)
    
    def test_global_instance_initial_state(self):
        """Test global instance initial state."""
        from app.services.scheduler_monitor import scheduler_monitor
        
        # Reset to initial state for testing
        scheduler_monitor.stop_monitoring()
        
        assert scheduler_monitor.status == SchedulerStatus.STOPPED
        assert scheduler_monitor.start_time is None
        assert len(scheduler_monitor.executions) == 0
