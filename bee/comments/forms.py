import django.contrib.comments.forms

from bee.comments.models import PostComment


class PostCommentForm(django.contrib.comments.forms.CommentForm):

    #atom_id = forms.CharField(max_length=255, 
    #avatar = forms.ModelChoiceField(queryset=Avatar.objects.filter(user=...?))

    def get_comment_model(self):
        return PostComment

    def get_comment_create_data(self):
        # Add any new fields... but our form doesn't have any yet.
        return super(PostCommentForm, self).get_comment_create_data()
