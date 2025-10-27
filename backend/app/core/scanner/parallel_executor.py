"""
Parallel execution engine for intelligent scan orchestration
"""

import asyncio
import logging
from typing import Dict, List, Any, Callable, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import time
import resource
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """Task priority levels"""
    CRITICAL = 1    # Must run immediately
    HIGH = 2        # Important but can wait briefly
    NORMAL = 3      # Standard priority
    LOW = 4         # Background tasks


class TaskType(Enum):
    """Types of scan tasks"""
    RECON = "reconnaissance"
    PORT_SCAN = "port_scan"
    WEB_SCAN = "web_scan"
    VULN_SCAN = "vulnerability_scan"
    AI_ANALYSIS = "ai_analysis"
    EXPLOIT_GEN = "exploit_generation"


@dataclass
class ScanTask:
    """Individual scan task definition"""
    task_id: str
    task_type: TaskType
    priority: TaskPriority
    function: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    dependencies: Set[str] = field(default_factory=set)
    estimated_duration: float = 60.0  # seconds
    cpu_intensive: bool = False
    network_intensive: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None
    retries: int = 0
    max_retries: int = 2


@dataclass
class ResourceLimits:
    """System resource limits for parallel execution"""
    max_concurrent_tasks: int = 6
    max_cpu_intensive_tasks: int = 2
    max_network_tasks: int = 10
    memory_limit_mb: int = 1024
    cpu_threshold: float = 0.8  # 80% CPU usage


