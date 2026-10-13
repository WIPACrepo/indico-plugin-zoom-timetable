import os
import threading

from flask import g, render_template, session
from markupsafe import Markup
from wtforms.fields import BooleanField, IntegerField
from wtforms.validators import InputRequired, NumberRange

from indico.core import signals
from indico.core.plugins import IndicoPlugin, render_plugin_template
from indico.modules.events.sessions.models.blocks import SessionBlock
from indico.modules.events.timetable.views import WPDisplayTimetable
from indico.modules.vc import get_vc_plugins
from indico.modules.vc.models.vc_rooms import VCRoomEventAssociation
from indico.util.date_time import now_utc
from indico.util.signals import values_from_signal
from indico.web.flask.templating import get_overridable_template_name
from indico.web.forms.base import IndicoForm
from indico.web.forms.widgets import SwitchWidget

from indico_zoom_timetable import _


class _BundleGuard(threading.local):
    active = False


_bundle_guard = _BundleGuard()


class SettingsForm(IndicoForm):
    timetable_markers = BooleanField(_('Timetable join buttons'), widget=SwitchWidget(),
                                     description=_('Show a join button on the session blocks in the timetable that '
                                                   'have a videoconference room.'))
    timetable_popups = BooleanField(_('Timetable popups'), widget=SwitchWidget(),
                                    description=_('Show the join button in the popup that opens when clicking such a '
                                                  'session block in the timetable.'))
    live_indicator = BooleanField(_('"Live now" indicator'), widget=SwitchWidget(),
                                  description=_('Show a red dot next to the join button of session blocks that are '
                                                'running right now, with a "Live now" key under the Timetable '
                                                'heading.'))
    live_lead_minutes = IntegerField(_('Live indicator lead time (minutes)'),
                                     [InputRequired(), NumberRange(min=0, max=240)],
                                     description=_('How many minutes before a session block starts its red "live" dot '
                                                   'appears (0: only while it is actually running).'))


