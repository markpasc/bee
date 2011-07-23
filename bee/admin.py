from os.path import basename

from django.contrib import admin

from bee.models import *


admin.site.register(TrustGroup)


class AssetAdmin(admin.ModelAdmin):
    list_display = ('filename', 'author', 'created', 'original_url')
    list_filter = ('author',)

    def filename(self, obj):
        return basename(obj.sourcefile.name)

admin.site.register(Asset, AssetAdmin)


class AvatarAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'width', 'height')
    list_display_links = ('user', 'name')
    list_filter = ('user',)

admin.site.register(Avatar, AvatarAdmin)


class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'slug', 'atom_id', 'private', 'published')
    list_display_links = ('title', 'slug')
    list_filter = ('author',)
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ('title', 'slug', 'html')

admin.site.register(Post, PostAdmin)


class AuthorSiteAdmin(admin.ModelAdmin):
    list_display = ('author', 'site')

admin.site.register(AuthorSite, AuthorSiteAdmin)


class TemplateAdmin(admin.ModelAdmin):
    list_display = ('author', 'purpose')

admin.site.register(Template, TemplateAdmin)
