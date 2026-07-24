from django.core.cache import cache

from massageProject.main_app.models import HomePage, BusinessInfo, SiteConfiguration

HOMEPAGE_CACHE_KEY = 'homepage_singleton'
BUSINESS_INFO_CACHE_KEY = 'business_info_singleton'


def get_cached_homepage():
    homepage = cache.get(HOMEPAGE_CACHE_KEY)
    if homepage is None:
        homepage = HomePage.get_solo()
        # Same 60s cross-worker-staleness bound as site_configuration below.
        cache.set(HOMEPAGE_CACHE_KEY, homepage, 60)
    return homepage


def get_cached_business_info():
    business_info = cache.get(BUSINESS_INFO_CACHE_KEY)
    if business_info is None:
        business_info = BusinessInfo.objects.first()
        cache.set(BUSINESS_INFO_CACHE_KEY, business_info, 60)
    return business_info


def admin_branding(request):
    try:
        homepage = get_cached_homepage()
        brand_name = homepage.brand_name
        brand_logo = homepage.logo.url if homepage.logo else None
        footer_tagline = homepage.footer_tagline
    except Exception:
        brand_name = 'Relax & Health'
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
        'brand_logo': brand_logo,
        'footer_tagline': footer_tagline,
        'business_info': business_info,
    }


def site_configuration(request):
    site_config = cache.get('site_configuration')
    if site_config is None:
        site_config = SiteConfiguration.get_solo()
        # 60s bound: caps cross-worker staleness in a multi-process deploy
        # (the post_save signal only invalidates the worker that saved).
        cache.set('site_configuration', site_config, 60)
    return {'site_config': site_config}
