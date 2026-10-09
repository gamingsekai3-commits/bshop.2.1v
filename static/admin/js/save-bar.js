/* Floating "Save" for editable list columns (list_editable: stock, active ...).
 *
 * The bar (#bshop-save-bar, drawn by templates/admin/change_list.html) is position:fixed in the
 * bottom-right corner and invisible until a field in the table really differs from what the server
 * sent. Showing / hiding it only changes opacity and a transform, so no other element on the page
 * moves. Everything is delegated on document, so it keeps working after table-filter.js re-draws
 * the list in place.
 */
(function () {
  'use strict';

  function fields() {
    return Array.prototype.slice.call(document.querySelectorAll(
      '#changelist-form #result_list input, #changelist-form #result_list select, #changelist-form #result_list textarea'
    )).filter(function (el) {
      // row-select checkboxes (for the Action dropdown) and hidden ids are not "edits"
      return !el.classList.contains('action-select') && el.name !== '_selected_action' &&
             !el.classList.contains('action-toggle') && el.type !== 'hidden' && el.name.indexOf('form-') === 0;
    });
  }
  function changed(el) {
    if (el.type === 'checkbox' || el.type === 'radio') return el.checked !== el.defaultChecked;
    if (el.tagName === 'SELECT') return Array.prototype.some.call(el.options, function (o) { return o.selected !== o.defaultSelected; });
    return el.value !== el.defaultValue;
  }
  function refresh() {
    var bar = document.getElementById('bshop-save-bar');
    if (!bar) return;
    bar.classList.toggle('is-visible', fields().some(changed));
  }

  document.addEventListener('input', function (e) { if (e.target.closest && e.target.closest('#result_list')) refresh(); });
  document.addEventListener('change', function (e) { if (e.target.closest && e.target.closest('#result_list')) refresh(); });

  // Enter inside an editable cell should save the edits (otherwise the browser would press
  // the first button of the form, which is the "Run" of the Action dropdown).
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter' || !e.target.closest || !e.target.closest('#result_list')) return;
    if (!/^(INPUT|SELECT)$/.test(e.target.tagName) || e.target.type === 'submit' || e.target.type === 'button') return;
    var save = document.querySelector('#bshop-save-bar .bsb-save');
    e.preventDefault();
    if (save && document.getElementById('bshop-save-bar').classList.contains('is-visible')) save.click();
  });

  document.addEventListener('click', function (e) {
    if (!e.target.closest || !e.target.closest('#bshop-save-cancel')) return;
    fields().forEach(function (el) {
      if (el.type === 'checkbox' || el.type === 'radio') el.checked = el.defaultChecked;
      else if (el.tagName === 'SELECT') Array.prototype.forEach.call(el.options, function (o) { o.selected = o.defaultSelected; });
      else el.value = el.defaultValue;
    });
    refresh();
  });

  // Browsers restore typed values on Back/reload: show the bar if so.
  window.addEventListener('pageshow', refresh);
  document.addEventListener('DOMContentLoaded', refresh);
})();
