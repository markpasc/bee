from django.conf.urls.defaults import patterns, include, url


urlpatterns = patterns('bee.views',
    url(r'^$', 'index', name='index'),
    url(r'^feed/$', 'feed', name='feed'),
    url(r'^_/editor', 'editor', name='editor'),
    url(r'^_/edit', 'edit'),

    url(r'^(?P<slug>[\w-]+)$', 'permalink', name='permalink'),
)
