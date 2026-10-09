(function () {
    'use strict';
    var overlay = document.getElementById('page-loading-overlay');
    var flash = document.getElementById('flash');
    var board = document.getElementById('board');
    var timer = null;

    function csrf() {
        var m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
        return m ? decodeURIComponent(m[1]) : '';
    }
    // Admin-тэй адил: 120ms-ээс удвал л overlay харуулна.
    function start() { if (!timer) timer = setTimeout(function () { overlay.classList.add('on'); }, 120); }
    function stop() { clearTimeout(timer); timer = null; overlay.classList.remove('on'); }
    function say(msg, ok) {
        if (!flash) return;
        flash.innerHTML = '';
        var d = document.createElement('div');
        d.className = 'flash flash-' + (ok ? 'success' : 'error');
        d.textContent = msg;
        flash.appendChild(d);
        window.scrollTo({ top: 0, behavior: 'smooth' });
        setTimeout(function () { if (d.parentNode) d.remove(); }, 5000);
    }

    // Theme toggle (admin-тай ижил localStorage түлхүүр)
    var tb = document.querySelector('.theme-toggle');
    if (tb) tb.addEventListener('click', function () {
        var next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
        document.documentElement.dataset.theme = next;
        try { localStorage.setItem('theme', next); } catch (e) {}
    });

    // Жирийн холбоос / form-оор хуудас солих үед overlay
    document.addEventListener('click', function (e) {
        var a = e.target.closest('a');
        if (!a || a.target === '_blank' || e.defaultPrevented) return;
        var h = a.getAttribute('href');
        if (!h || h.charAt(0) === '#' || h.indexOf('tel:') === 0 || e.metaKey || e.ctrlKey) return;
        start();
    });
    document.addEventListener('submit', function (e) {
        if (!e.defaultPrevented && !e.target.closest('#board')) start();
    });
    window.addEventListener('pageshow', stop);

    if (!board) return;

    function post(step, formData, btn) {
        start();
        board.classList.add('is-busy');
        if (btn) btn.disabled = true;
        return fetch(board.dataset.url.replace('STEP', step), {
            method: 'POST', body: formData, credentials: 'same-origin',
            headers: { 'X-CSRFToken': csrf(), 'X-Requested-With': 'XMLHttpRequest' }
        }).then(function (r) {
            if (r.status === 403 || r.redirected) { location.reload(); throw new Error('auth'); }
            return r.json();
        }).then(function (j) {
            if (j.html) board.innerHTML = j.html;   // зөвхөн самбарын хэсэг шинэчлэгдэнэ
            say(j.message || '', j.ok);
            return j;
        }).catch(function (err) {
            if (err.message !== 'auth') say('Сүлжээний алдаа. Дахин оролдоно уу.', false);
        }).then(function () {
            board.classList.remove('is-busy'); stop();
            if (btn) btn.disabled = false;
        });
    }

    board.addEventListener('submit', function (e) {
        var f = e.target;
        if (!f.dataset.step) return;
        e.preventDefault();
        var fd = new FormData(f);
        var btn = f.querySelector('[type=submit]');
        if (f.classList.contains('js-step') && !fd.getAll('ids').length) { say('Захиалга сонгоно уу.', false); return; }
        if (f.classList.contains('js-confirm-id')) {
            var id = String(fd.get('order_id') || '').replace('#', '').trim();
            var row = board.querySelector('li[data-order="' + id + '"]');
            if (!row) { say('#' + id + ' захиалга замд яваа жагсаалтад алга.', false); return; }
            if (!confirm('Захиалга #' + id + ' (' + row.querySelector('strong').textContent + ') хүргэгдсэн үү?')) return;
        }
        var dlg = f.closest('dialog');
        post(f.dataset.step, fd, btn).then(function (j) { if (dlg && dlg.open && j && j.ok) dlg.close(); });
    });

    board.addEventListener('change', function (e) {
        if (!e.target.classList.contains('js-all')) return;
        e.target.closest('form').querySelectorAll('input[name=ids]').forEach(function (c) { c.checked = e.target.checked; });
    });

    board.addEventListener('click', function (e) {
        var d = e.target.closest('.js-deliver'), x = e.target.closest('.js-fail'), c = e.target.closest('.js-close');
        if (d) {
            var id = d.dataset.order;
            if (!confirm('Захиалга #' + id + ' хүргэгдсэн гэж батлах уу?')) return;
            var fd = new FormData(); fd.append('result', 'deliver'); fd.append('order_id', id);
            post('confirm', fd, d);
        } else if (x) {
            var dlg = document.getElementById('fail-dialog');
            dlg.querySelector('[name=order_id]').value = x.dataset.order;
            dlg.querySelector('.js-fail-id').textContent = '#' + x.dataset.order;
            dlg.showModal();
        } else if (c) {
            c.closest('dialog').close();
        }
    });
})();
