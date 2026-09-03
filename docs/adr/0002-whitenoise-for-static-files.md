# Serve static files with WhiteNoise, not the reverse proxy

Gunicorn serves collected static files itself via WhiteNoise middleware, rather than having the host's reverse proxy read them from a mounted volume. This avoids any change to the existing reverse proxy config, at the cost of static assets passing through the Django process instead of being served directly by the proxy — an acceptable trade-off at this site's traffic level.
