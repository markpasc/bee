from datetime import datetime
import os
from os.path import join
from xml.etree import ElementTree

from django.contrib.auth.models import User

from bee.management.import_command import ImportCommand
import bee.models


class Command(ImportCommand):

    args = '<export dir>'
    help = 'Import posts from a TypePad export'
    option_list = ImportCommand.option_list + (
    )

    def handle(self, sourcedir, **options):
        self.sourcedir = sourcedir
        self.import_posts()

    def import_me(self, doc):
        pass

    def import_regular_post(self, post, doc):
        post.title = doc.findtext('regular-title') or ''
        post.html = doc.findtext('regular-body')

    def import_link_post(self, post, doc):
        post.title = doc.findtext('link-text') or ''
        post.html = u"""%s\n\n<p><a href="%s">Link</a>""" % (doc.findtext('link-description'), doc.findtext('link-url'))

    def import_quote_post(self, post, doc):
        post.title = ''
        post.html = u"""<blockquote><p>%s</p></blockquote>\n\n<p>&mdash;%s</p>""" % (doc.findtext('quote-text'), doc.findtext('quote-source'))

    def import_video_post(self, post, doc):
        post.title = ''
        post.html = u"""<p>%s</p>\n\n%s""" % (doc.findtext('video-player'), doc.findtext('video-caption'))

    def import_posts(self):
        importers = {
            'regular': self.import_regular_post,
            'link': self.import_link_post,
            'quote': self.import_quote_post,
            'video': self.import_video_post,
        }

        user = User.objects.get(pk=1)

        first = True
        for filename in os.listdir(self.sourcedir):
            if not filename.endswith('.xml'):
                continue

            with open(join(self.sourcedir, filename), 'r') as f:
                doc = ElementTree.fromstring(f.read())

            if first:
                self.import_me(doc)
                first = False

            importer = importers[doc.get('type')]
            if importer is None:
                continue

            post_url = doc.get('url')
            try:
                post = bee.models.Post.objects.get(atom_id=post_url)
            except bee.models.Post.DoesNotExist:
                post = bee.models.Post(atom_id=post_url)

            importer(post, doc)

            post.author = user
            post.published = datetime.utcfromtimestamp(int(doc.get('unix-timestamp')))
            post.slug = self.unused_slug_for_post(post, (doc.get('slug'),))
            post.private = False

            post.save()
            post.tags.add(tag_node.text for tag_node in doc.findall('tag'))
