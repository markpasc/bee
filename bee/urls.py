from django.conf.urls.defaults import patterns, include, url


urlpatterns = patterns('bee.views',
    url(r'^$', 'index'),
    url(r'^_/editor', 'editor', name='editor'),
    url(r'^_/edit', 'edit'),

    url(r'^(?P<slug>[\w-]+)$', 'permalink'),
)
