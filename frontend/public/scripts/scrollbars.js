// Reveal native scrollbars only on the element currently being scrolled.
(() => {
  const timers = new WeakMap();
  const held = new Set();
  const idleDelay = 900;

  function hideAfterIdle(element) {
    clearTimeout(timers.get(element));
    if (held.has(element)) return;
    timers.set(element, setTimeout(() => {
      element.classList.remove('scroll-active');
      timers.delete(element);
    }, idleDelay));
  }

  document.addEventListener('scroll', event => {
    const element = event.target === document
      ? document.scrollingElement || document.documentElement
      : event.target;
    if (!element?.classList) return;
    element.classList.add('scroll-active');
    hideAfterIdle(element);
  }, { capture: true, passive: true });

  document.addEventListener('pointerdown', event => {
    const element = event.target.closest?.('.scroll-active');
    if (!element) return;
    held.add(element);
    clearTimeout(timers.get(element));
  }, { passive: true });

  function releaseScrollbars() {
    for (const element of held) {
      held.delete(element);
      hideAfterIdle(element);
    }
  }
  window.addEventListener('pointerup', releaseScrollbars, { passive: true });
  window.addEventListener('pointercancel', releaseScrollbars, { passive: true });
  window.addEventListener('blur', releaseScrollbars);
})();
