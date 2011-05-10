from datetime import datetime

from django.db import models


class Image(models.Model):

    image_url = models.CharField(max_length=200, unique=True)
    width = models.IntegerField()
    height = models.IntegerField()


class Post(models.Model):

    author = models.ForeignKey('auth.User', related_name='posts_authored')
    avatar = models.ForeignKey(Image, blank=True, null=True)
    title = models.CharField(max_length=255, blank=True)
    html = models.TextField(blank=True)
    slug = models.SlugField()
    atom_id = models.CharField(max_length=255)
    created = models.DateTimeField(default=datetime.now)
    modified = models.DateTimeField(default=datetime.now)
    # render_mode = ...


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
