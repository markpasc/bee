from datetime import datetime
import json
import logging
import os
from os.path import join
import re

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
        self.user = User.objects.get(pk=1)
        self.import_entries()
        # TODO: import the several comments there are

    def filename_for_image_url(self, image_url):
        mo = re.match(r'http://www\.bestendtimesever\.com/image/(?P<image_key>.+)', image_url)
        if mo is None:
            return
        image_key = mo.group('image_key')
        return join(self.sourcedir, image_key)

    def import_entry(self, post_data):
        if post_data['object_type'] != 'http://activitystrea.ms/schema/1.0/blog-entry':
            return
        if post_data['in_reply_to'] is not None:
            return
        if post_data['author']['slug'] != 'markpasc':
            return

        atom_id = 'tag:www.bestendtimesever.com,2009:%s' % post_data['key']
        try:
            post = bee.models.Post.objects.get(atom_id=atom_id)
        except bee.models.Post.DoesNotExist:
            post = bee.models.Post(atom_id=atom_id)

        publ = post_data['published']
        publ_dt = datetime.strptime(publ[:19], '%Y-%m-%dT%H:%M:%S')
        post.published = publ_dt

        post.author = self.user
        post.title = post_data['title']
        post.slug = self.unused_slug_for_post(post, (post_data['slug'],))
        post.html = post_data['content_html']

        post.html, assets = self.import_images_for_post_html(post)

        post.save()
        logging.info('Saved new asset %s (%s) as #%d', post.atom_id, post.title, post.pk)

        # All posts were public, so no trust groups to mess with.

        for asset in assets:
            asset.posts.add(post)

    def import_entries(self):
        for filename in os.listdir(self.sourcedir):
            if filename.endswith('.json'):
                with open(join(self.sourcedir, filename), 'r') as f:
                    entry = json.loads(f.read())
                self.import_entry(entry)
