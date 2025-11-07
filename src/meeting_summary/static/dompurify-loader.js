// dompurify-loader.js
// If DOMPurify is not present, load it from the CDN to sanitize rendered HTML.
(function () {
  if (typeof window === 'undefined') return;
  if (window.DOMPurify && typeof window.DOMPurify.sanitize === 'function') return;

  var script = document.createElement('script');
  script.src = 'https://unpkg.com/dompurify@3.0.4/dist/purify.min.js';
  script.crossOrigin = 'anonymous';
  script.onload = function () {
    console.info('DOMPurify loaded from CDN');
  };
  script.onerror = function () {
    console.warn('failed to load DOMPurify from CDN');
  };
  document.head.appendChild(script);
})();
