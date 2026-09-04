from django.utils.translation import gettext_lazy as _


def _relative_luminance(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    r, g, b = (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def on_color(bg_hex):
    """Pick black or white text for legibility against bg_hex."""
    return '#000000' if _relative_luminance(bg_hex) > 0.179 else '#FFFFFF'


def contrast_ratio(hex1, hex2):
    l1, l2 = sorted((_relative_luminance(hex1), _relative_luminance(hex2)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


FONT_PAIRS = {
    'playfair_montserrat': {
        'google_fonts_url': (
            'https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700'
            '&family=Montserrat:wght@300;400;500;600&display=swap'
        ),
        'heading_family': "'Playfair Display', serif",
        'body_family': "'Montserrat', sans-serif",
    },
    'cormorant_lato': {
        'google_fonts_url': (
            'https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;600;700'
            '&family=Lato:wght@300;400;700&display=swap'
        ),
        'heading_family': "'Cormorant Garamond', serif",
        'body_family': "'Lato', sans-serif",
    },
    'poppins_opensans': {
        'google_fonts_url': (
            'https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700'
            '&family=Open+Sans:wght@300;400;600&display=swap'
        ),
        'heading_family': "'Poppins', sans-serif",
        'body_family': "'Open Sans', sans-serif",
    },
    'merriweather_sourcesans': {
        'google_fonts_url': (
            'https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700'
            '&family=Source+Sans+3:wght@300;400;600&display=swap'
        ),
        'heading_family': "'Merriweather', serif",
        'body_family': "'Source Sans 3', sans-serif",
    },
    'raleway_roboto': {
        'google_fonts_url': (
            'https://fonts.googleapis.com/css2?family=Raleway:wght@400;600;700'
            '&family=Roboto:wght@300;400;500&display=swap'
        ),
        'heading_family': "'Raleway', sans-serif",
        'body_family': "'Roboto', sans-serif",
    },
    'yeseva_ptsans': {
        'google_fonts_url': (
            'https://fonts.googleapis.com/css2?family=Yeseva+One'
            '&family=PT+Sans:wght@400;700&display=swap'
        ),
        'heading_family': "'Yeseva One', serif",
        'body_family': "'PT Sans', sans-serif",
    },
    'alegreya_alegreyasans': {
        'google_fonts_url': (
            'https://fonts.googleapis.com/css2?family=Alegreya:wght@400;600;700'
            '&family=Alegreya+Sans:wght@400;700&display=swap'
        ),
        'heading_family': "'Alegreya', serif",
        'body_family': "'Alegreya Sans', sans-serif",
    },
    'cormorant_ptsans': {
        'google_fonts_url': (
            'https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;600;700'
            '&family=PT+Sans:wght@400;700&display=swap'
        ),
        'heading_family': "'Cormorant Garamond', serif",
        'body_family': "'PT Sans', sans-serif",
    },
    'philosopher_manrope': {
        'google_fonts_url': (
            'https://fonts.googleapis.com/css2?family=Philosopher:wght@400;700'
            '&family=Manrope:wght@400;500;600;700&display=swap'
        ),
        'heading_family': "'Philosopher', sans-serif",
        'body_family': "'Manrope', sans-serif",
    },
    'oldstandard_nunitosans': {
        'google_fonts_url': (
            'https://fonts.googleapis.com/css2?family=Old+Standard+TT:wght@400;700'
            '&family=Nunito+Sans:wght@400;600;700&display=swap'
        ),
        'heading_family': "'Old Standard TT', serif",
        'body_family': "'Nunito Sans', sans-serif",
    },
}

COLOR_PRESETS = {
    'warm_earth': {
        'label': _('Топла земя'),
        'primary_color': '#4A3728', 'primary_light_color': '#6D5442',
        'secondary_color': '#C2A38E', 'accent_color': '#8E735B',
        'background_color': '#FAF7F2', 'text_color': '#2D241E',
        'text_muted_color': '#6B5E55', 'border_color': '#4A3728',
    },
    'ocean': {
        'label': _('Океан'),
        'primary_color': '#1B4B5A', 'primary_light_color': '#2C7A96',
        'secondary_color': '#7FB8C4', 'accent_color': '#E07A5F',
        'background_color': '#F5FAFA', 'text_color': '#16323A',
        'text_muted_color': '#4A6670', 'border_color': '#1B4B5A',
    },
    'monochrome': {
        'label': _('Монохром'),
        'primary_color': '#2B2B2B', 'primary_light_color': '#4A4A4A',
        'secondary_color': '#8A8A8A', 'accent_color': '#C9A227',
        'background_color': '#FAFAFA', 'text_color': '#1A1A1A',
        'text_muted_color': '#6B6B6B', 'border_color': '#2B2B2B',
    },
    'forest': {
        'label': _('Гора'),
        'primary_color': '#3B4F3A', 'primary_light_color': '#587556',
        'secondary_color': '#A8B99F', 'accent_color': '#C97B4A',
        'background_color': '#F7F8F3', 'text_color': '#24301F',
        'text_muted_color': '#5C6B54', 'border_color': '#3B4F3A',
    },
    'rose': {
        'label': _('Розово'),
        'primary_color': '#7A3B4E', 'primary_light_color': '#8F4D62',
        'secondary_color': '#E8B4C0', 'accent_color': '#4A7A6E',
        'background_color': '#FDF6F7', 'text_color': '#331A21',
        'text_muted_color': '#6E4A52', 'border_color': '#7A3B4E',
    },
    'neon_night': {
        'label': _('Неон нощ'),
        'primary_color': '#0D0D10', 'primary_light_color': '#2E2E36',
        'secondary_color': '#9497A6', 'accent_color': '#E6007E',
        'background_color': '#F7F7F9', 'text_color': '#0D0D10',
        'text_muted_color': '#5B5D66', 'border_color': '#0D0D10',
    },
    'pastel_duo': {
        'label': _('Пастелен дует'),
        'primary_color': '#3E6E88', 'primary_light_color': '#5C8BA3',
        'secondary_color': '#B9E8D5', 'accent_color': '#B84E32',
        'background_color': '#F7FBFC', 'text_color': '#1C2B31',
        'text_muted_color': '#51636A', 'border_color': '#3E6E88',
    },
    'emerald_jewel': {
        'label': _('Изумруд'),
        'primary_color': '#0B4A3A', 'primary_light_color': '#146B54',
        'secondary_color': '#C9A227', 'accent_color': '#8F6509',
        'background_color': '#F8F9F4', 'text_color': '#132621',
        'text_muted_color': '#4E6660', 'border_color': '#0B4A3A',
    },
    'sunset': {
        'label': _('Залез'),
        'primary_color': '#C1440E', 'primary_light_color': '#E0651F',
        'secondary_color': '#F2A65A', 'accent_color': '#8E2A6B',
        'background_color': '#FDF8F4', 'text_color': '#3A231C',
        'text_muted_color': '#7A5A4C', 'border_color': '#C1440E',
    },
}

STYLE_PRESETS = {
    'soft': {
        'radius_sm': '4px',
        'radius_md': '8px',
        'radius_lg': '16px',
        'shadow_sm': '0 2px 4px rgba(0,0,0,0.05)',
        'shadow_md': '0 4px 12px rgba(0,0,0,0.1)',
        'shadow_lg': '0 10px 25px rgba(0,0,0,0.15)',
    },
    'sharp': {
        'radius_sm': '0px',
        'radius_md': '0px',
        'radius_lg': '0px',
        'shadow_sm': 'none',
        'shadow_md': '0 1px 2px rgba(0,0,0,0.08)',
        'shadow_lg': '0 2px 4px rgba(0,0,0,0.1)',
    },
    'round': {
        'radius_sm': '8px',
        'radius_md': '16px',
        'radius_lg': '32px',
        'shadow_sm': '0 2px 6px rgba(0,0,0,0.08)',
        'shadow_md': '0 6px 16px rgba(0,0,0,0.12)',
        'shadow_lg': '0 14px 32px rgba(0,0,0,0.18)',
    },
}
