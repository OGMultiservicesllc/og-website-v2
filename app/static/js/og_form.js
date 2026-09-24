(function () {
    var form = document.getElementById('og-form');
    var csrf = form.querySelector('input[name="csrf_token"]').value;

    // ---- 1. Re-populate previously saved answers (back, language switch, validation redisplay)
    var prior = {};
    try { prior = JSON.parse(form.dataset.priorValues || '{}'); } catch (e) { prior = {}; }
    Object.keys(prior).forEach(function (name) {
        var raw = prior[name];
        var els = form.querySelectorAll('[name="' + name + '"], [name="' + name + '[]"]');
        if (!els.length) return;
        var first = els[0];
        if (first.type === 'radio' || first.type === 'checkbox') {
            var selected;
            try { selected = JSON.parse(raw); if (!Array.isArray(selected)) selected = [raw]; } catch (e) { selected = [raw]; }
            els.forEach(function (el) { el.checked = selected.indexOf(el.value) !== -1; });
        } else if (first.tagName === 'SELECT' && first.multiple) {
            var multi;
            try { multi = JSON.parse(raw); } catch (e) { multi = [raw]; }
            Array.prototype.forEach.call(first.options, function (opt) { opt.selected = multi.indexOf(opt.value) !== -1; });
        } else if (first.type !== 'file') {
            first.value = raw;
        }
    });

    // ---- 2. Live conditional logic (mirrors the server, which stays authoritative)
    var rules = [], others = {};
    try { rules = JSON.parse(form.dataset.rules || '[]'); } catch (e) {}
    try { others = JSON.parse(form.dataset.otherAnswers || '{}'); } catch (e) {}

    function liveValue(fieldId) {
        var els = form.querySelectorAll('[name="field_' + fieldId + '"], [name="field_' + fieldId + '[]"]');
        if (!els.length) {
            var saved = others[String(fieldId)];
            if (saved === undefined || saved === null) return '';
            if (Array.isArray(saved)) return saved;
            try { var p = JSON.parse(saved); if (Array.isArray(p)) return p; } catch (e) {}
            return saved;
        }
        var first = els[0];
        if (first.type === 'radio') { var r = form.querySelector('[name="' + first.name + '"]:checked'); return r ? r.value : ''; }
        if (first.type === 'checkbox') {
            var checked = Array.prototype.filter.call(els, function (e) { return e.checked; }).map(function (e) { return e.value; });
            return els.length > 1 ? checked : (checked.length ? 'accepted' : 'declined');
        }
        if (first.tagName === 'SELECT' && first.multiple) return Array.prototype.filter.call(first.options, function (o) { return o.selected; }).map(function (o) { return o.value; });
        return first.value;
    }
    function num(v) { var n = parseFloat(v); return isNaN(n) ? null : n; }
    function matches(op, actual, expected) {
        var list = Array.isArray(actual) ? actual : [actual === undefined || actual === null ? '' : actual];
        var empty = Array.isArray(actual) ? actual.length === 0 : !actual;
        expected = expected === null || expected === undefined ? '' : String(expected);
        switch (op) {
            case 'is_empty': return empty;
            case 'is_not_empty': return !empty;
            case 'selected': return list.indexOf(expected) !== -1;
            case 'not_selected': return list.indexOf(expected) === -1;
            case 'equals': return list.some(function (v) { return v === expected; });
            case 'not_equals': return list.every(function (v) { return v !== expected; });
            case 'contains': return list.some(function (v) { return expected && String(v).indexOf(expected) !== -1; });
            case 'not_contains': return list.every(function (v) { return !(expected && String(v).indexOf(expected) !== -1); });
            case 'greater_than': return list.some(function (v) { var a = num(v), b = num(expected); return a !== null && b !== null && a > b; });
            case 'less_than': return list.some(function (v) { var a = num(v), b = num(expected); return a !== null && b !== null && a < b; });
        }
        return false;
    }
    function ruleMatched(rule) {
        if (!rule.conditions.length) return false;
        var results = rule.conditions.map(function (c) { return matches(c.op, liveValue(c.field), c.value); });
        return rule.match === 'all' ? results.every(Boolean) : results.some(Boolean);
    }
    var requiredDefault = new Map();
    form.querySelectorAll('.og-field input, .og-field select, .og-field textarea').forEach(function (el) { requiredDefault.set(el, el.required); });
    function applyRules() {
        if (!rules.length) return;
        var effects = {}, shows = {};
        rules.forEach(function (rule) {
            var matched = ruleMatched(rule);
            var e = effects[rule.target] = effects[rule.target] || {};
            if (rule.action === 'show_field') (shows[rule.target] = shows[rule.target] || []).push(matched);
            else if (rule.action === 'hide_field') { if (matched) e.visible = false; }
            else if (rule.action === 'require_field' && matched) e.required = true;
            else if (rule.action === 'optional_field' && matched) e.required = false;
        });
        Object.keys(shows).forEach(function (t) {
            effects[t].visible = shows[t].some(Boolean) && effects[t].visible !== false;
        });
        Object.keys(effects).forEach(function (id) {
            var wrap = form.querySelector('.og-field[data-field-id="' + id + '"]');
            if (!wrap) return;
            var visible = effects[id].visible !== false;
            wrap.style.display = visible ? '' : 'none';
            wrap.querySelectorAll('input, select, textarea').forEach(function (el) { el.disabled = !visible; });
            wrap.querySelectorAll('input, select, textarea').forEach(function (el) {
                if (el.type === 'hidden') return;
                // File inputs' `required` is owned by the instant-upload logic below (cleared the moment a
                // document is actually saved, restored if it's removed again) — NOT by this function's stale
                // page-load snapshot. Without this guard, uploading a SECOND file on the same page (e.g. the
                // Green Card back after the front) fires a 'change' event that bubbles here and — because a
                // file field is normally only a show_field rule TARGET, never a require_field one, so
                // `effects[id].required` stays undefined — silently resets the FIRST field's `required` back
                // to true even though it already has a saved file, silently blocking "Continue" client-side
                // with no visible error (confirmed live, 2026-09-24: form.checkValidity() === false,
                // validationMessage "Please select a file." on a field the UI shows as already uploaded).
                // An explicit require_field/optional_field rule (effects[id].required is true/false, not
                // undefined) still applies normally — only the "fall back to the stale default" path is skipped.
                if (el.type === 'file' && effects[id].required === undefined) return;
                var base = requiredDefault.get(el) || false;
                el.required = visible && (effects[id].required === true ? true : (effects[id].required === false ? false : base));
            });
        });
    }
    form.addEventListener('input', applyRules);
    form.addEventListener('change', applyRules);
    applyRules();

    // Browsers validate visible required fields before submit; our own "back"/"exit" buttons skip it.
    form.addEventListener('submit', function (e) {
        var submitter = e.submitter;
        if (submitter && submitter.hasAttribute('formnovalidate')) return;
        if (!form.checkValidity()) { e.preventDefault(); form.reportValidity(); }
    });

    // ---- 3. Signature pads, star ratings, file pickers
    document.querySelectorAll('.og-signature-field').forEach(function (wrap) {
        var canvas = wrap.querySelector('.og-signature-pad');
        var hidden = wrap.querySelector('input[type=hidden]');
        var clearBtn = wrap.querySelector('.og-signature-clear');
        if (!canvas || typeof SignaturePad === 'undefined') return;
        var ratio = Math.max(window.devicePixelRatio || 1, 1);
        canvas.width = canvas.offsetWidth * ratio;
        canvas.height = canvas.offsetHeight * ratio;
        canvas.getContext('2d').scale(ratio, ratio);
        var pad = new SignaturePad(canvas, { penColor: '#0f1829' });
        pad.addEventListener('endStroke', function () { hidden.value = pad.toDataURL('image/png'); });
        clearBtn.addEventListener('click', function () { pad.clear(); hidden.value = ''; });
    });
    document.querySelectorAll('.og-rating').forEach(function (wrap) {
        var hidden = wrap.querySelector('input[type=hidden]');
        var stars = Array.prototype.slice.call(wrap.querySelectorAll('.og-rating-star'));
        function paint(value) {
            stars.forEach(function (star) {
                star.classList.toggle('text-amber-400', parseInt(star.dataset.value, 10) <= value);
                star.classList.toggle('text-slate-300', parseInt(star.dataset.value, 10) > value);
            });
        }
        paint(parseInt(hidden.value, 10) || 0);
        stars.forEach(function (star) {
            star.addEventListener('click', function () {
                hidden.value = star.dataset.value;
                paint(parseInt(star.dataset.value, 10));
                hidden.dispatchEvent(new Event('input', { bubbles: true }));
            });
        });
    });
    document.querySelectorAll('.og-file-field').forEach(function (wrap) {
        var input = wrap.querySelector('.og-file-input');
        var list = wrap.querySelector('.og-file-list');
        input.addEventListener('change', function () {
            list.innerHTML = '';
            Array.prototype.forEach.call(input.files, function (file) {
                var row = document.createElement('div');
                row.className = 'flex items-center justify-between text-xs text-slate-600 bg-slate-50 rounded-lg px-3 py-1.5';
                var kb = Math.round(file.size / 1024);
                row.textContent = file.name + ' — ' + (kb > 1024 ? (kb / 1024).toFixed(1) + ' MB' : kb + ' KB');
                list.appendChild(row);
            });
        });
    });

    // ---- 4. Autosave (signed-in service intakes only)
    var url = form.dataset.autosave;
    if (!url) return;
    var status = document.getElementById('og-save-status');
    var timer = null, dirty = false, inflight = false, failures = 0;
    var CHECK = '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>';
    var SPIN = '<svg class="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="3" opacity=".25"/><path d="M21 12a9 9 0 00-9-9" stroke="currentColor" stroke-width="3" stroke-linecap="round"/></svg>';
    function show(state) {
        if (!status) return;
        if (state === 'saving') { status.className = 'og-save-status inline-flex items-center gap-1.5 font-medium text-slate-400'; status.innerHTML = SPIN + status.dataset.saving; }
        else if (state === 'saved') { status.className = 'og-save-status inline-flex items-center gap-1.5 font-medium text-emerald-600'; status.innerHTML = CHECK + status.dataset.saved; }
        else if (state === 'failed') { status.className = 'og-save-status inline-flex items-center gap-1.5 font-medium text-amber-600'; status.textContent = status.dataset.failed; }
    }
    function payload() {
        var fd = new FormData(form);
        Array.from(fd.keys()).forEach(function (k) { if (fd.get(k) instanceof File) fd.delete(k); });
        fd.delete('nav');
        return fd;
    }
    function save() {
        if (inflight) { dirty = true; return Promise.resolve(); }
        inflight = true; dirty = false; show('saving');
        return fetch(url, { method: 'POST', body: payload(), headers: { 'X-CSRFToken': csrf }, credentials: 'same-origin' })
            .then(function (r) { if (!r.ok) throw new Error('save failed'); failures = 0; show('saved'); })
            .catch(function () { failures += 1; show('failed'); dirty = true; if (failures < 6) schedule(Math.min(1000 * Math.pow(2, failures), 15000)); })
            .then(function () { inflight = false; if (dirty && failures === 0) schedule(300); });
    }
    function schedule(delay) { clearTimeout(timer); timer = setTimeout(save, delay || 900); }
    form.addEventListener('input', function () { dirty = true; schedule(); });
    form.addEventListener('change', function () { dirty = true; schedule(); });

    // Never lose typing when the customer switches language or leaves the page.
    document.querySelectorAll('[data-lang-switch]').forEach(function (a) {
        a.addEventListener('click', function (e) {
            if (!dirty && !inflight) return;
            e.preventDefault();
            clearTimeout(timer);
            save().then(function () { window.location.href = a.href; });
        });
    });
    window.addEventListener('pagehide', function () {
        if (!dirty || !navigator.sendBeacon) return;
        var fd = payload(); fd.append('csrf_token', csrf);
        navigator.sendBeacon(url, fd);
    });
})();

