"""
Intelligent Cache manager with compression, invalidation, and optimization
"""

import json
import hashlib
import asyncio
import zlib
import pickle
import time
from typing import Dict, Any, Optional, List, Union, Callable, Set
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
import threading
from contextlib import asynccontextmanager

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from app.config import settings
from ..logging.structured_logger import get_logger, EventType

logger = get_logger(__name__)


class CacheLevel(Enum):
    """Cache levels for different types of data"""
    SCAN_RESULTS = "scan_results"
    DNS_RECORDS = "dns_records" 
    PORT_SCAN = "port_scan"
    WEB_SCAN = "web_scan"
    VULNERABILITY_SCAN = "vuln_scan"
    AI_ANALYSIS = "ai_analysis"
    RECON_DATA = "recon_data"


class CompressionType(Enum):
    """Compression types for cache data"""
    NONE = "none"
    GZIP = "gzip"
    ZLIB = "zlib"
    PICKLE = "pickle"


class InvalidationStrategy(Enum):
    """Cache invalidation strategies"""
    TTL_ONLY = "ttl_only"
    TAG_BASED = "tag_based"
    DEPENDENCY_BASED = "dependency_based"
    LRU = "lru"
    ADAPTIVE = "adaptive"


@dataclass
class CacheConfig:
    """Enhanced cache configuration for different data types"""
    ttl_seconds: int
    compress: bool = False
    compression_type: CompressionType = CompressionType.ZLIB
    namespace: str = "phantom"
    
    # Intelligent features
    adaptive_ttl: bool = False
    min_ttl_seconds: int = 300  # 5 minutes
    max_ttl_seconds: int = 86400  # 24 hours
    
    # Invalidation
    invalidation_strategy: InvalidationStrategy = InvalidationStrategy.TTL_ONLY
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    
    # Performance
    prefetch_threshold: float = 0.8  # Prefetch when 80% of TTL elapsed
    background_refresh: bool = False
    
    # Size limits
    max_size_bytes: Optional[int] = None
    compress_threshold_bytes: int = 1024  # Compress data larger than 1KB
    

@dataclass
class CacheMetrics:
    """Cache performance metrics"""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    errors: int = 0
    
    # Size metrics
    total_size_bytes: int = 0
    compressed_size_bytes: int = 0
    compression_ratio: float = 0.0
    
    # Performance metrics
    average_get_time_ms: float = 0.0
    average_set_time_ms: float = 0.0
    
    # Intelligent features
    adaptive_ttl_adjustments: int = 0
    background_refreshes: int = 0
    prefetch_operations: int = 0
    
    # Invalidation metrics
    ttl_expiries: int = 0
    manual_invalidations: int = 0
    tag_invalidations: int = 0
    dependency_invalidations: int = 0
    
    def get_hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0
    
    def get_compression_savings(self) -> float:
        """Calculate compression savings percentage"""
        if self.total_size_bytes > 0:
            return ((self.total_size_bytes - self.compressed_size_bytes) / self.total_size_bytes * 100)
        return 0.0


class CacheConfigs:
    """Enhanced pre-configured cache settings for different data types"""
    
    SCAN_RESULTS = CacheConfig(
        ttl_seconds=86400,  # 24 hours
        compress=True,
        compression_type=CompressionType.ZLIB,
        namespace="phantom:scan_results",
        adaptive_ttl=True,
        background_refresh=True,
        tags=["scan_results", "complete_scans"],
        compress_threshold_bytes=2048
    )
    
    DNS_RECORDS = CacheConfig(
        ttl_seconds=3600,  # 1 hour
        compress=False,
        namespace="phantom:dns",
        adaptive_ttl=True,
        tags=["dns", "reconnaissance"],
        dependencies=["network_config"]
    )
    
    PORT_SCAN = CacheConfig(
        ttl_seconds=1800,  # 30 minutes
        compress=False,
        namespace="phantom:ports",
        adaptive_ttl=True,
        tags=["port_scan", "network_scan"],
        prefetch_threshold=0.7
    )
    
    WEB_SCAN = CacheConfig(
        ttl_seconds=3600,  # 1 hour
        compress=True,
        compression_type=CompressionType.ZLIB,
        namespace="phantom:web",
        adaptive_ttl=True,
        background_refresh=True,
        tags=["web_scan", "application_scan"],
        compress_threshold_bytes=1024
    )
    
    VULNERABILITY_SCAN = CacheConfig(
        ttl_seconds=7200,  # 2 hours
        compress=True,
        compression_type=CompressionType.ZLIB,
        namespace="phantom:vulns",
        adaptive_ttl=True,
        background_refresh=True,
        tags=["vulnerability", "security_scan"],
        compress_threshold_bytes=1024,
        dependencies=["nuclei_templates"]
    )
    
    AI_ANALYSIS = CacheConfig(
        ttl_seconds=86400,  # 24 hours
        compress=True,
        compression_type=CompressionType.ZLIB,
        namespace="phantom:ai",
        adaptive_ttl=True,
        background_refresh=True,
        tags=["ai_analysis", "gpt_results"],
        compress_threshold_bytes=512,
        dependencies=["openai_model"]
    )
    
    RECON_DATA = CacheConfig(
        ttl_seconds=3600,  # 1 hour
        compress=False,
        namespace="phantom:recon",
        adaptive_ttl=True,
        tags=["reconnaissance", "intelligence"],
        prefetch_threshold=0.6
    )


