from datetime import datetime
import json
import logging
import os
from os.path import join
import re
import sys

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
import httplib2

from bee.management.import_command import ImportCommand
import bee.models


class Command(ImportCommand):

    args = '<export dir>'
    help = 'Import posts from a TypePad export'
    option_list = ImportCommand.option_list + (
    )

    def handle(self, sourcedir, **options):
        self.sourcedir = sourcedir
        self.import_entries()

    def import_me(self, author):
        # Make me an Identity.
        profile_url = author['profilePageUrl']
        user = User.objects.all().order_by('id')[0]
        ident_obj, created = bee.models.Identity.objects.get_or_create(identifier=profile_url)
        ident_obj.user = user
        ident_obj.save()

        # Make me an avatar.
        try:
            avatar = bee.models.Avatar.objects.get(user=user, name='TypePad')
        except bee.models.Avatar.DoesNotExist:
            avatar_url = author['avatarLink']['urlTemplate'].replace('{spec}', '75si')
            resp, content = httplib2.Http().request(avatar_url)
            assert resp.status == 200
            avatar = bee.models.Avatar(user=user, name='TypePad')
            avatar.image.save('typepad', ContentFile(content), save=True)
        self.avatar = avatar

    def person_for_openid(self, openid):
        ident_obj, created = bee.models.Identity.objects.get_or_create(identifier=openid)
        return ident_obj

    def filename_for_image_url(self, image_url):
        mo = re.search(r'(?P<asset_id>6a\w+)', image_url)
        if mo is None:
            return
        asset_id = mo.group('asset_id')
        for ext in ('jpeg', 'gif', 'png'):
            image_path = join(self.sourcedir, '%s-pi.%s' % (asset_id, ext))
            if os.access(image_path, os.R_OK):
                return image_path
        return

    def import_entry(self, obj):
        assert obj['objectType'] == 'Post'

        atom_id = obj['id']
        try:
            post = bee.models.Post.objects.get(atom_id=atom_id)
        except bee.models.Post.DoesNotExist:
            post = bee.models.Post(atom_id=atom_id)

        publ = obj['published']
        publ_dt = datetime.strptime(publ, '%Y-%m-%dT%H:%M:%SZ')
        post.published = publ_dt

        post.author = self.person_for_openid(obj['author']['profilePageUrl']).user
        post.avatar = self.avatar

        post.title = obj['title']
        post.slug = self.unused_slug_for_post(post, (obj['filename'],))
        post.html = obj['renderedContent']
        post.html, assets = self.import_images_for_post_html(post)

        # Everything's public hwhee!
        post.private = False
        post.save()
        logging.info('Saved new asset %s (%s) as #%d', post.atom_id, post.title, post.pk)

        for asset in assets:
            asset.posts.add(post)

    def import_entries(self):
        first = True
        for filename in os.listdir(self.sourcedir):
            if filename.endswith('.json'):
                with open(join(self.sourcedir, filename), 'r') as infile:
                    obj = json.loads(infile.read())

                if first:
                    self.import_me(obj['author'])
                    first = False

                self.import_entry(obj)
