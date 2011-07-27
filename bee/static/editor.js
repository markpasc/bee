function updatePublishedTimer() {
    var $publ = $('#entry-published');
    if ($publ.attr('data-now')) {
        var now = new Date();
        now.setSeconds(0);
        now.setMilliseconds(0);
        $publ.text(now.toISOString());
    }
}

function autosave() {
    var $editor = $('#entry-editor');
    if ($editor.attr('data-autosaved'))
        return;

    var $id = $('#entry-id');
    var postid = $id.size() ? $id.val() : 'new';

    localStorage['autosave.' + postid] = 1;
    localStorage['autosave.' + postid + '.title'] = $('#entry-editor .entry-header').text();
    localStorage['autosave.' + postid + '.html'] = $('#entry-editor .entry-content').html();
    localStorage['autosave.' + postid + '.slug'] = $('#entry-slug').text();

    var $publ = $('#entry-published');
    if (!$publ.attr('data-now'))
        localStorage['autosave.' + postid + '.published'] = $('#entry-published').text();

    $editor.attr('data-autosaved', 'yes');
}

function removeAutosave(postid) {
    $('#entry-editor').attr('data-autosaved', null);
    localStorage.removeItem('autosave.' + postid);
    localStorage.removeItem('autosave.' + postid + '.title');
    localStorage.removeItem('autosave.' + postid + '.html');
    localStorage.removeItem('autosave.' + postid + '.slug');
    localStorage.removeItem('autosave.' + postid + '.published');
}

var editorPublishedTimer;
var editorAutosaveTimer;

function startEditor() {
    updatePublishedTimer();
    editorPublishedTimer = setInterval(updatePublishedTimer, 60000);

    if (Modernizr.localstorage)
        editorAutosaveTimer = setInterval(autosave, 10000);

    $('#entry-link-editor').hide();
}
$(document).ready(startEditor);

function preventNavigation(e) {
    var ret = 'The editor is open.';
    if (e) e.returnValue = ret;
    return ret;
}
$(window).bind('beforeunload', preventNavigation);

$('#entry-published').bind('keypress', function (e) {
    $(this).attr('data-now', null);
});

$('#entry-editor .entry-header').add('#entry-editor .entry-content').add('#entry-published').add('#entry-slug').bind('textInput', function (e) {
    $('#entry-editor').attr('data-autosaved', null);
});

$('#entry-trust').multiselect({
    header: false,
    selectedList: 4,
    noneSelectedText: 'Private (draft)',
    click: function(event, ui) {
        if (ui.value == 'public' && ui.checked)
            return;
            //$('#entry-trust').multiselect('uncheckAll');
    }
});

$('#entry-editor .entry-header').bind('keypress', function (e) {
    if (e.which == 13)
        return false;
}).bind('keyup', function (e) {
    var $slug = $('#entry-slug');
    if (!$slug.attr('data-autotitle'))
        return;

    var title = $(this).text();
    var slug = title.replace(/\s+/g,'-').replace(/[^a-zA-Z0-9\-]/g,'').replace(/--+/g, '-').replace(/^-|-$/g, '').toLowerCase();
    $slug.text(slug);
});

$('#entry-slug').bind('keypress', function (e) {
    if (e.which != 45                          // -
        && (e.which < 48 || 57 < e.which)      // 0-9
        && (e.which < 97 || 122 < e.which)) {  // a-z
        return false;
    }

    $(this).attr('data-autotitle', null);
});

$('#entry-editor .entry-content').bind('keydown', function (e) {
    if (e.altKey || e.shiftKey || !e.ctrlKey)
        return true;

    if (e.which == 66) {
        document.execCommand('bold');
        return false;
    }
    else if (e.which == 72) {
        var text = window.getSelection().toString();
        document.execCommand('insertHTML', false, text);
        return false;
    }
    else if (e.which == 73) {
        document.execCommand('italic');
        return false;
    }
    else if (e.which == 76) {
        document.execCommand('createLink', false, '#');
        return false;
    }
    else if (e.which == 221) {
        document.execCommand('indent');
        return false;
    }
    else if (e.which == 219) {
        document.execCommand('outdent');
        return false;
    }

    return true;
});

$('#entry-editor .entry-content a').live('click', false).live('mouseover', function (e) {
    var $link = $(this);
    var linkpos = $link.offset();

    var $linkeditor = $('#entry-link-editor');
    $linkeditor.text($(this).attr('href'));
    $linkeditor.bind('keyup', function (e) {
        $link.attr('href', $(this).text());
    });
    $linkeditor.show();
    $linkeditor.offset({ top: linkpos.top + $(this).height(), left: linkpos.left });
    $linkeditor.focus();
}).live('mouseout', function (e) {
    var $linkeditor = $('#entry-link-editor');
    $linkeditor.blur();
    $linkeditor.unbind('keyup');
    $linkeditor.hide();
});

$('#editor-post-button').click(function (e) {
    var data = {
        //avatar: 
        title: $('#entry-editor .entry-header').text(),
        html: $.trim($('#entry-editor .entry-content').html()),
        slug: $('#entry-slug').text(),
        // TODO: use Date.toISOString() when we have a js date from a picker instead
        published: $.trim($('#entry-published').text()),
        tags: '',
        comments_enabled: true,
        private: true,
        private_to: []
    };

    var trust = $('#entry-trust').val();
    if (trust) {
        $.each(trust, function (key, value) {
            if (value == 'public') {
                data['private'] = false;
                data['private_to'] = [];
                return false;
            }
            data['private_to'].push(value);
        });
    }
    else {
        data['private'] = true;
        data['private_to'] = [];
    }

    var autosaveid = 'new';
    if ($('#entry-editor #entry-id').size()) {
        data['id'] = $('#entry-editor #entry-id').val();
        autosaveid = data['id'];
    }

    $.ajax({
        url: '/_/edit',
        type: 'POST',
        dataType: 'json',
        data: data,
        success: function (data, textStatus, xhr) {
            removeAutosave(autosaveid);
            $(window).unbind('beforeunload', preventNavigation);
            window.location = data['permalink'];
        },
        error: function (xhr, textStatus, errorThrown) {
            alert('ERROR: ' + xhr.responseText);
        }
    });
    return false;
});

$('#editor-discard-button').click(function (e) {
    var $entryid = $('#entry-editor #entry-id');
    var autosaveid = $entryid.size() ? $entryid.val() : 'new';
    removeAutosave($entryid);

    $('#entry-editor').remove();
    if (editorPublishedTimer) {
        clearTimeout(editorPublishedTimer);
        editorPublishedTimer = null;
    }
    if (editorAutosaveTimer) {
        clearTimeout(editorAutosaveTimer);
        editorAutosaveTimer = null;
    }

    $(window).unbind('beforeunload', preventNavigation);

    // If there's a hidden entry (that is, we're on a permalink page), show it.
    $('#content .entry:hidden').show();

    return false;
});
