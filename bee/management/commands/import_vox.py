from datetime import datetime
from itertools import ifilterfalse
import logging
from optparse import make_option
import os
from os.path import dirname, join, basename
import random
import re
import string
import sys
from xml.etree import ElementTree

from BeautifulSoup import BeautifulSoup, NavigableString
from django.contrib.auth.models import User
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.template.defaultfilters import slugify, striptags
from django.utils.text import truncate_words

from bee.management.import_command import ImportCommand
import bee.models


class Command(ImportCommand):

    args = '<export file>'
    help = 'Import posts from a Vox XML export.'
    option_list = BaseCommand.option_list + (
        make_option('--openid',
            metavar='URL',
            help='Your Vox OpenID for linking your posts and comments to you',
        ),
    )

    def handle(self, source, **options):
        openid = options.get('openid')
        if not openid:
            raise ValueError("Argument --openid is required")
        self.make_my_openid(openid)

        self.sourcepath = dirname(source)
        tree = ElementTree.parse(source)

        self.import_assets(tree)
        self.import_comments(tree)

    def person_for_openid(self, openid, display_name):
        ident_obj, created = bee.models.Identity.objects.get_or_create(identifier=openid)
        return ident_obj

    def make_my_openid(self, openid):
        # Rectify my OpenID first.
        person = User.objects.all().order_by('id')[0]
        try:
            ident = bee.models.Identity.objects.get(identifier=openid)
        except bee.models.Identity.DoesNotExist:
            logging.info('Creating new identity mapping to %s for %s', person.username, openid)
            ident = bee.models.Identity(identifier=openid, user=person)
            ident.save()
        else:
            if ident.user.pk == person.pk:
                logging.debug('Identity %s is already yours, yay', openid)
            else:
                logging.info('Merging existing person %s for identity %s into person %s',
                    ident.user.username, openid, person.username)
                ident.user.merge_into(person)

    def basic_asset_for_element(self, asset_el):
        atom_id = asset_el.findtext('{http://www.w3.org/2005/Atom}id')
        logging.debug('Parsing asset %s', atom_id)

        try:
            asset = bee.models.Post.objects.get(atom_id=atom_id)
        except bee.models.Post.DoesNotExist:
            asset = bee.models.Post(atom_id=atom_id)

        publ = asset_el.findtext('{http://www.w3.org/2005/Atom}published')
        publ_dt = datetime.strptime(publ, '%Y-%m-%dT%H:%M:%SZ')
        asset.published = publ_dt

        content_el = asset_el.find('{http://www.w3.org/2005/Atom}content')
        if content_el is None:
            html = ''
        else:
            content_type = content_el.get('type')
            if content_type == 'html':
                html = content_el.text
            elif content_type == 'xhtml':
                html_el = content_el.find('{http://www.w3.org/1999/xhtml}div')
                html = html_el.text or u''
                html += u''.join(ElementTree.tostring(el) for el in html_el.getchildren())
        asset.html = html

        author_el = asset_el.find('{http://www.w3.org/2005/Atom}author')
        author_name = author_el.findtext('{http://www.w3.org/2005/Atom}name')
        openid = author_el.findtext('{http://www.w3.org/2005/Atom}uri')
        # Import "gone" folks' comments anonymously.
        if openid != 'http://www.vox.com/gone/':
            asset.author = self.person_for_openid(openid, author_name).user

        if not asset.slug:
            def possible_slugs():
                atom_links = asset_el.findall('{http://www.w3.org/2005/Atom}link')
                permalinks = [el for el in atom_links if el.get('rel') == 'alternate' and el.get('type') == 'text/html']
                if not permalinks:
                    raise ValueError("Could not find text/html alternate link for post %r" % atom_id)
                vox_url = permalinks[0].get('href')
                mo = re.search(r'/(?P<slug>[^/\.]+)\.html', vox_url)
                if mo is None:
                    raise ValueError("Could not find slug in Vox post URL %r" % vox_url)
                vox_slug = mo.group('slug')
                yield vox_slug  # should always be?
                yield asset.title
                yield truncate_words(striptags(asset.html), 7, end_text='')

            asset.slug = self.unused_slug_for_post(asset, possible_slugs())

        return asset

    def filename_for_image_url(self, image_url):
        mo = re.match(r'http://a\d+\.vox\.com/(?P<asset_id>6a\w+)', image_url)
        if mo is None:
            return
        asset_id = mo.group('asset_id')

        for ext in ('gif', 'jpg', 'png'):
            img_path = join(self.sourcepath, 'assets', asset_id + '-pi.' + ext)
            if os.access(img_path, os.R_OK):
                return img_path

        return

    def import_assets(self, tree):
        groups = dict()

        for asset_el in tree.findall('{http://www.w3.org/2005/Atom}entry'):
            # Skip comments this go-round.
            if asset_el.find('{http://purl.org/syndication/thread/1.0}in-reply-to') is not None:
                continue

            # Skip anything that isn't a post.
            atom_links = asset_el.findall('{http://www.w3.org/2005/Atom}link')
            permalinks = [el for el in atom_links if el.get('rel') == 'alternate' and el.get('type') == 'text/html']
            if not permalinks:
                raise ValueError("Could not find text/html alternate link for post %r" % atom_id)
            vox_url = permalinks[0].get('href')
            if re.search(r'/library/post/', vox_url) is None:
                continue

            asset = self.basic_asset_for_element(asset_el)
            asset.title = asset_el.findtext('{http://www.w3.org/2005/Atom}title')

            asset.html, image_assets = self.import_images_for_post_html(asset)

            logging.info("Saving asset with author ID %d and slug '%s'", asset.author_id, asset.slug)
            asset.save()
            logging.info('Saved new asset %s (%s) as #%d', asset.atom_id, asset.title, asset.pk)

            for image_asset in image_assets:
                image_asset.posts.add(asset)

            asset_groups = list()
            privacies = asset_el.findall('{http://www.sixapart.com/ns/atom/privacy}privacy/{http://www.sixapart.com/ns/atom/privacy}allow')
            for privacy in privacies:
                assert privacy.get('policy') == 'http://www.sixapart.com/ns/atom/permissions#read', 'Privacy policy for post is not about reading :('
                group_ref = privacy.get('ref')

                # Ignore "everyone" since that's the absence of a group.
                if group_ref == 'http://www.sixapart.com/ns/atom/groups#everyone':
                    # Ignore this one.
                    continue

                # Use the special private group for "self".
                if group_ref == 'http://www.sixapart.com/ns/atom/groups#self':
                    asset.private = True
                    continue

                try:
                    group = groups[group_ref]
                except KeyError:
                    group, created = bee.models.TrustGroup.objects.get_or_create(tag=group_ref,
                        defaults={'user': asset.author, 'display_name': privacy.get('name')})
                    groups[group_ref] = group
                asset.private = True
                asset_groups.append(group)

            logging.debug('Assigning asset %s to %d groups', asset.atom_id, len(asset_groups))
            asset.private_to = asset_groups

    def import_comments(self, tree):
        # TODO: deal with comments again
        return

        for comment_el in tree.findall('{http://www.w3.org/2005/Atom}entry'):
            # This time, *only* comments.
            reply_el = asset_el.find('{http://purl.org/syndication/thread/1.0}in-reply-to')
            if reply_el is None:
                continue

            parent_ref = reply_el.get('ref')
            try:
                parent_asset = bee.models.Post.objects.get(atom_id=parent_ref)
            except bee.models.Post.DoesNotExist:
                # OOPS
                logging.warn('Referenced parent asset %s does not exist; skipping comment :(', reply_el.get('href'))
                continue

            asset = basic_asset_for_element(comment_el)

            asset.in_reply_to = parent_asset
            asset.in_thread_of = parent_asset.in_thread_of or parent_asset

            asset.save()

            asset.private_to = parent_asset.private_to.all()
