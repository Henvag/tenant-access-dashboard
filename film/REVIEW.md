# Review

## Creative calls

- Built storyline A, "Someone leaves" (`STORYLINES.md`): one owner, one person switched off, one
  refusal in the log. B (refusal first, endless zoom) and C (two companies side by side) were not built.
- One continuous take inside one window. The camera pushes to 1.76 to 1.84x so 14 px UI text lands at
  25 to 26 px on a 1080p frame.
- The left column carries one line per beat, each entering differently (per-word blur, grey to ink,
  whole-line blur). "refusal" is the only coloured word, in the product's danger red.
- Jonas Lie is disabled in the seed data. The capture clears `disabled_at` in the local database for
  two screenshots and restores it, so the active row, the open menu with "Disable" and the disabled row
  are all real UI states.
- The end card is entered through an object: the sidebar's brand mark lifts out and lands centred.

## Measured

- `hyperframes check`: no errors. Contrast 22 of 22 passed.
- Frames looked at: the review sheets, a QA set at 0.1, 2, 3.7, 5.3, 7.4, 10.3, 11.8, 12.35, 12.9,
  14.2, 17.5, 18.9, 20.9, 21.25 and 24.5 s, and 12 frames pulled from the rendered MP4.
- Fixed after review: the Apps heading was clipped (camera moved up 15 px), "Account disabled" touched
  the window edge (audit push 1.8 to 1.76), the cursor covered the refusal text (now points at the
  Failed sign-in pill), and screen swaps ghosted for 4 frames (now 2).

## Not checked

- No sound, on purpose; nobody listened to anything.
- At phone width (360 px) the lines are about 9 px and not readable. The film is a desktop piece; the
  landing page keeps the live demo button right under it.

## Weakest shot

The apps beat (3.7 to 9.0 s) is the camera over a still screen with a row spotlight. With more time it
would change a real policy (open Outline's menu, switch "Assigned people" to "Everyone") the way the
people beat performs a real disable.

## Warnings kept

- `film_silent`: the film autoplays muted on the landing page.
- `timeline_track_too_dense`: the four lines sit in the demo scene so their timing stays next to the
  clicks they describe.
