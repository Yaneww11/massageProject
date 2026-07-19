from massageProject.main_app.models import HomePage, BusinessInfo

def admin_branding(request):
    try:
        homepage = HomePage.get_solo()
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
        business_info = BusinessInfo.objects.first()
    except Exception:
        business_info = None

    return {
        'brand_name': brand_name,
        'brand_logo': brand_logo,
        'footer_tagline': footer_tagline,
        'business_info': business_info,
    }
