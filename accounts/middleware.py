class FriendlyErrorMiddleware:
    """Show recoverable, safe errors for failed page and JSON requests."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (response.status_code >= 400
                and not getattr(response, 'streaming', False)
                and response.get('Content-Type', '').startswith('text/html')
                and request.headers.get('Sec-Fetch-Dest', '') in ('', 'document')
                and not request.path.startswith(('/static/', '/media/'))
                and b'servinn-error-dialog' not in response.content):
            replacement = self.error_response(request, response.status_code)
            for header in ('Allow', 'Retry-After'):
                if response.has_header(header):
                    replacement[header] = response[header]
            return replacement
        return response

    def process_exception(self, request, exception):
        from django.http import Http404
        from django.core.exceptions import PermissionDenied, SuspiciousOperation
        if isinstance(exception, (Http404, PermissionDenied, SuspiciousOperation)):
            return None
        import logging
        logging.getLogger(__name__).error('Request failed (%s); user receives a recovery popup.', type(exception).__name__)
        return self.error_response(request, 503)

    @staticmethod
    def error_response(request, status):
        import json
        from django.http import JsonResponse
        from django.shortcuts import render
        messages = {
            400: 'Some submitted details could not be processed. Return to the form and check your information.',
            403: 'Your session or security token is no longer valid. Return to the page, refresh it, and try again.',
            404: 'This page or item is unavailable. It may have moved or been removed. Return to SERVINN to continue.',
            405: 'This action cannot be opened directly. Return to the previous page and use its form or button.',
            429: 'Too many requests were made. Please wait a moment before trying again.',
        }
        message = messages.get(status, 'The service is temporarily unavailable. Your request may have completed; check its status before submitting again.')
        if request.content_type == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            response = JsonResponse({'message': message}, status=status)
        else:
            from django.utils.http import url_has_allowed_host_and_scheme
            previous = request.headers.get('Referer', '')
            return_url = previous if url_has_allowed_host_and_scheme(previous, {request.get_host()}, require_https=request.is_secure()) else '/'
            response = render(request, 'error.html', {'error_message': message, 'error_message_json': json.dumps(message), 'return_url': return_url}, status=status)
        response['Cache-Control'] = 'no-store'
        return response
