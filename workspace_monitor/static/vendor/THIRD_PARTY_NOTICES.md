# Third-party notices — vendored shell assets

These files are vendored under `static/vendor/` so the app and the
Pages freeze work without a CDN. They are not workspace-monitor code
and are not covered by this repo's MIT licence text alone; each
carries its own MIT licence (headers are preserved in the files).

- **AdminLTE 4.10.0** — `adminlte.min.css`, `adminlte.min.js`.
  MIT, © Colorlib. Upstream: https://github.com/ColorlibHQ/AdminLTE
  (licence: https://opensource.org/licenses/MIT).
- **Bootstrap 5.3.8** — `bootstrap.min.css`, `bootstrap.bundle.min.js`.
  MIT, © The Bootstrap Authors. Upstream:
  https://github.com/twbs/bootstrap
  (licence: https://github.com/twbs/bootstrap/blob/main/LICENSE).
- **Bootstrap Icons 1.11.3** — `bootstrap-icons.min.css`,
  `fonts/bootstrap-icons.woff`, `fonts/bootstrap-icons.woff2`.
  MIT, © The Bootstrap Authors. Upstream:
  https://github.com/twbs/icons
  (licence: https://github.com/twbs/icons/blob/main/LICENSE).

Leaflet (used only on Attendance/Distance maps) is not vendored here;
it is loaded from its CDN in those pages' templates, as before.
