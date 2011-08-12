from datetime import datetime
import json
import logging
from optparse import make_option
import os
from os.path import join, abspath, dirname
import re
from urllib import unquote
from urlparse import urlsplit, urljoin

from django.conf import settings
from django.contrib.auth.models import User
import django.contrib.comments
from django.db import models
from django.db.models.base import ModelBase
from django.template.defaultfilters import striptags
from django.utils.text import truncate_words
from markdown import markdown
import social_auth.backends

from bee.management.import_command import ImportCommand
import bee.models


STATUS_HOLD, STATUS_RELEASE, STATUS_REVIEW, STATUS_FUTURE, STATUS_JUNK = range(1, 6)


class MtType(ModelBase):

    def add_to_class(cls, name, value):
        # Auto-specify a field's db_column with the table name on the front.
        if isinstance(value, models.Field):
            db_column_parts = [cls.__name__.lower(), value.db_column or name]
            if isinstance(value, models.ForeignKey):
                db_column_parts.append('id')
            value.db_column = '_'.join(db_column_parts)
        ModelBase.add_to_class(cls, name, value)


class MtObject(models.Model):

    __metaclass__ = MtType

    def save(self, **kwargs):
        raise NotImplementedError("Don't save any MtObject instances")

    class Meta:
        abstract = True
        managed = False
        app_label = 'mt'


class Author(MtObject):

    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=50)
    nickname = models.CharField(max_length=50)
    typecode = models.IntegerField(db_column='type')


class OpenIDIdentity(MtObject):

    id = models.IntegerField(primary_key=True)
    author = models.ForeignKey(Author)
    pic_url = models.CharField(max_length=255, blank=True, null=True)
    url = models.CharField(max_length=255, blank=True, null=True)


class Blog(MtObject):

    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    site_url = models.CharField(max_length=255)
    archive_url = models.CharField(max_length=255, blank=True, null=True)
    archive_tmpl_individual = models.CharField(max_length=255, blank=True, null=True)
    convert_paras_comments = models.CharField(max_length=30, blank=True, null=True)
    file_extension = models.CharField(max_length=10, blank=True, null=True)
    old_style_archive_links = models.BooleanField(blank=True)


class Entry(MtObject):

    id = models.IntegerField(primary_key=True)
    blog = models.ForeignKey(Blog)
    atom_id = models.CharField(max_length=255, blank=True, null=True)
    basename = models.CharField(max_length=255, blank=True, null=True)

    title = models.CharField(max_length=255, blank=True, null=True)
    author = models.ForeignKey(Author)
    text_format = models.CharField(max_length=30, blank=True, null=True, db_column='convert_breaks')
    status = models.IntegerField(blank=True)
    allow_comments = models.BooleanField(blank=True)
    created_on = models.DateTimeField(blank=True, null=True)
    modified_on = models.DateTimeField(blank=True, null=True)

    excerpt = models.TextField(blank=True, null=True)
    keywords = models.TextField(blank=True, null=True)
    text = models.TextField(blank=True, null=True)
    text_more = models.TextField(blank=True, null=True)


class Comment(MtObject):

    id = models.IntegerField(primary_key=True)
    entry = models.ForeignKey(Entry)
    commenter = models.ForeignKey(Author, blank=True, null=True)

    author = models.CharField(max_length=100, blank=True, null=True)
    email = models.CharField(max_length=75, blank=True, null=True)
    url = models.CharField(max_length=255, blank=True, null=True)
    ip = models.CharField(max_length=16, blank=True, null=True)

    text = models.TextField(blank=True, null=True)
    visible = models.BooleanField(blank=True)
    created_on = models.DateTimeField(blank=True, null=True)
    modified_on = models.DateTimeField(blank=True)


