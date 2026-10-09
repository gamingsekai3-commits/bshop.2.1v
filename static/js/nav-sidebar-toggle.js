'use strict';

/*
 * Close the admin sidebar when the user clicks outside of it.
 *
 * Opening/closing with the toggle button is already handled by Django's own
 * admin/js/nav_sidebar.js (loaded by admin/base.html). That script keeps the
 * open/closed state (aria-expanded, the "shifted" class and localStorage), so
 * this file must NOT flip aria-expanded itself - it would fall out of sync
 * with Django's script and the toggle button would need two clicks.
 * Instead, "close" here simply clicks the real toggle button.
 */
document.addEventListener('DOMContentLoaded', function () {
    const navSidebar = document.getElementById('nav-sidebar');
    const toggleButton = document.getElementById('toggle-nav-sidebar');

    if (!navSidebar || !toggleButton) {
        return;
    }

    document.addEventListener('click', function (event) {
        const isOpen = navSidebar.getAttribute('aria-expanded') === 'true';

        if (!isOpen) {
            return;
        }

        // Clicks inside the sidebar, or on the toggle button itself, are
        // handled elsewhere - only react to clicks anywhere else.
        if (navSidebar.contains(event.target) || toggleButton.contains(event.target)) {
            return;
        }

        toggleButton.click();
    });
});