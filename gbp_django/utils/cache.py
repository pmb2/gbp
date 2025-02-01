import hashlib
from functools import wraps
from django.core.cache import cache

def cache_on_arguments(timeout=300):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Exclude access_token from cache key or hash it
            key_parts = [func.__module__, func.__name__]

            # Process args, replace access_token with its hash
            processed_args = []
            for arg in args:
                if isinstance(arg, str) and len(arg) > 100:
                    arg_hash = hashlib.sha256(arg.encode('utf-8')).hexdigest()[:10]
                    processed_args.append(f"<hashed:{arg_hash}>")
                else:
                    processed_args.append(str(arg))

            # Process kwargs similarly
            processed_kwargs = {}
            for k, v in kwargs.items():
                if k == 'access_token':
                    v_hash = hashlib.sha256(v.encode('utf-8')).hexdigest()[:10]
                    processed_kwargs[k] = f"<hashed:{v_hash}>"
                else:
                    processed_kwargs[k] = v

            key_parts.extend(processed_args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(processed_kwargs.items()))
            key = "cache:" + ":".join(key_parts)

            # Truncate the key if necessary
            if len(key) > 200:
                key = "cache:" + hashlib.sha256(key.encode('utf-8')).hexdigest()

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
