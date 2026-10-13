# Indico-plugin-zoom-timetable
Indico Zoom Timetable Plugin

Shows videoconference (Zoom) `Join` buttons on the timetable of `Conference` events in Indico 3.3.

## Why

In Indico, a videoconference room linked to a session block or contribution gets a Join button only in Meeting/Lecture events, but for the most IceCube meetings, we use a collab event. Those buttons come from the `vc-actions` template hook, which is called only by the meeting/lecture display templates. In Conference events, the same rooms appear only on the event's Videoconference page. The timetable, session pages and contribution pages show no zoom buttons. 

This plugin adds Join buttons to the conference Timetable page, on session blocks only.

The popup button is rendered by the Zoom plugin itself, exactly as in meetings. Preserving passcode visibility (everyone / logged-in / registered / no one), "make me alternative host", the info popup with meeting ID and passcode.

Rooms linked to a contribution, or to the whole event, are still listed on the event's
Videoconference page, as without the plugin.

## Requirements

* Indico 3.3.x. Tested on 3.3.11 and 3.3.13, with `indico-plugin-vc-zoom` 3.3.6.

## Install

Install the plugin into the Indico image from a release tag; pip builds it from source:

```dockerfile
RUN pip install git+https://github.com/WIPACrepo/Indico-plugin-zoom-timetable@v3.3
```

Pin a tag (or commit) rather than `main`, so image rebuilds are reproducible.

Enable it in `indico.conf` (e.g. in the ConfigMap the Indico and Celery pods mount):

```python
PLUGINS = {'vc_zoom', 'zoom_timetable'}   # plus whatever you already have
```

Roll out the new image to the Indico web and Celery deployments.

Settings are under **Administration → Plugins → Zoom timetable buttons**. Every feature has its
own on/off switch (grid buttons, popup buttons, live dot). The red "live" dot can be shown some
minutes before a block starts (default 0: only while it runs). The plugin adds no database
tables and needs no migrations. To uninstall, remove it from `PLUGINS` and redeploy.

## How it works / upgrade notes

* **Template overrides** live in `indico_zoom_timetable/template_overrides/core/…` and are
  registered through Indico's `get_template_customization_paths` signal. Each one *extends* the
  original template with the `~` prefix and only adds a `template_hook(...)` call:
  * `events/timetable/display.html`: block `content`
  * `events/timetable/balloons/block.html`: includes the original and inserts the button
    before its last `</div>`

  After an Indico upgrade, check that these pages still render. A renamed block is the only
  likely thing to break.
* If you already use a global `CUSTOMIZATION_DIR` that overrides any of these same templates,
  your global override wins and the plugin's version of that template is ignored.
* **Timetable markers** patch `TimetableBlockNormalDisplay` / `TimetableBlockWholeDayDisplay`
  in Indico's legacy timetable JS. Errors are caught, so the worst case is a missing icon.
* **Asset loading:** the Zoom plugin doesn't load its JS/CSS on the timetable page, which the
  popup buttons need. This plugin loads it there (only there), and never loads anything twice.
* **Live dot:** the page carries each entry's start/end and the server's clock; the browser
  decides what is live (re-checked every 30 s and when the tab becomes visible again), so the
  dot appears and disappears without a reload and a wrong visitor clock doesn't matter.
* The timetable shows block rooms with *Show in event* enabled that are not deleted, the same
  rooms the Videoconference page lists.

## Without the plugin

Setting **Customization → Layout → Timetable → Theme** to **"Indico style"** in a conference
makes the Timetable page use the meeting-style layout, which shows Join buttons on every
session block natively. Everything else about the conference stays the same. This covers
the timetable only.
