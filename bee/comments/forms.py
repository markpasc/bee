from django import forms
import django.contrib.comments.forms
from django.utils.translation import ugettext_lazy as _

from bee.comments.models import PostComment


class PostCommentForm(django.contrib.comments.forms.CommentForm):

    avatar = forms.IntegerField(required=False, min_value=1)
    email = forms.EmailField(label=_("Email address"), required=False)

    def get_comment_model(self):
        return PostComment

    def get_comment_create_data(self):
        # Add any new fields... but our form doesn't have any yet.
        return super(PostCommentForm, self).get_comment_create_data()
