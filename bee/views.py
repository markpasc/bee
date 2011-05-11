from functools import wraps
import json

from django.contrib.auth.models import User
from django.http import HttpResponse, HttpResponseNotFound, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import render
import pystache

from bee.models import Post, Template
from bee.forms import PostForm


def author_site(fn):
    @wraps(fn)
    def moo(request, *args, **kwargs):
        try:
            print request.META['HTTP_HOST']
            author = User.objects.get(authorsite__site__domain=request.META['HTTP_HOST'])
        except User.DoesNotExist:
            return HttpResponseNotFound('No author selected')
        kwargs['author'] = author

        return fn(request, *args, **kwargs)
    return moo


@author_site
def index(request, author=None):
    posts = author.posts_authored.all()[:10]
    data = {
        'author': author,
        'posts': posts,
    }

    return render(request, 'index.html', data)


@author_site
def permalink(request, slug, author=None):
    try:
        post = author.posts_authored.get(slug=slug)
    except Post.DoesNotExist:
        return HttpResponseNotFound('No such post %r' % slug)

    data = {
        'author': author,
        'post': post,
    }

    return render(request, 'permalink.html', data)


@author_site
def edit(request, author=None):
    if request.user.pk != author.pk:
        return HttpResponseForbidden('Not your site!')

    if 'id' in request.POST:
        post = Post.objects.get(pk=request.POST['id'])
    else:
        post = Post(author=author)

    form = PostForm(request.POST, instance=post)
    if form.is_valid():
        post = form.save(commit=False)
        post.atom_id = 'tag:butt:%d:%s' % (post.author.pk, post.slug)
        post.save()
        return HttpResponseRedirect(post.permalink)

    return HttpResponseForbidden(json.dumps(form.errors), content_type='text/plain')
