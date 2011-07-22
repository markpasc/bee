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

$(document).ready(function () {
    updatePublishedTimer();
    setInterval(updatePublishedTimer, 60000);

    if (Modernizr.localstorage)
        setInterval(autosave, 10000);
});

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

$('#editor-post-button').click(function (e) {
    var data = {
        //avatar: 
        title: $('#entry-editor .entry-header').text(),
        html: $.trim($('#entry-editor .entry-content').html()),
        slug: $('#entry-slug').text(),
        // TODO: use Date.toISOString() when we have a js date from a picker instead
        published: $.trim($('#entry-published').text()),
        tags: '',
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

    if ($('#entry-editor #entry-id').size()) {
        data['id'] = $('#entry-editor #entry-id').val();
    }

    $.ajax({
        url: '/_/edit',
        type: 'POST',
        dataType: 'json',
        data: data,
        success: function (data, textStatus, xhr) {
            window.location = data['permalink'];
        },
        error: function (xhr, textStatus, errorThrown) {
            alert('ERROR: ' + xhr.responseText);
        }
    });
    return false;
});
