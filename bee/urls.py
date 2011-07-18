from django.conf.urls.defaults import patterns, include, url


urlpatterns = patterns('bee.views',
    url(r'^$', 'index', name='index'),
    url(r'^before/(?P<before>[\w-]+)$', 'index', name='index_before'),
    url(r'^feed/$', 'feed', name='feed'),
    url(r'^search/$', 'search', name='search'),
    url(r'^(?P<slug>[\w-]+)$', 'permalink', name='permalink'),

    url(r'^_/editor$', 'editor', name='editor'),
    url(r'^_/edit$', 'edit'),
    url(r'^_/comments/', include('django.contrib.comments.urls')),
)
