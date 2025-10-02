/*
(function setupConsoleSilencer() {
  try {
    var host = (typeof window !== 'undefined' && window.location && window.location.hostname) || '';
    var isLocal = host === 'localhost' || host === '127.0.0.1' || host.endsWith('.local');

    // Allow query flag to re-enable logs for debugging in prod: ?debugLogs=1
    var search = (typeof window !== 'undefined' && window.location && window.location.search) || '';
    var params = {};
    if (search && search.indexOf('?') !== -1) {
      search.substring(1).split('&').forEach(function (pair) {
        var kv = pair.split('=');
        params[decodeURIComponent(kv[0] || '')] = decodeURIComponent(kv[1] || '');
      });
    }
    var allowDebug = params.debugLogs === '1' || params.debug === '1';

    if (isLocal || allowDebug) {
      return; // keep console as-is in local or when explicitly enabled
    }

    if (!window.console) {
      window.console = {};
    }

    var noop = function () {};
    // Preserve error but cap payload to avoid sensitive data flooding
    var originalError = window.console.error ? window.console.error.bind(window.console) : noop;
    // Replace noisy methods
    window.console.log = noop;
    window.console.info = noop;
    window.console.debug = noop;
    window.console.warn = noop;

    // Wrap error to reduce accidental leakage of massive objects
    window.console.error = function () {
      try {
        var args = Array.prototype.slice.call(arguments, 0);
        // Stringify non-primitive args shallowly to avoid dumping huge objects
        var sanitized = args.map(function (arg) {
          if (arg == null) return arg;
          var t = typeof arg;
          if (t === 'string' || t === 'number' || t === 'boolean') return arg;
          if (arg instanceof Error) return arg.stack || arg.message || String(arg);
          try {
            return JSON.stringify(arg, function (k, v) {
              if (typeof v === 'string' && v.length > 500) return v.slice(0, 500) + '…';
              return v;
            });
          } catch (_e) {
            return '[object]';
          }
        });
        originalError.apply(null, sanitized);
      } catch (_err) {
        try { originalError('[console-silencer] error printing console.error'); } catch (_ignored) {}
      }
    };
  } catch (_e) {
    // If anything fails, do nothing; do not break the page
  }
})();


*/