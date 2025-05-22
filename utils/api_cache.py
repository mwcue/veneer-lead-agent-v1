# utils/api_cache.py
"""
Simple in-memory caching system for API responses to reduce duplicate calls.
"""

import time
import hashlib
import json
from typing import Dict, Any, Callable, Optional
from utils.logging_utils import get_logger

logger = get_logger(__name__)

class APICache:
    """
    Simple in-memory cache for API responses.
    """
    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize the cache.
        
        Args:
            ttl_seconds: Time-to-live in seconds for cache entries
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl_seconds = ttl_seconds
        logger.debug(f"Initialized API cache with TTL of {ttl_seconds} seconds")
        
    def _generate_key(self, func_name: str, args: tuple, kwargs: Dict[str, Any]) -> str:
        """
        Generate a unique cache key for the function call.
        
        Args:
            func_name: Name of the function being called
            args: Positional arguments to the function
            kwargs: Keyword arguments to the function
            
        Returns:
            A unique hash string representing the function call
        """
        # Create a string representation of the function call
        key_parts = [func_name]
        
        # Add args
        for arg in args:
            if isinstance(arg, (str, int, float, bool, type(None))):
                key_parts.append(str(arg))
            else:
                # For complex types, use their string representation
                key_parts.append(str(arg))
        
        # Add kwargs (sorted for consistency)
        for k in sorted(kwargs.keys()):
            v = kwargs[k]
            if isinstance(v, (str, int, float, bool, type(None))):
                key_parts.append(f"{k}={v}")
            else:
                # For complex types, use their string representation
                key_parts.append(f"{k}={str(v)}")
        
        # Join and hash
        call_str = "|".join(key_parts)
        return hashlib.md5(call_str.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get a value from the cache if it exists and hasn't expired.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found or expired
        """
        if key not in self.cache:
            return None
            
        entry = self.cache[key]
        
        # Check if expired
        if time.time() - entry["timestamp"] > self.ttl_seconds:
            # Remove expired entry
            del self.cache[key]
            logger.debug(f"Cache entry expired for key {key[:8]}...")
            return None
            
        logger.debug(f"Cache hit for key {key[:8]}...")
        return entry["value"]
        
    def set(self, key: str, value: Any) -> None:
        """
        Store a value in the cache.
        
        Args:
            key: Cache key
            value: Value to store
        """
        self.cache[key] = {
            "value": value,
            "timestamp": time.time()
        }
        logger.debug(f"Cached value for key {key[:8]}...")
        
    def clear(self) -> None:
        """Clear all entries from the cache."""
        self.cache.clear()
        logger.debug("Cache cleared")
        
    def cached(self, func: Callable) -> Callable:
        """
        Decorator to cache function results.
        
        Args:
            func: Function to cache
            
        Returns:
            Wrapped function that uses the cache
        """
        def wrapper(*args, **kwargs):
            # Generate a unique key for this function call
            key = self._generate_key(func.__name__, args, kwargs)
            
            # Check if we have a cached result
            cached_result = self.get(key)
            if cached_result is not None:
                return cached_result
                
            # Otherwise, call the function and cache the result
            result = func(*args, **kwargs)
            self.set(key, result)
            return result
            
        return wrapper

# Create global instance
api_cache = APICache()

def cached_api_call(ttl_seconds: int = 3600):
    """
    Decorator to cache API calls with a specific TTL.
    
    Args:
        ttl_seconds: Time-to-live in seconds for the cache entry
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        # Create a cache specific to this function
        func_cache = APICache(ttl_seconds=ttl_seconds)
        
        def wrapper(*args, **kwargs):
            # Generate a unique key for this function call
            key = func_cache._generate_key(func.__name__, args, kwargs)
            
            # Check if we have a cached result
            cached_result = func_cache.get(key)
            if cached_result is not None:
                return cached_result
                
            # Otherwise, call the function and cache the result
            result = func(*args, **kwargs)
            func_cache.set(key, result)
            return result
            
        return wrapper
    return decorator
