// Shows a full-screen loading overlay (black background + spinning ring)
// whenever the user navigates to a new page (clicking a normal link or
// submitting a form), so slow page loads don't feel like the click "did
// nothing".
(function () {
    var overlay = document.getElementById('page-loading-overlay');
    if (!overlay) return;

    function startLoading() {
        overlay.classList.add('page-loading-overlay--active');
    }

    function finishLoading() {
        overlay.classList.remove('page-loading-overlay--active');
    }

    document.addEventListener('click', function (e) {
        var link = e.target.closest('a');
        if (!link) return;

        // Skip things that are NOT a real page navigation:
        if (link.target === '_blank') return;
        if (link.hasAttribute('data-bs-toggle') || link.hasAttribute('data-bs-target')) return; // dropdowns/modals
        if (link.classList.contains('no-page-loader')) return; // manual opt-out
        var href = link.getAttribute('href');
        if (!href || href.charAt(0) === '#' || href.indexOf('javascript:') === 0) return;
        if (href.indexOf('/media/') === 0) return; // uploaded file/image, not a page
        if (link.hasAttribute('download')) return;
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;

        // Generic safety net: if some other script already handled this
        // click and called preventDefault() (an AJAX popup that isn't
        // caught by the checks above, a JS-driven window.open, etc.),
        // there's no real page navigation to wait for, so don't show the
        // overlay — otherwise it can get stuck on screen forever.
        if (e.defaultPrevented) return;

        startLoading();
    });

    document.addEventListener('submit', function (e) {
        var form = e.target;
        if (form.classList.contains('no-page-loader')) return;
        if (form.defaultPrevented) return; // AJAX forms that cancel the real submit
        startLoading();
    });

    // Runs on normal loads AND when a page is restored from the
    // back/forward cache, so the overlay never gets stuck showing.
    window.addEventListener('pageshow', function () {
        finishLoading();
    });
})();