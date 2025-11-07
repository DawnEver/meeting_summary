// marked-loader.js
// Lightweight loader: if `window.marked` is not present, load marked from unpkg CDN.
// This keeps repo size small while providing an easy path to vendor a local copy later.
(function(){
  if (typeof window === 'undefined') return;
  if (window.marked && typeof window.marked.parse === 'function') return;

  var script = document.createElement('script');
  script.src = 'https://unpkg.com/marked@5.1.1/marked.min.js';
  script.crossOrigin = 'anonymous';
  script.onload = function(){
    console.info('marked loaded from CDN');
  };
  script.onerror = function(){
    console.warn('failed to load marked from CDN');
  };
  document.head.appendChild(script);
})();
