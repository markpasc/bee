(function ($) {

    function Editor (jelement, settings) {
        this.jelement = jelement;
        $.extend(this, settings);

        var editor = this;

        var $title = jelement.find('.editor-title');
        var $content = jelement.find('.editor-content');
        var $published = jelement.find('.editor-published');
        var $slug = jelement.find('.editor-slug');
        var $linkEditor = jelement.find('.editor-link-editor');

        // Set up key controls.
        $content.bind('keydown', function (e) { return editor.editorKey(e) });
        $title.bind('keypress', titleKeypress).bind('keyup', function (e) { return editor.titleKeyup(e) });
        $slug.bind('keypress', slugKeypress);
        $published.bind('keypress', publishedKeypress);
        if (Modernizr.localstorage)
            $title.add($content).add($published).add($slug).bind('textInput', function (e) {
                // Unnamed, so it won't debounce, but rather save again in another 10 secs.
                $.doTimeout(10000, editor.autosave);
            });

        // Set up buttons.
        jelement.find('.editor-post-button').click(function (e) { editor.post(); return false });
        jelement.find('.editor-discard-button').click(function (e) { editor.discard(); return false });

        // Set up link editor.
        $linkEditor.hide();
        $content.find('a').live('click', false).live('mouseover', function (e) { return editor.activateLinkEditor(e) })
            .live('mouseout', function (e) { return editor.deactivateLinkEditor(e) });

        // Set up more stuff.
        $(window).bind('beforeunload', preventNavigation);
        this.updatePublished();
        $.doTimeout('editor.updatePublished', 60000, this.updatePublished);
        jelement.find('.editor-trust').multiselect({
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
        var $editor = this.jelement;

        localStorage['autosave.' + this.autosaveid] = 1;
        localStorage['autosave.' + this.autosaveid + '.title'] = $editor.find('.editor-title').text();
        localStorage['autosave.' + this.autosaveid + '.html'] = $editor.find('.editor-content').html();
        localStorage['autosave.' + this.autosaveid + '.slug'] = $editor.find('.editor-slug').text();

        var $publ = $editor.find('.editor-published');
        if (!$publ.attr('data-now'))
            localStorage['autosave.' + this.autosaveid + '.published'] = $publ.text();

        return true;
    };

    Editor.prototype.removeAutosave = function () {
        localStorage.removeItem('autosave.' + this.autosaveid);
        localStorage.removeItem('autosave.' + this.autosaveid + '.title');
        localStorage.removeItem('autosave.' + this.autosaveid + '.html');
        localStorage.removeItem('autosave.' + this.autosaveid + '.slug');
        localStorage.removeItem('autosave.' + this.autosaveid + '.published');
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
    };

    Editor.prototype.activateLinkEditor = function (e) {
        var $link = $(e.target);
        var linkpos = $link.offset();

        var $linkeditor = this.jelement.find('.link-editor');
        $linkeditor.text($link.attr('href'));
        $linkeditor.bind('keyup', function (e) {
            $link.attr('href', $(this).text());
        });
        $linkeditor.show();
        $linkeditor.offset({ top: linkpos.top + $(this).height(), left: linkpos.left });
        $linkeditor.focus();
    };

    Editor.prototype.deactivateLinkEditor = function (e) {
        var $linkeditor = this.jelement.find('.link-editor');
        $linkeditor.blur();
        $linkeditor.unbind('keyup');
        $linkeditor.hide();
    };

    Editor.prototype.post = function () {
        var $editor = this.jelement;

        var data = {
            //avatar: 
            title: $editor.find('.editor-title').text(),
            html: $.trim($editor.find('.editor-content').html()),
            slug: $editor.find('.editor-slug').text(),
            // TODO: use Date.toISOString() when we have a js date from a picker instead
            published: $.trim($editor.find('.editor-published').text()),
            tags: '',
            comments_enabled: true,
            private: true,
            private_to: []
        };

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
        else {
            data['private'] = true;
            data['private_to'] = [];
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
                $(window).unbind('beforeunload', preventNavigation);
                window.location = data['permalink'];
            },
            error: function (xhr, textStatus, errorThrown) {
                alert('ERROR: ' + xhr.responseText);
            }
        });
    };

    Editor.prototype.discard = function (e) {
        this.removeAutosave();
        $.doTimeout('editor.updatePublished');  // cancel
        $(window).unbind('beforeunload', preventNavigation);

        this.jelement.remove();

        // Let the page undo the editor's appearance.
        $(document).trigger('editorClose');
    };

    $.fn.editor = function (options) {
        var settings = {
            autosaveid: '',
            lastSetting: null
        };
        $.extend(settings, options);

        return this.each(function () {
            var $this = $(this);
            $this.data('editor', new Editor($this, settings));
        });
    };

})(jQuery);
