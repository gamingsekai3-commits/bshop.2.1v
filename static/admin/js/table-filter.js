/* Odoo-style column headers for admin tables.
 *
 *  - SERVER-SIDE sorting: model lists (Django's ?o=) and paginated reports (?sort=) are
 *    sorted by the server over ALL rows, on every page; the header link is followed as is.
 *    Only unpaginated tables (e.g. the overview) are sorted here in the browser.
 *  - Every sortable header always shows an indicator: dim \u21C5 when unsorted, \u25B2 / \u25BC when sorted.
 *  - Click a header  -> sort A-Z, click again Z-A, third click clears the sort.
 *    Model lists and paginated reports sort on the server (see above); small
 *    unpaginated tables sort in the browser on the same page.
 *  - Funnel icon     -> Excel/Odoo-like popup with a search box and a list of
 *    the values in that column; untick values to hide those rows.
 *  - Report tables can also turn sorting off per column with <th data-sort="no">
 *    (the funnel, if any, keeps working).
 *  - Report tables can choose per column with <th data-filter="...">:
 *      none  -> sorting only, no funnel icon
 *      list  -> the value list above (default, also used by model lists)
 *      count -> four fixed buckets: 0-9, 10-19, 20-29, 30+   (stock, units sold)
 *      money -> intervals built from the column's lowest / highest value
 *               (e.g. 100,000-500,000, 500,000-1,000,000 ...)             (price)
 *  - On Reports the funnel is SERVER-SIDE too: ticking boxes and pressing Apply reloads the
 *    page with ?f<column>=... so the filter covers every page, not just the one on screen.
 *    The options come from the server in the header's data-fopts attribute.
 *  - Model lists work the same way now: the funnel is SERVER-SIDE (?f_<column>=...), its options come from
 *    <script id="bshop-fopts"> (templates/admin/change_list.html, built in store/admin.py). A column the admin
 *    does not declare in column_filters has no funnel, exactly like a Reports column without options.
 *  - A "Reset all" button appears above the table whenever a sort or filter is active.
 *  - Neither Reports nor model lists reload the page for sorting, filtering, paging or reset: the new
 *    HTML is fetched in the background and only the list region is swapped (Reports: #report-dyn;
 *    model lists: #changelist-form + the #changelist-filter sidebar). The URL and the Back button
 *    keep working. Every swap REPLACES the current history entry, so no new "page" is added to Back.
 *    No full-screen loader is shown.
 *
 * Works on `table.report-table` (Reports) and `#result_list` (model lists).
 * Sorting and filtering happen in the browser, so on a paginated model list
 * they only cover the rows on the current page.
 * Language comes from window.BSHOP_LANG (set in admin/base_site.html).
 */