/* ------------------------------------------------------------------------
   Smart-intake enhancements (only when the form is marked data-intake):
   instant document upload with a saved list (view / replace / remove),
   drag & drop, accessible error wiring, and double-submit protection.
   ------------------------------------------------------------------------ */
(function () {
    var form = document.getElementById('og-form');
    if (!form || !form.dataset.intake) return;
    var csrf = form.querySelector('input[name="csrf_token"]').value;
    var token = form.querySelector('input[name="resume_token"]').value;
    var uploadUrl = form.dataset.uploadUrl;
    var msg = {};
    try { msg = JSON.parse(form.dataset.msg || '{}'); } catch (e) { msg = {}; }
    var existing = {};
    try { existing = JSON.parse(form.dataset.existingFiles || '{}'); } catch (e) { existing = {}; }

    function fmtSize(bytes) { var kb = Math.round(bytes / 1024); return kb > 1024 ? (kb / 1024).toFixed(1) + ' MB' : kb + ' KB'; }
    function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text) n.textContent = text; return n; }

    function toggleDrop(wrap, count) {
        var max = parseInt(wrap.dataset.maxFiles, 10);
        var drop = wrap.querySelector('.og-file-drop');
        var label = drop.querySelector('span');
        label.textContent = (max === 1 && count > 0) ? msg.replace : msg.choose;
        drop.style.display = (max > 1 && count >= max) ? 'none' : '';
    }
    function showError(wrap, text) {
        var box = wrap.querySelector('[data-upload-error]');
        if (!box) { box = el('p', 'mt-1.5 text-[13px] font-medium text-red-700'); box.setAttribute('data-upload-error', ''); box.setAttribute('role', 'alert'); wrap.appendChild(box); }
        box.textContent = text || '';
    }
    function renderFiles(wrap, files) {
        // The single place that owns this file input's `required` attribute: required only while the
        // field is BOTH form-required (wrap._trueRequired, captured once at setup from the server-rendered
        // value, before any upload/remove has happened) AND currently empty. Called after every list change
        // (initial load, a successful upload, a removal), so "Remove" now correctly re-requires an emptied
        // required field instead of leaving it permanently satisfied — this was silently NOT true before.
        var input = wrap.querySelector('.og-file-input');
        input.required = files.length === 0 && !!wrap._trueRequired;
        var box = wrap.querySelector('.og-file-existing');
        box.innerHTML = '';
        files.forEach(function (f) {
            var row = el('div', 'flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-3.5 py-2.5');
            var ok = el('span', 'w-6 h-6 rounded-full bg-emerald-500 text-white flex items-center justify-center shrink-0');
            ok.innerHTML = '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>';
            var info = el('div', 'min-w-0 flex-1');
            info.appendChild(el('p', 'text-sm font-semibold text-emerald-900 truncate', f.name));
            info.appendChild(el('p', 'text-xs text-emerald-800/70', fmtSize(f.size)));
            var view = el('a', 'text-sm font-semibold text-accent-700 hover:underline', msg.view); view.href = f.view; view.target = '_blank'; view.rel = 'noopener';
            var del = el('button', 'text-sm font-semibold text-red-600 hover:underline min-h-[36px] px-1', msg.remove); del.type = 'button';
            del.addEventListener('click', function () {
                del.disabled = true;
                fetch(f.remove, { method: 'POST', headers: { 'X-CSRFToken': csrf }, credentials: 'same-origin' })
                    .then(function (r) { if (!r.ok) throw new Error('remove'); renderFiles(wrap, files.filter(function (x) { return x.id !== f.id; })); })
                    .catch(function () { del.disabled = false; showError(wrap, msg.failed); });
            });
            row.appendChild(ok); row.appendChild(info); row.appendChild(view); row.appendChild(del);
            box.appendChild(row);
        });
        toggleDrop(wrap, files.length);
    }
    function upload(wrap, fileList) {
        if (!fileList.length) return;
        var fd = new FormData();
        fd.append('resume_token', token);
        fd.append('field_id', wrap.dataset.fieldId);
        var name = wrap.dataset.inputName + (parseInt(wrap.dataset.maxFiles, 10) > 1 ? '[]' : '');
        Array.prototype.forEach.call(fileList, function (f) { fd.append(name, f); });
        showError(wrap, '');
        var busy = el('p', 'text-sm text-slate-500 mt-1', msg.uploading); wrap.appendChild(busy);
        fetch(uploadUrl, { method: 'POST', body: fd, headers: { 'X-CSRFToken': csrf }, credentials: 'same-origin' })
            .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
            .then(function (res) {
                busy.remove();
                if (!res.ok) { showError(wrap, res.j.message || msg.failed); return; }
                renderFiles(wrap, res.j.files);
                var input = wrap.querySelector('.og-file-input'); input.value = '';
                var list = wrap.querySelector('.og-file-list'); if (list) list.innerHTML = '';
            })
            .catch(function () { busy.remove(); showError(wrap, msg.failed); });
    }
    document.querySelectorAll('.og-file-field').forEach(function (wrap) {
        var input = wrap.querySelector('.og-file-input');
        var drop = wrap.querySelector('.og-file-drop');
        // Captured BEFORE renderFiles() touches `required` below — this is the server-rendered, form-design
        // requiredness (matches field.required from Python), independent of whether a file already exists.
        wrap._trueRequired = input.required;
        var files = existing[wrap.dataset.inputName] || existing[wrap.dataset.inputName + '[]'] || [];
        renderFiles(wrap, files);
        input.addEventListener('change', function () { upload(wrap, input.files); });
        ['dragenter', 'dragover'].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add('border-accent-500', 'bg-accent-50'); }); });
        ['dragleave', 'drop'].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove('border-accent-500', 'bg-accent-50'); }); });
        drop.addEventListener('drop', function (e) { if (e.dataTransfer && e.dataTransfer.files.length) upload(wrap, e.dataTransfer.files); });
    });

    // Errors: mark inputs invalid, tie the message to them, and move focus to the summary.
    document.querySelectorAll('.og-field [data-error]').forEach(function (err) {
        err.closest('.og-field').querySelectorAll('input, select, textarea').forEach(function (i) { i.setAttribute('aria-invalid', 'true'); i.setAttribute('aria-describedby', err.id); });
    });
    var summary = document.getElementById('og-error-summary');
    if (summary) summary.focus();

    // One submission at a time.
    form.addEventListener('submit', function (e) {
        if (form.dataset.submitting === '1') { e.preventDefault(); return; }
        if (e.defaultPrevented) return;
        form.dataset.submitting = '1';
        setTimeout(function () { form.dataset.submitting = ''; }, 6000);
    });
})();
