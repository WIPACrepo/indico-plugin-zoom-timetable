"""Show videoconference join buttons inside *conference* events.

Out of the box, Indico only renders the join button of a videoconference room for
specific themes that we don't use.
In Conference events such rooms are only listed on the
"Videoconference" page.  This plugin adds them to the conference Timetable
page, for session blocks only (not for contributions, and not on the session
or contribution pages, to keep those uncluttered):

* the timetable grid: a Join button on session blocks that have a room, with a
  red "live" dot while the block is running, and a "Live now" key under the
  Timetable heading explaining the dot
* the popup that opens when clicking such a session block

The popup's join button is rendered by the videoconference plugin (e.g. the
Zoom plugin) exactly like in meetings, so passcode visibility, registration
requirements, etc. are respected; the grid button follows the same rules.
"""

from indico.util.i18n import make_bound_gettext


_ = make_bound_gettext('zoom_timetable')
