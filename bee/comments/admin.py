from django.contrib import admin

from bee.comments.models import *


class AssetAdmin(admin.ModelAdmin):
    list_display = ('filename', 'author', 'created', 'original_url')
    list_filter = ('author',)

    def filename(self, obj):
        return basename(obj.sourcefile.name)

admin.site.register(PostComment)
