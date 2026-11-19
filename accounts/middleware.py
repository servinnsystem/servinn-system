class GooglePopupPolicyMiddleware:
    """Allow Google's OAuth popup to communicate with its sign-in page."""
    popup_pages = {'accounts_home', 'login', 'register', 'register_seeker', 'register_employer'}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        match = getattr(request, 'resolver_match', None)
        if (match and match.url_name in self.popup_pages
                and response.get('Content-Type', '').startswith('text/html')):
            response['Cross-Origin-Opener-Policy'] = 'same-origin-allow-popups'
        return response
