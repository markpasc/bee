from django.contrib import admin

from bee.models import *


class PostAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('title',)}

admin.site.register(Post, PostAdmin)

admin.site.register(Image)
admin.site.register(AuthorSite)
admin.site.register(Template)
