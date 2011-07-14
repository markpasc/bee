from datetime import datetime

from haystack import indexes
from haystack import site

from bee.models import Post


class PostIndex(indexes.SearchIndex):

    text = indexes.CharField(document=True, use_template=True)
    title = indexes.CharField(model_attr='title', null=True)
    author_pk = indexes.IntegerField(model_attr='author__id')
    published = indexes.DateTimeField(model_attr='published')
    private = indexes.IntegerField(model_attr='private')

    def index_queryset(self):
        return Post.objects.filter(published__lte=datetime.now())


site.register(Post, PostIndex)
