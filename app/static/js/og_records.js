/* Record / timeline builder for Smart Intakes (address history, work & school history,
   travel history, children, offenses, other names...).

   The component only EDITS records. Every date calculation (coverage, gaps, overlaps,
   trip totals) is done by the server (app/intake_records.py) and fetched after each
   change, so what the customer sees here is exactly what the review and Admin see.

   Markup: <div class="og-records" data-input-name data-field-id data-analyze-url data-spec>
   The records are kept in a hidden input named like the field, as JSON. */
(function () {
    var form = document.getElementById('og-form');
    if (!form) return;
    var csrfEl = form.querySelector('input[name="csrf_token"]');
    var prior = {};
    try { prior = JSON.parse(form.dataset.priorValues || '{}'); } catch (e) { prior = {}; }

    function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
    function iso(d) { return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); }
    function parse(s) { if (!s) return null; var p = s.split('-'); return new Date(+p[0], +p[1] - 1, +p[2]); }
    function months(d, lang) {
        var m = lang === 'es' ? ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'] : ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        return m[d.getMonth()] + ' ' + d.getFullYear();
    }
    var LANG = document.documentElement.lang === 'es' ? 'es' : 'en';
    var ICON_WARN = '<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/></svg>';
    var ICON_OK = '<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>';

    document.querySelectorAll('.og-records').forEach(function (root) { init(root); });

    function init(root) {
        var spec = JSON.parse(root.dataset.spec);
        var ui = spec.ui;
        var name = root.dataset.inputName;
        var hidden = root.querySelector('input[type=hidden]');
        var records = [];
        try { records = JSON.parse(prior[name] || '[]') || []; } catch (e) { records = []; }
        if (!Array.isArray(records)) records = [];
        var editing = null;   // null | -1 (new) | index
        var analysis = null;
        var timer = null, seq = 0;

        var summaryBox = el('div'), listBox = el('ul', 'space-y-2 mt-3'), issuesBox = el('ul', 'mt-3 space-y-1.5'), editorBox = el('div'), actionBox = el('div', 'mt-3'), tipBox = el('div');
        root.appendChild(summaryBox); root.appendChild(listBox); root.appendChild(issuesBox); root.appendChild(editorBox); root.appendChild(actionBox); root.appendChild(tipBox);
        if (spec.intro) root.insertBefore(el('p', 'text-[13px] text-slate-500 mb-2', spec.intro), summaryBox);

        function sortRecords() {
            if (!spec.has_dates) return;
            records.sort(function (a, b) {
                if (a.present && !b.present) return -1;
                if (b.present && !a.present) return 1;
                var da = a.from || '', db_ = b.from || '';
                return da < db_ ? 1 : da > db_ ? -1 : 0;
            });
        }
        function commit() {
            sortRecords();
            hidden.value = records.length ? JSON.stringify(records) : '';
            hidden.dispatchEvent(new Event('change', { bubbles: true }));
            schedule();
        }
        function schedule() {
            render();
            clearTimeout(timer);
            timer = setTimeout(analyze, 250);
        }
        function analyze() {
            var my = ++seq;
            var fd = new FormData();
            fd.append('field_id', root.dataset.fieldId);
            fd.append('records', JSON.stringify(records));
            if (spec.since_input) {
                var sinceEl = document.querySelector('[name="' + spec.since_input + '"]');
                if (sinceEl && sinceEl.value) fd.append('since', sinceEl.value);
            }
            fetch(root.dataset.analyzeUrl, { method: 'POST', body: fd, headers: { 'X-CSRFToken': csrfEl ? csrfEl.value : '' }, credentials: 'same-origin' })
                .then(function (r) { return r.ok ? r.json() : null; })
                .then(function (data) { if (my !== seq || !data) return; analysis = data; render(); })
                .catch(function () {});
        }

        function fieldVisible(f, rec) { return !f.show_if || f.show_if.values.indexOf(rec[f.show_if.field] || '') !== -1; }

        // ---------- rendering
        function render() {
            renderSummary(); renderList(); renderIssues(); renderAction(); renderTip();
        }
        function renderSummary() {
            summaryBox.innerHTML = '';
            if (spec.kind_trip) {
                if (analysis && records.length) {
                    var box = el('div', 'rounded-xl bg-mist-50 border border-mist-200 px-3.5 py-2.5 flex flex-wrap gap-x-6 gap-y-1 text-[13px] text-brand-800');
                    var s = analysis.summary || {};
                    box.appendChild(el('span', '', ui.trips + ': ')); box.lastChild.appendChild(el('strong', '', String(s.trips || 0)));
                    var d = el('span', '', ui.days_outside + ': '); d.appendChild(el('strong', '', String(s.days_outside || 0))); box.appendChild(d);
                    summaryBox.appendChild(box);
                }
                return;
            }
            if (!spec.timeline) return;
            var s2 = analysis && analysis.summary, tl = analysis && analysis.timeline;
            var wrap = el('div', 'rounded-xl bg-mist-50 border border-mist-200 px-3.5 py-3');
            var pct = s2 ? s2.percent : 0;
            var line = el('p', 'text-[13px] font-semibold text-brand-800');
            if (s2 && records.length) {
                var t = (s2.years ? s2.years + ' ' + ui.years + ' ' : '') + (s2.months || !s2.years ? s2.months + ' ' + ui.months : '');
                line.textContent = t.trim() + ' ' + ui.covered + ' ' + ui.of + ' ' + s2.window_years + ' ' + ui.years + ' (' + pct + '%)';
            } else {
                line.textContent = ui.window + ': ' + spec.timeline.years + ' ' + ui.years;
            }
            wrap.appendChild(line);
            var bar = el('div', 'mt-2 flex h-2.5 rounded-full overflow-hidden bg-fog-200');
            bar.setAttribute('role', 'img');
            bar.setAttribute('aria-label', line.textContent);
            if (tl && records.length) {
                var total = parse(tl.end) - parse(tl.start) + 86400000;
                tl.segments.forEach(function (seg) {
                    var w = (parse(seg.end) - parse(seg.start) + 86400000) / total * 100;
                    var part = el('div', seg.covered ? 'bg-accent-500' : 'bg-amber-400');
                    part.style.width = w + '%';
                    bar.appendChild(part);
                });
            }
            wrap.appendChild(bar);
            if (tl) {
                var ends = el('div', 'mt-1 flex justify-between text-[11px] text-slate-500');
                ends.appendChild(el('span', '', months(parse(tl.start), LANG))); ends.appendChild(el('span', '', ui.present));
                wrap.appendChild(ends);
            }
            summaryBox.appendChild(wrap);
        }
        function flagsOf(i) {
            var f = analysis && analysis.cards && analysis.cards[i] ? analysis.cards[i].flags : [];
            return f || [];
        }
        function renderList() {
            listBox.innerHTML = '';
            records.forEach(function (rec, i) {
                var card = analysis && analysis.cards && analysis.cards[i] && analysis.cards.length === records.length ? analysis.cards[i] : null;
                var warn = card && card.flags.some(function (f) { return f === 'warn' || f === 'error' || f === 'review'; });
                var li = el('li', 'rounded-xl border bg-white px-3.5 py-3 flex items-start gap-3 ' + (warn ? 'border-amber-300' : 'border-slate-200'));
                var body = el('div', 'min-w-0 flex-1');
                var title = el('p', 'text-[15px] font-semibold text-brand-800 break-words', card ? card.title : '');
                if (!card) title.textContent = '…';
                body.appendChild(title);
                if (card && card.subtitle) body.appendChild(el('p', 'text-[13px] text-slate-500 break-words', card.subtitle));
                if (rec.present && spec.timeline) { var b = el('span', 'inline-block mt-1 rounded-full bg-emerald-50 text-emerald-700 text-[11px] font-bold px-2 py-0.5', ui.current); body.appendChild(b); }
                li.appendChild(body);
                var acts = el('div', 'flex flex-col sm:flex-row gap-1 shrink-0');
                var eb = el('button', 'min-h-[40px] px-3 rounded-lg border border-slate-200 text-[13px] font-semibold text-accent-700 hover:border-accent-300', ui.edit); eb.type = 'button';
                eb.addEventListener('click', function () { openEditor(i); });
                var rb = el('button', 'min-h-[40px] px-3 rounded-lg text-[13px] font-semibold text-red-600 hover:bg-red-50', ui.remove); rb.type = 'button';
                rb.addEventListener('click', function () { records.splice(i, 1); if (editing !== null) editing = null; renderEditor(); commit(); });
                acts.appendChild(eb); acts.appendChild(rb); li.appendChild(acts);
                listBox.appendChild(li);
            });
        }
        function renderIssues() {
            issuesBox.innerHTML = '';
            if (!analysis) return;
            var shown = analysis.issues.filter(function (x) { return x.level !== 'info'; });
            var okAll = spec.timeline && records.length && analysis.complete;
            if (okAll) {
                var ok = el('li', 'flex items-center gap-2 text-[13px] font-semibold text-emerald-700');
                ok.innerHTML = ICON_OK; ok.appendChild(el('span', '', ui.complete)); issuesBox.appendChild(ok);
            }
            shown.forEach(function (x) {
                var li = el('li', 'flex items-start gap-2 rounded-lg px-3 py-2 text-[13px] leading-snug ' + (x.level === 'error' ? 'bg-red-50 text-red-800' : 'bg-amber-50 text-amber-900'));
                li.innerHTML = ICON_WARN; li.appendChild(el('span', 'min-w-0', x.message));
                issuesBox.appendChild(li);
            });
            analysis.issues.filter(function (x) { return x.level === 'info'; }).forEach(function (x) {
                issuesBox.appendChild(el('li', 'text-[12px] text-slate-500 px-1', x.message));
            });
        }
        function renderAction() {
            actionBox.innerHTML = '';
            if (editing !== null) return;
            if (records.length >= spec.max) return;
            var label = records.length ? spec.add : spec.add_first;
            if (!records.length && spec.empty) actionBox.appendChild(el('p', 'text-[15px] font-semibold text-brand-800 mb-2', spec.empty));
            var b = el('button', 'w-full sm:w-auto min-h-[48px] rounded-xl border-2 border-dashed border-accent-300 bg-accent-50/40 px-5 text-[15px] font-semibold text-accent-700 hover:bg-accent-50 transition', '+ ' + label);
            b.type = 'button'; b.addEventListener('click', function () { openEditor(-1); });
            actionBox.appendChild(b);
        }
        function renderTip() {
            tipBox.innerHTML = '';
            if (spec.kind_trip) tipBox.appendChild(el('p', 'mt-3 text-[13px] text-slate-500 leading-relaxed', ui.memory));
        }

        // ---------- editor
        function openEditor(index) { editing = index; renderEditor(); render(); var f = editorBox.querySelector('input:not([type=hidden]), select'); if (f) { f.focus({ preventScroll: false }); } }
        function closeEditor() { editing = null; editorBox.innerHTML = ''; render(); }
        function renderEditor() {
            editorBox.innerHTML = '';
            if (editing === null) return;
            var isNew = editing === -1;
            var rec = isNew ? defaults() : JSON.parse(JSON.stringify(records[editing]));
            var panel = el('div', 'mt-3 rounded-2xl border-2 border-accent-300 bg-white p-4 space-y-4');
            panel.setAttribute('role', 'group');
            panel.setAttribute('aria-label', isNew ? (records.length ? spec.add : spec.add_first) : ui.edit);
            var errBox = el('p', 'text-[13px] font-semibold text-red-700 hidden');
            errBox.setAttribute('role', 'alert');
            var grid = el('div', 'grid grid-cols-1 sm:grid-cols-2 gap-x-3 gap-y-3');
            var inputs = {};
            var groups = {};

            function refreshVisibility() {
                Object.keys(groups).forEach(function (k) {
                    var f = groups[k].f;
                    groups[k].node.style.display = fieldVisible(f, rec) ? '' : 'none';
                });
            }
            function labelFor(text, id, required) {
                var l = el('label', 'block text-sm font-semibold text-slate-800 mb-1.5', text);
                l.setAttribute('for', id);
                if (required) { var s = el('span', 'text-red-600', ' *'); s.setAttribute('aria-hidden', 'true'); l.appendChild(s); }
                return l;
            }
            var uid = 'rec-' + root.dataset.fieldId + '-';

            // dates first (they are what places an entry on the timeline)
            function dateBlock() {
                var box = el('div', 'sm:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-x-3 gap-y-3');
                var fromL = spec.kind_trip ? ui.left : ui.from, toL = spec.kind_trip ? ui.returned : ui.to;
                var a = el('div'); a.appendChild(labelFor(fromL, uid + 'from', true));
                var fi = el('input', 'w-full min-h-[48px] rounded-xl border border-slate-200 px-3 text-[15px]'); fi.type = 'date'; fi.id = uid + 'from'; fi.value = rec.from || ''; fi.max = spec.today;
                fi.addEventListener('input', function () { rec.from = fi.value; });
                a.appendChild(fi); inputs.from = fi;
                var b = el('div'); b.appendChild(labelFor(toL, uid + 'to', true));
                var ti = el('input', 'w-full min-h-[48px] rounded-xl border border-slate-200 px-3 text-[15px]'); ti.type = 'date'; ti.id = uid + 'to'; ti.value = rec.to || ''; ti.max = spec.today;
                ti.addEventListener('input', function () { rec.to = ti.value; });
                b.appendChild(ti); inputs.to = ti;
                box.appendChild(a); box.appendChild(b);
                if (!spec.kind_trip) {
                    var pw = el('label', 'sm:col-span-2 flex items-center gap-2.5 text-[14px] text-slate-700 min-h-[44px] cursor-pointer');
                    var pc = el('input', 'w-5 h-5 rounded text-accent-600'); pc.type = 'checkbox'; pc.checked = !!rec.present;
                    pc.addEventListener('change', function () { rec.present = pc.checked; b.style.display = pc.checked ? 'none' : ''; if (pc.checked) { rec.to = ''; ti.value = ''; } });
                    pw.appendChild(pc); pw.appendChild(el('span', '', ui.present_check));
                    box.appendChild(pw);
                    b.style.display = rec.present ? 'none' : '';
                    inputs.present = pc;
                }
                return box;
            }
            var dateAfterFirst = spec.record === 'activity' || spec.record === 'address';
            if (spec.has_dates && !dateAfterFirst) grid.appendChild(dateBlock());

            spec.fields.forEach(function (f) {
                var wrap = el('div', f.width === 'half' ? '' : 'sm:col-span-2');
                var id = uid + f.name;
                wrap.appendChild(labelFor(f.label, id, f.required));
                if (f.help) wrap.appendChild(el('p', 'text-[13px] text-slate-500 -mt-0.5 mb-1.5 leading-snug', f.help));
                var input;
                if (f.type === 'choice') {
                    input = el('div', 'grid grid-cols-1 sm:grid-cols-2 gap-2');
                    input.setAttribute('role', 'radiogroup');
                    f.options.forEach(function (o) {
                        var lab = el('label', 'flex items-center gap-3 rounded-xl border-2 border-slate-200 bg-white px-4 min-h-[48px] text-[15px] text-slate-800 cursor-pointer hover:border-accent-300 has-[:checked]:border-accent-500 has-[:checked]:bg-accent-50');
                        var r = el('input', 'w-5 h-5 text-accent-600'); r.type = 'radio'; r.name = id; r.value = o.value; r.checked = rec[f.name] === o.value;
                        r.addEventListener('change', function () { rec[f.name] = o.value; refreshVisibility(); });
                        lab.appendChild(r); lab.appendChild(document.createTextNode(o.label)); input.appendChild(lab);
                    });
                } else if (f.type === 'select') {
                    input = el('select', 'w-full min-h-[48px] rounded-xl border border-slate-200 bg-white px-3 text-[15px]'); input.id = id;
                    var blank = el('option', '', ui.select); blank.value = ''; input.appendChild(blank);
                    f.options.forEach(function (o) { var op = el('option', '', o.label); op.value = o.value; if (rec[f.name] === o.value) op.selected = true; input.appendChild(op); });
                    input.addEventListener('change', function () { rec[f.name] = input.value; refreshVisibility(); });
                } else {
                    input = el('input', 'w-full min-h-[48px] rounded-xl border border-slate-200 px-3 text-[15px]'); input.id = id;
                    input.type = f.type === 'date' ? 'date' : 'text'; input.value = rec[f.name] || '';
                    if (f.maxlength) input.maxLength = f.maxlength;
                    if (f.type === 'date') input.max = spec.today;
                    if (f.name === 'zip') input.inputMode = 'numeric';
                    input.addEventListener('input', function () { rec[f.name] = input.value; });
                }
                wrap.appendChild(input);
                var fe = el('p', 'mt-1 text-[13px] font-medium text-red-700 hidden'); fe.setAttribute('role', 'alert'); wrap.appendChild(fe);
                inputs[f.name] = { node: input, err: fe };
                groups[f.name] = { node: wrap, f: f };
                grid.appendChild(wrap);
            });
            if (spec.has_dates && dateAfterFirst) grid.appendChild(dateBlock());
            refreshVisibility();
            panel.appendChild(errBox);
            panel.appendChild(grid);

            var row = el('div', 'flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-1');
            var cancel = el('button', 'min-h-[48px] px-5 rounded-xl border border-slate-200 text-[15px] font-semibold text-slate-700 hover:border-slate-300', ui.cancel); cancel.type = 'button';
            cancel.addEventListener('click', closeEditor);
            var save = el('button', 'min-h-[48px] px-6 rounded-xl bg-accent-600 text-white text-[15px] font-semibold hover:bg-accent-700', ui.save); save.type = 'button';
            save.addEventListener('click', function () {
                var bad = 0;
                spec.fields.forEach(function (f) {
                    var g = inputs[f.name]; if (!g) return; g.err.classList.add('hidden'); g.err.textContent = '';
                    if (!fieldVisible(f, rec)) { delete rec[f.name]; return; }
                    var v = (rec[f.name] || '').toString().trim();
                    var msg = '';
                    if (f.required && !v) msg = ui.required;
                    else if (f.pattern && v && !new RegExp('^' + f.pattern + '$').test(v)) msg = ui.required;
                    if (msg) { g.err.textContent = msg; g.err.classList.remove('hidden'); bad++; }
                });
                if (spec.has_dates) {
                    if (!rec.from) { bad++; errBox.textContent = ui.fix_form; errBox.classList.remove('hidden'); }
                    if (!rec.present && !rec.to) { bad++; errBox.textContent = ui.fix_form; errBox.classList.remove('hidden'); }
                }
                if (bad) { errBox.textContent = ui.fix_form; errBox.classList.remove('hidden'); return; }
                if (isNew) records.push(rec); else records[editing] = rec;
                editing = null; editorBox.innerHTML = '';
                commit();
                var addBtn = actionBox.querySelector('button'); if (addBtn) addBtn.focus();
            });
            row.appendChild(cancel); row.appendChild(save);
            panel.appendChild(row);
            editorBox.appendChild(panel);
        }
        function defaults() {
            var rec = {};
            spec.fields.forEach(function (f) { if (f.type === 'choice' && f.options.length === 2 && f.name === 'is_us') rec[f.name] = 'yes'; });
            if (spec.timeline && spec.has_dates) {
                if (!records.length) { rec.present = true; }
                else {
                    var earliest = records.reduce(function (m, r) { return r.from && (!m || r.from < m) ? r.from : m; }, null);
                    if (earliest) { var d = parse(earliest); d.setDate(d.getDate() - 1); rec.to = iso(d); }
                }
            }
            return rec;
        }

        // an unsaved editor must not be silently lost when the customer presses Continue
        form.addEventListener('submit', function (e) {
            if (editing !== null && e.submitter && e.submitter.getAttribute('name') !== 'nav') {
                e.preventDefault();
                var p = editorBox.querySelector('[role=alert]');
                editorBox.scrollIntoView({ block: 'center' });
                var msg = LANG === 'es' ? 'Guarda o cancela esta entrada antes de continuar.' : 'Save or cancel this entry before continuing.';
                var first = editorBox.querySelector('p[role=alert]'); if (first) { first.textContent = msg; first.classList.remove('hidden'); }
            }
        }, true);

        if (spec.since_input) {
            var sinceWatch = document.querySelector('[name="' + spec.since_input + '"]');
            if (sinceWatch) sinceWatch.addEventListener('change', function () { if (records.length) analyze(); });
        }
        hidden.value = records.length ? JSON.stringify(records) : '';
        sortRecords();
        render();
        if (records.length) analyze();
        else { analysis = null; }
    }
})();
