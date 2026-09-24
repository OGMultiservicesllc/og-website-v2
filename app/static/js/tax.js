/* Tax Smart Intake: autosave, conditional questions, document actions. No dependencies. */
(function () {
    'use strict';
    var form = document.getElementById('tax-form') || document.getElementById('dl-form') || document.getElementById('ct-form');
    var statusEl = document.getElementById('tax-save-status');
    var csrf = window.TAX_CSRF || '';
    var timer = null;

    function say(key) { if (statusEl) { statusEl.textContent = statusEl.getAttribute('data-' + key) || ''; } }

    function toggle(visible) {
        document.querySelectorAll('[data-q]').forEach(function (wrap) {
            var on = visible.indexOf(wrap.getAttribute('data-q')) > -1;
            wrap.hidden = !on;
            wrap.querySelectorAll('input, select, textarea').forEach(function (el) { el.disabled = !on; });
        });
    }

    function save() {
        if (!form || form.getAttribute('data-autosave') !== 'on') { return Promise.resolve(); }
        say('saving');
        var fd = new FormData(form);
        fd.set('autosave', '1');
        fd.delete('nav');
        return fetch(form.getAttribute('action'), { method: 'POST', body: fd, credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch', 'X-CSRFToken': csrf } })
            .then(function (r) { return r.json(); })
            .then(function (j) { say('saved'); if (j && j.visible) { toggle(j.visible); } })
            .catch(function () { say('failed'); });
    }

    if (form && form.getAttribute('data-autosave') === 'on') {
        form.addEventListener('input', function (e) {
            if (e.target.type === 'radio' || e.target.type === 'checkbox' || e.target.tagName === 'SELECT') { return; }
            clearTimeout(timer); timer = setTimeout(save, 900);
        });
        form.addEventListener('change', function (e) {
            var t = e.target;
            if (t.type === 'checkbox' && t.name) {
                var group = form.querySelectorAll('input[type=checkbox][name="' + t.name + '"]');
                if (t.getAttribute('data-exclusive') && t.checked) {
                    group.forEach(function (o) { if (o !== t) { o.checked = false; } });
                } else if (t.checked) {
                    group.forEach(function (o) { if (o.getAttribute('data-exclusive')) { o.checked = false; } });
                }
            }
            clearTimeout(timer); timer = setTimeout(save, 250);
        });
    }

    function docAction(li, url, body, done) {
        var err = li.querySelector('[data-doc-error]');
        if (err) { err.textContent = ''; }
        fetch(url, { method: 'POST', body: body, credentials: 'same-origin', headers: { 'X-CSRFToken': csrf, 'X-Requested-With': 'fetch' } })
            .then(function (r) { return r.json().then(function (j) { return { ok: r.ok && j.ok, j: j }; }); })
            .then(function (res) {
                if (res.ok) { save().then(function () { location.reload(); }); }
                else if (err) { err.textContent = (res.j && res.j.error) || '⚠️'; }
            })
            .catch(function () { if (err) { err.textContent = '⚠️'; } });
    }

    document.addEventListener('change', function (e) {
        var input = e.target;
        if (!input.matches || !input.matches('input[type=file][data-file]')) { return; }
        var li = input.closest('[data-doc]');
        if (!li || !input.files.length) { return; }
        var fd = new FormData();
        fd.append('file', input.files[0]);
        docAction(li, li.getAttribute('data-upload-url'), fd);
    });

    document.addEventListener('click', function (e) {
        var btn = e.target.closest ? e.target.closest('[data-choice], [data-remove]') : null;
        if (!btn) { return; }
        var li = btn.closest('[data-doc]');
        if (!li) { return; }
        var fd = new FormData();
        if (btn.hasAttribute('data-remove')) {
            docAction(li, li.getAttribute('data-remove-url'), fd);
        } else {
            var already = btn.className.indexOf('border-accent-600') > -1;
            fd.append('choice', already ? '' : btn.getAttribute('data-choice'));
            docAction(li, li.getAttribute('data-choice-url'), fd);
        }
    });
})();
