from datetime import datetime
from functools import wraps
import json
import logging

from django.contrib.auth.models import User
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest, HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import render

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
    # TODO: is there a better place to put this biz logic?
    if request.user.is_anonymous():
        posts = author.posts_authored.filter(private=False)
    elif request.user.pk == author.pk:
        posts = author.posts_authored.all()
    else:
        is_public = Q(private=False)
        shared_with_user = Q(private_to__members__user=request.user)
        posts = author.posts_authored.filter(is_public | shared_with_user)

    posts = posts.filter(published__lt=datetime.utcnow()).order_by('-published')

    data = {
        'author': author,
        'posts': posts[:10],
    }
    return render(request, 'index.html', data)


@author_site
def permalink(request, slug, author=None):
    try:
        post = author.posts_authored.get(slug=slug)
    except Post.DoesNotExist:
        return HttpResponseNotFound('No such post %r' % slug)

    if not post.visible_to(request.user):
        logging.info("Author %s's post %s is not visible to viewer %r, pretending 404",
            author.username, slug, request.user)
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
        # TODO: build this tag from the author's site domain
        post.atom_id = 'tag:butt:%d:%s' % (post.author.pk, post.slug)
        post.save()

        return HttpResponse(json.dumps({'id': post.pk, 'permalink': post.permalink}))

    return HttpResponseBadRequest(json.dumps(form.errors), content_type='application/json')
