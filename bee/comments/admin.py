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

admin.site.register(PostComment, PostCommentAdmin)
