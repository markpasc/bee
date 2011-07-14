from datetime import datetime
from functools import wraps
import json
import logging

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest, HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import render
from django.utils import feedgenerator
from haystack.query import SearchQuerySet
import haystack.views

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

        for datefield in (u'published', u'updated'):
            datevalue = item.get(datefield)
            if datevalue is not None:
                handler.addQuickElement(datefield, feedgenerator.rfc3339_date(datevalue).decode('utf-8'))

        content_html = item.get('content_html')
        if content_html is not None:
            handler.addQuickElement(u'content', content_html, {u'type': u'html'})


@author_site
def feed(request, author=None):
    author_name = ' '.join(filter(None, (author.first_name, author.last_name)))
    index_url = request.build_absolute_uri(reverse('index'))
    # TODO: use the author's site instead of hardcoding for me?
    feed_id = 'tag:bestendtimesever.com,2009:%s' % author.username

    feed = RealAtomFeed(title=author.username, link=index_url, description=None,
        author_email=author.email, author_name=author_name, author_link=index_url,
        feed_url=request.build_absolute_uri(), feed_guid=feed_id)

    posts = posts_for_request(request, author)
    posts = posts.filter(published__lt=datetime.utcnow()).order_by('-published')
    posts = posts[:20]

    for post in posts:
        post_url = request.build_absolute_uri(reverse('permalink', kwargs={'slug': post.slug}))
        feed.add_item(title=post.title, link=post_url, description=None,
            unique_id=post.atom_id, updated=post.modified, published=post.published,
            content_html=post.html)

    return HttpResponse(feed.writeString('utf-8'), content_type=feed.mime_type)


class PostSearch(haystack.views.SearchView):

    def build_form(self, form_kwargs=None):
        log = logging.getLogger('.'.join((__name__, 'PostSearch')))
        request = self.request

        log.debug("which author has domain %r?", request.META['HTTP_HOST'])
        try:
            author = User.objects.get(authorsite__site__domain=request.META['HTTP_HOST'])
        except User.DoesNotExist:
            log.debug("    no such author! no results at all!")
            sqs = SearchQuerySet().none()
        else:
            sqs = SearchQuerySet().filter(author_pk=author.pk)
            # What visibility of posts can the searcher see?
            if request.user.is_anonymous():
                log.debug("    viewer is anonymous, so only %s's public posts", author.username)
                sqs = sqs.filter(private=0)
            elif request.user.pk == author.pk:
                log.debug("    viewer is %s, so all their posts", author.username)
            else:
                # TODO: honor trust groups instead of giving everyone else only public posts
                log.debug("    viewer is logged in as somebody else, so only %s's public posts", author.username)
                sqs = sqs.filter(private=0)

        self.searchqueryset = sqs

        return super(PostSearch, self).build_form(form_kwargs)


search = PostSearch()


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