class ZoomTimetablePlugin(IndicoPlugin):
    """Zoom timetable buttons

    Show videoconference (e.g. Zoom) join buttons on the session blocks in the timetable of conference
    events, not only on the "Videoconference" page.
    """

    configurable = True
    settings_form = SettingsForm
    default_settings = {
        'timetable_markers': True,
        'timetable_popups': True,
        'live_indicator': True,
        'live_lead_minutes': 0,
    }

    def init(self):
        super().init()
        self.connect(signals.plugin.get_template_customization_paths, self._get_template_customization_path)
        # Hooks called from our template overrides (see template_overrides/)
        self.template_hook('zoom-timetable-balloon', self._render_balloon)
        self.template_hook('zoom-timetable-markers', self._render_timetable_markers)
        self.template_hook('zoom-timetable-key', self._render_timetable_key)
        # VC plugins (e.g. Zoom) don't load their JS/CSS on the timetable page; its popups need them
        self.connect(signals.plugin.inject_bundle, self._inject_vc_plugin_bundles)

    def _get_template_customization_path(self, sender, **kwargs):
        return os.path.join(self.root_path, 'template_overrides')

    def _inject_vc_plugin_bundles(self, sender, **kwargs):
        """Load the VC plugins' assets on the conference timetable page.

        Without this, e.g. the Zoom join button in the timetable popups (a custom element defined in
        the Zoom plugin's JS) would not render.  We only add bundles that are not already injected for
        that page by the VC plugin itself, to avoid loading anything twice.
        """
        if _bundle_guard.active:
            return
        if not issubclass(sender, WPDisplayTimetable):
            return
        _bundle_guard.active = True
        try:
            already = values_from_signal(signals.plugin.inject_bundle.send(sender), as_list=True,
                                         multi_value_types=list)
        finally:
            _bundle_guard.active = False
        already_ids = {id(x) for x in already}
        bundles = []
        for plugin in get_vc_plugins().values():
            for name in ('main.js', 'main.css'):
                try:
                    entry = plugin.manifest[name]
                except (KeyError, TypeError, RuntimeError):
                    continue
                if id(entry) not in already_ids:
                    bundles.append(entry)
        return bundles

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _is_conference(event):
        return event is not None and event.type == 'conference'

    @staticmethod
    def _block_rooms(event):
        """Map session blocks to their visible VC room associations."""
        return {obj: assoc for obj, assoc in VCRoomEventAssociation.get_linked_for_event(event).items()
                if isinstance(obj, SessionBlock) and assoc.vc_room.plugin is not None}

    @classmethod
    def _render_buttons(cls, assoc):
        """Render the VC plugin's own join buttons (same as the meeting timetable).

        The buttons are custom elements defined by the VC plugin's JavaScript.  If that script fails
        to load they would render as nothing at all, so a plain link (shown via CSS only while the
        element is undefined) is added as a fallback.
        """
        plugin = assoc.vc_room.plugin
        tpl = get_overridable_template_name('vc_room_timetable_buttons.html', plugin, core_prefix='vc/')
        buttons = Markup(render_template(tpl, event=assoc.event, event_vc_room=assoc))
        url, needs_passcode = cls._direct_join_url(assoc)
        return Markup(render_plugin_template('join_buttons.html', buttons=buttons, url=url,
                                             needs_passcode=needs_passcode,
                                             title=f'{plugin.friendly_name}: {assoc.vc_room.name}'))

    @staticmethod
    def _direct_join_url(assoc):
        """Return ``(url, needs_passcode)`` for a one-click join link, or ``(None, False)``.

        Mirrors the visibility rules of the Zoom plugin's join button: the full join link is only
        handed out when the current user may see it; if the passcode is hidden from everyone the
        public (passcode-less) link is used.  In all other cases (registration/login required) no
        direct link is given and the timetable marker just opens the popup, whose button explains
        what the user needs to do.
        """
        vc_room = assoc.vc_room
        event = assoc.event
        user = session.user
        url = vc_room.data.get('url')
        if not url:
            return None, False
        get_personalized = getattr(vc_room.plugin, 'get_personalized_join_url', None)
        personalized = get_personalized(vc_room, assoc, user) if get_personalized else None
        visibility = assoc.data.get('password_visibility', 'everyone')
        if (personalized or visibility == 'everyone' or event.can_manage(user)
                or (user and visibility == 'logged_in')
                or (user and visibility == 'registered' and event.is_user_registered(user))):
            return personalized or url, False
        if visibility == 'no_one' and not vc_room.data.get('auto_register') and vc_room.data.get('public_url'):
            return vc_room.data['public_url'], True
        return None, False

    def _styles(self):
        """Inline CSS, emitted at most once per request."""
        if g.get('zoom_timetable_styles_emitted'):
            return ''
        g.zoom_timetable_styles_emitted = True
        return render_plugin_template('styles.html')

    # -------------------------------------------------------------- hook output

    def _render_balloon(self, block, **kwargs):
        if not self._is_conference(block.event) or not self.settings.get('timetable_popups'):
            return
        assoc = self._block_rooms(block.event).get(block)
        if assoc is None:
            return
        # The balloon is loaded via AJAX, so always include the styles
        return render_plugin_template('styles.html') + render_plugin_template(
            'balloon_room.html', assoc=assoc, buttons=self._render_buttons(assoc))

    def _render_timetable_markers(self, event, **kwargs):
        if not self._is_conference(event) or not self.settings.get('timetable_markers'):
            return
        if g.get('zoom_timetable_markers_emitted'):
            return
        blocks = self._marker_data(event)
        if not blocks:
            return
        g.zoom_timetable_markers_emitted = True
        markers = {'blocks': blocks,
                   # the live dot is computed in the browser (so it appears/disappears without a reload);
                   # send the server time so a wrong client clock doesn't matter
                   'live': self.settings.get('live_indicator'),
                   'now': _epoch_ms(now_utc()),
                   'lead': self.settings.get('live_lead_minutes') * 60 * 1000}
        return self._styles() + render_plugin_template('timetable_markers.html', markers=markers)

    def _marker_data(self, event):
        """Join button info for the session blocks that have a room, by block id."""
        blocks = {}
        for block, assoc in self._block_rooms(event).items():
            url, needs_passcode = self._direct_join_url(assoc)
            blocks[block.id] = {'icon': assoc.vc_room.plugin.icon_url,
                                'title': f'{assoc.vc_room.plugin.friendly_name}: {assoc.vc_room.name}',
                                'url': url,
                                'needsPasscode': needs_passcode,
                                'start': _epoch_ms(block.start_dt),
                                'end': _epoch_ms(block.end_dt)}
        return blocks

    def _render_timetable_key(self, event, **kwargs):
        """The "Live now" key under the Timetable heading, explaining the red dot on the entries."""
        if (not self._is_conference(event) or not self.settings.get('timetable_markers')
                or not self.settings.get('live_indicator')):
            return
        if not self._marker_data(event):
            return
        return self._styles() + render_plugin_template('timetable_key.html')


def _epoch_ms(dt):
    return int(dt.timestamp() * 1000) if dt is not None else None
