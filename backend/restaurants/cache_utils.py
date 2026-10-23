from django.core.cache import cache


def get_cache_generation(namespace):
    key = f"foodflow:generation:{namespace}"

    # Initialize the generation if it doesn't exist.
    cache.add(key, 1, timeout=None)

    return cache.get(key, 1)


def invalidate_cache(namespace):
    key = f"foodflow:generation:{namespace}"

    cache.add(key, 1, timeout=None)

    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 2, timeout=None)