from datetime import datetime

from django import forms
import django.forms.widgets
from django.utils.translation import ugettext_lazy as _
import haystack.forms
import iso8601

from bee.models import Post


class IsoDateTimeField(forms.Field):

    def __init__(self, widget=forms.DateTimeInput, **kwargs):
        super(IsoDateTimeField, self).__init__(widget=widget, **kwargs)

    def clean(self, val):
        super(IsoDateTimeField, self).clean(val)

        if not val:
            return None
        if isinstance(val, datetime):
            return val

        try:
            iso_date = iso8601.parse_date(val)
        except ValueError, err:
            raise forms.ValidationError(*err.args)
        return iso_date.astimezone(iso8601.iso8601.Utc()).replace(tzinfo=None)


class PostForm(forms.ModelForm):

    published = IsoDateTimeField()

    class Meta:
        model = Post
        exclude = ('author', 'atom_id', 'created', 'modified')


class SearchInput(django.forms.widgets.Input):

    input_type = 'search'


class SearchForm(haystack.forms.SearchForm):

    q = forms.CharField(required=True, label=_('Search'), widget=SearchInput(attrs={'placeholder': 'Search'}))
