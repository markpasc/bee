from django.conf.urls.defaults import patterns, include, url


urlpatterns = patterns('bee.views',
    url(r'^$', 'index', name='index'),
    url(r'^before/(?P<before>[\w-]+)$', 'index',
        {'template_name': 'index_before.html'}, name='index_before'),
    url(r'^(?P<year>\d{4})/(?P<month>\d\d)/(?P<day>\d\d)/$', 'day', name='day'),
    url(r'^feed/$', 'feed', name='feed'),
    url(r'^search/$', 'search', name='search'),
    url(r'^archive/$', 'archive', name='archive'),
    url(r'^archive/data/$', 'archivedata', name='archivedata'),
    url(r'^(?P<slug>[\w-]+)$', 'permalink', name='permalink'),

    url(r'^_/editor$', 'editor', name='editor'),
    url(r'^_/edit$', 'edit'),
    url(r'^_/comments/', include('django.contrib.comments.urls')),
)

urlpatterns += patterns('django.contrib.auth.views',
    url(r'^signin/$', 'login', {'template_name': 'accounts/signin.html'}, name='signin'),
    url(r'^signout/$', 'logout', {'template_name': 'accounts/signed_out.html'}, name='signout'),
)
