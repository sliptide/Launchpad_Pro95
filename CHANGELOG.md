# Changelog

Changes made in this fork ([sliptide/Launchpad_Pro95](https://github.com/sliptide/Launchpad_Pro95)) of [hdavid/Launchpad_Pro95](https://github.com/hdavid/Launchpad_Pro95) to get the scripts fully working in Ableton Live 12.4 (Python 3.11) with a Novation Launchpad Pro. Upstream's own change log is in `web/index.html`.

Keeping this up to date: add every change under **Unreleased** with its commit, and move items from **Known issues** to **Fixed** as they're done.

## Installing

Quit Live, then copy the script into Live, leaving out the files that only belong in the repo:

```bash
rsync -av --exclude .git --exclude tests --exclude web --exclude .claude --exclude __pycache__ --exclude .DS_Store --exclude .gitignore "/Volumes/Storage/Dev/Claude/Ableton Launchpad_Pro95-master/" "/Applications/Ableton Live 12 Suite.app/Contents/App-Resources/MIDI Remote Scripts/Launchpad_Pro95/"
```

Then start Live. Live updates can overwrite the app bundle, so re-copy after updating Live.

## Tests

```bash
python3 tests/test_melodic_step_sequencer.py
```

Runs the step sequencer code outside of Live, against stand-ins for Live and `_Framework` (`tests/live_stubs.py`). The tests don't cover LEDs or the hardware, so also check changes on the Launchpad.

## Unreleased (branch `melodic-step-sequencer-fixes`)

### Fixed

Melodic step sequencer, all in `315b705`. Before this, the sequencer rewrote the whole clip from its internal grid on every change, and these bugs fed it a wrong or empty grid:

| Symptom | Cause | Test |
|---|---|---|
| Entering the melodic sequencer for the first time collapsed the selected clip to a single 1/16 step | The note editor started with a 16-beat step size, and assigning the Quant button "rescaled" the clip from it | `test_entering_leaves_clip_untouched` |
| Leaving and re-entering with a quantisation other than 1/16 stretched or shortened the clip | Quantisation reset to 1/16 every time the mode's buttons were reassigned | `test_reentering_keeps_quantization_and_clip` |
| Changing key gave wrong notes, which then dropped off the grid and were wiped by the next edit | Python 3 `/` produced fractional pitches in `_scale_updated` | `test_key_change_moves_notes_into_new_key` |
| Notes were written with zero length | `int(quantization / 4.0)` is always 0 | `test_new_notes_last_one_step` |
| The first scale edit scrambled the melody, and G/A/B notes were dropped on entry | The rows started as chromatic C–F# instead of the scale editor's C major | `test_opening_scale_editor_without_changes_leaves_clip_untouched` |
| Viewing another clip from another mode, then coming back, erased the clip; the first edit on a duplicated clip erased its other notes | Changing clip reset the grid, but notes weren't reloaded when they looked unchanged | `test_clip_viewed_elsewhere_is_kept`, `test_first_edit_on_identical_clip_keeps_its_notes` |
| Double-tapping Pitch (mono/poly) rewrote the clip | Unneeded clip write | `test_mono_poly_toggle_does_not_rewrite_clip` |
| Clips longer than 128 steps (8 bars at 1/16) raised `IndexError` | No bounds checks | `test_clip_longer_than_128_steps_does_not_crash` |
| 8- and 10-note scales wrote notes into the next step | `max(7, …)` instead of `min(7, …)` in `_parse_notes` | none |
| Pressing a pad on an audio track raised "MIDI clips can only be created on MIDI tracks" | No track type check before creating a clip | `test_pad_on_audio_track_does_not_create_clip` |

### Changed

- Both step sequencers now remember their quantisation between visits. Before, they reset to 1/16 every time you entered them.
- Pressing a pad on an audio track shows "stepseq : select a MIDI track to create a clip".

## Known issues

- **Editing still rewrites the whole clip (melodic sequencer).** The first edit removes or moves notes that aren't on the current scale rows, muted notes, off-grid timing, a second octave on the same step, and notes past step 128. It also resets Chance and velocity-range settings. Planned fix: Phase 2.
- **Quant press stretches the pattern (melodic sequencer).** Going from 1/16 to 1/32 halves the clip. This is the original behaviour and was kept. Open decision: change the step size only and leave the clip alone, like the drum sequencer.
- **Hidden held-button combos (melodic sequencer)**, inherited from the drum sequencer through shared flags. Open decision: keep, trim or remove.
  - Hold Velocity and select a loop range: deletes the notes in it.
  - Hold Pitch and select a range: extends the clip.
  - Hold Pitch and press a pad: fills the whole loop with that note.
  - Double-tap a page pad: sets the loop to that page, shortening the clip.
- **Python 3.11 SyntaxWarnings** (`value is 0`, `is not 0`) are logged at every load.
- **Broken or dead code:**
  - an unused `side_buttons` block in `MelodicNoteEditorComponent.__init__`
  - `_scale_selector` should be `_scale_component`
  - the `"DefaultButton.Disaled"` typo
  - two uninitialised shift flags
  - `ScaleComponent.set_matrix` never removes its listener and blanks every LED on each call
- **`DeviceComponent.py:182` raises `TypeError`** whenever the selected track has no device (about 1,100 times in one Live 12.3.2 log).
- **The branch `melodic-step-sequencer-length-bug`** (Sept 2024) fixes note length differently (default note 4 steps long) and conflicts with `315b705`. Delete it once this branch is merged.

## Planned

Details, and the decisions these are waiting on, are in [PLANS.md](PLANS.md).

- **Phase 2:** edit only the notes a change touches, using Live 11/12's note API (`get_notes_extended`, `add_new_notes`, `apply_note_modifications`, `remove_notes_by_id`). Notes the grid doesn't own are left alone, and Chance, velocity range, release velocity and MPE are kept.
- **Phase 3:** Python 3.11 and dead-code cleanup, and separating the melodic sequencer's held-button combos from the drum sequencer's.
- **Optional:** follow Live 12's global key and scale (`song.root_note`, `song.scale_name`), so the scale is saved with the set.
