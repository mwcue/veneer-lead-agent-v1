# utils/error_handler.py
import time
import logging
import functools
from typing import Callable, Any, TypeVar, Dict

# Type variable for generic function return type
T = TypeVar('T')

logger = logging.getLogger(__name__)

def retry(max_attempts=3, delay=2, backoff=2, exceptions=(Exception,)):
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
            mtries, mdelay = max_attempts, delay
            
            while mtries > 1:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    # Check if the exception is retriable
                    if "rate limit" in str(e).lower() or "timeout" in str(e).lower():
                        msg = f"{str(e)}, Retrying in {mdelay} seconds..."
                        logger.warning(msg)
                        
                        time.sleep(mdelay)
                        mtries -= 1
                        mdelay *= backoff
                    else:
                        # If not a rate limit or timeout error, don't retry
                        logger.error(f"Error not eligible for retry: {str(e)}")
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
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Log detailed error
            logger.error(f"API Error in {func.__name__}: {str(e)}", exc_info=True)
            
            # Return a graceful error message instead of failing
            # This assumes functions return strings or dicts - adjust as needed
            if func.__annotations__.get('return') == dict:
                return {"error": str(e), "status": "failed"}
            else:
                return f"Error: {str(e)}"
                
    return wrapper
