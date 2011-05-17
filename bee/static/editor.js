var $publ = $('#entry-published');
function updatePublishedTimer() {
    if ($publ.attr('data-now'))
        $publ.text($.relatizeDate.strftime(new Date(), '%Y-%m-%d %I:%M %p'));
}
$(document).ready(function () {
    updatePublishedTimer();
    setInterval("updatePublishedTimer()", 60000);
});

$publ.bind('keypress', function (e) {
    $(this).attr('data-now', null);
});

$('#entry-editor .entry-header').bind('keypress', function (e) {
    if (e.which == 13)
        return false;
}).bind('keyup', function (e) {
    var $slug = $('#entry-slug');
    if ($slug.data('edited'))
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

    $(this).data('edited', true);
});

$('#editor-post-button').click(function (e) {
    var data = {
        //avatar: 
        title: $('#entry-editor .entry-header').text(),
        html: $('#entry-editor .entry-content').html(),
        slug: $('#entry-slug').text(),
        private: true
        //private_to: 
    };

    var published = $('#entry-published').text();
    var match = published.match(/(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2}):(\d{2})\s+([AP]M)/i);
    if (match) {
        var publishdate = new Date(match[1], match[2] - 1, match[3],
            match[6].toLowerCase() == 'pm' ? match[4] + 12 : match[4], match[5], 0);
        data['published'] = publishdate.toISOString();
    }
    else {
        $('#entry-published').addClass('oops').focus();
        return false;
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
