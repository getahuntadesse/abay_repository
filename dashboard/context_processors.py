from django.conf import settings

def app_context(request):
    return {
        'APP_NAME': settings.APP_NAME,
        'APP_VERSION': settings.APP_VERSION,
    }