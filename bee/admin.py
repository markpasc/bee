from django.contrib import admin

from bee.models import *


admin.site.register(Image)
admin.site.register(TrustGroup)


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
