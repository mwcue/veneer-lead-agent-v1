# utils/logging_utils.py
"""
Centralized logging and error handling utilities for the HR Lead Generation system.
"""

import logging
import functools
import time
from typing import Callable, Any, TypeVar, Dict, List, Optional

# Type variable for generic function return type
T = TypeVar('T')

def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure global logging settings with consistent format.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO
        
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Reduce verbosity of some external libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    
    logging.info(f"Logging initialized at {log_level} level")

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name, using the consistent format.
    
    Args:
        name: Name for the logger, typically the module name
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)

def retry(max_attempts: int = 3, 
          delay: int = 2, 
          backoff: int = 2, 
          exceptions: tuple = (Exception,)) -> Callable:
    """
    Retry decorator with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Backoff multiplier e.g. value of 2 will double the delay each retry
        exceptions: Exceptions to catch and retry on
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Dict[str, Any]) -> T:
            logger = get_logger(func.__module__)
            mtries, mdelay = max_attempts, delay
            
            while mtries > 1:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    # Check if the exception is retriable
                    if "rate limit" in str(e).lower() or "timeout" in str(e).lower():
                        msg = f"{str(e)}, Retrying {func.__name__} in {mdelay} seconds..."
                        logger.warning(msg)
                        
                        time.sleep(mdelay)
                        mtries -= 1
                        mdelay *= backoff
                    else:
                        # If not a rate limit or timeout error, don't retry
                        logger.error(f"Error not eligible for retry in {func.__name__}: {str(e)}")
                        raise
                        
            # Final attempt
            return func(*args, **kwargs)
            
        return wrapper
    return decorator

def handle_api_error(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator for handling API errors with detailed logging.
    
    Args:
        func: Function to decorate
        
    Returns:
        Decorated function with error handling
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Dict[str, Any]) -> T:
        logger = get_logger(func.__module__)
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Log detailed error
            logger.error(f"API Error in {func.__name__}: {str(e)}", exc_info=True)
            
            # Return a graceful error message instead of failing
            if func.__annotations__.get('return') == dict:
                return {"error": str(e), "status": "failed"}
            else:
                return f"Error: {str(e)}"
                
    return wrapper

class ErrorCollection:
    """
    Collect and track errors during batch processing.
    """
    def __init__(self):
        self.errors = []
        self.logger = get_logger("error_collection")
        
    def add(self, context: str, error: Exception, fatal: bool = False) -> None:
        """
        Add an error to the collection.
        
        Args:
            context: Description of where the error occurred
            error: The exception that was raised
            fatal: Whether this error should be considered fatal
        """
        error_info = {
            "context": context,
            "error": str(error),
            "type": type(error).__name__,
            "fatal": fatal
        }
        
        self.errors.append(error_info)
        
        if fatal:
            self.logger.error(f"FATAL ERROR in {context}: {str(error)}")
        else:
            self.logger.warning(f"Error in {context}: {str(error)}")
            
    def has_errors(self) -> bool:
        """Check if any errors have been collected."""
        return len(self.errors) > 0
        
    def has_fatal_errors(self) -> bool:
        """Check if any fatal errors have been collected."""
        return any(e["fatal"] for e in self.errors)
        
    def get_summary(self) -> str:
        """Get a summary of all collected errors."""
        if not self.has_errors():
            return "No errors"
            
        summary = f"Collected {len(self.errors)} errors:\n"
        for i, error in enumerate(self.errors):
            fatal_marker = "[FATAL] " if error["fatal"] else ""
            summary += f"{i+1}. {fatal_marker}{error['context']}: {error['type']} - {error['error']}\n"
            
        return summary
