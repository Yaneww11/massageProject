from massageProject.main_app.models import HomePage, BusinessInfo, SiteConfiguration


def get_homepage():
    return HomePage.get_solo()


def get_business_info():
    return BusinessInfo.objects.first()


def admin_branding(request):
    try:
        homepage = get_homepage()
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
        business_info = get_business_info()
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
    return {'site_config': SiteConfiguration.get_solo()}
