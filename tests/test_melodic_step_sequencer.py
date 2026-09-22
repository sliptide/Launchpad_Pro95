"""Regression tests for the melodic step sequencer (StepSequencerComponent2).

Runs the script's own code against stand-ins for Live (see live_stubs.py), outside of Live:

	python3 tests/test_melodic_step_sequencer.py
"""
import os
import sys
import unittest
import warnings

sys.dont_write_bytecode = True
warnings.simplefilter('ignore', SyntaxWarning)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import live_stubs
live_stubs.install(os.path.dirname(HERE))
from script.StepSequencerComponent2 import StepSequencerComponent2

C_MAJOR = [0, 2, 4, 5, 7, 9, 11]


def c_major_run(count=64):
	# one 1/16 note per step, walking up C major from C1 (36) over two octaves: 4 bars
	return [(36 + C_MAJOR[i % 7] + 12 * ((i // 7) % 2), i * 0.25, 0.25, 100, False) for i in range(count)]


class MelodicStepSequencerTest(unittest.TestCase):

	def setUp(self):
		self.control_surface = live_stubs.ControlSurface()

	def make(self, *clips, **k):
		self.song = live_stubs.make_song(clips, **k)
		self.seq = StepSequencerComponent2(self.control_surface)

	def enter(self):
		# what entering the mode does: enable, then the layer assigns the matrix and the buttons
		self.seq.set_enabled(True)
		self.matrix = live_stubs.ButtonMatrixElement()
		self.seq.set_matrix(self.matrix)
		self.seq.set_quantization_button(live_stubs.ButtonElement())

	def leave(self):
		self.seq.set_matrix(None)
		self.seq.set_quantization_button(None)
		self.seq.set_enabled(False)

	def select_scene(self, index):
		self.song.select_scene(index)
		self.seq.on_selected_scene_changed()

	def press_quantization(self):
		self.seq._quantization_button_value(127)

	def change_key(self, key):
		self.seq._scale_button_value(127)
		self.seq._scale_component.set_key(key, message=False)
		self.seq._scale_button_value(0)

	def test_entering_leaves_clip_untouched(self):
		clip = live_stubs.Clip(c_major_run())
		self.make(clip)
		before = clip.snapshot()
		self.enter()
		self.assertEqual(clip.snapshot(), before)
		self.assertEqual(clip.writes, 0)

	def test_reentering_keeps_quantization_and_clip(self):
		clip = live_stubs.Clip(c_major_run())
		self.make(clip)
		self.enter()
		self.press_quantization()  # 1/16 -> 1/32
		before = clip.snapshot()
		self.leave()
		self.enter()
		self.assertEqual(self.seq._quantization, 0.125)
		self.assertEqual(clip.snapshot(), before)

	def test_quantization_press_stretches_pattern(self):
		# original behaviour, kept: the pattern keeps its steps at the new step size
		clip = live_stubs.Clip(c_major_run())
		self.make(clip)
		self.enter()
		self.press_quantization()  # 1/16 -> 1/32
		self.assertEqual(clip.loop_end, 8.0)
		self.assertEqual(sorted(note[1] for note in clip.notes), [i * 0.125 for i in range(64)])
		self.assertEqual({note[2] for note in clip.notes}, {0.125})

	def test_key_change_moves_notes_into_new_key(self):
		clip = live_stubs.Clip(c_major_run())
		self.make(clip)
		self.enter()
		self.change_key(2)  # C major -> D major
		pitches = sorted(note[0] for note in clip.notes)
		self.assertTrue(all(isinstance(pitch, int) for pitch in pitches))
		self.assertEqual(pitches, sorted(note[0] + 2 for note in c_major_run()))

	def test_opening_scale_editor_without_changes_leaves_clip_untouched(self):
		clip = live_stubs.Clip(c_major_run())
		self.make(clip)
		self.enter()
		before = clip.snapshot()
		self.change_key(0)
		self.assertEqual(clip.snapshot(), before)
		self.assertEqual(clip.writes, 0)

	def test_clip_viewed_elsewhere_is_kept(self):
		clip_a = live_stubs.Clip(c_major_run())
		clip_b = live_stubs.Clip([(60, 0.0, 1.0, 100, False)])
		self.make(clip_a, clip_b)
		self.enter()
		self.leave()
		self.select_scene(1)
		self.select_scene(0)
		before = clip_a.snapshot()
		self.enter()
		self.assertEqual(clip_a.snapshot(), before)

	def test_first_edit_on_identical_clip_keeps_its_notes(self):
		clip_a = live_stubs.Clip(c_major_run())
		clip_b = live_stubs.Clip(c_major_run())  # e.g. a duplicate
		self.make(clip_a, clip_b)
		self.enter()
		self.select_scene(1)
		self.matrix.press(0, 5)  # adds a D on the first step
		self.assertEqual(len(clip_b.notes), 65)
		self.assertTrue(set(c_major_run()) <= set(clip_b.notes))

	def test_new_notes_last_one_step(self):
		clip = live_stubs.Clip()
		self.make(clip)
		self.enter()
		self.matrix.press(0, 6)
		self.assertEqual(clip.notes, [(36, 0.0, 0.25, 100, False)])

	def test_mono_poly_toggle_does_not_rewrite_clip(self):
		clip = live_stubs.Clip(c_major_run())
		self.make(clip)
		self.enter()
		pitch_button = live_stubs.ButtonElement()
		self.seq.set_pitch_button(pitch_button)
		editor = self.seq._note_editor
		editor._last_notes_pitches_button_press = 0  # long after startup
		for value in (127, 0, 127, 0):  # double tap
			editor._mode_button_notes_pitches_value(value, pitch_button)
		self.assertTrue(editor._is_monophonic)
		self.assertEqual(clip.writes, 0)

	def test_clip_longer_than_128_steps_does_not_crash(self):
		clip = live_stubs.Clip([(36, 0.0, 0.25, 100, False), (38, 50.0, 0.25, 100, False)], loop_end=64.0)
		self.make(clip)
		self.enter()
		clip.is_playing = True
		self.song.is_playing = True
		clip.playing_position = 60.0
		self.seq._on_playing_position_changed()
		# hold pitch and press a pad: fills every step of the 16-bar loop
		pitch_button = live_stubs.ButtonElement()
		self.seq.set_pitch_button(pitch_button)
		self.seq._note_editor._mode_button_notes_pitches_value(127, pitch_button)
		self.matrix.press(0, 6)
		self.seq._note_editor._mode_button_notes_pitches_value(0, pitch_button)

	def test_pad_on_audio_track_does_not_create_clip(self):
		self.make(None, has_midi_input=False)
		self.enter()
		self.matrix.press(0, 6)
		self.assertFalse(self.song.tracks[0].clip_slots[0].has_clip)
		self.assertIn("stepseq : select a MIDI track to create a clip", self.control_surface.messages)


if __name__ == '__main__':
	unittest.main()
