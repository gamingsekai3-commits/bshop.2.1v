"use strict";
{
    function setTheme(mode) {
        if (mode !== "light" && mode !== "dark") {
            console.error(
                `Got invalid theme mode: ${mode}. Resetting to light.`,
            );
            mode = "light";
        }
        document.documentElement.dataset.theme = mode;
        localStorage.setItem("theme", mode);
    }

    function cycleTheme() {
        const currentTheme = localStorage.getItem("theme") || "light";

        // Light -> Dark -> Light (no auto)
        if (currentTheme === "light") {
            setTheme("dark");
        } else {
            setTheme("light");
        }
    }

    function initTheme() {
        // set theme defined in localStorage if there is one, or fallback to light mode
        const currentTheme = localStorage.getItem("theme");
        setTheme(currentTheme === "dark" ? "dark" : "light");
    }

    window.addEventListener("load", function (_) {
        const buttons = document.getElementsByClassName("theme-toggle");
        Array.from(buttons).forEach((btn) => {
            btn.addEventListener("click", cycleTheme);
        });
    });

    initTheme();
}