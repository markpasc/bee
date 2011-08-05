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
from urlparse import urlsplit
from xml.etree import ElementTree

from BeautifulSoup import BeautifulSoup, NavigableString
from django.contrib.auth.models import User
import django.contrib.comments
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.template.defaultfilters import slugify, striptags
from django.utils.text import truncate_words
import social_auth.backends
import social_auth.models

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
        make_option('--skip-posts',
            help='Skip import of posts (go straight to comments)',
            action='store_false',
            dest='import_posts',
            default=True,
        ),
    )

    def handle(self, source, **options):
        openid = options.get('openid')
        if not openid:
            raise ValueError("Argument --openid is required")
        self.make_my_openid(openid)

        self.sourcepath = dirname(source)
        tree = ElementTree.parse(source)

        if options.get('import_posts'):
            self.import_assets(tree)
        self.import_comments(tree)

    def person_for_openid(self, openid, display_name):
        backend = social_auth.backends.OpenIDBackend()
        try:
            ident_obj = backend.get_social_auth_user(openid)
        except social_auth.models.UserSocialAuth.DoesNotExist:
            # make a user then i guess
            details = {
                'username': urlsplit(openid).netloc,
                'email': '',
                'first_name': display_name[:30],
            }
            username = backend.username(details)
            comment_author = User.objects.create_user(username=username, email='')
            comment_author.first_name = details['first_name']
            comment_author.save()
            ident_obj = backend.associate_auth(comment_author, openid, None, details)

        return ident_obj

    def make_my_openid(self, openid):
        # Rectify my OpenID first.
        person = User.objects.all().order_by('id')[0]
        backend = social_auth.backends.OpenIDBackend()
        try:
            ident_obj = backend.get_social_auth_user(openid)
        except social_auth.models.UserSocialAuth.DoesNotExist:
            ident_obj = backend.associate_auth(person, openid, None, {})

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
        for comment_el in tree.findall('{http://www.w3.org/2005/Atom}entry'):
            # This time, *only* comments.
            reply_el = comment_el.find('{http://purl.org/syndication/thread/1.0}in-reply-to')
            if reply_el is None:
                continue

            parent_ref = reply_el.get('ref')
            try:
                parent_asset = bee.models.Post.objects.get(atom_id=parent_ref)
            except bee.models.Post.DoesNotExist:
                # OOPS
                logging.warn('Referenced parent asset %s does not exist; skipping comment :(', reply_el.get('href'))
                continue

            author_site_bridge = bee.models.AuthorSite.objects.get(author=parent_asset.author)
            author_site = author_site_bridge.site
            comment_cls = django.contrib.comments.get_model()

            atom_id = comment_el.findtext('{http://www.w3.org/2005/Atom}id')
            try:
                comment = comment_cls.objects.get(atom_id=atom_id)
            except comment_cls.DoesNotExist:
                comment = comment_cls(atom_id=atom_id)

            comment.site = author_site
            comment.content_object = parent_asset

            content_el = comment_el.find('{http://www.w3.org/2005/Atom}content')
            assert content_el is not None, "Comment %s had no content?!" % atom_id
            content_content_type = content_el.get('type')
            if content_content_type == 'html':
                html = content_el.text
            elif content_content_type == 'xhtml':
                html_el = content_el.find('{http://www.w3.org/1999/xhtml}div')
                html = html_el.text or u''
                html += u''.join(ElementTree.tostring(el) for el in html_el.getchildren())
            else:
                assert False, "Comment %s had unexpected content of type %r?!" % (atom_id, content_content_type)
            comment.comment = html

            publ = comment_el.findtext('{http://www.w3.org/2005/Atom}published')
            publ_dt = datetime.strptime(publ, '%Y-%m-%dT%H:%M:%SZ')
            comment.submit_date = publ_dt

            # Comments are marked with the privacy of their parent assets, so just assume they're all public.
            privacy_el = comment_el.find('{http://www.sixapart.com/ns/atom/privacy}privacy/{http://www.sixapart.com/ns/atom/privacy}allow')
            assert privacy_el is not None, "Comment %s had no privacy element?!" % atom_id
            assert privacy_el.get('name') in ('Everyone', 'Friends', 'Family', 'Neighborhood'), "Privacy for comment %s wasn't Everyone?!" % atom_id
            comment.is_public = True

            comment.user_name = comment_el.findtext('{http://www.w3.org/2005/Atom}author/{http://www.w3.org/2005/Atom}name')
            comment.user_url = comment_el.findtext('{http://www.w3.org/2005/Atom}author/{http://www.w3.org/2005/Atom}uri')
            comment.user = self.person_for_openid(comment.user_url, comment.user_name).user

            comment.save()
