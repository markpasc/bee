from functools import wraps

from django.contrib.auth.models import User
from django.http import HttpResponse, HttpResponseNotFound
from django.shortcuts import render
import pystache

from bee.models import Post, Template


def author_site(fn):
    @wraps(fn)
    def moo(request, *args, **kwargs):
        try:
            author = User.objects.get(authorsite__site__domain=request.META['HTTP_HOST'])
        except User.DoesNotExist:
            pass
        else:
            kwargs['author'] = author

        return fn(request, *args, **kwargs)
    return moo


@author_site
def index(request, author=None):
    if author is None:
        return HttpResponseNotFound('No author selected')

    posts = author.posts_authored.all()[:10]
    data = {
        'author': author,
        'posts': posts,
    }

    return render(request, 'index.html', data)


@author_site
def permalink(request, slug, author=None):
    if author is None:
        return HttpResponseNotFound('No author selected')

    try:
        post = author.posts_authored.get(slug=slug)
    except Post.DoesNotExist:
        return HttpResponseNotFound('No such post %r' % slug)

    data = {
        'author': author,
        'post': post,
    }

    return render(request, 'permalink.html', data)
