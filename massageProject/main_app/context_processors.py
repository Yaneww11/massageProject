from massageProject.main_app.models import HomePage, MessageStudio

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
        studio = MessageStudio.objects.first()
    except Exception:
        studio = None

    return {
        'brand_name': brand_name,
        'brand_logo': brand_logo,
        'footer_tagline': footer_tagline,
        'studio': studio,
    }
