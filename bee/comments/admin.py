from django.contrib import admin
from django.contrib.comments.admin import CommentsAdmin
from django.utils.text import truncate_words

from bee.comments.models import *


class PostCommentAdmin(CommentsAdmin):

    fieldsets = CommentsAdmin.fieldsets + (
        (
            'Bee',
            {'fields': ('avatar', 'title', 'atom_id', 'in_reply_to')},
        ),
    )

    list_display = ('summary', 'name', 'is_user', 'content_object', 'submit_date', 'is_visible')

    def summary(self, obj):
        if obj.title:
            return obj.title
        return truncate_words(obj.comment, 7)

    def is_visible(self, obj):
        return obj.is_public and not obj.is_removed
    is_visible.boolean = True

    def is_user(self, obj):
        return bool(obj.user_id)
    is_user.boolean = True


admin.site.register(PostComment, PostCommentAdmin)