class ParallelExecutor:
    """Intelligent parallel executor for scan tasks"""
    
    def __init__(self, resource_limits: ResourceLimits = None):
        self.limits = resource_limits or ResourceLimits()
        self.tasks: Dict[str, ScanTask] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.completed_tasks: Set[str] = set()
        self.failed_tasks: Set[str] = set()
        self.task_queue: List[str] = []
        
        # Resource tracking
        self.current_cpu_tasks = 0
        self.current_network_tasks = 0
        self.current_memory_usage = 0
        
        # Thread pool for CPU-intensive tasks
        self.thread_pool = ThreadPoolExecutor(
            max_workers=self.limits.max_cpu_intensive_tasks
        )
        
        # Performance metrics
        self.metrics = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "average_duration": 0.0,
            "concurrent_peak": 0,
            "start_time": None,
            "end_time": None
        }
    
    def add_task(self, task: ScanTask) -> str:
        """Add a task to the execution queue"""
        self.tasks[task.task_id] = task
        self.task_queue.append(task.task_id)
        self.metrics["total_tasks"] += 1
        
        # Sort queue by priority
        self.task_queue.sort(key=lambda tid: self.tasks[tid].priority.value)
        
        logger.info(f"Added task {task.task_id} ({task.task_type.value}) with priority {task.priority.name}")
        return task.task_id
    
    def add_dependency(self, task_id: str, dependency_id: str):
        """Add a dependency between tasks"""
        if task_id in self.tasks:
            self.tasks[task_id].dependencies.add(dependency_id)
            logger.debug(f"Added dependency: {task_id} depends on {dependency_id}")
    
    async def execute_all(self) -> Dict[str, Any]:
        """Execute all tasks with intelligent parallelization"""
        if not self.tasks:
            return {"status": "no_tasks", "results": {}}
        
        self.metrics["start_time"] = datetime.utcnow()
        logger.info(f"Starting parallel execution of {len(self.tasks)} tasks")
        
        try:
            # Main execution loop
            while self._has_pending_tasks():
                # Get next batch of tasks to run
                ready_tasks = self._get_ready_tasks()
                
                if not ready_tasks and self.running_tasks:
                    # Wait for running tasks to complete
                    await asyncio.sleep(0.1)
                    continue
                elif not ready_tasks and not self.running_tasks:
                    # Deadlock or all tasks completed
                    break
                
                # Start ready tasks within resource limits
                for task_id in ready_tasks:
                    if await self._can_start_task(task_id):
                        await self._start_task(task_id)
                    else:
                        break  # Resource limits reached
                
                # Update peak concurrent tasks
                self.metrics["concurrent_peak"] = max(
                    self.metrics["concurrent_peak"], 
                    len(self.running_tasks)
                )
                
                # Brief pause to prevent busy waiting
                await asyncio.sleep(0.05)
            
            # Wait for all remaining tasks to complete
            if self.running_tasks:
                logger.info(f"Waiting for {len(self.running_tasks)} remaining tasks...")
                await asyncio.gather(*self.running_tasks.values(), return_exceptions=True)
            
            self.metrics["end_time"] = datetime.utcnow()
            self.metrics["completed_tasks"] = len(self.completed_tasks)
            self.metrics["failed_tasks"] = len(self.failed_tasks)
            
            # Calculate average duration
            completed_durations = []
            for task_id in self.completed_tasks:
                task = self.tasks[task_id]
                if task.started_at and task.completed_at:
                    duration = (task.completed_at - task.started_at).total_seconds()
                    completed_durations.append(duration)
            
            if completed_durations:
                self.metrics["average_duration"] = sum(completed_durations) / len(completed_durations)
            
            logger.info(f"Parallel execution completed: {self.metrics['completed_tasks']} completed, {self.metrics['failed_tasks']} failed")
            
            return {
                "status": "completed",
                "results": {task_id: task.result for task_id in self.completed_tasks},
                "errors": {task_id: self.tasks[task_id].error for task_id in self.failed_tasks},
                "metrics": self.metrics
            }
            
        except Exception as e:
            logger.error(f"Parallel execution failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "results": {task_id: task.result for task_id in self.completed_tasks},
                "metrics": self.metrics
            }
        finally:
            self.thread_pool.shutdown(wait=False)
    
    def _has_pending_tasks(self) -> bool:
        """Check if there are tasks still pending execution"""
        return bool(
            self.running_tasks or 
            (self.task_queue and 
             len(self.completed_tasks) + len(self.failed_tasks) < len(self.tasks))
        )
    
    def _get_ready_tasks(self) -> List[str]:
        """Get tasks that are ready to execute (dependencies satisfied)"""
        ready_tasks = []
        
        for task_id in self.task_queue:
            if (task_id not in self.running_tasks and 
                task_id not in self.completed_tasks and 
                task_id not in self.failed_tasks):
                
                task = self.tasks[task_id]
                
                # Check if all dependencies are completed
                if task.dependencies.issubset(self.completed_tasks):
                    ready_tasks.append(task_id)
                elif task.dependencies.intersection(self.failed_tasks):
                    # Dependency failed, mark this task as failed too
                    self.failed_tasks.add(task_id)
                    task.error = "Dependency failed"
                    logger.warning(f"Task {task_id} failed due to failed dependencies")
        
        # Sort by priority
        ready_tasks.sort(key=lambda tid: self.tasks[tid].priority.value)
        return ready_tasks
    
    async def _can_start_task(self, task_id: str) -> bool:
        """Check if we can start a task given current resource usage"""
        task = self.tasks[task_id]
        
        # Check concurrent task limit
        if len(self.running_tasks) >= self.limits.max_concurrent_tasks:
            return False
        
        # Check CPU intensive task limit
        if task.cpu_intensive and self.current_cpu_tasks >= self.limits.max_cpu_intensive_tasks:
            return False
        
        # Check network task limit
        if task.network_intensive and self.current_network_tasks >= self.limits.max_network_tasks:
            return False
        
        # Check system resources
        if not self._check_system_resources():
            return False
        
        return True
    
    def _check_system_resources(self) -> bool:
        """Check if system has enough resources"""
        try:
            # Check memory usage
            memory_usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024  # MB
            if memory_usage > self.limits.memory_limit_mb:
                logger.warning(f"Memory limit exceeded: {memory_usage:.1f}MB > {self.limits.memory_limit_mb}MB")
                return False
            
            # Check CPU load (basic check)
            # In production, you might want to use psutil for more accurate metrics
            
            return True
            
        except Exception as e:
            logger.warning(f"Could not check system resources: {e}")
            return True  # Allow execution if we can't check
    
    async def _start_task(self, task_id: str):
        """Start executing a task"""
        task = self.tasks[task_id]
        task.started_at = datetime.utcnow()
        
        # Update resource tracking
        if task.cpu_intensive:
            self.current_cpu_tasks += 1
        if task.network_intensive:
            self.current_network_tasks += 1
        
        logger.info(f"Starting task {task_id} ({task.task_type.value})")
        
        # Create and start the task
        if task.cpu_intensive:
            # Run CPU-intensive tasks in thread pool
            async_task = asyncio.create_task(
                self._run_in_thread(task.function, *task.args, **task.kwargs)
            )
        else:
            # Run I/O tasks in async context
            async_task = asyncio.create_task(
                task.function(*task.args, **task.kwargs)
            )
        
        self.running_tasks[task_id] = async_task
        
        # Set up task completion callback
        async_task.add_done_callback(lambda t: asyncio.create_task(self._task_completed(task_id, t)))
    
    async def _run_in_thread(self, func: Callable, *args, **kwargs):
        """Run a function in the thread pool"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.thread_pool, func, *args, **kwargs)
    
    async def _task_completed(self, task_id: str, async_task: asyncio.Task):
        """Handle task completion"""
        task = self.tasks[task_id]
        task.completed_at = datetime.utcnow()
        
        # Update resource tracking
        if task.cpu_intensive:
            self.current_cpu_tasks -= 1
        if task.network_intensive:
            self.current_network_tasks -= 1
        
        # Remove from running tasks
        if task_id in self.running_tasks:
            del self.running_tasks[task_id]
        
        try:
            # Get task result
            result = async_task.result()
            task.result = result
            self.completed_tasks.add(task_id)
            
            duration = (task.completed_at - task.started_at).total_seconds()
            logger.info(f"Task {task_id} completed successfully in {duration:.2f}s")
            
        except Exception as e:
            task.error = str(e)
            task.retries += 1
            
            logger.error(f"Task {task_id} failed: {e}")
            
            # Retry if possible
            if task.retries <= task.max_retries:
                logger.info(f"Retrying task {task_id} (attempt {task.retries}/{task.max_retries})")
                # Add back to queue with higher priority
                task.priority = TaskPriority.HIGH
                self.task_queue.insert(0, task_id)
                task.started_at = None
                task.completed_at = None
            else:
                self.failed_tasks.add(task_id)
                logger.error(f"Task {task_id} failed after {task.max_retries} retries")
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get detailed execution statistics"""
        stats = self.metrics.copy()
        
        # Task status breakdown
        stats["task_status"] = {
            "pending": len(self.task_queue) - len(self.completed_tasks) - len(self.failed_tasks),
            "running": len(self.running_tasks),
            "completed": len(self.completed_tasks),
            "failed": len(self.failed_tasks)
        }
        
        # Resource usage
        stats["resource_usage"] = {
            "cpu_intensive_tasks": self.current_cpu_tasks,
            "network_tasks": self.current_network_tasks,
            "concurrent_tasks": len(self.running_tasks)
        }
        
        # Task type breakdown
        task_types = defaultdict(int)
        for task in self.tasks.values():
            task_types[task.task_type.value] += 1
        stats["task_types"] = dict(task_types)
        
        # Duration statistics
        if self.metrics["start_time"] and self.metrics["end_time"]:
            total_duration = (self.metrics["end_time"] - self.metrics["start_time"]).total_seconds()
            stats["total_duration"] = total_duration
            
            if total_duration > 0:
                stats["tasks_per_second"] = len(self.completed_tasks) / total_duration
        
        return stats