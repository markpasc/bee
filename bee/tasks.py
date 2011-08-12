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
    post = bee.models.Post.objects.values('html').get(pk=post_pk)

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
