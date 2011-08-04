from django.contrib.auth.models import User
import django.contrib.comments.models
from django.db import models


class PostComment(django.contrib.comments.models.Comment):

    atom_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    avatar = models.ForeignKey('bee.Avatar', blank=True, null=True)
    title = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        app_label = 'bee'