(function () {
  'use strict';

  var EN = (window.BSHOP_LANG || document.documentElement.lang || 'mn').indexOf('en') === 0;
  var L = EN
    ? { search: 'Search…', all: 'All', clear: 'Clear filter', empty: '(empty)', none: 'No matches', apply: 'Apply', reset: 'Clear sort', resetTitle: 'Clear sorting and filters' }
    : { search: 'Хайх…', all: 'Бүгд', clear: 'Цэвэрлэх', empty: '(хоосон)', none: 'Олдсонгүй', apply: 'Хэрэглэх', reset: 'Эрэмбэ цуцлах', resetTitle: 'Эрэмбэ, шүүлтийг цуцлах' };

  // Fixed buckets for the "count" / "money" modes on MODEL LISTS (browser-side). Reports get theirs from the server. `max` is the
  // inclusive upper edge of each bucket (the last one has none).
  var BUCKETS = {
    count: {
      labels: ['0 – 9', '10 – 19', '20 – 29', EN ? '30 and up' : '30-с дээш'],
      max: [9, 19, 29]
    },
    money: {
      labels: ['0 – 500,000', '500,001 – 1,000,000', '1,000,001 – 2,000,000', '2,000,001 – 3,000,000',
               EN ? '3,000,001 and up' : '3,000,001-с дээш'],
      max: [500000, 1000000, 2000000, 3000000]
    }
  };
  // Index of the bucket a cell falls in; blank / non-numeric cells fall in none.
  function bucketOf(text, mode) {
    if (isBlank(text)) return -1;
    var n = parseFloat(text.replace(/[,\s]/g, ''));
    if (isNaN(n)) return -1;
    var max = BUCKETS[mode].max;
    for (var i = 0; i < max.length; i++) if (n <= max[i]) return i;
    return max.length;
  }

  var FUNNEL = '<svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">' +
    '<path d="M1.5 1.5A.5.5 0 0 1 2 1h12a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-.128.334L10 8.692V13.5a.5.5 0 0 1-.342.474l-3 1A.5.5 0 0 1 6 14.5V8.692L1.628 3.834A.5.5 0 0 1 1.5 3.5v-2z"/></svg>';

  var css = document.createElement('style');
  css.textContent =
    /* header tools: sort arrow + funnel always sit on ONE line, as a small tidy group */
    'table.tf-sortable thead th{white-space:nowrap}' +
    'table.tf-sortable thead th .text{display:flex;align-items:center;gap:6px;flex-wrap:nowrap}' +
    'table.tf-sortable thead th .clear{display:none}' +
    'table.tf-sortable thead th.num{text-align:right}' +
    'table.tf-sortable thead th.num .text{justify-content:flex-end}' +
    '.tf-tools{display:inline-flex;flex-wrap:nowrap;align-items:center;gap:2px;margin-left:6px;vertical-align:middle;white-space:nowrap}' +
    '.tf-arrow{display:inline-flex;align-items:center;justify-content:center;width:18px;height:22px;font-size:10px;color:var(--primary,#417690)}' +
    '.tf-arrow.idle{opacity:.4;color:inherit}' +
    'th.tf-sortable-th:hover .tf-arrow.idle{opacity:.9}' +
    '.tf-btn{position:relative;display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border:0;background:transparent;' +
    'color:inherit;opacity:.45;cursor:pointer;padding:0;border-radius:6px;line-height:0;transition:background .15s,opacity .15s}' +
    '.tf-btn:hover{opacity:1;background:rgba(128,128,128,.18)}' +
    '.tf-btn.active{opacity:1;color:#fff;background:var(--primary,#417690)}' +
    '.tf-btn.active:hover{filter:brightness(1.1)}' +
    'table.tf-sortable thead th.tf-sortable-th{cursor:pointer;user-select:none}' +
    /* model lists: stacked up/down arrows, both always visible, the active one lights up */
    'table#result_list thead th .tf-tools .rs-arrows{display:inline-flex;flex-direction:column;align-items:center;gap:1px;padding:0}' +
    'table#result_list thead th .text .tf-tools a.rs-dir{display:block;padding:2px 4px;line-height:0;color:inherit;text-decoration:none;background:none;opacity:.3;cursor:pointer;transition:opacity .12s,color .12s,filter .12s,transform .12s}' +
    'table#result_list thead th .rs-dir svg{display:block;width:10px;height:6px;fill:currentColor}' +
    'table#result_list thead th .text .tf-tools a.rs-dir:hover{opacity:.75;transform:scale(1.15)}' +
    'table#result_list thead th[data-dir="asc"] .rs-up,table#result_list thead th[data-dir="desc"] .rs-down{opacity:1!important;color:var(--primary,#417690)!important;filter:drop-shadow(0 0 2px rgba(201,136,10,.5))}' +
    'html[data-theme="dark"] table#result_list thead th[data-dir="asc"] .rs-up,html[data-theme="dark"] table#result_list thead th[data-dir="desc"] .rs-down{color:#fff!important;filter:drop-shadow(0 0 3px rgba(255,255,255,.65))}' +
    /* Django's own sort marks (priority number + arrows + X) are replaced by ONE arrow, like Reports.\n       The selectors are as specific as Django's base.css rules (which would otherwise win). */
    'table.tf-sortable thead th .sortoptions,table.tf-sortable thead th.sorted .sortoptions{display:none!important}' +
    'table.tf-sortable thead th.sorted .text{padding-right:0}' +
    'table.tf-sortable thead th .text a{display:block;flex:0 1 auto;padding:0;background:none}' +
    /* base.css gives every span in a header display:block + padding, which stacked arrow and funnel */
    'table.tf-sortable thead th .text span.tf-tools{display:inline-flex;padding:0}' +
    'table.tf-sortable thead th .text span.tf-arrow{display:inline-flex;padding:0}' +
    'table.tf-sortable thead th.tf-sortable-th a{cursor:pointer}' +
    '.tf-pop{position:absolute;z-index:99998;width:240px;padding:10px;background:var(--body-bg,#fff);color:var(--body-fg,#333);' +
    'border:1px solid var(--hairline-color,#ddd);border-radius:10px;box-shadow:0 10px 28px rgba(0,0,0,.22);font-size:13px;' +
    'text-transform:none;letter-spacing:0;font-weight:400;text-align:left;opacity:0;transform:translateY(-6px);transition:opacity .25s ease,transform .25s ease}' +
    '.tf-pop.show{opacity:1;transform:none}' +
    '.tf-pop input[type=search]{width:100%;box-sizing:border-box;padding:6px 8px;margin-bottom:6px}' +
    '.tf-list{max-height:240px;overflow:auto;border-top:1px solid var(--hairline-color,#ddd);padding-top:4px}' +
    '.tf-list label{display:flex;align-items:center;gap:8px;padding:5px 4px;border-radius:6px;cursor:pointer;word-break:break-word}' +
    '.tf-list label:hover{background:var(--darkened-bg,#f5f5f5)}' +
    '.tf-list input{margin:0;flex:none}' +
    '.tf-foot{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-top:8px;padding-top:8px;border-top:1px solid var(--hairline-color,#ddd)}' +
    '.tf-foot button{border:0;background:transparent;color:var(--link-fg,#447e9b);cursor:pointer;font-size:12px;padding:4px 6px;border-radius:6px}' +
    '.tf-foot button:hover{background:var(--darkened-bg,#f5f5f5)}' +
    '.tf-foot button.tf-apply{background:var(--primary,#417690);color:#fff;font-weight:600;padding:5px 14px}' +
    '.tf-foot button.tf-apply:hover{filter:brightness(1.1)}' +
    '.tf-none{padding:6px 2px;color:var(--body-quiet-color,#888)}' +
    '#report-dyn{transition:opacity .15s}#report-dyn.tf-busy{opacity:.6;pointer-events:none}' +
    /* "Clear sort" sits in the pager's footer row, which is always there: it is only hidden
       (visibility), never removed, so showing / hiding it moves nothing on the page. */
    '.bshop-pager .bp-footer .tf-reset{display:inline-flex;align-items:center;justify-content:center;gap:6px;height:34px;padding:0 16px;' +
    'margin:0;border:1.5px solid var(--primary,#417690);border-radius:999px;background:transparent;color:var(--primary,#417690);' +
    'font:inherit;font-size:13px;font-weight:600;line-height:1;white-space:nowrap;cursor:pointer;text-decoration:none;' +
    'visibility:hidden;opacity:0;transition:opacity .2s ease,background .15s,color .15s}' +
    '.bshop-pager .bp-footer .tf-reset.is-on{visibility:visible;opacity:1}' +
    '.bshop-pager .bp-footer .tf-reset:hover{background:var(--primary,#417690);color:#fff}';
  document.head.appendChild(css);

  var openPop = null;
  var modelFilters = null;       // model lists: column filters kept while the list is re-drawn in place
  function closePop() {
    if (!openPop) return;
    var gone = openPop;
    openPop = null;
    gone.classList.remove('show');                       // fade out 0.5 s, then remove
    setTimeout(function () { gone.remove(); }, 500);
  }
  document.addEventListener('click', function (e) {
    if (openPop && !openPop.contains(e.target) && !e.target.closest('.tf-btn')) closePop();
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closePop(); });

  function cellText(row, i) {
    var c = row.cells[i];
    return c ? c.textContent.replace(/\s+/g, ' ').trim() : '';
  }
  function isBlank(v) { return v === '' || v === '—' || v === '-'; }

  // Model lists: the funnel options the server put in the page (see change_list.html).
  function modelFopts() {
    var el = document.getElementById('bshop-fopts');
    if (!el) return {};
    try { return JSON.parse(el.textContent) || {}; } catch (e) { return {}; }
  }

  function init(table) {
    var thead = table.tHead, tbody = table.tBodies[0];
    if (!thead || !tbody) return;
    var serverSort = table.hasAttribute('data-server-sort') || table.id === 'result_list';
    var isModelList = table.id === 'result_list';
    var headers = Array.prototype.slice.call(thead.rows[0].cells);
    var rows = Array.prototype.slice.call(tbody.rows).filter(function (r) {
      return !r.querySelector('td[colspan]');
    });
    if (!rows.length && !serverSort) return;      // reports keep their funnels even when a filter leaves 0 rows
    rows.forEach(function (r, i) { r._tfIndex = i; });

    var filters = {};                                  // col -> Set of allowed values, or {range: Set of bucket indexes}
    if (isModelList) { filters = modelFilters || {}; modelFilters = filters; }   // survives an in-place sort
    var sort = { col: -1, dir: 0 };

    function apply() {
      rows.forEach(function (r) {
        var show = true;
        for (var c in filters) {
          var f = filters[c];
          var ok = f.range ? f.range.has(bucketOf(cellText(r, +c), f.mode)) : f.has(cellText(r, +c));
          if (!ok) { show = false; break; }
        }
        r.style.display = show ? '' : 'none';
      });
      updateResetBtn();
    }

    function doSort() {
      var col = sort.col, dir = sort.dir;
      var list = rows.slice();
      if (dir === 0 || col < 0) {
        list.sort(function (a, b) { return a._tfIndex - b._tfIndex; });
      } else {
        var vals = list.map(function (r) { return cellText(r, col); });
        var numeric = vals.every(function (v) { return isBlank(v) || /^-?[\d.,\s]+$/.test(v); });
        var key = function (r) {
          var v = cellText(r, col);
          if (isBlank(v)) return null;
          return numeric ? parseFloat(v.replace(/[,\s]/g, '')) : v;
        };
        list.sort(function (a, b) {
          var x = key(a), y = key(b);
          if (x === null && y === null) return 0;
          if (x === null) return 1;                    // empty cells always last
          if (y === null) return -1;
          var r = numeric ? x - y : String(x).localeCompare(String(y), undefined, { numeric: true, sensitivity: 'base' });
          return dir * r;
        });
      }
      list.forEach(function (r) { tbody.appendChild(r); });
      updateArrows();
    }

    function updateArrows() {
      headers.forEach(function (h, i) {
        // Every sortable column always shows both arrows; the active direction's one lights up.
        var on = (i === sort.col && sort.dir);
        h.setAttribute('data-dir', on ? (sort.dir === 1 ? 'asc' : 'desc') : '');
        if (i === sort.col) return;
        h.classList.remove('sorted', 'ascending', 'descending');
      });
    }

    function placePopup(pop, btn) {
      document.body.appendChild(pop);
      var r = btn.getBoundingClientRect();
      var left = r.left + window.scrollX;
      left = Math.min(left, window.scrollX + document.documentElement.clientWidth - 240);
      pop.style.left = Math.max(4, left) + 'px';
      pop.style.top = (r.bottom + window.scrollY + 4) + 'px';
      openPop = pop;
      requestAnimationFrame(function () { requestAnimationFrame(function () { pop.classList.add('show'); }); });
    }

    // Filter-modes "count" / "money": a tick-list of the fixed buckets.
    function buildRangePopup(col, btn) {
      closePop();
      var mode = btn._mode, B = BUCKETS[mode].labels;
      function everyBucket() { return new Set(B.map(function (_, i) { return i; })); }
      var allowed = filters[col] ? new Set(filters[col].range) : everyBucket();
      var pop = document.createElement('div');
      pop.className = 'tf-pop';
      var list = document.createElement('div');
      list.className = 'tf-list';
      list.style.borderTop = '0';
      var foot = document.createElement('div');
      foot.className = 'tf-foot';
      var clear = document.createElement('button');
      clear.type = 'button'; clear.textContent = L.clear;
      foot.appendChild(clear);
      pop.append(list, foot);

      function commit() {
        if (allowed.size === B.length) delete filters[col]; else filters[col] = { range: new Set(allowed), mode: mode };
        btn.classList.toggle('active', !!filters[col]);
        apply();
      }
      function renderList() {
        list.innerHTML = '';
        B.forEach(function (label, i) {
          var lbl = document.createElement('label');
          var cb = document.createElement('input'); cb.type = 'checkbox'; cb.checked = allowed.has(i);
          cb.onchange = function () { if (cb.checked) allowed.add(i); else allowed.delete(i); commit(); };
          lbl.append(cb, document.createTextNode(label));
          list.appendChild(lbl);
        });
      }
      clear.onclick = function () { allowed = everyBucket(); commit(); renderList(); };
      renderList();
      placePopup(pop, btn);
    }


    // ---- Reports: server-side funnel. Options come from the server (data-fopts);
    // Apply reloads the page with ?f<col>=... so every page is filtered, not one.
    function buildServerPopup(btn) {
      closePop();
      var f = btn._f;
      var allowed = new Set(f.selected.length ? f.selected : f.values);
      var pop = document.createElement('div');
      pop.className = 'tf-pop';
      var search = null;
      if (f.kind === 'list' && f.options.length > 8) {
        search = document.createElement('input');
        search.type = 'search'; search.placeholder = L.search;
        pop.appendChild(search);
      }
      var list = document.createElement('div');
      list.className = 'tf-list';
      if (!search) list.style.borderTop = '0';
      var foot = document.createElement('div');
      foot.className = 'tf-foot';
      var clear = document.createElement('button');
      clear.type = 'button'; clear.textContent = L.clear;
      var apply = document.createElement('button');
      apply.type = 'button'; apply.className = 'tf-apply'; apply.textContent = L.apply;
      foot.append(clear, apply);
      pop.append(list, foot);

      function go(values) {
        var params = new URLSearchParams(window.location.search);
        params.delete(f.param); params.delete('p');
        values.forEach(function (v) { params.append(f.param, v); });
        var q = params.toString();
        closePop();
        swapPage(window.location.pathname + (q ? '?' + q : ''));
      }
      function renderList() {
        var q = search ? search.value.trim().toLowerCase() : '';
        list.innerHTML = '';
        var n = 0;
        f.options.forEach(function (label, i) {
          if (q && label.toLowerCase().indexOf(q) === -1) return;
          n++;
          var v = f.values[i];
          var lbl = document.createElement('label');
          var cb = document.createElement('input'); cb.type = 'checkbox'; cb.checked = allowed.has(v);
          cb.onchange = function () { if (cb.checked) allowed.add(v); else allowed.delete(v); apply.disabled = !allowed.size; };
          lbl.append(cb, document.createTextNode(label));
          list.appendChild(lbl);
        });
        if (!n) { var e = document.createElement('div'); e.className = 'tf-none'; e.textContent = L.none; list.appendChild(e); }
      }
      if (search) search.addEventListener('input', renderList);
      clear.onclick = function () { go([]); };
      apply.onclick = function () { go(allowed.size === f.values.length ? [] : Array.from(allowed)); };
      renderList();
      placePopup(pop, btn);
      if (search) search.focus();
    }

    function buildPopup(col, btn) {
      if (btn._f) return buildServerPopup(btn);
      if (btn._mode === 'count' || btn._mode === 'money') return buildRangePopup(col, btn);
      closePop();
      var values = [];
      var seen = {};
      rows.forEach(function (r) {
        var v = cellText(r, col);
        if (!seen.hasOwnProperty(v)) { seen[v] = 1; values.push(v); }
      });
      var numeric = values.every(function (v) { return isBlank(v) || /^-?[\d.,\s]+$/.test(v); });
      values.sort(function (a, b) {
        if (numeric) return (parseFloat(a.replace(/[,\s]/g, '')) || 0) - (parseFloat(b.replace(/[,\s]/g, '')) || 0);
        return a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' });
      });
      var allowed = filters[col] ? new Set(filters[col]) : new Set(values);

      var pop = document.createElement('div');
      pop.className = 'tf-pop';
      var search = document.createElement('input');
      search.type = 'search'; search.placeholder = L.search;
      var list = document.createElement('div');
      list.className = 'tf-list';
      var foot = document.createElement('div');
      foot.className = 'tf-foot';
      var clear = document.createElement('button');
      clear.type = 'button'; clear.textContent = L.clear;
      foot.appendChild(clear);
      pop.append(search, list, foot);

      function commit() {
        if (allowed.size === values.length) delete filters[col]; else filters[col] = new Set(allowed);
        btn.classList.toggle('active', !!filters[col]);
        apply();
      }

      function renderList() {
        var q = search.value.trim().toLowerCase();
        var shown = values.filter(function (v) { return (isBlank(v) ? L.empty : v).toLowerCase().indexOf(q) !== -1; });
        list.innerHTML = '';
        if (!shown.length) { var n = document.createElement('div'); n.className = 'tf-none'; n.textContent = L.none; list.appendChild(n); return; }

        var allLbl = document.createElement('label');
        var allCb = document.createElement('input'); allCb.type = 'checkbox';
        allCb.checked = shown.every(function (v) { return allowed.has(v); });
        allLbl.append(allCb, document.createTextNode(L.all));
        allCb.onchange = function () {
          shown.forEach(function (v) { if (allCb.checked) allowed.add(v); else allowed.delete(v); });
          commit(); renderList();
        };
        list.appendChild(allLbl);

        shown.forEach(function (v) {
          var lbl = document.createElement('label');
          var cb = document.createElement('input'); cb.type = 'checkbox'; cb.checked = allowed.has(v);
          cb.onchange = function () {
            if (cb.checked) allowed.add(v); else allowed.delete(v);
            commit();
            allCb.checked = shown.every(function (x) { return allowed.has(x); });
          };
          lbl.append(cb, document.createTextNode(isBlank(v) ? L.empty : v));
          list.appendChild(lbl);
        });
      }
      search.addEventListener('input', renderList);
      clear.onclick = function () { values.forEach(function (v) { allowed.add(v); }); commit(); renderList(); };
      renderList();

      placePopup(pop, btn);
      search.focus();
    }

    headers.forEach(function (th, col) {
      // skip the "select all" checkbox column of model lists
      if (th.querySelector('input[type=checkbox]') || th.classList.contains('action-checkbox-column')) return;

      var tools = document.createElement('span');
      tools.className = 'tf-tools';
      // Sorting is on unless the column says data-sort="no"; the funnel is
      // skipped for data-filter="none". Either can be off independently.
      var sortable = th.getAttribute('data-sort') !== 'no';
      // Server-sorted report tables draw their own mark inside the header link;
      // model lists get theirs here, read from the classes Django put on the <th>.
      if (sortable && (!serverSort || isModelList)) {
        var arrow = document.createElement('span');
        arrow.className = 'rs-arrows';
        var UP = '<svg viewBox="0 0 10 6" aria-hidden="true"><path d="M5 0 10 6H0z"/></svg>';
        var DOWN = '<svg viewBox="0 0 10 6" aria-hidden="true"><path d="M0 0h10L5 6z"/></svg>';
        if (!isModelList) {                          // browser-sorted table: stacked up / down, lit by th[data-dir]
          arrow.innerHTML = '<span class="rs-dir rs-up">' + UP + '</span><span class="rs-dir rs-down">' + DOWN + '</span>';
        } else {
          // Django's ?o= number is the column's position in the header row. The "select all" checkbox
          // column is list_display[0] ('action_checkbox'), so it counts too.
          var oi = (th.classList.contains('sortable') && th.querySelector('.text a[href]')) ? col : null;
          if (oi === null) { arrow = null; }          // not sortable
          else {
            th.setAttribute('data-o', String(oi));
            th.setAttribute('data-dir', th.classList.contains('sorted') ? (th.classList.contains('descending') ? 'desc' : 'asc') : '');
            arrow.innerHTML = '<a class="rs-dir rs-up" data-dir="asc" href="' + modelSortUrl(oi, th.getAttribute('data-dir') === 'asc' ? '' : 'asc') + '" aria-label="Sort ascending">' + UP + '</a>' +
                              '<a class="rs-dir rs-down" data-dir="desc" href="' + modelSortUrl(oi, th.getAttribute('data-dir') === 'desc' ? '' : 'desc') + '" aria-label="Sort descending">' + DOWN + '</a>';
          }
        }
        if (arrow) tools.appendChild(arrow);
      }
      (th.querySelector('.text') || th).appendChild(tools);   // model lists wrap the title in div.text
      var mode = th.getAttribute('data-filter') || 'list';
      var fopts = null;
      if (serverSort) {                              // Reports AND model lists: the funnel exists only if the server sent options
        if (isModelList) {
          var cm = /(?:^|\s)column-(\S+)/.exec(th.className);
          fopts = (cm && modelFopts()[cm[1]]) || null;
        } else {
          try { fopts = JSON.parse(th.getAttribute('data-fopts') || 'null'); } catch (e) { fopts = null; }
        }
        if (!fopts) mode = 'none';
      }
      if (mode !== 'none') {
        var btn = document.createElement('button');
        btn.type = 'button'; btn.className = 'tf-btn'; btn.innerHTML = FUNNEL;
        btn.setAttribute('aria-label', 'Filter');
        btn._mode = mode;
        if (fopts) {
          btn._f = fopts;
          var on = isModelList ? !!(fopts.selected.length && fopts.selected.length < fopts.values.length)
                               : th.getAttribute('data-factive') === '1';
          btn.classList.toggle('active', on);
        }
        else if (filters[col]) btn.classList.add('active');
        tools.appendChild(btn);
        btn.addEventListener('click', function (e) {
          e.stopPropagation(); e.preventDefault();
          if (openPop && openPop._btn === btn) { closePop(); return; }
          buildPopup(col, btn);
          if (openPop) openPop._btn = btn;
        });
      }

      if (serverSort) {
        // Model lists: Django's header link only toggles asc <-> desc. Reports go asc -> desc -> off,
        // so a column that is already descending gets a link that clears the sort.
        if (isModelList && th.classList.contains('sorted') && th.classList.contains('descending')) {
          var clearLink = th.querySelector('.text a[href]');
          if (clearLink) {
            var cp = new URLSearchParams(window.location.search);
            cp.delete('o'); cp.delete('p');
            var cq = cp.toString();
            clearLink.setAttribute('href', window.location.pathname + (cq ? '?' + cq : ''));
          }
        }
        // Clicking anywhere on the header follows its sort link (the server sorts all pages).
        if (th.querySelector('a[href]')) {
          th.classList.add('tf-sortable-th');
          th.addEventListener('click', function (e) {
            if (e.target.closest('a') || e.target.closest('.tf-btn')) return;
            th.querySelector('a[href]').click();
          });
        }
        return;
      }
      if (!sortable) return;
      th.classList.add('tf-sortable-th');
      // The list is already sorted the way Django's ?o= says: show that as the start state.
      if (th.classList.contains('sorted')) {
        sort.col = col;
        sort.dir = th.classList.contains('descending') ? -1 : 1;
        th.classList.remove('sorted', 'ascending', 'descending');
      }
      th.addEventListener('click', function (e) {
        if (e.target.closest('.tf-btn')) return;
        if (e.target.closest('a')) e.preventDefault();   // stay on this page
        if (sort.col !== col) { sort.col = col; sort.dir = 1; }
        else if (sort.dir === 1) sort.dir = -1;
        else if (sort.dir === -1) { sort.dir = 0; sort.col = -1; }
        doSort();
      });
    });
    table.classList.add('tf-sortable');
    if (!serverSort) updateArrows();
    if (Object.keys(filters).length) apply();
    updateResetBtn();
  }

  // ---------------------------------------------------------------------
  // "Clear sort" button (one for Reports and model lists)
  // ---------------------------------------------------------------------
  // URL keys that are NOT a sort / filter: they stay when everything is cleared.
  var KEEP_KEYS = ['q', 'per_page', '_popup', '_to_field', 'date_from', 'date_to'];
  function hasState() {
    var on = false;
    new URLSearchParams(window.location.search).forEach(function (_v, k) {
      if (k !== 'p' && KEEP_KEYS.indexOf(k) === -1) on = true;
    });
    return on || (modelFilters && Object.keys(modelFilters).length > 0);
  }
  function updateResetBtn() {
    var foot = document.querySelector('.bshop-pager .bp-footer');
    if (!foot) return;
    var btn = foot.querySelector('.tf-reset');
    if (!btn) {
      btn = document.createElement('button');
      btn.type = 'button'; btn.className = 'tf-reset';
      btn.textContent = L.reset; btn.title = L.resetTitle;
      btn.addEventListener('click', function () {
        var cur = new URLSearchParams(window.location.search), out = new URLSearchParams();
        KEEP_KEYS.forEach(function (k) { if (cur.has(k)) out.set(k, cur.get(k)); });
        var qs = out.toString();
        modelFilters = null;                             // browser-side column filters go too
        swapPage(window.location.pathname + (qs ? '?' + qs : ''));
      });
      foot.insertBefore(btn, foot.firstChild);
    }
    btn.classList.toggle('is-on', !!hasState());
  }

  // ---------------------------------------------------------------------
  // Swap the list in place instead of navigating (Reports and model lists)
  // ---------------------------------------------------------------------
  // Which parts of the page are re-drawn. Everything else (header, sidebar menu, search box,
  // popups) stays untouched.
  function regionIds() {
    if (document.getElementById('report-dyn')) return ['report-dyn'];
    if (document.getElementById('changelist-form')) return ['changelist-form', 'changelist-filter'];
    return null;
  }

  // Django's sidebar filter (<details> open/closed state is remembered in sessionStorage by
  // filters.js, which only runs once at page load - so redo that bit after a swap).
  function rewireSidebar() {
    var KEY = 'django.admin.filtersState', state = {};
    try { state = JSON.parse(sessionStorage.getItem(KEY)) || {}; } catch (e) { state = {}; }
    document.querySelectorAll('#changelist-filter details').forEach(function (d) {
      var k = d.dataset.filterTitle;
      if (k in state) { if (state[k]) d.setAttribute('open', ''); else d.removeAttribute('open'); }
      d.addEventListener('toggle', function () {
        state[k] = d.open;
        try { sessionStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* private mode */ }
      });
    });
  }

  var swapSeq = 0;
  function swapPage(url) {
    var ids = regionIds();
    if (!ids || !window.fetch || !window.DOMParser) { window.location.href = url; return; }
    // An edited-but-unsaved list_editable field would be lost by the swap: ask first.
    if (document.querySelector('#bshop-save-bar.is-visible') &&
        !window.confirm(EN ? 'You have unsaved changes. Discard them?' : 'Хадгалаагүй өөрчлөлт байна. Устгаад үргэлжлүүлэх үү?')) return;
    var main = document.getElementById(ids[0]);
    var seq = ++swapSeq, slow = setTimeout(function () { main.classList.add('tf-busy'); }, 400);
    closePop();
    var target = new URL(url, window.location.href);
    if (target.searchParams.get('p') !== new URLSearchParams(window.location.search).get('p')) modelFilters = null;
    fetch(target.href, { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (res) {
        if (!res.ok || new URL(res.url).pathname !== target.pathname) throw new Error('nav');
        return res.text();
      })
      .then(function (text) {
        if (seq !== swapSeq) return;                         // a newer click already won
        var doc = new DOMParser().parseFromString(text, 'text/html');
        if (!doc.getElementById(ids[0])) throw new Error('nav');
        ids.forEach(function (id) {
          var fresh = doc.getElementById(id), cur = document.getElementById(id);
          if (fresh && cur) cur.innerHTML = fresh.innerHTML;
        });
        history.replaceState({ tf: 1 }, '', target.href);   // same history entry: Back leaves the page, not the last sort. Before init: the reset button reads the URL
        document.querySelectorAll('table.report-table, table#result_list').forEach(init);
        if (document.getElementById('changelist-form')) {
          var boxes = document.querySelectorAll('tr input.action-select');   // Django's "select rows" logic
          if (boxes.length && window.Actions) window.Actions(boxes);
          rewireSidebar();
        }
      })
      .catch(function () { if (seq === swapSeq) window.location.href = target.href; })   // anything odd: normal page load
      .then(function () { clearTimeout(slow); main.classList.remove('tf-busy'); });
  }

  // ---------------------------------------------------------------------
  // Reports: header sorting (\u25B2 / \u25BC), done in place - never a new page
  // ---------------------------------------------------------------------
  // The arrows light up on the very click. When every row of the report is already on this page
  // (table[data-all-rows]) the rows are re-ordered right here, with the same keys the server sorts
  // by (data-sv / data-n / data-ord); otherwise the other pages' rows live on the server, so the
  // sorted list is fetched in the background and swapped in (swapPage). The URL follows either way.
  function sortUrl(col, dir) {
    var p = new URLSearchParams(window.location.search);
    p.delete('p');
    if (dir) { p.set('sort', String(col)); p.set('dir', dir); } else { p.delete('sort'); p.delete('dir'); }
    var q = p.toString();
    return window.location.pathname + (q ? '?' + q : '');
  }

  // Light the right arrow and keep every header link pointing at what its next click does
  // (so middle-click / open-in-new-tab stay correct).
  function paintSort(table, col, dir) {
    Array.prototype.forEach.call(table.tHead.rows[0].cells, function (th) {
      var c = th.getAttribute('data-col');
      if (c === null) return;
      c = +c;
      var d = c === col ? dir : '';
      th.setAttribute('data-dir', d);
      if (d) th.setAttribute('aria-sort', d === 'asc' ? 'ascending' : 'descending'); else th.removeAttribute('aria-sort');
      var link = th.querySelector('a.rs-link'), up = th.querySelector('a.rs-up'), down = th.querySelector('a.rs-down');
      if (link) {
        link.classList.toggle('is-sorted', !!d);
        link.setAttribute('href', sortUrl(c, d === 'asc' ? 'desc' : (d === 'desc' ? '' : 'asc')));
      }
      if (up) up.setAttribute('href', sortUrl(c, d === 'asc' ? '' : 'asc'));
      if (down) down.setAttribute('href', sortUrl(c, d === 'desc' ? '' : 'desc'));
    });
  }

  function clientSort(table, col, dir) {
    var tbody = table.tBodies[0];
    var rows = Array.prototype.filter.call(tbody.rows, function (r) { return r.hasAttribute('data-ord'); });
    var ord = function (r) { return +r.getAttribute('data-ord'); };
    if (!dir) {
      rows.sort(function (a, b) { return ord(a) - ord(b); });             // back to the report's own order
    } else {
      var val = function (r) { var c = r.cells[col]; return c ? c.getAttribute('data-sv') : ''; };
      var filled = rows.map(val).filter(function (v) { return v !== '' && v !== null; });
      var numeric = filled.length > 0 && rows.every(function (r) {
        var c = r.cells[col];
        return !c || c.getAttribute('data-sv') === '' || c.hasAttribute('data-n');
      });
      var key = function (r) { var v = val(r); return (v === '' || v === null) ? null : (numeric ? parseFloat(v) : v); };
      var sign = dir === 'desc' ? -1 : 1;
      rows.sort(function (a, b) {
        var x = key(a), y = key(b);
        if (x === null || y === null) return x === y ? ord(a) - ord(b) : (x === null ? 1 : -1);   // empty cells always last
        if (x !== y) return (x < y ? -1 : 1) * sign;
        return ord(a) - ord(b);                                            // ties keep the report's order
      });
    }
    rows.forEach(function (r) { tbody.appendChild(r); });
  }

  // Page-size dropdown and page links are rendered with the URL of the last full load: give them
  // the new sort too, so changing rows-per-page afterwards does not lose it.
  function carrySort(col, dir) {
    function fix(href) {
      var u = new URL(href, window.location.href);
      if (dir) { u.searchParams.set('sort', String(col)); u.searchParams.set('dir', dir); }
      else { u.searchParams.delete('sort'); u.searchParams.delete('dir'); }
      return u.pathname + u.search;
    }
    document.querySelectorAll('#report-dyn .bshop-pager select option').forEach(function (o) { o.value = fix(o.value); });
    document.querySelectorAll('#report-dyn .bshop-pager a[href]').forEach(function (a) { a.setAttribute('href', fix(a.getAttribute('href'))); });
  }

  function reportSort(a) {
    var th = a.closest('th'), table = th.closest('table');
    var col = +th.getAttribute('data-col'), cur = th.getAttribute('data-dir') || '', dir;
    if (a.classList.contains('rs-dir')) {                    // \u25B2 / \u25BC: go straight to that direction, again = off
      var want = a.getAttribute('data-dir');
      dir = cur === want ? '' : want;
    } else {                                                 // header text: asc -> desc -> off
      dir = cur === 'asc' ? 'desc' : (cur === 'desc' ? '' : 'asc');
    }
    var url = sortUrl(col, dir);
    paintSort(table, col, dir);                              // lights up immediately
    if (table.hasAttribute('data-all-rows') && table.tBodies[0]) {
      clientSort(table, col, dir);
      carrySort(col, dir);
      history.replaceState({ tf: 1 }, '', url);               // same history entry, like swapPage
      updateResetBtn();
    } else {
      swapPage(url);
    }
  }

  document.addEventListener('click', function (e) {
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var a = e.target.closest && e.target.closest('#report-dyn th a.rs-link, #report-dyn th a.rs-dir');
    if (!a || !a.closest('th').hasAttribute('data-col')) return;
    e.preventDefault();
    e.stopPropagation();                                     // admin-page-loader must not show its overlay
    reportSort(a);
  }, true);

  // Model lists (Django ?o=): column index of a header link, and the URL for "this column, this direction".
  function modelSortIndex(href) {
    var o = new URL(href, window.location.href).searchParams.get('o');
    if (!o) return null;
    var n = parseInt(o.split('.')[0], 10);
    return isNaN(n) ? null : Math.abs(n);
  }
  function modelSortUrl(idx, dir) {
    var p = new URLSearchParams(window.location.search);
    p.delete('p');
    if (dir) p.set('o', (dir === 'desc' ? '-' : '') + idx); else p.delete('o');
    var q = p.toString();
    return window.location.pathname + (q ? '?' + q : '');
  }
  // Click on a model-list header (the arrows OR the title / anywhere on the cell): light it up on the very
  // click, then swap the list in place. Arrows go straight to their direction; the title cycles asc -> desc -> off.
  document.addEventListener('click', function (e) {
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var t = e.target;
    if (!t.closest || t.closest('.tf-btn') || t.closest('.tf-pop') || t.closest('input,select,label')) return;
    var th = t.closest('#result_list thead th');
    if (!th || !th.hasAttribute('data-o')) return;
    var arrow = t.closest('a.rs-dir'), cur = th.getAttribute('data-dir') || '', dir;
    if (arrow) { var want = arrow.getAttribute('data-dir'); dir = cur === want ? '' : want; }
    else dir = cur === 'asc' ? 'desc' : (cur === 'desc' ? '' : 'asc');
    e.preventDefault();
    e.stopImmediatePropagation();                            // no second swap, and admin-page-loader must not show its overlay
    Array.prototype.forEach.call(th.parentNode.cells, function (c) { if (c.hasAttribute('data-o')) c.setAttribute('data-dir', ''); });
    th.setAttribute('data-dir', dir);
    previewSort(th, dir);                                    // rows move on the click; the server's answer (all pages) replaces them
    swapPage(modelSortUrl(+th.getAttribute('data-o'), dir));
  }, true);

  // Instant preview: re-order the rows already on screen while the server sorts ALL pages.
  function previewSort(th, dir) {
    var table = th.closest('table'), tbody = table && table.tBodies[0];
    if (!tbody || !dir) return;
    var col = th.cellIndex, sign = dir === 'desc' ? -1 : 1;
    var rows = Array.prototype.slice.call(tbody.rows).filter(function (r) { return !r.querySelector('td[colspan]'); });
    function raw(r) {
      var c = r.cells[col];
      if (!c) return '';
      var inp = c.querySelector('input:not([type=hidden]), select');
      return (inp ? inp.value : c.textContent).replace(/\s+/g, ' ').trim();
    }
    var vals = rows.map(raw);
    var numeric = vals.every(function (v) { return v === '' || v === '-' || v === '\u2014' || /^-?[\d.,\s]+%?$/.test(v); });
    function key(v) {
      if (v === '' || v === '-' || v === '\u2014') return null;
      return numeric ? parseFloat(v.replace(/[,\s%]/g, '')) : v.toLowerCase();
    }
    var keyed = rows.map(function (r, i) { return { r: r, k: key(vals[i]), i: i }; });
    keyed.sort(function (a, b) {
      if (a.k === null || b.k === null) return a.k === b.k ? a.i - b.i : (a.k === null ? 1 : -1);
      if (a.k !== b.k) return (a.k < b.k ? -1 : 1) * sign;
      return a.i - b.i;
    });
    keyed.forEach(function (x) { tbody.appendChild(x.r); });
  }

  // Capture phase, so we run before admin-page-loader.js: it ignores clicks that are
  // already defaultPrevented, which is why no loading overlay appears.
  var SWAP_LINKS = [
    '#report-dyn .bshop-pager a[href]',                                  // Reports: pages (header sort: reportSort below)
    '#result_list thead a[href]', '#changelist .bshop-pager a[href]',                                // model lists: sort, pages
    '#changelist-filter a[href]'                                                                     // model lists: sidebar filters
  ].join(',');
  document.addEventListener('click', function (e) {
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var a = e.target.closest && e.target.closest(SWAP_LINKS);
    if (!a || !a.getAttribute('href') || a.getAttribute('href').charAt(0) === '#' || a.target === '_blank') return;
    e.preventDefault();
    swapPage(a.getAttribute('href'));
  }, true);
  // Rows-per-page dropdown: its inline onchange would navigate; take over instead.
  document.addEventListener('change', function (e) {
    var sel = e.target;
    if (!sel.closest || !sel.closest('#report-dyn .bshop-pager select, #changelist .bshop-pager select')) return;
    e.stopPropagation();
    swapPage(sel.value);
  }, true);
  window.addEventListener('popstate', function () {
    if (regionIds()) swapPage(window.location.pathname + window.location.search);
  });

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('table.report-table, table#result_list, table.ov-table').forEach(init);
    if (regionIds()) history.replaceState({ tf: 1 }, '', window.location.href);
  });
})();