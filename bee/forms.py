from django import forms

from bee.models import Post


class PostForm(forms.ModelForm):

    class Meta:
        model = Post
        exclude = ('author', 'atom_id', 'created', 'modified')
