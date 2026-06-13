from massageProject.main_app.models import HomePage

def admin_branding(request):
    """
    Returns the brand name and logo from the HomePage singleton.
    Also attaches them to the request object for use in settings callables if needed,
    and returns them for use in templates.
    """
    try:
        homepage = HomePage.get_solo()
        brand_name = homepage.brand_name
        brand_logo = homepage.logo.url if homepage.logo else None
    except Exception:
        brand_name = 'Relax & Health'
        brand_logo = None
    
    # Attach to request for potential use in settings (though we'll prefer template)
    request.brand_name = brand_name
    request.brand_logo = brand_logo
    
    return {
        'brand_name': brand_name,
        'brand_logo': brand_logo,
    }
