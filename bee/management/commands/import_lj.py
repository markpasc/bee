from base64 import b64decode
from datetime import datetime
from functools import partial
from itertools import ifilterfalse
import logging
from optparse import make_option
import os
from os.path import join, basename, expanduser
import random
import re
import string
import sys
from urllib import unquote
from urlparse import urlsplit, urljoin
from xml.etree import ElementTree

from BeautifulSoup import BeautifulSoup
import django
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.template.defaultfilters import slugify, striptags
from django.utils.text import truncate_words
import social_auth.backends
import social_auth.models

from bee.management.import_command import ImportCommand
import bee.models
from bee.models import Post, Avatar, Asset


class Command(ImportCommand):

    args = '<export file>'
    help = 'Import posts from a livejournal XML export.'
    option_list = ImportCommand.option_list + (
        make_option('--foaf',
            metavar='FILE',
            help='The filename of the FOAF document from which to pull friend names and userpic URLs',
        ),
        make_option('--atomid',
            help='The prefix of the Atom ID to store',
            default=None,
        ),
        make_option('--images',
            action='append',
            dest='imagemap',
            metavar='BASEURL=PATH',
            help='When posts refer to images at BASEURL, import them from PATH on disk',
        ),
    )

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.foaf_names = dict()
        self.foaf_pics = dict()

    def handle(self, source, **options):
        author_site_bridge = bee.models.AuthorSite.objects.get(author=1)
        self.author_site = author_site_bridge.site

        self.imagemaps = dict((k, expanduser(v)) for k, v in (imageurl.split('=', 1) for imageurl in options['imagemap'] or ()))
        self.import_events(sys.stdin if source == '-' else source,
            options['atomid'], options['foaf'])

    def generate_openid(self, server_domain, username):
        if username.startswith('_'):
            return 'http://users.%s/%s/' % (server_domain, username)
        username = username.replace('_', '-')
        return 'http://%s.%s/' % (username, server_domain)

    def import_foaf(self, source, server_domain):
        tree = ElementTree.parse(source)
        logging.debug('Yay processing a FOAF document!')

        for person in tree.findall('//{http://xmlns.com/foaf/0.1/}Person'):
            nick = person.findtext('{http://xmlns.com/foaf/0.1/}nick')
            logging.debug('Processing FOAF sack for %s', nick)
            name = person.findtext('{http://xmlns.com/foaf/0.1/}member_name') or ''
            pic = person.findtext('{http://xmlns.com/foaf/0.1/}image') or ''

            openid = self.generate_openid(server_domain, nick)
            self.foaf_names[openid] = name
            self.foaf_pics[openid] = pic

    def person_for_openid(self, openid, **details):
        username = details['username']
        display_name = details.get('display_name', self.foaf_names.get(openid, ''))
        userpic_url = details.get('userpic_url', self.foaf_pics.get(openid, ''))

        backend = social_auth.backends.OpenIDBackend()
        try:
            ident_obj = backend.get_social_auth_user(openid)
        except social_auth.models.UserSocialAuth.DoesNotExist:
            # make a user then i guess
            user_details = {
                'username': username,
                'email': '',
                'first_name': display_name,
            }
            username = backend.username(user_details)
            comment_author = User.objects.create_user(username=username, email='')
            comment_author.first_name = user_details['first_name']
            comment_author.save()
            ident_obj = backend.associate_auth(comment_author, openid, None, user_details)

        return ident_obj

    def make_my_openid(self, openid):
        person = User.objects.all().order_by('id')[0]

        backend = social_auth.backends.OpenIDBackend()
        try:
            ident = backend.get_social_auth_user(openid)
        except social_auth.models.UserSocialAuth.DoesNotExist:
            ident = backend.associate_auth(person, openid, None, {'username': person.username})

        return person

    def import_comment(self, comment_el, asset, openid_for, root_atom_id=None):
        if root_atom_id is None:
            root_atom_id = asset.atom_id
        jtalkid = comment_el.get('jtalkid')
        atom_id = '%s:talk:%s' % (root_atom_id, jtalkid)
        logging.debug('Yay importing comment %s', jtalkid)

        comment_cls = django.contrib.comments.get_model()
        try:
            comment = comment_cls.objects.get(atom_id=atom_id)
        except comment_cls.DoesNotExist:
            comment = comment_cls(atom_id=atom_id)

        comment_props = {}
        for prop in comment_el.findall('props/prop'):
            key = prop.get('name')
            val = prop.get('value')
            comment_props[key] = val

        comment.title = comment_el.findtext('subject') or ''

        body = comment_el.findtext('body')
        if int(comment_props.get('opt_preformatted') or 0):
            comment.comment = body
        else:
            logging.debug("    Oops, comment not preformatted, let's parse it")
            content_root = BeautifulSoup(body)
            comment.comment = str(content_root).decode('utf8')
            comment.comment = self.html_text_transform(comment.comment)

        if isinstance(asset, comment_cls):
            comment.content_object = asset.content_object
            comment.in_reply_to = asset
        else:
            comment.content_object = asset

        poster = comment_el.get('poster')
        if poster:
            openid = openid_for(poster)
            logging.debug("    Saving %s as comment author", openid)
            comment.user = self.person_for_openid(openid, username=poster).user
            comment.user_name = poster
            comment.user_url = openid
        else:
            logging.debug("    Oh huh this comment was anonymous, fancy that")
            comment.user_name = 'anonymous'
            comment.user_url = ''

        publ = comment_el.findtext('date')
        publ_dt = datetime.strptime(publ, '%Y-%m-%dT%H:%M:%SZ')
        comment.submit_date = publ_dt

        comment.site = self.author_site
        comment.is_public = True

        comment.save()

        for reply_el in comment_el.findall('comments/comment'):
            self.import_comment(reply_el, comment, openid_for, root_atom_id)

    def filename_for_image_url(self, image_url):
        matching_maps = [(map_url, map_path) for map_url, map_path in self.imagemaps.iteritems() if image_url.startswith(map_url)]
        if not matching_maps:
            return
        map_url, map_path = matching_maps[0]
        img_path = join(map_path, unquote(image_url[len(map_url):]))

        # Try more aggressively to find an image if it doesn't exist as-is.
        if not os.access(img_path, os.F_OK):
            maybe_stem = img_path.rstrip('/')
            for ext in ('gif', 'png', 'jpg', 'jpeg'):
                maybe_path = '{0}.{1}'.format(maybe_stem, ext)
                if os.access(maybe_path, os.F_OK):
                    return maybe_path

        return img_path  # which may not exist

    def import_images_for_post_html(self, post):
        if not self.imagemaps:
            return post.html, ()
        return super(Command, self).import_images_for_post_html(post)

    def import_events(self, source, atomid_prefix, foafsource):
        tree = ElementTree.parse(source)

        username = tree.getroot().get('username')
        server = tree.getroot().get('server')
        server_domain = '.'.join(server.rsplit('.', 2)[1:])
        openid_for = partial(self.generate_openid, server_domain)
        if atomid_prefix is None:
            atomid_prefix = 'urn:lj:%s:atom1:%s:' % (server_domain, username)

        author_openid = openid_for(username)
        post_author = self.make_my_openid(author_openid)

        # First, if there's a FOAF, learn all my friends' names and faces.
        if foafsource:
            self.import_foaf(foafsource, server_domain)

        # Next import all my userpics.
        avatars = dict()
        for userpic in tree.findall('/userpics/user/userpic'):
            keyword = userpic.get('keyword')
            logging.debug("Importing userpic %r", keyword)
            try:
                avatar = Avatar.objects.get(user=post_author, name=keyword)
            except Avatar.DoesNotExist:
                data64 = userpic.text
                data = b64decode(data64)
                avatar = Avatar(user=post_author, name=keyword)
                avatar.image.save(slugify(keyword) or 'userpic', ContentFile(data), save=True)
            avatars[keyword] = avatar

        # Now update groups and friends, so we can knit the posts together right.
        group_objs = dict()
        for group in tree.findall('/friends/group'):
            groupid = int(group.findtext('id'))
            name = group.findtext('name')

            tag = '%sgroup:%d' % (atomid_prefix, groupid)
            group_obj, created = bee.models.TrustGroup.objects.get_or_create(user=post_author, tag=tag,
                defaults={'display_name': name})
            group_objs[groupid] = group_obj

        all_friends_tag = '%sfriends' % atomid_prefix
        all_friends_group, created = bee.models.TrustGroup.objects.get_or_create(
            user=post_author, tag=all_friends_tag, defaults={'display_name': 'LiveJournal friends'})

        for friend in tree.findall('/friends/friend'):
            friendname = friend.findtext('username')
            openid = openid_for(friendname)

            ident_person = self.person_for_openid(openid, username=friendname, display_name=friend.findtext('fullname'))

            # Update their groups.
            group_ids = tuple(int(groupnode.text) for groupnode in friend.findall('groups/group'))
            logging.debug("Setting %s's groups to %r", friendname, group_ids)
            ident_person.groups = [all_friends_group] + [group_objs[groupid] for groupid in group_ids]

        # Import the posts.
        for event in tree.findall('/events/event'):
            ditemid = event.get('ditemid')
            logging.debug('Parsing event %s', ditemid)
            atom_id = '%s%s' % (atomid_prefix, ditemid)

            try:
                post = Post.objects.get(atom_id=atom_id)
            except Post.DoesNotExist:
                post = Post(atom_id=atom_id)

            event_props = {}
            for prop in event.findall('props/prop'):
                key = prop.get('name')
                val = prop.get('value')
                event_props[key] = val

            subject = event.findtext('subject')
            post.title = striptags(subject) if subject else ''
            post.author = post_author

            publ = event.findtext('date')
            assert publ, 'event has no date :('
            publ_dt = datetime.strptime(publ, '%Y-%m-%d %H:%M:%S')
            # TODO: is this in the account's timezone or what?
            post.published = publ_dt

            content_root = BeautifulSoup(event.findtext('event'), selfClosingTags=('lj',))
            # Remove any lj-raw tags.
            for el in content_root.findAll(re.compile(r'lj-(?:raw|cut)')):
                # Replace it with its children.
                el_parent = el.parent
                el_index = el_parent.contents.index(el)
                el.extract()
                for child in reversed(list(el.contents)):
                    el_parent.insert(el_index, child)
            for el in content_root.findAll('lj'):
                el_parent = el.parent
                el_index = el_parent.contents.index(el)
                el.extract()

                try:
                    user_name = el['user']
                except KeyError:
                    comm_name = el['comm']
                    user_url = 'http://communities.livejournal.com/{0}/'.format(comm_name)
                else:
                    if user_name.startswith('_') or user_name.endswith('_'):
                        user_url = 'http://users.livejournal.com/{0}/'.format(user_name)
                    else:
                        user_url = 'http://{0}.livejournal.com/'.format(user_name)
                user_link = BeautifulSoup(u'<a href="{0}">{1}</a>'.format(user_url, user_name))

                el_parent.insert(el_index, user_link)
            # TODO: handle opt_nocomments prop
            # TODO: put music and mood in the post content
            # TODO: handle taglist prop

            post.html = str(content_root).decode('utf8')
            # Add line breaks to the post if it's not preformatted.
            if not int(event_props.get('opt_preformatted', 0)):
                post.html = self.html_text_transform(post.html)
            post.html, assets = self.import_images_for_post_html(post)

            pic_keyword = event_props.get('picture_keyword')
            if pic_keyword and pic_keyword in avatars:
                post.avatar = avatars[pic_keyword]

            if not post.slug:
                def possible_slugs():
                    yield post.title
                    post_text = striptags(post.html)
                    slug_source = truncate_words(post_text, 7, end_text='')
                    yield slug_source

                post.slug = self.unused_slug_for_post(post, possible_slugs())

            # Pre-save the post in case we want to assign trust groups.
            post_is_new = not post.pk
            post.save()

            for asset in assets:
                asset.posts.add(post)

            legacy_url = urljoin(author_openid, '%s.html' % ditemid)
            legacy_url_parts = urlsplit(legacy_url)
            bee.models.PostLegacyUrl.objects.get_or_create(post=post,
                defaults={'netloc': legacy_url_parts.netloc, 'path': legacy_url_parts.path})

            if post_is_new:
                security = event.get('security')
                if security == 'private':
                    logging.debug('Oh ho post %s is all fancy private', ditemid)
                    post.private = True
                elif security == 'usemask':
                    bin = lambda s: str(s) if s<=1 else bin(s>>1) + str(s&1)

                    mask = int(event.get('allowmask'))
                    logging.debug('Post %s has mask %s?', ditemid, bin(mask))

                    if mask == 1:
                        mask_groups = [all_friends_group]
                        # Plus all the other bits are 0, so we'll add no other groups.
                    else:
                        mask_groups = list()

                    for i in range(1, 30):
                        mask = mask >> 1
                        if mask == 0:
                            break
                        logging.debug('    Remaining mask %s', bin(mask))
                        if mask & 0x01:
                            logging.debug('    Yay %s has group %d!', ditemid, i)
                            if i in group_objs:
                                logging.debug('    And group %d exists woohoo!!', i)
                                mask_groups.append(group_objs[i])

                    logging.debug('So post %s gets %d groups', ditemid, len(mask_groups))
                    post.private = True
                    post.private_to = mask_groups
                else:
                    # Public!
                    post.private = False
                    post.private_to = []

                post.save()

            logging.info('Saved new post %s (%s) as #%d', ditemid, post.title, post.pk)

            # Import the comments.
            for comment in event.findall('comments/comment'):
                self.import_comment(comment, post, openid_for)
