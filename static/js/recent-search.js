(function () {
    var STORAGE_KEY = 'eshop-recent-searches';
    var MAX_ITEMS = 8;
    var DEBOUNCE_MS = 250;

    var input = document.getElementById('searched-input');
    var dropdown = document.getElementById('recent-search-dropdown');
    var header = document.getElementById('recent-search-header-label');
    var clearBtn = document.getElementById('recent-search-clear');
    var list = document.getElementById('recent-search-list');
    var form = input ? input.closest('form') : null;

    // The search input lives in the shared navbar, included on every page,
    // so bail out defensively if any piece isn't there.
    if (!input || !dropdown || !list || !form) return;

    var searchUrl = form.getAttribute('action') || '/search/';
    var debounceTimer = null;
    var currentRequest = null;

    // ---------- recent searches (stored in localStorage) ----------

    function getRecent() {
        try {
            var raw = localStorage.getItem(STORAGE_KEY);
            var arr = raw ? JSON.parse(raw) : [];
            return Array.isArray(arr) ? arr : [];
        } catch (e) {
            return [];
        }
    }

    function saveRecent(arr) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(arr));
        } catch (e) {
            // Storage unavailable (private mode, quota, etc) - fail silently.
        }
    }

    function addRecent(term) {
        term = (term || '').trim();
        if (!term) return;
        var arr = getRecent().filter(function (t) {
            return t.toLowerCase() !== term.toLowerCase();
        });
        arr.unshift(term);
        if (arr.length > MAX_ITEMS) arr = arr.slice(0, MAX_ITEMS);
        saveRecent(arr);
    }

    function removeRecent(term) {
        saveRecent(getRecent().filter(function (t) { return t !== term; }));
        renderRecent();
    }

    function clearAllRecent() {
        saveRecent([]);
        renderRecent();
    }

    function renderRecent() {
        dropdown.classList.remove('dropdown-mode-suggest');
        if (header) header.textContent = header.dataset.recentLabel || 'Recent';
        if (clearBtn) clearBtn.classList.remove('d-none');

        var arr = getRecent();
        list.innerHTML = '';

        if (!arr.length) {
            dropdown.classList.add('d-none');
            return;
        }

        arr.forEach(function (term) {
            var li = document.createElement('li');
            li.className = 'recent-search-item';

            var icon = document.createElement('span');
            icon.className = 'recent-search-icon';
            icon.innerHTML = '<i class="bi bi-clock-history"></i>';

            var text = document.createElement('span');
            text.className = 'recent-search-text';
            text.textContent = term;

            var removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'recent-search-remove';
            removeBtn.setAttribute('aria-label', 'Remove');
            removeBtn.innerHTML = '<i class="bi bi-x-lg"></i>';

            li.appendChild(icon);
            li.appendChild(text);
            li.appendChild(removeBtn);

            li.addEventListener('click', function (e) {
                if (e.target.closest('.recent-search-remove')) return;
                input.value = term;
                dropdown.classList.add('d-none');
                form.submit();
            });

            removeBtn.addEventListener('click', function (e) {
                e.stopPropagation();
                removeRecent(term);
            });

            list.appendChild(li);
        });

        dropdown.classList.remove('d-none');
    }

    // ---------- live product suggestions (name starts with query) ----------

    function formatPrice(n) {
        return Math.round(n).toLocaleString() + '\u20AE';
    }

    function renderSuggestions(products, query) {
        dropdown.classList.add('dropdown-mode-suggest');
        if (header) header.textContent = header.dataset.productsLabel || 'Products';
        if (clearBtn) clearBtn.classList.add('d-none');

        list.innerHTML = '';

        if (!products.length) {
            dropdown.classList.add('d-none');
            return;
        }

        products.forEach(function (p) {
            var li = document.createElement('li');
            li.className = 'recent-search-item suggest-item';

            var thumb = document.createElement('img');
            thumb.className = 'suggest-thumb';
            thumb.src = p.image || '';
            thumb.alt = p.name;

            var text = document.createElement('span');
            text.className = 'recent-search-text';
            text.textContent = p.name;

            var price = document.createElement('span');
            price.className = 'suggest-price';
            price.textContent = formatPrice(p.price);

            li.appendChild(thumb);
            li.appendChild(text);
            li.appendChild(price);

            li.addEventListener('click', function () {
                addRecent(query);
                window.location.href = p.url;
            });

            list.appendChild(li);
        });

        var seeAll = document.createElement('li');
        seeAll.className = 'recent-search-item suggest-see-all';
        var prefix = (header && header.dataset.seeAllPrefix) || 'See all results for';
        seeAll.textContent = prefix + ' \u201C' + query + '\u201D';
        seeAll.addEventListener('click', function () {
            dropdown.classList.add('d-none');
            form.submit();
        });
        list.appendChild(seeAll);

        dropdown.classList.remove('d-none');
    }

    function fetchSuggestions(value) {
        if (currentRequest) currentRequest.abort();
        var controller = new AbortController();
        currentRequest = controller;

        var url = searchUrl + '?searched=' + encodeURIComponent(value) + '&suggest=1';

        fetch(url, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            signal: controller.signal
        })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                renderSuggestions(data.results || [], value);
            })
            .catch(function (err) {
                if (err.name !== 'AbortError') {
                    console.error('Search suggest failed:', err);
                }
            });
    }

    // ---------- wiring ----------

    input.addEventListener('focus', function () {
        var value = input.value.trim();
        if (value) {
            fetchSuggestions(value);
        } else {
            renderRecent();
        }
    });

    input.addEventListener('input', function () {
        var value = input.value.trim();
        clearTimeout(debounceTimer);

        if (!value) {
            if (currentRequest) currentRequest.abort();
            renderRecent();
            return;
        }

        debounceTimer = setTimeout(function () {
            fetchSuggestions(value);
        }, DEBOUNCE_MS);
    });

    document.addEventListener('click', function (e) {
        if (!dropdown.contains(e.target) && e.target !== input) {
            dropdown.classList.add('d-none');
        }
    });

    if (clearBtn) {
        clearBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            clearAllRecent();
        });
    }

    // Enter / search-button submit still navigates to the full search page
    // (search.html) - the dropdown is for quick previews, not a replacement
    // for browsing complete results.
    form.addEventListener('submit', function () {
        addRecent(input.value);
    });

    dropdown.classList.add('d-none');
})();
