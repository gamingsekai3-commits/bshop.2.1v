"use strict";
/*
 * Sidebar app groups (Store, Cart, ...) expand on mouse hover purely via
 * CSS (custom_theme.css - #nav-sidebar .module:hover tbody.app-models).
 * Hover doesn't exist on touch screens, and shouldn't be the only way to
 * reach it for keyboard users either, so this adds a click / Enter / Space
 * fallback that toggles the same open state with an .app-expanded class.
 */
{
    function toggleModule(moduleEl, toggleEl) {
        var expanded = moduleEl.classList.toggle("app-expanded");
        toggleEl.setAttribute("aria-expanded", expanded ? "true" : "false");
    }

    document.addEventListener("DOMContentLoaded", function () {
        var sidebar = document.getElementById("nav-sidebar");
        if (!sidebar) {
            return;
        }

        sidebar.querySelectorAll(".module .app-toggle").forEach(function (toggleEl) {
            var moduleEl = toggleEl.closest(".module");
            if (!moduleEl) {
                return;
            }

            toggleEl.addEventListener("click", function () {
                toggleModule(moduleEl, toggleEl);
            });

            toggleEl.addEventListener("keydown", function (event) {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    toggleModule(moduleEl, toggleEl);
                }
            });
        });
    });
}
