import bleach
from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe


register = template.Library()


ALLOWED_HTML_TAGS = ('a', 'abbr', 'address', 'aside', 'b', 'blockquote', 'br', 'cite', 'code', 'dd', 'del', 'dfn', 'div', 'dl', 'dt', 'em', 'hr', 'i', 'img', 'ins', 'kbd', 'li', 'ol', 'p', 'pre', 'q', 'samp', 'small', 'span', 'strong', 'sub', 'sup', 'tt', 'ul', 'wbr')
ALLOWED_HTML_ATTRIBUTES = {
    'a': ('href', 'hreflang'),
    'blockquote': ('cite',),
    'del': ('cite', 'datetime'),
    'img': ('alt', 'height', 'src', 'width'),
    'ins': ('cite', 'datetime'),
    'q': ('cite',),
    '*': ('dir', 'title'),
}


@register.filter
@stringfilter
def bleachhtml(value):
    return mark_safe(bleach.clean(value, tags=ALLOWED_HTML_TAGS, attributes=ALLOWED_HTML_ATTRIBUTES))
