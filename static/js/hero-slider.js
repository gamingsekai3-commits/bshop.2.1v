(function () {
  var INTERVAL = 3000; // 3 sekund

  function init(root) {
    var track = root.querySelector('.hero-slider__track');
    var slides = root.querySelectorAll('.hero-slider__slide');
    var dotsBox = root.querySelector('.hero-slider__dots');
    var n = slides.length, idx = 0, timer = null;
    if (!n) return;

    var dots = [];
    for (var i = 0; i < n; i++) {
      (function (i) {
        var b = document.createElement('button');
        b.type = 'button';
        b.className = 'hero-slider__dot';
        b.setAttribute('aria-label', 'Slide ' + (i + 1));
        b.addEventListener('click', function () { go(i); restart(); });
        dotsBox.appendChild(b);
        dots.push(b);
      })(i);
    }

    function go(i) {
      idx = (i + n) % n;
      track.style.transform = 'translateX(' + (-idx * 100) + '%)';
      dots.forEach(function (d, k) { d.classList.toggle('is-active', k === idx); });
    }
    function start() { if (n > 1) timer = setInterval(function () { go(idx + 1); }, INTERVAL); }
    function stop() { clearInterval(timer); }
    function restart() { stop(); start(); }

    root.querySelector('.hero-slider__btn--prev').addEventListener('click', function () { go(idx - 1); restart(); });
    root.querySelector('.hero-slider__btn--next').addEventListener('click', function () { go(idx + 1); restart(); });
    root.addEventListener('mouseenter', stop);
    root.addEventListener('mouseleave', start);

    // gar utas: shudeh
    var x0 = null;
    root.addEventListener('touchstart', function (e) { x0 = e.touches[0].clientX; stop(); }, { passive: true });
    root.addEventListener('touchend', function (e) {
      if (x0 !== null) {
        var dx = e.changedTouches[0].clientX - x0;
        if (Math.abs(dx) > 40) go(idx + (dx < 0 ? 1 : -1));
      }
      x0 = null; start();
    });

    document.addEventListener('visibilitychange', function () { document.hidden ? stop() : restart(); });

    if (n === 1) root.querySelectorAll('.hero-slider__btn, .hero-slider__dots').forEach(function (e) { e.style.display = 'none'; });
    go(0); start();
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-hero-slider]').forEach(init);
  });
})();
