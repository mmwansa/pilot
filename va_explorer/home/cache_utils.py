from django.core.cache import cache


HOME_DASHBOARD_FASTPATH_VERSION_KEY = "home_dashboard_fastpath:version"


def get_home_dashboard_fastpath_version() -> int:
    version = cache.get(HOME_DASHBOARD_FASTPATH_VERSION_KEY)
    if version is None:
        version = 1
        cache.set(HOME_DASHBOARD_FASTPATH_VERSION_KEY, version, timeout=None)
    return int(version)


def bump_home_dashboard_fastpath_version() -> int:
    version = cache.get(HOME_DASHBOARD_FASTPATH_VERSION_KEY)
    if version is None:
        version = 1
    next_version = int(version) + 1
    cache.set(HOME_DASHBOARD_FASTPATH_VERSION_KEY, next_version, timeout=None)
    return next_version
