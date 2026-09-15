from django.core.cache import cache

from massageProject.main_app.models import HomePage, BusinessInfo, SiteConfiguration

HOMEPAGE_CACHE_KEY = 'homepage_singleton'
BUSINESS_INFO_CACHE_KEY = 'business_info_singleton'
SITE_CONFIGURATION_CACHE_KEY = 'site_configuration'

# Caps cross-worker staleness in a multi-process deploy: the invalidation
# signals only clear the cache in the worker that handled the write, so every
# other worker keeps serving its entry until this expires.
SINGLETON_CACHE_TTL = 60


def get_cached_homepage():
    homepage = cache.get(HOMEPAGE_CACHE_KEY)
    if homepage is None:
        homepage = HomePage.get_solo()
        cache.set(HOMEPAGE_CACHE_KEY, homepage, SINGLETON_CACHE_TTL)
    return homepage


def get_cached_business_info():
    business_info = cache.get(BUSINESS_INFO_CACHE_KEY)
    if business_info is None:
        business_info = BusinessInfo.objects.first()
        cache.set(BUSINESS_INFO_CACHE_KEY, business_info, SINGLETON_CACHE_TTL)
    return business_info


def admin_branding(request):
    try:
        homepage = get_cached_homepage()
        brand_name = homepage.brand_name_plain
        brand_name_html = homepage.brand_name
        brand_logo = homepage.logo.url if homepage.logo else None
        footer_tagline = homepage.footer_tagline
    except Exception:
        brand_name = 'Relax & Health'
        brand_name_html = 'Relax & Health'
        brand_logo = None
        footer_tagline = ''

    request.brand_name = brand_name
    request.brand_logo = brand_logo

    try:
        business_info = get_cached_business_info()
    except Exception:
        business_info = None

    return {
        'brand_name': brand_name,
        'brand_name_html': brand_name_html,
        'brand_logo': brand_logo,
        'footer_tagline': footer_tagline,
        'business_info': business_info,
    }


def site_configuration(request):
    site_config = cache.get(SITE_CONFIGURATION_CACHE_KEY)
    if site_config is None:
        site_config = SiteConfiguration.get_solo()
        cache.set(SITE_CONFIGURATION_CACHE_KEY, site_config, SINGLETON_CACHE_TTL)
    return {'site_config': site_config}
