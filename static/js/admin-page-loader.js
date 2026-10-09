// Shows a full-screen loading overlay in the admin (same behavior as the
// storefront's static/js/page-loader.js) whenever the user navigates to a
// new page, so slow admin page loads don't feel like the click "did
// nothing".
(function () {
    var overlay = document.getElementById('page-loading-overlay');
    if (!overlay) return;
    // Inside the edit popup's <iframe> the popup itself is the feedback: no second loader.
    if (window.self !== window.top) return;

    // Only show the overlay if the next page takes longer than this (ms).
    // Fast navigations finish before then, so the user never sees a flash.
    var SHOW_DELAY = 120;
    var timer = null;

    function startLoading() {
        if (timer) return;
        timer = setTimeout(function () {
            overlay.classList.add('page-loading-overlay--active');
        }, SHOW_DELAY);
    }

    function finishLoading() {
        clearTimeout(timer);
        timer = null;
        overlay.classList.remove('page-loading-overlay--active');
    }

    document.addEventListener('click', function (e) {
        var link = e.target.closest('a');
        if (!link) return;

        // Skip things that are NOT a real page navigation:
        if (link.target === '_blank') return;
        if (link.hasAttribute('data-bs-toggle') || link.hasAttribute('data-bs-target')) return;
        if (link.classList.contains('no-page-loader')) return; // manual opt-out
        var href = link.getAttribute('href');
        if (!href || href.charAt(0) === '#' || href.indexOf('javascript:') === 0) return;
        if (href.indexOf('/media/') === 0) return; // uploaded file/image (e.g. "Currently: <a>" on edit forms), not a page
        if (link.hasAttribute('download')) return;
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;

        // The "/admin/.../add/" popup links (see base_site.html) already
        // intercept their own clicks with a capturing stopPropagation(),
        // so this bubble-phase listener never runs for them and the popup
        // keeps its own inline spinner instead of the full-page overlay.
        //
        // Django's OWN related-object popups (the change/add/view/delete
        // icons next to a ForeignKey field, and the raw_id "lookup" icon)
        // work differently: RelatedObjectLookups.js calls preventDefault()
        // on the click but does NOT stop propagation, then opens a *new*
        // window with window.open(). Without this check, this listener
        // would still show the overlay in the current window even though
        // that window never navigates anywhere, leaving it stuck on
        // screen. Checking defaultPrevented here catches this case (and
        // any future one) generically, the same way the submit handler
        // below already checks form.defaultPrevented.
        if (e.defaultPrevented) return;

        startLoading();
    });

    document.addEventListener('submit', function (e) {
        var form = e.target;
        if (form.classList.contains('no-page-loader')) return;
        if (form.defaultPrevented) return; // AJAX forms (e.g. the add-popup) that cancel the real submit
        startLoading();
    });

    // Runs on normal loads AND when a page is restored from the
    // back/forward cache, so the overlay never gets stuck showing.
    window.addEventListener('pageshow', function () {
        finishLoading();
    });
})();