from itertools import ifilterfalse
import logging
import os
from os.path import basename
import random
import string

from BeautifulSoup import BeautifulSoup
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.template.defaultfilters import slugify

import bee.models


class ImportCommand(BaseCommand):

    def unused_slug_for_post(self, post, candidate_slugs):
        def gunk_slugs():
            chars = string.letters + string.digits + string.digits
            while True:
                gunk = ''.join(random.choice(chars) for i in range(7))
                yield gunk

        def possible_slugs():
            slug_sources = (slug for slug in candidate_slugs if slug)
            try:
                slug_source = slug_sources.next()
            except StopIteration:
                for gunk in gunk_slugs():
                    yield gunk
            yield slugify(slug_source)
            for gunk in gunk_slugs():
                possible_unique = '%s %s' % (slug_source, gunk)
                yield slugify(possible_unique)

        other_posts = post.author.posts_authored.all()
        if post.id:
            other_posts = other_posts.exclude(id=post.id)
        def is_slug_used(slug):
            return other_posts.filter(slug=slug).exists()

        unused_slugs = ifilterfalse(is_slug_used, possible_slugs())
        return unused_slugs.next()

    def filename_for_image_url(self, image_url):
        raise NotImplementedError

    def import_images_for_post_html(self, post):
        content_root = BeautifulSoup(post.html)
        assets = list()

        for el in content_root.findAll('img'):
            img_src = el.get('src')
            img_path = self.filename_for_image_url(img_src)
            if img_path is None:
                continue

            if not os.access(img_path, os.R_OK):
                logging.warn("Couldn't import asset for URL %s: file %s doesn't exist", img_src, img_path)
                continue

            try:
                asset = bee.models.Asset.objects.get(author=post.author, original_url=img_src)
            except bee.models.Asset.DoesNotExist:
                asset = bee.models.Asset(author=post.author, created=post.published, original_url=img_src)
                with open(img_path, 'r') as f:
                    asset.sourcefile.save(basename(img_path), File(f), save=True)
                logging.debug("Importing asset for URL %s (will now be at %s)", img_src, asset.sourcefile.url)
            else:
                logging.debug("Already imported asset for URL %s", img_src)

            assets.append(asset)
            el['src'] = asset.sourcefile.url  # guess this is a property?

        return str(content_root), assets
