from django.contrib import admin
from django.contrib.comments.admin import CommentsAdmin

from bee.comments.models import *


class PostCommentAdmin(CommentsAdmin):

    fieldsets = CommentsAdmin.fieldsets + (
        (
            'Bee',
            {'fields': ('avatar', 'title', 'atom_id')},
        ),
    )

    list_display = ('comment', 'name', 'is_user', 'content_object', 'ip_address', 'submit_date', 'is_visible')

    def is_visible(self, obj):
        return obj.is_public and not obj.is_removed
    is_visible.boolean = True

    def is_user(self, obj):
        return bool(obj.user_id)
    is_user.boolean = True


admin.site.register(PostComment, PostCommentAdmin)
