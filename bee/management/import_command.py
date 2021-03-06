from itertools import ifilterfalse
import logging
from optparse import make_option
import os
from os.path import basename, dirname, normpath, expanduser, join, isfile
import random
import re
import string
from urllib import unquote

from BeautifulSoup import BeautifulSoup
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.template.defaultfilters import slugify

import bee.models


class ImportCommand(BaseCommand):

    option_list = BaseCommand.option_list + (
        make_option('--filemap',
            dest='filemaps',
            metavar='PATH',
            help='Path to some standard file-URL maps for your import data',
        ),
    )

    def set_up_filemaps(self, **options):
        def expandpath(path, base):
            path = expanduser(path)
            path = join(base, path)
            return normpath(path)

        self.filemaps = dict()
        try:
            filemap_path = options['filemaps']
        except KeyError:
            return

        filemaps_dir = dirname(expandpath(filemap_path, os.getcwd()))
        with open(filemap_path, 'r') as f:
            filemap_specs = (line.strip() for line in f.readlines() if line.strip())
            raw_filemaps = (url.split('=', 1) for url in filemap_specs)
            filemaps = ((k, expandpath(v, filemaps_dir)) for k, v in raw_filemaps)
            self.filemaps.update(filemaps)

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
        matching_maps = [(map_url, map_path) for map_url, map_path in self.filemaps.iteritems() if image_url.startswith(map_url)]
        if not matching_maps:
            return
        map_url, map_path = matching_maps[0]
        img_path = join(map_path, unquote(image_url[len(map_url):]))
        return img_path

    def import_images_for_post_html(self, post):
        content_root = BeautifulSoup(post.html)
        assets = list()

        for el in content_root.findAll(['img', 'a']):
            url_attr = 'href' if el.name == 'a' else 'src'
            img_src = el.get(url_attr)
            if img_src is None:
                continue
            img_path = self.filename_for_image_url(img_src)
            if img_path is None:
                continue

            if not os.access(img_path, os.R_OK):
                logging.warn("Couldn't import asset for URL %s: file %s doesn't exist", img_src, img_path)
                continue
            if not isfile(img_path):
                logging.warn("Couldn't import asset for URL %s: path %s is not a file", img_src, img_path)
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
            el[url_attr] = asset.sourcefile.url  # guess this is a property?

        return str(content_root), assets

    html_block_re = re.compile(r'\A </? (?: h1|h2|h3|h4|h5|h6|table|ol|dl|ul|menu|dir|p|pre|center|form|fieldset|select|blockquote|address|div|hr )', re.MULTILINE | re.DOTALL | re.IGNORECASE | re.VERBOSE)

    def html_text_transform(self, text):
        # Convert line breaks like Movable Type does.
        text = text.replace(u'\r', u'')  # don't really care about \rs
        grafs = text.split(u'\n\n')
        return u'\n\n'.join(graf if self.html_block_re.match(graf) else u'<p>{0}</p>'.format(graf.replace(u'\n', u'<br>\n')) for graf in grafs)
