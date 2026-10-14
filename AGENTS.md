# AGENTS.md

Indico 3.x plugin (`zoom_timetable`) that adds videoconference (Zoom) **Join** buttons to session
blocks on the Timetable page of **Conference** events. See `README.md` for user-facing details.

## Layout

| Path | Purpose |
|------|---------|
| `indico_zoom_timetable/plugin.py` | `ZoomTimetablePlugin`: settings form, signal handlers, template hooks |
| `indico_zoom_timetable/__init__.py` | Module docstring + bound gettext `_` (`zoom_timetable` domain) |
| `indico_zoom_timetable/template_overrides/core/events/timetable/` | Overrides of core templates; each extends the original (`~` prefix) and only adds a `template_hook(...)` |
| `indico_zoom_timetable/templates/` | Plugin templates rendered via `render_plugin_template` |
| `pyproject.toml` | Hatchling build; entry point `indico.plugins: zoom_timetable` |
| `hatch_build.py` | Standard Indico plugin build hook (compiles translations if present; none exist yet) |

## How it fits together

- **Template overrides** are registered via `signals.plugin.get_template_customization_paths`.
  - `display.html` → hooks `zoom-timetable-key` and `zoom-timetable-markers` in block `content`.
  - `balloons/block.html` → hook `zoom-timetable-balloon`, spliced before the last `</div>`.
- **Grid markers** (`timetable_markers.html`): server emits JSON (block id → icon, title, url,
  start/end, server `now`, lead time); browser JS places buttons and computes the "live" dot
  (every 30 s and on tab visibility change), correcting for client clock offset.
  Buttons sit in the block's top-right corner, or left of Indico's materials button
  (`a.entry-attachments`) when the block has materials.
- **Popup buttons** (`balloon_room.html`, `join_buttons.html`): rendered by the VC plugin's own
  `vc_room_timetable_buttons.html`, plus a plain-link fallback if the custom element never loads.
- **Asset injection**: `_inject_vc_plugin_bundles` adds VC plugins' `main.js`/`main.css` on
  `WPDisplayTimetable` only, skipping bundles already injected (thread-local guard prevents recursion).
- **Join URL visibility**: `_direct_join_url` mirrors the Zoom plugin's `password_visibility` rules.
  Changes here are security-relevant — never leak a join URL/passcode the user couldn't otherwise see.
- Only rooms linked to a `SessionBlock` are shown; contribution/event-level rooms are untouched.
- Per-request `g.*_emitted` flags ensure styles/markers are output once (balloons are AJAX, so they
  always include styles).

## Constraints

- Target: Indico 3.3.x, Python `>=3.12.2,<3.13`. Tested on 3.3.11 and 3.3.13.
- No DB models, no migrations, no React/webpack client build. Keep it that way unless necessary.
- Every feature has a setting toggle (`default_settings` in `plugin.py`); new features should too.
- User-visible strings go through `_()` (Python) or `{% trans %}` (Jinja).
- CSS classes are prefixed `zt-`; template variables in overrides are prefixed `_zt_`.
- A global `CUSTOMIZATION_DIR` overriding the same templates takes precedence over this plugin.

## Development

- No test suite. Follow Indico code style (single quotes, ~120 cols); `ruff check .` enforces it
  (config in `pyproject.toml`).
- CI (`.github/workflows/lint.yml`): ruff, Python byte-compile, Jinja template parse
  (`.github/scripts/check_templates.py`), and `python -m build`.
- Install into an Indico dev environment: `pip install -e .`, then add `'zoom_timetable'` to
  `PLUGINS` in `indico.conf` (alongside `vc_zoom`).
- Manual verification: a Conference event with a Zoom room linked to a session block; check the
  timetable grid button, the block popup, and the live dot/key with each setting on and off.
- After an Indico upgrade, confirm the overridden templates still have the expected block names
  and markup (`content` block; balloon's outer `</div>`), and that the legacy timetable JS
  (`Draw.js`) still uses the classes the grid markers rely on: `.timetableBlock`,
  `.timetableBlockWrapper` > `.timetableBlockTitle`, `.timetableBlockTime(Discreet)`, `.entry-attachments`,
  and the `_getRightSideDecorators` method.
