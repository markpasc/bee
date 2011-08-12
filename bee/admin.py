from os.path import basename

from django.contrib import admin

from bee.models import *


def desc(**kwargs):
    def derp(fn):
        for k, v in kwargs.iteritems():
            setattr(fn, k, v)
        return fn
    return derp


class TrustGroupAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'user', 'tag')
    list_filter = ('user', 'tag')

admin.site.register(TrustGroup, TrustGroupAdmin)


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

    @desc(short_description='Privatize selected posts')
    def make_private(self, request, queryset):
        queryset.update(private=True)

    @desc(short_description='Entrust selected posts')
    def make_trusted(self, request, queryset):
        queryset.update(private=True)
        trustgroup = None
        for obj in queryset:
            if trustgroup is None:
                trustgroup, created = TrustGroup.objects.get_or_create(user=obj.author, tag='trusted',
                    defaults={'display_name': 'Trusted'})
            obj.private_to = [trustgroup]

    actions = [make_private, make_trusted]

admin.site.register(Post, PostAdmin)


class PostLegacyUrlAdmin(admin.ModelAdmin):
    list_display = ('url', 'post')

    def url(self, obj):
        return u''.join((obj.netloc, obj.path))

admin.site.register(PostLegacyUrl, PostLegacyUrlAdmin)


class AuthorSiteAdmin(admin.ModelAdmin):
    list_display = ('author', 'site')

admin.site.register(AuthorSite, AuthorSiteAdmin)


class TemplateAdmin(admin.ModelAdmin):
    list_display = ('author', 'purpose')

admin.site.register(Template, TemplateAdmin)
