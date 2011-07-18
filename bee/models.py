from datetime import datetime
import logging

from django.db import models
from taggit.managers import TaggableManager


class Avatar(models.Model):

    user = models.ForeignKey('auth.User', related_name='avatars')
    name = models.CharField(max_length=200)
    image = models.ImageField(upload_to=lambda inst, fn: 'avatars/%s/%s' % (inst.user.username, fn),
        height_field='height', width_field='width')
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()

    def __unicode__(self):
        return u'%s: %s' % (self.user.username, self.name)


class Identity(models.Model):

    identifier = models.CharField(max_length=200)
    user = models.ForeignKey('auth.User', blank=True, null=True)

    def __unicode__(self):
        return self.identifier


class TrustGroup(models.Model):

    user = models.ForeignKey('auth.User', related_name='trust_groups')
    tag = models.CharField(max_length=200)
    display_name = models.CharField(max_length=200)
    members = models.ManyToManyField(Identity)

    def __unicode__(self):
        return self.display_name

    class Meta:
        unique_together = (('user', 'tag'),)


class Post(models.Model):

    author = models.ForeignKey('auth.User', related_name='posts_authored')
    avatar = models.ForeignKey(Avatar, blank=True, null=True)
    title = models.CharField(max_length=255, blank=True)
    html = models.TextField(blank=True)
    slug = models.SlugField(max_length=80)
    atom_id = models.CharField(max_length=255, unique=True)  # even for different authors, should be unique

    created = models.DateTimeField(default=datetime.utcnow)
    published = models.DateTimeField(default=datetime.utcnow)
    modified = models.DateTimeField(default=datetime.utcnow)

    # render_mode = ...
    private = models.BooleanField(blank=True, default=True)
    private_to = models.ManyToManyField(TrustGroup, blank=True)

    tags = TaggableManager(blank=True)

    @property
    def permalink(self):
        return 'http://%s/%s' % (self.author.authorsite_set.get().site.domain, self.slug)

    def visible_to(self, viewer):
        logging.debug("Is post %r visible to user %r?", self, viewer)
        if not self.private:
            logging.debug("    Post is not private, so it's visible")
            return True
        if not viewer.is_authenticated():
            logging.debug("    Post is private but viewer is anonymous, so it's NOT visible")
            return False
        if self.author.pk == viewer.pk:
            logging.debug("    Post is private but viewer is the author, so it's visible")
            return True
        if self.private_to.filter(members=viewer).exists():
            logging.debug("    Post is private but it's shared to a group that contains the viewer, so it's visible")
            return True
        logging.debug("    Post is private and not shared to the viewer, so it's NOT visible")
        return False

    def __unicode__(self):
        return self.title or self.slug

    def save(self, *args, **kwargs):
        if len(self.slug) > 80:
            self.slug = self.slug[:80]
        super(Post, self).save(*args, **kwargs)

    class Meta:
        unique_together = (('author', 'slug'),)


class Asset(models.Model):

    def _upload_to(instance, filename):
        created = instance.created or datetime.utcnow()
        path = created.strftime('assets/%Y/%m/%%s')
        return path % (filename,)

    sourcefile = models.FileField(upload_to=_upload_to)
    created = models.DateTimeField(default=datetime.utcnow)
    author = models.ForeignKey('auth.User', related_name='assets_authored')
    posts = models.ManyToManyField(Post, blank=True)
    original_url = models.CharField(max_length=255, unique=True, blank=True, null=True)


# TODO: is this really a siteinfo? with site's display name?
class AuthorSite(models.Model):

    author = models.ForeignKey('auth.User', unique=True)
    site = models.ForeignKey('sites.Site', unique=True)


class Template(models.Model):

    TEMPLATE_PURPOSES = (
        ('index', 'index'),
        ('permalink', 'permalink'),
    )

    author = models.ForeignKey('auth.User', related_name='templates')
    purpose = models.CharField(max_length=20, choices=TEMPLATE_PURPOSES)
    text = models.TextField(blank=True)

    class Meta:
        unique_together = (('author', 'purpose'),)
