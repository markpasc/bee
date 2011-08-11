from collections import defaultdict

from django.contrib.comments.templatetags.comments import BaseCommentNode
from django import template


register = template.Library()


def comment_tree_iter(comments_by_root, comment_pk=None, depth=0):
    try:
        child_comments = comments_by_root[comment_pk]
    except KeyError:
        return

    for comment in child_comments:
        comment.depth = depth
        yield comment
        for comment in comment_tree_iter(comments_by_root, comment.pk, depth+1):
            yield comment


class CommentTreeNode(BaseCommentNode):

    def get_context_value_from_queryset(self, context, qs):
        comments_by_root = defaultdict(list)
        for comment in qs:
            in_reply_to = comment.in_reply_to
            parent_pk = None if in_reply_to is None else in_reply_to.pk
            children = comments_by_root[parent_pk]
            children.append(comment)

        return comment_tree_iter(comments_by_root)


@register.tag
def get_comment_tree(parser, token):
    return CommentTreeNode.handle_token(parser, token)
