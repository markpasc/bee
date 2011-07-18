from django.conf import settings


def sitecodes(request):
    return {
        'googleanalytics': getattr(settings, 'GOOGLEANALYTICS', None),
    }
