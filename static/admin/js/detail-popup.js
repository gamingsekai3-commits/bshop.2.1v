/* Detail popups: any element with data-rd-template="<id>" (e.g. the report cards)
   opens the contents of that <template> in the same modal, without a request.
   Any <a class="rd-link" href="..."> in the admin loads that URL
   (an HTML fragment) into a modal with a 0.5 s fade. Fragments containing a
   .receipt get a working print button. Loaded from admin/base_site.html. */
(function () {
  'use strict';

    var EN = (window.BSHOP_LANG || document.documentElement.lang || 'mn').indexOf('en') === 0;
    var overlay = document.createElement('div');
    overlay.className = 'rd-overlay';
    overlay.id = 'rd-overlay';
    overlay.innerHTML =
      '<div class="rd-modal" role="dialog" aria-modal="true">' +
      '<button type="button" class="rd-x" id="rd-close" aria-label="' + (EN ? 'Close' : 'Хаах') + '">&times;</button>' +
      '<div id="rd-body"></div></div>';
    document.body.appendChild(overlay);
    var body = overlay.querySelector('#rd-body');

    // Receipt look - shared by the popup and by the print window below.
    var RCSS =
      '.receipt{width:400px;max-width:100%;margin:0 auto;padding:26px 28px 30px;box-sizing:border-box;background:#fff;color:#1a1a1a;' +
      'font:14px/1.45 "DM Sans",Arial,Helvetica,sans-serif;text-align:left;border-radius:10px;box-shadow:0 2px 14px rgba(0,0,0,.14)}' +
      '.receipt b{font-weight:700}' +
      '.receipt .r{text-align:right}' +
      '.receipt .rc-logo{text-align:center;margin:2px 0 26px;line-height:1}' +
      '.receipt .rc-logo b{display:block;font-size:34px;font-weight:800;letter-spacing:-1.5px}' +
      '.receipt .rc-logo small{display:block;margin-top:5px;font-size:10px;letter-spacing:.42em;text-transform:uppercase;text-indent:.42em}' +
      '.receipt .rc-kv{display:grid;grid-template-columns:42% 1fr;gap:14px 8px;margin-bottom:22px}' +
      '.receipt .rc-kv span{word-break:break-word}' +
      '.receipt .rc-line{border:0;border-top:1px solid #dcdcdc;margin:0}' +
      '.receipt .rc-items{display:grid;grid-template-columns:1fr 54px auto;gap:6px 10px;padding:16px 0}' +
      '.receipt .rc-items small{display:block;font-size:11px;color:#777}' +
      '.receipt .rc-totals{display:grid;grid-template-columns:1fr auto;gap:4px 14px;padding-top:16px;width:62%;margin-left:auto;box-sizing:border-box}' +
      '.receipt .rc-thanks{margin:26px 0 22px;text-align:center;font-size:12px;color:#777}' +
      '.receipt .rc-code{text-align:center;font-size:11px;color:#777;margin-bottom:8px}' +
      '.receipt .rc-barcode{display:block;width:100%;height:56px}' +
      '@media print{.receipt{box-shadow:none}}';
    var st = document.createElement('style');
    st.textContent = RCSS;
    document.head.appendChild(st);

    function close() {
      overlay.classList.remove('open');
      setTimeout(function () { if (!overlay.classList.contains('open')) body.innerHTML = ''; }, 500);  // after the fade-out
    }
    function openHtml(html) {
      body.innerHTML = html;
      overlay.classList.add('open');
    }
    function open(url) {
      // "Loading… please wait" inside the popup until the detail has arrived (inline style,
      // so it does not depend on which CSS file the browser cached).
      body.innerHTML = '<p class="rd-empty rd-loading" style="display:flex;align-items:center;justify-content:center;' +
        'min-height:140px;margin:0;font-size:15px;">' +
        (EN ? 'Loading… please wait' : 'Ачааллаж байна… Түр хүлээнэ үү') + '</p>';
      overlay.classList.add('open');
      fetch(url, { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.text(); })
        .then(function (html) { body.innerHTML = html; })
        .catch(function (err) { body.innerHTML = '<p class="rd-empty">' + err.message + '</p>'; });
    }

    function printReceipt(el) {
      var f = document.createElement('iframe');
      f.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0';
      document.body.appendChild(f);
      var d = f.contentWindow.document;
      d.open();
      d.write('<!doctype html><html><head><meta charset="utf-8"><style>body{margin:0;padding:8px}' + RCSS +
              '</style></head><body>' + el.outerHTML + '</body></html>');
      d.close();
      setTimeout(function () {
        f.contentWindow.focus();
        f.contentWindow.print();
        setTimeout(function () { f.remove(); }, 1500);
      }, 150);
    }

    // Detail links are handled in the CAPTURE phase and stop there, so admin-page-loader.js
    // never sees the click and no full-screen loading overlay appears behind the popup.
    document.addEventListener('click', function (e) {
      var l = e.target.closest && e.target.closest('a.rd-link');
      if (!l || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
      e.preventDefault();
      e.stopPropagation();
      open(l.getAttribute('href'));
    }, true);

    document.addEventListener('click', function (e) {
      var card = e.target.closest('[data-rd-template]');
      if (card) {
        var tpl = document.getElementById(card.getAttribute('data-rd-template'));
        if (tpl) openHtml(tpl.innerHTML);
        return;
      }
      var link = e.target.closest('a.rd-link');
      if (link) { e.preventDefault(); open(link.getAttribute('href')); return; }
      var pr = e.target.closest('[data-print-receipt]');
      if (pr) {
        var receipt = pr.parentElement.querySelector('.receipt');
        if (receipt) printReceipt(receipt);
        return;
      }
      if (e.target === overlay || e.target.closest('#rd-close')) close();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') close();
      // Cards are role="button": Enter / Space opens them like a click.
      if ((e.key === 'Enter' || e.key === ' ') && e.target.matches && e.target.matches('[data-rd-template]')) {
        e.preventDefault();
        e.target.click();
      }
    });
  })();