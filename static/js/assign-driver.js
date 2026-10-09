// Order list: picking a driver in the "Хүргэгч" dropdown of a NEW order assigns it
// (POST to the row's data-url). The order then becomes "Бэлтгэгдэж буй" and the
// cell shows the driver's name as text. Delegated on document, because the list is
// swapped in place by table-filter.js.
(function () {
  function csrfToken() {
    var input = document.querySelector('input[name=csrfmiddlewaretoken]');
    if (input) return input.value;
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  document.addEventListener('change', function (e) {
    var select = e.target;
    if (!select.classList || !select.classList.contains('js-assign-driver')) return;
    if (!select.value) return;

    var body = new FormData();
    body.append('driver', select.value);
    select.disabled = true;

    fetch(select.dataset.url, {
      method: 'POST',
      body: body,
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': csrfToken(), 'X-Requested-With': 'XMLHttpRequest' }
    })
      .then(function (r) { return r.json().catch(function () { return { ok: false }; }); })
      .then(function (data) {
        if (data.ok) { window.location.reload(); return; }
        alert(data.error || 'Error');
        select.value = '';
        select.disabled = false;
      })
      .catch(function () {
        alert('Error');
        select.value = '';
        select.disabled = false;
      });
  });
})();
