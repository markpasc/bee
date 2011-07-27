def get_model():
    import bee.comments.models
    return bee.comments.models.PostComment

def get_form():
    import bee.comments.forms
    return bee.comments.forms.PostCommentForm
