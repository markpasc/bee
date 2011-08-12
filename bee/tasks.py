from datetime import date, datetime, timedelta
import logging
from urlparse import urlsplit, urlunsplit, urljoin

from BeautifulSoup import BeautifulSoup
from celery.decorators import task
import httplib2

import bee.models


log = logging.getLogger(__name__)


@task()
def add(x, y):
    return x + y


@task()
def perform_for_author_posts_in_month(author_pk, year, month, callback):
    """
    Dispatch the callback with the PK of each post by the given author in the
    given month.
    """
    start_date = datetime(year, month, 1, 0, 0, 0)
    end_date = (start_date + timedelta(days=31)).replace(day=1)

    posts = bee.models.Post.objects.filter(author=author_pk, published__gte=start_date, published__lt=end_date)
    for post_pk in posts.values_list('pk', flat=True):
        callback.delay(post_pk)


@task()
def perform_for_author_posts(author_pk, callback):
    """
    Dispatch `perform_for_author_posts_in_month` tasks for the given author
    and callback in each month for which the author has posts.
    """
    author_posts = bee.models.Post.objects.filter(author=author_pk).values_list('published', flat=True)
    start_date = author_posts.order_by('published')[0]
    end_date = author_posts.order_by('-published')[0]

    end_month = date(end_date.year, end_date.month, 1)
    month = date(start_date.year, start_date.month, 1)
    while month <= end_month:
        perform_for_author_posts_in_month.delay(author_pk, month.year, month.month, callback)
        month = (month + timedelta(days=31)).replace(day=1)


@task()
def find_404s_in_post(post_pk, author_domain):
    """
    Record any <a href> or <img src> links in the given post that have 404s as
    `Link404Result` instances in the database.
    """
    try:
        post = bee.models.Post.objects.values('html').get(pk=post_pk)
    except bee.models.Post.DoesNotExist:
        return

    author_url = urlunsplit(('http', author_domain, '/', '', ''))

    http = httplib2.Http(timeout=10)
    root = BeautifulSoup(post['html'])
    for link in root.findAll(['a', 'img']):
        link_url = urljoin(author_url, link.get('href' if link.name == 'a' else 'src'))
        if urlsplit(link_url).netloc == author_domain:
            continue

        try:
            resp, cont = http.request(link_url, method='HEAD', headers={'User-Agent': 'bee/1.0'})
        except Exception, exc:
            log.info('Error fetching %s', link_url)
            bee.models.Link404Result.objects.create(post_id=post_pk, url=link_url, status=0, error=str(exc))
            continue

        if resp.status == 405:
            try:
                resp, cont = http.request(link_url, method='GET', headers={'User-Agent': 'bee/1.0'})
            except Exception, exc:
                log.info('Error fetching %s', link_url)
                bee.models.Link404Result.objects.create(post_id=post_pk, url=link_url, status=0, error=str(exc))
                continue

        if resp.status < 200 or resp.status >= 300:
            log.info('Unexpected status fetching %s', link_url)
            bee.models.Link404Result.objects.create(post_id=post_pk, url=link_url, status=resp.status)
        else:
            log.info('Success fetching %s', link_url)


@task()
def find_404s_for_author(author_pk):
    """
    Dispatch jobs to check all the given author's posts for 404s in <a href>
    and <img src> URLs.
    """
    author_site = bee.models.AuthorSite.objects.get(author=author_pk)
    author_domain = author_site.site.domain

    perform_for_author_posts.delay(author_pk, find_404s_in_post.subtask(args=(author_domain,)))


@task()
def update_imported_infralinks_in_post(post_pk):
    # Only imported posts need updated.
    try:
        post_legacy = bee.models.PostLegacyUrl.objects.get(post=post_pk)
    except bee.models.PostLegacyUrl.DoesNotExist:
        return
    old_permalink = urlunsplit(('http', post_legacy.netloc, post_legacy.path, None, None))

    try:
        post = bee.models.Post.objects.get(pk=post_pk)
    except bee.models.Post.DoesNotExist:
        return

    root = BeautifulSoup(post.html)
    root_updated = False
    for link in root.findAll('a'):
        # Don't change accidental blank URLs.
        if not link.get('href'):
            log.warn("Skipping empty link in post %r", post)
            continue
        link_url = urljoin(old_permalink, link.get('href'))
        link_parts = urlsplit(link_url)

        try:
            link_legacy = bee.models.PostLegacyUrl.objects.get(netloc=link_parts.netloc, path=link_parts.path)
        except bee.models.PostLegacyUrl.DoesNotExist:
            continue

        new_post_url = link_legacy.post.permalink
        new_parts = urlsplit(new_post_url)
        new_link_url = urlunsplit((link_parts.scheme, new_parts.netloc, new_parts.path, link_parts.query, link_parts.fragment))
        log.warn("Changing link in post %r from %r to %r", post, link_url, new_link_url)
        link['href'] = new_link_url

        root_updated = True

    if root_updated:
        post.html = str(root)
        post.save()
