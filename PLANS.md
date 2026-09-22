# Plans

Work that's planned but not started, and the decisions it's waiting on. Done work is tracked in [CHANGELOG.md](CHANGELOG.md). Phase 1 (the melodic step sequencer data-loss fixes, `315b705`) is done.

Suggested order: settle decisions 1 and 2, then Phase 2, then Phase 3, then the optional scale sync.

## Decisions needed

1. **What should a Quant press do in the melodic sequencer?**
   - (a) *Recommended:* change the step size only, and leave the clip alone, like the drum sequencer.
   - (b) Current: stretch or compress the pattern so it keeps its steps. Going from 1/16 to 1/32 halves the clip.
2. **Held-button combos in the melodic sequencer.** They're inherited from the drum sequencer through shared flags, and none of them are in the manual. Keep, trim or remove each:
   - Hold Velocity and select a loop range: deletes the notes in it.
   - Hold Pitch and select a loop range: extends the clip, copying its content.
   - Hold Pitch and press a pad: fills every step of the loop with that note.
   - Double-tap a page pad: sets the loop to that one page, shortening the clip.
   - Side effect: holding Pitch can also implicitly arm the track and switch the MIDI feedback channel, because the drum sequencer's "velocity shift" flag gets set.
3. **Live 12 scale sync (optional feature):** include it? If yes, should a key or scale change made in Live move the melody into the new key, like a scale edit on the Launchpad does, or only change which notes the rows show?
4. **Phase 2 scope:** melodic sequencer only, or also move the drum sequencer and the loop-selector range actions onto the new note API? They also rewrite whole clips and reset Chance and velocity range.
5. **Live version:** make Phase 2 require Live 11 or later and drop the old note API path? Recommended: yes, since the target is 12.4.
6. **Old branch `melodic-step-sequencer-length-bug`:** delete once `melodic-step-sequencer-fixes` is merged? It fixes note length differently and conflicts with `315b705`.

## Phase 2: non-destructive edits (melodic sequencer)

Goal: an edit changes only the notes it touches. Everything else in the clip is left exactly as it was.

Today, every edit selects all notes and calls `replace_selected_notes` with the whole clip, rebuilt from the sequencer's grid (7 scale rows × 128 steps, one octave, velocity and length per step). As a result, the first edit removes or moves:

- notes that aren't on the rows
- muted notes
- off-grid timing
- a second octave on the same step
- notes past step 128

It also resets Chance, velocity range, release velocity and MPE.

### Design

- **Read notes** with `clip.get_notes_extended(...)`. It returns note objects that carry a `note_id` and the extended properties. This replaces `select_all_notes` / `get_selected_notes` / `deselect_all_notes`, which also clobber your note selection in Live's clip editor on every change.
- **Ownership:** while reading notes into the grid (`_parse_notes`), record which notes the grid owns, by `note_id` per step and row. A note is owned if it's unmuted, starts inside a step below 128, and its pitch is one of the 7 rows at that step's octave. The script never touches notes it doesn't own.
- **Writes, by page:**
  - *Pitch:* toggling a cell adds a note (`add_new_notes` with `MidiNoteSpecification`) or removes the owned note (`remove_notes_by_id`). In mono mode, adding also removes the other owned notes on that step.
  - *Octave, velocity, length:* modify the step's owned notes in place with `apply_note_modifications`: pitch ±12, velocity or duration. This keeps start times, ids and extended properties.
  - *Held-button range edits and Randomise:* the same operations over `_edit_range()`.
  - *Key or scale change:* re-pitch the owned notes to the new rows with `apply_note_modifications`.
  - *Quant press:* if decision 1 keeps stretching, scale the start and duration of every note in the clip, owned or not. If it doesn't, there are no writes at all.
- **No writes from listeners:** writes only happen from button handlers. Writing from inside a Live listener raises "Changes cannot be triggered by notifications". The `notes` listener re-reads the notes into the grid afterwards and must not write.
- If decision 4 says yes: move `LoopSelectorComponent._delete_notes_in_range` / `_mute_notes_in_range` / `_copy_notes_in_range` and the drum `NoteEditorComponent` (`_matrix_value_message`, `mute_lane`) onto the same API. `clip.duplicate_region` may suit the copy.

### Tests

- Extend `tests/live_stubs.py`: give `Clip` the extended API, with note objects that carry `note_id` and `probability`.
- New tests: out-of-scale, muted, off-grid, beyond-step-128 and second-octave notes survive a pad edit, a key change and Randomise. Chance survives a velocity edit.

### Verify in Live 12.4

- The exact keyword arguments of `MidiNoteSpecification` and `get_notes_extended`.
- Whether `note_id`s stay stable after `apply_note_modifications`.
- That undo still works, with one undo step per edit.

## Phase 3: Python 3.11 and cleanup

- `value is 0` / `is not 0` → `==` / `!=`: 23 instances in `StepSequencerComponent.py`, `StepSequencerComponent2.py`, `NoteEditorComponent.py`, `TrackControllerComponent.py`, `DeviceComponent.py` and `SpecialSessionComponent.py`. Live 12 logs a SyntaxWarning for each at every load.
- `MelodicNoteEditorComponent.__init__`: remove the unused `side_buttons` block, which would raise `NameError` if reached. Initialise `_is_notes_octaves_shifted` and `_is_notes_velocities_shifted`.
- `_scale_selector` → `_scale_component` in `StepSequencerComponent.set_osd` / `_update_OSD` and `StepSequencerComponent2._update_OSD`. Only matters if an on-screen display is ever attached.
- The `"DefaultButton.Disaled"` typo in `StepSequencerComponent2._update_mode_button`.
- `ScaleComponent.set_matrix`: it never removes its listener, because `self._matrix` is overwritten before the check. It also calls `matrix.reset()`, blanking every LED, on each call.
- Separate the melodic sequencer's held-button flags from the drum sequencer's, following decision 2. Pitch-press sets `_is_mute_shifted` / `_is_velocity_shifted` on the note editor, which `NoteSelectorComponent` and `LoopSelectorComponent` read as drum-sequencer shifts. Velocity-press sets the sequencer's `_is_mute_shifted`.
- Small bugs:
  - `TrackControllerComponent.set_enabled` tests `self.is_enabled` without calling it.
  - `LoopSelectorComponent` mixes `last_button_time` and `_last_button_time`.
  - `StepSequencerComponent.set_left_button` / `set_right_button` call methods `LoopSelectorComponent` doesn't have.
- **Verify:** the drum `NoteEditorComponent` uses the skin colour `StepSequencer.NoteEditor.Velocity4`, which `SkinMK2.py` doesn't define (only `Velocity0`–`Velocity3`). It likely raises an error for 127-velocity notes and for the fifth velocity setting.
- `DeviceComponent.set_device` raises `TypeError` when the selected track has no device: `_number_of_parameter_banks()` returns `None`. About 1,100 times in one Live 12.3.2 log.

## Optional: follow Live 12's global scale

- On enable, and through listeners, read `song.root_note` (0–11) and `song.scale_name` (plus `scale_intervals`), and set the scale editor's key and scale from them. When the scale is edited on the Launchpad, write back to `song.root_note` / `song.scale_name`. Ableton's own Move and Push scripts use these properties in 12.4.
- The scale names here (`MUSICAL_MODES` in `ScaleComponent.py`) don't all match Live's. Build a mapping and check it against 12.4's scale list.
- Make it a setting in `Settings.py`. It would replace the experimental clip-name setting `STEPSEQ__SAVE_SCALE`, since the scale is then saved with the set.
- See decision 3 on whether a scale change made in Live moves the melody.
