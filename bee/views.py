from datetime import datetime
from functools import wraps
import json
import logging

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest, HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import render
from django.utils import feedgenerator

from bee.models import Post, Template
from bee.forms import PostForm


def author_site(fn):
    @wraps(fn)
    def moo(request, *args, **kwargs):
        try:
            author = User.objects.get(authorsite__site__domain=request.META['HTTP_HOST'])
        except User.DoesNotExist:
            return HttpResponseNotFound('No author selected')
        kwargs['author'] = author

        return fn(request, *args, **kwargs)
    return moo


def author_only(fn):
    @wraps(fn)
    def moo(request, *args, **kwargs):
        try:
            author = kwargs['author']
        except KeyError:
            raise ValueError("View requires @author_only but is not for the @author_site")

        if request.user.pk != author.pk:
            return HttpResponseForbidden('Not your site!', content_type='text/plain')

        return fn(request, *args, **kwargs)
    return moo


def posts_for_request(request, author):
    if request.user.is_anonymous():
        return author.posts_authored.filter(private=False)

    if request.user.pk == author.pk:
        return author.posts_authored.all()

    is_public = Q(private=False)
    shared_with_user = Q(private_to__members__user=request.user)
    return author.posts_authored.filter(is_public | shared_with_user)


@author_site
def index(request, author=None):
    # TODO: is there a better place to put this biz logic?
    posts = posts_for_request(request, author)
    posts = posts.filter(published__lt=datetime.utcnow()).order_by('-published')

    data = {
        'author': author,
        'posts': posts[:10],
    }
    return render(request, 'index.html', data)


class RealAtomFeed(feedgenerator.Atom1Feed):

    def add_item_elements(self, handler, item):
        super(RealAtomFeed, self).add_item_elements(handler, item)

        created_date = item.get('createddate', item.get('pubdate'))
        if created_date is not None:
            handler.addQuickElement(u'published', feedgenerator.rfc3339_date(created_date).decode('utf-8'))


@author_site
def feed(request, author=None):
    author_name = ' '.join(filter(None, (author.first_name, author.last_name)))
    index_url = request.build_absolute_uri(reverse('index'))
    # TODO: use the author's site instead of hardcoding for me?
    feed_id = 'tag:bestendtimesever.com,2009:%s' % author.username

    feed = RealAtomFeed(title=author.username, link=index_url, description='',
        author_email=author.email, author_name=author_name, author_link=index_url,
        feed_url=request.build_absolute_uri(), feed_guid=feed_id)

    posts = posts_for_request(request, author)
    posts = posts.filter(published__lt=datetime.utcnow()).order_by('-published')
    posts = posts[:20]

    for post in posts:
        post_url = request.build_absolute_uri(reverse('permalink', kwargs={'slug': post.slug}))
        feed.add_item(title=post.title, link=post_url, description=post.html,
            pubdate=post.modified, unique_id=post.atom_id, createddate=post.published)

    return HttpResponse(feed.writeString('utf-8'), content_type='application/atom+xml')


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
@author_only
def editor(request, author=None):
    data = {}

    post_id = request.GET.get('post')
    if post_id is not None:
        post = Post.objects.get(pk=int(post_id))
        if post.author.pk != author.pk:
            return HttpResponseForbidden("Post %s is not your post" % post_id)
        data['post'] = post

    return render(request, 'editor.html', data)


@author_site
@author_only
def edit(request, author=None):
    if 'id' in request.POST:
        post = Post.objects.get(pk=request.POST['id'])
    else:
        post = Post(author=author)

    form = PostForm(request.POST, instance=post)
    if form.is_valid():
        post = form.save(commit=False)
        # TODO: build this tag from the author's site domain
        if not post.atom_id:
            post.atom_id = 'tag:bestendtimesever.com,2009:%s,%s' % (post.author.username, post.slug)
        post.save()

        return HttpResponse(json.dumps({'id': post.pk, 'permalink': post.permalink}))

    return HttpResponseBadRequest(json.dumps(form.errors), content_type='application/json')
