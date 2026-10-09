document.addEventListener('DOMContentLoaded', function () {
    const overlay = document.getElementById('popup-edit-overlay');
    const frame = document.getElementById('popup-edit-frame');
    const closeBtn = document.getElementById('popup-edit-close');
    const loading = document.getElementById('popup-edit-loading');

    // The changelist URL is the current page (minus querystring), used to
    // detect "the iframe just landed back here" = save succeeded.
    const changelistPath = window.location.pathname;

    // Ignore the very first load event, which fires for the iframe's
    // initial blank document before any row has been clicked.
    let hasOpened = false;

    // "Loading… please wait" is shown INSIDE the popup until the form has loaded.
    // Toggled with an inline style so it never depends on which CSS file the browser cached.
    function showLoading() {
        if (loading) loading.style.display = 'flex';
    }

    function hideLoading() {
        if (loading) loading.style.display = 'none';
    }

    function openPopup(url) {
        hasOpened = true;
        showLoading();
        // _popup=1 is Django's own flag (the same one its related-object
        // popups use): the change page then renders the bare form - no
        // admin header, user tools, breadcrumbs or sidebar - and, once the
        // form is saved (or the object deleted), Django answers the POST
        // with a tiny "popup response" page that the load handler below
        // detects to close the popup.
        frame.src = url + (url.indexOf('?') === -1 ? '?' : '&') + '_popup=1';
        overlay.classList.add('is-open');
    }

    function closePopup(shouldReload) {
        overlay.classList.remove('is-open');
        hasOpened = false;
        hideLoading();
        // Let the 0.5 s fade-out finish before blanking the iframe / reloading.
        setTimeout(function () {
            if (shouldReload) { window.location.reload(); return; }
            if (!overlay.classList.contains('is-open')) frame.src = 'about:blank';
        }, 500);
    }

    // Intercept clicks on the row links Django renders for list_display_links
    // (id="result_list" is the changelist table).
    // Delegated on document (not bound to each link) so it keeps working when the
    // list is re-drawn in place after a sort / page change (see table-filter.js).
    document.addEventListener('click', function (e) {
        const link = e.target.closest && e.target.closest('#result_list a');
        if (!link) return;
        // Only intercept links that go to a change page (…/<id>/change/),
        // skip anything already opting out.
        if (!/\/\d+\/change\/$/.test(link.pathname)) return;
        if (link.dataset.noPopup !== undefined) return;
        e.preventDefault();
        e.stopPropagation();          // admin-page-loader.js must not show its full-screen overlay
        openPopup(link.href);
    }, true);                         // capture phase: runs before admin-page-loader.js

    // Show the loading indicator again for navigations that happen *inside*
    // the iframe (submitting the form, "Save and continue editing", a link
    // in the breadcrumbs, etc.) - each of those replaces the iframe's
    // document just like the first open did, so it's worth the same
    // feedback. Re-run after every load, since the old document (and its
    // listeners) is gone once the iframe navigates.
    function wireInnerNavigation() {
        let innerDoc;
        try {
            innerDoc = frame.contentDocument;
        } catch (err) {
            return; // cross-origin safety net, shouldn't happen same-origin
        }
        if (!innerDoc) return;

        innerDoc.addEventListener('submit', showLoading, true);
        innerDoc.querySelectorAll('a[href]').forEach(function (a) {
            a.addEventListener('click', showLoading);
        });
    }

    frame.addEventListener('load', function () {
        if (!hasOpened) return; // initial blank/about:blank load, ignore

        let framePath;
        try {
            framePath = frame.contentWindow.location.pathname;
        } catch (err) {
            return; // cross-origin safety net, shouldn't happen same-origin
        }

        // Django returned its tiny "popup response" page: the save (or the
        // confirmed delete) succeeded, so close the popup and refresh the
        // list so it shows the new state.
        if (frame.contentDocument &&
            frame.contentDocument.getElementById('django-admin-popup-response-constants')) {
            closePopup(true);
            return;
        }

        // Fallback: if Django redirected the iframe back to the changelist,
        // the save (or delete) succeeded too.
        if (framePath === changelistPath) {
            closePopup(true);
            return;
        }

        hideLoading();
        wireInnerNavigation();
    });

    closeBtn.addEventListener('click', function () {
        closePopup(false);
    });

    overlay.addEventListener('click', function (e) {
        if (e.target === overlay) closePopup(false);
    });
});