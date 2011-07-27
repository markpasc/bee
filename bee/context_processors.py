from django.conf import settings


def current_url(request):
    return {
        'current_url': request.build_absolute_uri(),
        'current_path': request.get_full_path(),
    }


def sitecodes(request):
    return {
        'googleanalytics': getattr(settings, 'GOOGLEANALYTICS', None),
    }
