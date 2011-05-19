from datetime import datetime
from functools import partial
from itertools import ifilterfalse
import logging
from optparse import make_option
import random
import re
import string
import sys
from xml.etree import ElementTree

from BeautifulSoup import BeautifulSoup, NavigableString
import django
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.template.defaultfilters import slugify, striptags
from django.utils.text import truncate_words

import bee.models
from bee.models import Post


class Command(BaseCommand):

    args = '<export file>'
    help = 'Import posts from a livejournal XML export.'
    option_list = BaseCommand.option_list + (
        make_option('--foaf',
            metavar='FILE',
            help='The filename of the FOAF document from which to pull friend names and userpic URLs',
        ),
        make_option('--atomid',
            help='The prefix of the Atom ID to store',
            default=None,
        ),
    )

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.foaf_names = dict()
        self.foaf_pics = dict()

    def handle(self, source, **options):
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

    def person_for_openid(self, openid, display_name=None, userpic_url=None):
        if display_name is None:
            display_name = self.foaf_names.get(openid, '')
        if userpic_url is None:
            userpic_url = self.foaf_pics.get(openid, '')

        try:
            ident_obj = bee.models.Identity.objects.get(identifier=openid)
        except bee.models.Identity.DoesNotExist:
            ident_obj = bee.models.Identity(identifier=openid)
            ident_obj.save()

        return ident_obj

    def make_my_openid(self, openid):
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

        return person

    def format_soup(self, content_root):
        for el in content_root.findAll(text=lambda t: '\n' in t):
            if el.findParent(re.compile(r'pre|lj-raw|table')) is None:
                new_content = el.string.replace('\n', '<br>\n')
                el.replaceWith(BeautifulSoup(new_content))

    def import_comment(self, comment_el, asset, openid_for):
        # TODO: import comments for realsies
        return

        jtalkid = comment_el.get('jtalkid')
        atom_id = '%s:talk:%s' % (asset.atom_id, jtalkid)
        logging.debug('Yay importing comment %s', jtalkid)

        try:
            comment = Asset.objects.get(atom_id=atom_id)
        except Asset.DoesNotExist:
            comment = Asset(atom_id=atom_id)

        comment_props = {}
        for prop in comment_el.findall('props/prop'):
            key = prop.get('name')
            val = prop.get('value')
            comment_props[key] = val

        comment.title = comment_el.findtext('subject') or ''

        body = comment_el.findtext('body')
        if int(comment_props.get('opt_preformatted') or 0):
            comment.content = body
        else:
            logging.debug("    Oops, comment not preformatted, let's parse it")
            content_root = BeautifulSoup(body)
            self.format_soup(content_root)
            comment.content = str(content_root)

        comment.in_reply_to = asset
        comment.in_thread_of = asset.in_thread_of or asset

        poster = comment_el.get('poster')
        if poster:
            openid = openid_for(poster)
            logging.debug("    Saving %s as comment author", openid)
            comment.author = person_for_openid(openid)
        else:
            logging.debug("    Oh huh this comment was anonymous, fancy that")

        comment.imported = True
        comment.save()

        comment.private = asset.private
        comment.private_to = asset.private_to.all()

        for reply_el in comment_el.findall('comments/comment'):
            self.import_comment(reply_el, comment, openid_for)

    def import_events(self, source, atomid_prefix, foafsource):
        tree = ElementTree.parse(source)

        username = tree.getroot().get('username')
        server = tree.getroot().get('server')
        server_domain = '.'.join(server.rsplit('.', 2)[1:])
        openid_for = partial(self.generate_openid, server_domain)
        if atomid_prefix is None:
            atomid_prefix = 'urn:lj:%s:atom1:%s:' % (server_domain, username)

        post_author = self.make_my_openid(openid_for(username))

        # First, if there's a FOAF, learn all my friends' names and faces.
        if foafsource:
            self.import_foaf(foafsource, server_domain)

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

            ident_person = self.person_for_openid(openid, friend.findtext('fullname'))

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

            content_root = BeautifulSoup(event.findtext('event'))
            # Add line breaks to the post if it's not preformatted.
            if not int(event_props.get('opt_preformatted', 0)):
                self.format_soup(content_root)
            # Remove any lj-raw tags.
            for el in content_root.findAll(re.compile(r'lj-(?:raw|cut)')):
                # Replace it with its children.
                el_parent = el.parent
                el_index = el_parent.contents.index(el)
                el.extract()
                for child in reversed(list(el.contents)):
                    el_parent.insert(el_index, child)
            # TODO: handle opt_nocomments prop
            # TODO: put music and mood in the post content
            # TODO: handle taglist prop
            post.html = str(content_root)

            if not post.slug:
                def gunk_slugs():
                    chars = string.letters + string.digits + string.digits
                    while True:
                        gunk = ''.join(random.choice(chars) for i in range(7))
                        yield gunk

                def possible_slugs():
                    slug_source = post.title
                    if not slug_source:
                        post_text = striptags(post.html)
                        slug_source = truncate_words(post_text, 7, end_text='')
                    if not slug_source:
                        for gunk in gunk_slugs():
                            yield gunk
                    yield slugify(slug_source)
                    for gunk in gunk_slugs():
                        possible_unique = u'%s %s' % (slug_source, gunk)
                        yield slugify(possible_unique)

                other_posts = post.author.posts_authored.all()
                if post.id:
                    other_posts = other_posts.exclude(id=post.id)
                def is_slug_used(slug):
                    return other_posts.filter(slug=slug).exists()

                unused_slugs = ifilterfalse(is_slug_used, possible_slugs())
                post.slug = unused_slugs.next()  # only need the first that's not used

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
