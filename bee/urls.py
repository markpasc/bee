from django.conf.urls.defaults import patterns, include, url


urlpatterns = patterns('bee.views',
    url(r'^$', 'index'),
    url(r'^(?P<slug>\w+)$', 'permalink'),
)
