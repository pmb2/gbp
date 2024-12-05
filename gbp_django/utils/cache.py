from django.core.cache import cache
from functools import wraps

def cache_on_arguments(timeout=300):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create a more robust cache key
            key_parts = [
                func.__module__,
                func.__name__,
                ":".join(str(arg) for arg in args),
                ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
            ]
            key = "cache:" + ":".join(key_parts)
            
            result = cache.get(key)
            if result is None:
                result = func(*args, **kwargs)
                if result is not None:  # Only cache non-None results
                    cache.set(key, result, timeout)
            return result
        return wrapper
    return decorator

def invalidate_cache(pattern):
    """
    Invalidate cache entries matching a pattern
    """
    keys = cache.keys(f"cache:{pattern}*")
    cache.delete_many(keys)