class Command(ImportCommand):

    args = '<sqlite database>'
    help = 'Import posts from a Movable Type database'
    option_list = ImportCommand.option_list + (
        make_option('--list-blogs',
            action='store_const',
            dest='action',
            const='list_blogs',
        ),
        make_option('--list-authors',
            action='store_const',
            dest='action',
            const='list_authors',
        ),
        make_option('--blog',
            help='The ID of the blog to list/import',
        ),
        make_option('--author',
            help='The ID of the author whose posts to list/import',
        ),
        make_option('--list-entries',
            action='store_const',
            dest='action',
            const='list_entries',
        ),
    )

    def handle(self, dbpath, **options):
        # Set up our database.
        self.set_up_database(dbpath)

        self.user = User.objects.get(pk=1)
        author_site_bridge = bee.models.AuthorSite.objects.get(author=self.user)
        self.author_site = author_site_bridge.site

        action = options['action']
        if action == 'list_blogs':
            return self.list_blogs()
        elif action == 'list_authors':
            return self.list_authors()

        blog_id = options['blog']
        blog = Blog.objects.using('mt').get(id=blog_id)
        entries = Entry.objects.using('mt').filter(blog=blog)
        if options.get('author'):
            author = Author.objects.using('mt').get(id=options['author'])
            entries = entries.filter(author=author)

        if action == 'list_entries':
            self.list_entries(entries)
        else:
            self.import_entries(entries)

    def set_up_database(self, dbpath):
        self.dbpath = dbpath

        settings.DATABASES['mt'] = {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': abspath(dbpath),
        }

        # Make sure we've used the SQLite connection.
        from django.db import connections
        connections['mt'].cursor().execute('SELECT 1')

        # Enable our own converter for "text" columns, in case there are some really old posts still in Latin-1 (like I have).
        from django.db.backends.sqlite3.base import Database
        Database.register_converter('text', self.convert_text)

    def convert_text(self, text):
        try:
            return text.decode('utf-8')
        except UnicodeDecodeError:
            return text.decode('latin-1')

    def list_blogs(self):
        blogs = Blog.objects.using('mt').all().annotate(num_entries=models.Count('entry')).order_by('id')

        tablefmt = u'{0:>4} {1:<30} {2:<50} {3}'
        print tablefmt.format('ID', 'Name', 'Site URL', 'Post')
        for blog in blogs:
            print tablefmt.format(blog.id, blog.name, blog.site_url, blog.num_entries)

    def list_authors(self):
        authors = Author.objects.using('mt').all().annotate(num_entries=models.Count('entry'), num_comments=models.Count('comment'))

        tablefmt = u'{0:>4} {1:<30} {2:<50} {3:<4} {4}'
        print tablefmt.format('ID', 'Name', 'Nickname', 'Post', 'Comm')
        for author in authors:
            print tablefmt.format(author.id, author.name.replace('\n', r'\n')[:30],
                author.nickname[:50] if author.nickname else '',
                author.num_entries or '', author.num_comments or '')

    def list_entries(self, entries):
        entries = entries.annotate(num_comments=models.Count('comment'))

        tablefmt = u'{0:>4} {1:<20} {2:<4} {3:<30} {4:<50} {5:<4}'
        print tablefmt.format('ID', 'Basename', 'St', 'Title', 'Text', 'Comm')
        for entry in entries[:20]:
            print tablefmt.format(entry.id, entry.basename, entry.status,
                entry.atom_id[len(entry.atom_id)-30:] if entry.atom_id else '',
                entry.title[:50] if entry.text else '',
                entry.num_comments or '')

    def filename_for_image_url(self, image_url):
        url_parts = urlsplit(image_url)
        path_parts = [unquote(part) for part in url_parts.path.split('/') if part]
        image_path = join(dirname(self.dbpath), url_parts.netloc, *path_parts)
        logging.debug('~~ LOOKING FOR IMAGE %r. IS IT AT %r? ~~', image_url, image_path)
        return image_path

    html_block_re = re.compile(r'\A </? (?: h1|h2|h3|h4|h5|h6|table|ol|dl|ul|menu|dir|p|pre|center|form|fieldset|select|blockquote|address|div|hr )', re.MULTILINE | re.DOTALL | re.IGNORECASE | re.VERBOSE)

    def html_text_transform(self, text):
        # Convert line breaks like Movable Type does.
        text = text.replace(u'\r', u'')  # don't really care about \rs
        grafs = text.split(u'\n\n')
        return u'\n\n'.join(graf if self.html_block_re.match(graf) else u'<p>{0}</p>'.format(graf.replace(u'\n', u'<br>\n')) for graf in grafs)

    def generate_atom_id(self, mt_entry):
        # Generate an Atom ID like Movable Type does.
        mt_blog = mt_entry.blog
        site_url_parts = urlsplit(mt_blog.site_url)
        data = {
            'host': site_url_parts.netloc,
            'path': site_url_parts.path,
            'year': mt_entry.created_on.year,
            'blog_id': mt_blog.id,
            'entry_id': mt_entry.id,
        }
        return 'tag:{host},{year}:{path}/{blog_id}.{entry_id}'.format(**data)

    def htmlizer_for_text_format(self, text_format):
        if text_format == 'markdown':
            return markdown
        elif text_format == '__default__':
            return self.html_text_transform
        elif text_format in (None, '', '0'):
            # Yay, already HTML.
            return lambda html: html

        raise ValueError("Unknown text format %r" % (text_format,))

    def import_entries(self, entries):
        for mt_entry in entries:
            atom_id = mt_entry.atom_id
            if not atom_id:
                atom_id = self.generate_atom_id(mt_entry)
                logging.debug('GENERATED Atom ID %r for entry %r (#%d %s)', atom_id, mt_entry.title, mt_entry.id, mt_entry.basename)

            try:
                post = bee.models.Post.objects.get(atom_id=atom_id)
            except bee.models.Post.DoesNotExist:
                post = bee.models.Post(atom_id=atom_id)

            post.author = self.user
            post.published = mt_entry.created_on

            htmlize = self.htmlizer_for_text_format(mt_entry.text_format)
            html = '' if mt_entry.text is None else htmlize(mt_entry.text)
            if mt_entry.text_more is not None:
                html = u'\n\n'.join((html, htmlize(mt_entry.text_more)))

            # Ignore the title if it's the first five words of the post (it was autosummarized).
            if not mt_entry.title or truncate_words(striptags(html), 5, '') == mt_entry.title:
                post.title = ''
            else:
                post.title = mt_entry.title

            # Only *use* that HTML if we're importing the post for the first time.
            if not post.pk:
                post.html = html

            post.html, assets = self.import_images_for_post_html(post)

            if not post.slug:
                basename = mt_entry.basename.replace('_', '-')
                post.slug = self.unused_slug_for_post(post, (basename, mt_entry.title))

            # Only published posts (even if they're in the future) are public.
            if not post.pk:
                post.private = True if mt_entry.status not in (STATUS_RELEASE, STATUS_FUTURE) else False

            post.comments_enabled = True if mt_entry.allow_comments else False

            post.save()

            for asset in assets:
                asset.posts.add(post)

            legacy_url_parts = urlsplit(self.archive_url_for_post(mt_entry))
            bee.models.PostLegacyUrl.objects.get_or_create(post=post,
                defaults={'netloc': legacy_url_parts.netloc, 'path': legacy_url_parts.path})

            logging.debug('Imported %r (%r)!', post.title, atom_id)

            self.import_comments(post, mt_entry)

    def archive_url_for_post(self, mt_entry):
        mt_blog = mt_entry.blog

        # TODO: handle using the real blog.archive_tmpl_individual, but none of my blogs use it
        assert not mt_blog.old_style_archive_links, 'Blog %r uses old style archive links :( :( :(' % (mt_blog.name,)
        assert not mt_blog.archive_tmpl_individual, 'Blog %r uses an archive_tmpl_individual :(' % (mt_blog.name,)
        archive_tmpl = '{year}/{month}/{basename}.{extension}'

        data = {
            'year': str(mt_entry.created_on.year),
            'month': '%02d' % mt_entry.created_on.month,
            'basename': mt_entry.basename,
            'extension': mt_blog.file_extension or 'html',
        }

        blog_url = mt_blog.archive_url or mt_blog.site_url
        return urljoin(blog_url, archive_tmpl.format(**data))

    def person_for_commenter(self, mt_author):
        if mt_author is None:
            return None

        idents = mt_author.openididentity_set.using('mt').all()
        if not idents:
            return None

        openids = set(ident.url for ident in idents)
        assert len(openids) < 2, "Commenter %r has too many identities (%d)!" % (mt_author, len(idents))
        (openid,) = openids

        backend = social_auth.backends.OpenIDBackend()
        try:
            ident_obj = backend.get_social_auth_user(openid)
        except social_auth.models.UserSocialAuth.DoesNotExist:
            # make a user then i guess
            user_details = {
                'username': mt_author.name,
                'email': '',
                'first_name': mt_author.nickname,
            }
            username = backend.username(user_details)
            user = User.objects.create_user(username=username, email='')
            user.first_name = user_details['first_name']
            user.save()
            ident_obj = backend.associate_auth(user, openid, None, user_details)

        # TODO: make an avatar from the pic url

        return ident_obj.user

    def import_comments(self, post, mt_entry):
        comment_cls = django.contrib.comments.get_model()
        htmlize = self.htmlizer_for_text_format(mt_entry.blog.convert_paras_comments)
        for mt_comment in mt_entry.comment_set.using('mt').all():
            atom_id = '%s.%d' % (post.atom_id, mt_comment.id)
            try:
                comment = comment_cls.objects.get(atom_id=atom_id)
            except comment_cls.DoesNotExist:
                comment = comment_cls(atom_id=atom_id)

            comment.content_object = post
            comment.site = self.author_site
            comment.submit_date = mt_comment.created_on
            comment.is_public = mt_comment.visible
            comment.ip_address = mt_comment.ip

            comment.comment = htmlize(mt_comment.text)

            comment.user_name = mt_comment.author or ''
            comment.user_email = mt_comment.email or ''
            comment.user_url = mt_comment.url or ''
            comment.user = self.person_for_commenter(mt_comment.commenter)

            comment.save()
            logging.debug('Saved comment %r!', atom_id)