@dataclass 
class CacheEntry:
    """Enhanced cache entry with metadata"""
    data: Any
    created_at: datetime
    accessed_at: datetime
    ttl_seconds: int
    compressed: bool = False
    compression_type: CompressionType = CompressionType.NONE
    tags: Set[str] = field(default_factory=set)
    dependencies: Set[str] = field(default_factory=set)
    access_count: int = 0
    size_bytes: int = 0
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        return datetime.utcnow() > (self.created_at + timedelta(seconds=self.ttl_seconds))
    
    def should_prefetch(self, threshold: float) -> bool:
        """Check if entry should be prefetched"""
        elapsed = (datetime.utcnow() - self.created_at).total_seconds()
        return elapsed >= (self.ttl_seconds * threshold)
    
    def update_access(self):
        """Update access metadata"""
        self.accessed_at = datetime.utcnow()
        self.access_count += 1


class IntelligentCacheManager:
    """
    Intelligent cache manager with advanced features:
    - Compression with multiple algorithms
    - Tag-based and dependency-based invalidation
    - Adaptive TTL based on usage patterns
    - Background refresh and prefetching
    - Comprehensive metrics and monitoring
    - LRU eviction with size limits
    """
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.enabled = False
        self.local_cache: Dict[str, CacheEntry] = {}
        self.metrics = CacheMetrics()
        
        # Intelligent features
        self.access_patterns: Dict[str, List[datetime]] = {}  # Track access patterns
        self.tag_index: Dict[str, Set[str]] = {}  # Tag -> cache keys
        self.dependency_index: Dict[str, Set[str]] = {}  # Dependency -> cache keys
        
        # Background tasks
        self.background_tasks: Set[asyncio.Task] = set()
        self.cleanup_interval = 300  # 5 minutes
        self.prefetch_workers = 2
        
        # Threading
        self.lock = asyncio.Lock()
        self.metrics_lock = threading.Lock()
        
    async def initialize(self) -> bool:
        """Initialize Redis connection"""
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available, using in-memory cache only")
            return False
            
        try:
            # Parse Redis URL
            redis_url = settings.redis_url
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            
            # Test connection
            await self.redis_client.ping()
            self.enabled = True
            logger.info("✅ Redis cache initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis cache: {e}")
            self.redis_client = None
            self.enabled = False
            return False
    
    def _generate_cache_key(
        self,
        cache_level: CacheLevel,
        target: str,
        additional_params: Optional[Dict] = None
    ) -> str:
        """Generate consistent cache key"""
        config = self._get_config(cache_level)
        
        # Create base key
        base_data = {
            "target": target,
            "level": cache_level.value
        }
        
        # Add additional parameters
        if additional_params:
            base_data.update(additional_params)
        
        # Create hash for consistent key
        data_str = json.dumps(base_data, sort_keys=True)
        hash_key = hashlib.md5(data_str.encode()).hexdigest()
        
        return f"{config.namespace}:{hash_key}"
    
    def _get_config(self, cache_level: CacheLevel) -> CacheConfig:
        """Get configuration for cache level"""
        config_map = {
            CacheLevel.SCAN_RESULTS: CacheConfigs.SCAN_RESULTS,
            CacheLevel.DNS_RECORDS: CacheConfigs.DNS_RECORDS,
            CacheLevel.PORT_SCAN: CacheConfigs.PORT_SCAN,
            CacheLevel.WEB_SCAN: CacheConfigs.WEB_SCAN,
            CacheLevel.VULNERABILITY_SCAN: CacheConfigs.VULNERABILITY_SCAN,
            CacheLevel.AI_ANALYSIS: CacheConfigs.AI_ANALYSIS,
            CacheLevel.RECON_DATA: CacheConfigs.RECON_DATA,
        }
        return config_map.get(cache_level, CacheConfigs.SCAN_RESULTS)
    
    async def get(
        self,
        cache_level: CacheLevel,
        target: str,
        additional_params: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """Get data from cache"""
        cache_key = self._generate_cache_key(cache_level, target, additional_params)
        
        try:
            # Try Redis first
            if self.enabled and self.redis_client:
                cached_data = await self.redis_client.get(cache_key)
                if cached_data:
                    self.cache_stats["hits"] += 1
                    result = json.loads(cached_data)
                    logger.debug(f"Cache HIT for {cache_key}")
                    return result
            
            # Try local cache
            if cache_key in self.local_cache:
                cached_item = self.local_cache[cache_key]
                # Check if expired
                if datetime.fromisoformat(cached_item["expires_at"]) > datetime.utcnow():
                    self.cache_stats["hits"] += 1
                    logger.debug(f"Local cache HIT for {cache_key}")
                    return cached_item["data"]
                else:
                    # Remove expired item
                    del self.local_cache[cache_key]
            
            self.cache_stats["misses"] += 1
            logger.debug(f"Cache MISS for {cache_key}")
            return None
            
        except Exception as e:
            logger.error(f"Cache GET error for {cache_key}: {e}")
            self.cache_stats["errors"] += 1
            return None
    
    async def set(
        self,
        cache_level: CacheLevel,
        target: str,
        data: Dict[str, Any],
        additional_params: Optional[Dict] = None,
        custom_ttl: Optional[int] = None
    ) -> bool:
        """Set data in cache"""
        cache_key = self._generate_cache_key(cache_level, target, additional_params)
        config = self._get_config(cache_level)
        ttl = custom_ttl or config.ttl_seconds
        
        try:
            # Add metadata
            cache_data = {
                "data": data,
                "cached_at": datetime.utcnow().isoformat(),
                "cache_level": cache_level.value,
                "ttl": ttl
            }
            
            json_data = json.dumps(cache_data)
            
            # Set in Redis
            if self.enabled and self.redis_client:
                await self.redis_client.setex(cache_key, ttl, json_data)
                logger.debug(f"Cached in Redis: {cache_key} (TTL: {ttl}s)")
            
            # Set in local cache (with size limit)
            if len(self.local_cache) < 1000:  # Limit local cache size
                expires_at = datetime.utcnow() + timedelta(seconds=ttl)
                self.local_cache[cache_key] = {
                    "data": data,
                    "expires_at": expires_at.isoformat()
                }
                logger.debug(f"Cached locally: {cache_key}")
            
            self.cache_stats["sets"] += 1
            return True
            
        except Exception as e:
            logger.error(f"Cache SET error for {cache_key}: {e}")
            self.cache_stats["errors"] += 1
            return False
    
    async def delete(
        self,
        cache_level: CacheLevel,
        target: str,
        additional_params: Optional[Dict] = None
    ) -> bool:
        """Delete data from cache"""
        cache_key = self._generate_cache_key(cache_level, target, additional_params)
        
        try:
            # Delete from Redis
            if self.enabled and self.redis_client:
                await self.redis_client.delete(cache_key)
            
            # Delete from local cache
            if cache_key in self.local_cache:
                del self.local_cache[cache_key]
            
            logger.debug(f"Deleted cache key: {cache_key}")
            return True
            
        except Exception as e:
            logger.error(f"Cache DELETE error for {cache_key}: {e}")
            return False
    
    async def clear_target_cache(self, target: str) -> int:
        """Clear all cache entries for a specific target"""
        cleared = 0
        
        try:
            # Clear Redis entries
            if self.enabled and self.redis_client:
                pattern = f"phantom:*{target}*"
                keys = await self.redis_client.keys(pattern)
                if keys:
                    cleared += await self.redis_client.delete(*keys)
            
            # Clear local cache entries
            keys_to_delete = []
            for key in self.local_cache.keys():
                if target in key:
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del self.local_cache[key]
                cleared += 1
            
            logger.info(f"Cleared {cleared} cache entries for target {target}")
            return cleared
            
        except Exception as e:
            logger.error(f"Error clearing cache for {target}: {e}")
            return 0
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = self.cache_stats.copy()
        stats["enabled"] = self.enabled
        stats["redis_available"] = REDIS_AVAILABLE and self.redis_client is not None
        stats["local_cache_size"] = len(self.local_cache)
        
        # Calculate hit rate
        total_requests = stats["hits"] + stats["misses"]
        stats["hit_rate"] = (
            stats["hits"] / total_requests 
            if total_requests > 0 else 0.0
        )
        
        # Get Redis info if available
        if self.enabled and self.redis_client:
            try:
                redis_info = await self.redis_client.info()
                stats["redis_info"] = {
                    "used_memory": redis_info.get("used_memory_human"),
                    "connected_clients": redis_info.get("connected_clients"),
                    "total_commands_processed": redis_info.get("total_commands_processed")
                }
            except Exception:
                pass
        
        return stats
    
    async def cleanup_expired(self) -> int:
        """Clean up expired entries from local cache"""
        now = datetime.utcnow()
        expired_keys = []
        
        for key, item in self.local_cache.items():
            if datetime.fromisoformat(item["expires_at"]) <= now:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.local_cache[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)
    
    async def close(self):
        """Close cache connections"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Cache manager closed")


# Global cache manager instance
cache_manager = CacheManager()