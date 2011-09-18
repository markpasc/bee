(function ($) {

    function Editor (jelement, settings) {
        this.jelement = jelement;
        $.extend(this, settings);

        var editor = this;

        var $content = jelement.find('.editor-content');
        var $linkEditor = jelement.find('.editor-link-editor');
        // these might not exist:
        var $title = jelement.find('.editor-title');
        var $published = jelement.find('.editor-published');
        var $slug = jelement.find('.editor-slug');

        // Set up key controls.
        $content.bind('keydown', function (e) { return editor.editorKey(e) });
        $title.bind('keypress', titleKeypress).bind('keyup', function (e) { return editor.titleKeyup(e) });
        $slug.bind('keypress', slugKeypress);
        $published.bind('keypress', publishedKeypress);
        if (Modernizr.localstorage) {
            editor.autosave();
            $title.add($content).add($published).add($slug).bind('textInput', function (e) {
                $.doTimeout('editor.autosave', 1000, function () { return editor.autosave() });
            });
        }

        // Set up buttons.
        jelement.find('.editor-post-button').click(function (e) { editor.post(); return false });
        jelement.find('.editor-discard-button').click(function (e) { editor.discard(); return false });

        // Set up link editor.
        $linkEditor.hide();
        $content.find('a').live('click', false).live('mouseover', function (e) { return editor.activateLinkEditor(e) })
            .live('mouseout', function (e) { return editor.deactivateLinkEditor(e) });

        // Set up more stuff.
        this.preventNavigation();
        if ($published.size()) {
            this.updatePublished();
            $.doTimeout('editor.updatePublished', 60000, function () { return editor.updatePublished() });
        }
        jelement.find('.editor-trust').multiselect({  // might not exist
            header: false,
            selectedList: 4,
            noneSelectedText: 'Private (draft)',
            click: function(event, ui) {
                if (ui.value == 'public' && ui.checked)
                    return;
                    //$('#entry-trust').multiselect('uncheckAll');
            }
        });
    }

    Editor.prototype.updatePublished = function () {
        var $publ = this.jelement.find('.editor-published');
        if ($publ.attr('data-now')) {
            var now = new Date();
            now.setSeconds(0);
            now.setMilliseconds(0);
            $publ.text(now.toISOString());
        }
        return true;
    };

    Editor.prototype.autosave = function () {
        var autokey = 'autosave.' + this.autosaveid;
        localStorage[autokey] = 1;

        var data = this.serialize();
        $.each(data, function (key, val) {
            localStorage[autokey + '.' + key] = val;
        });

        return false;
    };

    Editor.prototype.removeAutosave = function () {
        // Cancel autosaving if we're going to autosave.
        $.doTimeout('editor.autosave');  // cancel

        localStorage.removeItem('autosave.' + this.autosaveid);

        // Laboriously remove all the autosave keys, so we don't have to assume what they are.
        var autoPrefix = 'autosave.' + this.autosaveid + '.';
        var keysToRemove = new Array();
        for (var i = 0; i < localStorage.length; i++) {
            var key = localStorage.key(i);
            if (key.slice(0, autoPrefix.length) == autoPrefix) {
                keysToRemove.push(key);
            }
        }
        $.each(keysToRemove, function (i, val) {
            localStorage.removeItem(keysToRemove);
        });
    };

    if (!Modernizr.localstorage) {
        Editor.prototype.autosave = function () { return false };
        Editor.prototype.removeAutosave = function () {};
    }

    function preventNavigation (e) {
        var ret = 'The editor is open.';
        if (e) e.returnValue = ret;
        return ret;
    }

    Editor.prototype.preventNavigation = function () {
        $(window).bind('beforeunload.editor', preventNavigation);
    };

    Editor.prototype.allowNavigation = function () {
        $(window).unbind('beforeunload.editor');
    };

    function publishedKeypress (e) {
        $(this).attr('data-now', null);
    }

    function titleKeypress (e) {
        if (e.which == 13)
            return false;
    }

    Editor.prototype.titleKeyup = function (e) {
        var $slug = this.jelement.find('.editor-slug');
        if (!$slug.attr('data-autotitle'))
            return;

        var title = $(e.target).text();
        var slug = title.replace(/\s+/g,'-').replace(/[^a-zA-Z0-9\-]/g,'').replace(/--+/g, '-').replace(/^-|-$/g, '').toLowerCase();
        $slug.text(slug);
    };

    function slugKeypress (e) {
        if (e.which != 45                          // -
            && (e.which < 48 || 57 < e.which)      // 0-9
            && (e.which < 97 || 122 < e.which)) {  // a-z
            return false;
        }

        $(this).attr('data-autotitle', null);
    }

    Editor.prototype.editorKey = function (e) {
        if (e.altKey || e.shiftKey || !e.ctrlKey)
            return true;

        if (e.which == 66) {  // Bold
            document.execCommand('bold');
            return false;
        }
        else if (e.which == 72) {  // Htmlify
            var text = window.getSelection().toString();
            document.execCommand('insertHTML', false, text);
            return false;
        }
        else if (e.which == 73) {  // Italicize
            document.execCommand('italic');
            return false;
        }
        else if (e.which == 76) {  // Linkify
            document.execCommand('createLink', false, '#');
            return false;
        }
        else if (e.which == 221) {  // ] to blockquote
            document.execCommand('indent');
            return false;
        }
        else if (e.which == 219) {  // [ to unblockquote
            document.execCommand('outdent');
            return false;
        }

        return true;
    };

    Editor.prototype.activateLinkEditor = function (e) {
        var $link = $(e.target);
        var linkpos = $link.offset();

        var $linkeditor = this.jelement.find('.editor-link-editor');
        $linkeditor.text($link.attr('href'));
        $linkeditor.bind('keyup', function (e) {
            $link.attr('href', $(this).text());
        });
        $linkeditor.show();
        $linkeditor.offset({ top: linkpos.top + $link.height(), left: linkpos.left });
        $linkeditor.focus();
    };

    Editor.prototype.deactivateLinkEditor = function (e) {
        var $linkeditor = this.jelement.find('.editor-link-editor');
        $linkeditor.blur();
        $linkeditor.unbind('keyup');
        $linkeditor.hide();
    };

    Editor.prototype.serialize = function () {
        var $editor = this.jelement;
        var data = {
            //avatar: 
            title: $editor.find('.editor-title').text(),
            html: $.trim($editor.find('.editor-content').html()),
            slug: $editor.find('.editor-slug').text(),
            tags: '',
            comments_enabled: true,
            private: true,
            private_to: []
        };

        // TODO: use Date.toISOString() when we have a js date from a picker instead
        var $publ = $editor.find('.editor-published');
        if (!$publ.attr('data-now')) {
            data['published'] = $.trim($publ.text());
        }

        var trust = $editor.find('.editor-trust').val();
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

        return data;
    };

    Editor.prototype.post = function () {
        var $editor = this.jelement;
        var data = this.serialize();

        // Always have a published date if the editor has one.
        var $published = $editor.find('.editor-published');
        if ($published.size() && !data['published']) {
            data['published'] = $.trim($published.text());
        }

        var $entryId = $editor.find('.editor-id');
        if ($entryId.size()) {
            data['id'] = $entryId.val();
        }

        var editor = this;
        $.ajax({
            url: '/_/edit',
            type: 'POST',
            dataType: 'json',
            data: data,
            success: function (data, textStatus, xhr) {
                editor.removeAutosave();
                editor.allowNavigation();
                window.location = data['permalink'];
            },
            error: function (xhr, textStatus, errorThrown) {
                alert('ERROR: ' + xhr.responseText);
            }
        });
    };

    Editor.prototype.discard = function (e) {
        this.removeAutosave();
        this.allowNavigation();
        $.doTimeout('editor.updatePublished');  // cancel
        this.ondiscard();
    };

    $.fn.editor = function (options) {
        var settings = {
            autosaveid: '',
            ondiscard: function () {},
            lastSetting: null
        };
        $.extend(settings, options);

        return this.each(function () {
            var $this = $(this);
            $this.data('editor', new Editor($this, settings));
        });
    };

})(jQuery);
