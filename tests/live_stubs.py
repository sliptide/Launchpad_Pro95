"""Minimal stand-ins for Live and _Framework, so the step sequencer code can run outside of Live.

Only what the step sequencers touch is implemented. Clip notes use the old tuple format:
(pitch, time, duration, velocity, muted).
"""
import sys
import types

song = None


def _module(name, **attrs):
	module = types.ModuleType(name)
	module.__dict__.update(attrs)
	sys.modules[name] = module
	return module


# _Framework

class ControlSurfaceComponent(object):

	def __init__(self, *a, **k):
		self._enabled = True

	def set_enabled(self, enabled):
		self._enabled = bool(enabled)

	def is_enabled(self):
		return self._enabled

	def update(self):
		pass

	def song(self):
		return song

	def application(self):
		return _Application()

	def on_selected_track_changed(self):
		pass

	def on_selected_scene_changed(self):
		pass


class CompoundComponent(ControlSurfaceComponent):

	def register_component(self, component):
		return component


class MixerComponent(ControlSurfaceComponent):

	def __init__(self, num_tracks, *a, **k):
		ControlSurfaceComponent.__init__(self)

	def disconnect(self):
		pass


class ButtonElement(object):

	def __init__(self):
		self._on_value = None
		self._off_value = None
		self._listeners = []

	def set_on_off_values(self, on_value, off_value=None):
		self._on_value = on_value
		self._off_value = off_value

	def add_value_listener(self, listener, identify_sender=False):
		self._listeners.append(listener)

	def remove_value_listener(self, listener):
		self._listeners.remove(listener)

	def is_momentary(self):
		return True

	def __getattr__(self, name):
		# turn_on, set_light, set_channel, ...: LED and MIDI calls are no-ops here
		return lambda *a, **k: None


class ButtonMatrixElement(object):

	def __init__(self):
		self._buttons = [[ButtonElement() for y in range(8)] for x in range(8)]
		self._listeners = []

	def width(self):
		return 8

	def height(self):
		return 8

	def get_button(self, x, y):
		return self._buttons[x][y]

	def iterbuttons(self):
		for x in range(8):
			for y in range(8):
				yield self._buttons[x][y], (x, y)

	def add_value_listener(self, listener):
		if listener not in self._listeners:
			self._listeners.append(listener)

	def remove_value_listener(self, listener):
		self._listeners.remove(listener)

	def reset(self):
		pass

	def press(self, x, y):
		for listener in list(self._listeners):
			listener(127, x, y, True)
		for listener in list(self._listeners):
			listener(0, x, y, True)


class _View(object):

	def is_view_visible(self, name):
		return True

	def show_view(self, name):
		pass


class _Application(object):
	view = _View()


# Live objects

class Clip(object):

	def __init__(self, notes=(), loop_end=16.0):
		self.notes = [tuple(note) for note in notes]
		self.loop_start = 0.0
		self.loop_end = loop_end
		self.start_marker = 0.0
		self.end_marker = loop_end
		self.is_midi_clip = True
		self.name = "clip"
		self.is_playing = False
		self.is_triggered = False
		self.playing_position = 0.0
		self.writes = 0
		self._notes_listeners = []

	def snapshot(self):
		return (sorted(self.notes), self.loop_start, self.loop_end)

	def select_all_notes(self):
		pass

	def deselect_all_notes(self):
		pass

	def get_selected_notes(self):
		return tuple(self.notes)

	def replace_selected_notes(self, notes):
		self.writes += 1
		self.notes = [tuple(note) for note in notes]
		for listener in list(self._notes_listeners):
			listener()

	def add_notes_listener(self, listener):
		self._notes_listeners.append(listener)

	def remove_notes_listener(self, listener):
		self._notes_listeners.remove(listener)

	def notes_has_listener(self, listener):
		return listener in self._notes_listeners

	def __getattr__(self, name):
		# other listeners (playing status, loop points...) are accepted and never fire
		if name.endswith('_has_listener'):
			return lambda listener: False
		if name.startswith('add_') or name.startswith('remove_'):
			return lambda listener: None
		raise AttributeError(name)


class ClipSlot(object):

	def __init__(self, track, clip=None):
		self.canonical_parent = track
		self.clip = clip

	@property
	def has_clip(self):
		return self.clip is not None

	def create_clip(self, length):
		if not self.canonical_parent.has_midi_input:
			raise RuntimeError("MIDI clips can only be created on MIDI tracks")
		self.clip = Clip(loop_end=length)

	def fire(self):
		pass

	def has_clip_has_listener(self, listener):
		return False

	def add_has_clip_listener(self, listener):
		pass

	def remove_has_clip_listener(self, listener):
		pass


class Track(object):

	def __init__(self, clips, has_midi_input=True):
		self.name = "track"
		self.has_midi_input = has_midi_input
		self.clip_slots = [ClipSlot(self, clip) for clip in clips]


class Song(object):

	def __init__(self, clips, has_midi_input=True):
		track = Track(clips, has_midi_input)
		self.tracks = [track]
		self.scenes = [object() for _ in clips]
		self.is_playing = False
		self.view = types.SimpleNamespace(selected_track=track)
		self.select_scene(0)

	def select_scene(self, index):
		self.view.selected_scene = self.scenes[index]
		self.view.highlighted_clip_slot = self.tracks[0].clip_slots[index]


class ControlSurface(object):

	def __init__(self):
		self.messages = []

	def show_message(self, message):
		self.messages.append(message)

	def __getattr__(self, name):
		# log_message, schedule_message, set_feedback_channels, ...
		return lambda *a, **k: None


def make_song(clips, has_midi_input=True):
	global song
	song = Song(clips, has_midi_input)
	return song


def install(script_dir):
	_module('Live', Base=types.SimpleNamespace(LimitationError=Exception))
	_module('_Framework', __path__=[])
	_module('_Framework.ControlSurfaceComponent', ControlSurfaceComponent=ControlSurfaceComponent)
	_module('_Framework.CompoundComponent', CompoundComponent=CompoundComponent)
	_module('_Framework.MixerComponent', MixerComponent=MixerComponent)
	_module('_Framework.ButtonElement', ButtonElement=ButtonElement)
	_module('_Framework.ButtonMatrixElement', ButtonMatrixElement=ButtonMatrixElement)
	_module('_Framework.ToggleComponent', ToggleComponent=object)
	_module('_Framework.Util', find_if=lambda predicate, seq: next((x for x in seq if predicate(x)), None))
	# import the script's modules as package "script" without running its __init__ (which needs a real Live)
	_module('script', __path__=[script_dir])
