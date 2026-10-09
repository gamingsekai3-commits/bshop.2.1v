'use strict';

/*
 * Make each app group in the admin sidebar (#nav-sidebar .module) collapse
 * and expand independently, accordion-style.
 *
 * This deliberately does NOT touch templates/admin/app_list.html - the
 * per-model rows Django renders after <thead> with no explicit <tbody> are
 * still wrapped in one implicit <tbody> by the browser's HTML parser, so
 * `table.tBodies[0]` reliably grabs "all the model rows for this app"
 * without any markup changes, for both the real app groups and the
 * hand-written "Stock" entry in nav_sidebar.html.
 *
 * State is remembered per app (by its "app-<label>" class) in localStorage,
 * the same storage Django's own nav_sidebar.js already uses for open/closed
 * and theme.js uses for light/dark, so it survives reloads and new tabs.
 *
 * Whichever app the current page belongs to (".current-app") starts
 * expanded the first time it's seen, so navigating into a model never hides
 * the very link the visitor is standing on - but if they collapse it
 * anyway, that explicit choice is remembered too.
 *
 * Django's own admin/js/nav_sidebar.js (initSidebarQuickFilter) shows/hides
 * individual <tr> elements by setting style.display directly while
 * filtering. A row inside a collapsed group's display:none <tbody> would
 * stay invisible no matter what it sets on the <tr>, so while the filter
 * box has a value every group is force-expanded via the "filtering" class
 * below, independent of its stored collapsed state.
 */
document.addEventListener('DOMContentLoaded', function () {
    const navSidebar = document.getElementById('nav-sidebar');
    if (!navSidebar) {
        return;
    }

    // Fold any custom, non-model links (e.g. "Stock") into a real app
    // group's table, right alongside its models, per
    // templates/admin/nav_sidebar.html's [data-merge-app] wrapper. Runs
    // first so the merged rows are already in place by the time the
    // accordion below measures each group's row count.
    navSidebar.querySelectorAll('.merge-target[data-merge-app]').forEach(function (wrapper) {
        const targetModule = navSidebar.querySelector('.app-' + wrapper.dataset.mergeApp);
        const targetTbody = targetModule && targetModule.querySelector('table').tBodies[0];
        if (targetTbody) {
            wrapper.querySelectorAll('tr').forEach(function (row) {
                targetTbody.appendChild(row);
            });
        }
        wrapper.remove();
    });

    const STORAGE_KEY = 'django.admin.sidebarCollapsedApps';

    function loadState() {
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
        } catch (e) {
            return {};
        }
    }

    function saveState(state) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        } catch (e) {
            // Storage unavailable (private browsing, quota, ...) - the
            // accordion still works for the rest of this page view.
        }
    }

    const state = loadState();
    let stateChanged = false;

    function appKeyFor(moduleEl) {
        const match = Array.from(moduleEl.classList).find(function (cls) {
            return cls.indexOf('app-') === 0;
        });
        return match || null;
    }

    function setCollapsed(moduleEl, toggleBtn, tbody, collapsed) {
        moduleEl.classList.toggle('collapsed', collapsed);
        toggleBtn.setAttribute('aria-expanded', String(!collapsed));
        tbody.hidden = false; // visibility is driven by CSS on .collapsed, not [hidden]
    }

    navSidebar.querySelectorAll('.module').forEach(function (moduleEl) {
        const table = moduleEl.querySelector('table');
        const caption = table && table.querySelector('caption');
        const tbody = table && table.tBodies[0];

        if (!table || !caption || !tbody || !tbody.rows.length) {
            return; // nothing to collapse (e.g. an empty group)
        }

        const key = appKeyFor(moduleEl);
        const isCurrentApp = moduleEl.classList.contains('current-app');

        let collapsed;
        if (key && Object.prototype.hasOwnProperty.call(state, key)) {
            collapsed = state[key];
        } else {
            collapsed = false; // first time we see this app: start open
            if (key) {
                state[key] = collapsed;
                stateChanged = true;
            }
        }
        if (isCurrentApp && collapsed && !(key && state['__explicit_' + key])) {
            // Never seen this app collapsed by an explicit click yet; keep
            // the active section visible.
            collapsed = false;
        }

        if (!tbody.id) {
            tbody.id = 'nav-sidebar-group-' + (key || Math.random().toString(36).slice(2));
        }

        const toggleBtn = document.createElement('button');
        toggleBtn.type = 'button';
        toggleBtn.className = 'app-toggle';
        toggleBtn.setAttribute('aria-controls', tbody.id);
        toggleBtn.setAttribute(
            'aria-label',
            (caption.querySelector('.section') || caption).textContent.trim()
        );
        toggleBtn.innerHTML =
            '<svg class="app-toggle-chevron" viewBox="0 0 24 24" width="14" height="14" ' +
            'aria-hidden="true"><path d="M8 5l8 7-8 7" fill="none" stroke="currentColor" ' +
            'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
        caption.appendChild(toggleBtn);

        setCollapsed(moduleEl, toggleBtn, tbody, collapsed);

        toggleBtn.addEventListener('click', function () {
            const nowCollapsed = !moduleEl.classList.contains('collapsed');
            setCollapsed(moduleEl, toggleBtn, tbody, nowCollapsed);
            if (key) {
                state[key] = nowCollapsed;
                state['__explicit_' + key] = true;
                saveState(state);
            }
        });
    });

    if (stateChanged) {
        saveState(state);
    }

    // Keep filtered-out models reachable even inside a collapsed group.
    const navFilter = document.getElementById('nav-filter');
    if (navFilter) {
        navFilter.addEventListener('input', function () {
            navSidebar.classList.toggle('filtering', navFilter.value.length > 0);
        });
    }
});
