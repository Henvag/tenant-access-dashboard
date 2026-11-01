# Landing film

The 25-second film on the landing page, made with [HyperFrames](https://github.com/heygen-com/hyperframes)
(HTML rendered to video by seeking a GSAP timeline, so every render is the same). Everything in it is
the real product: screens are captured from the read-only demo company, nothing is drawn.

| File | What it is |
| --- | --- |
| `STORYLINES.md` | The three films considered and why "Someone leaves" was built |
| `SPEC.md` | Every size, colour, ease and shot timing as a number |
| `REVIEW.md` | What was checked, the weakest shot, warnings kept on purpose |
| `index.html` | Root composition: the demo scene, then the end card |
| `compositions/demo.html` | The app window, camera, cursor and the four lines |
| `compositions/endcard.html` | Mark, wordmark, "Explore the live demo" |
| `scripts/capture.mjs` | Takes the seven screens from a local backend |
| `scripts/setup.sh` | Fetches GSAP and the Schibsted Grotesk font into `assets/` |

## Remake it after a UI change

1. Run the backend locally against a database role without `BYPASSRLS`, with the built frontend in
   `backend/app/static` (the same setup `scripts/capture-demo.mjs` needs).
2. From `film/`:

   ```sh
   sh scripts/setup.sh
   BASE=http://localhost:8000 FILM_DB_URL=postgresql://postgres@localhost:5432/access_dashboard \
     node scripts/capture.mjs
   npx hyperframes@0.8.225 check        # no errors; the two warnings in REVIEW.md are expected
   npx hyperframes@0.8.225 snapshot --at 2,5.3,10.3,12.9,18.9,24.5
   npx hyperframes@0.8.225 render -o renders/tenant-access-film.mp4
   ```

   The capture script refuses to run unless both URLs are on localhost, because it edits the
   database for a moment (see the comment at its top).
3. If a layout moved, update the measured points at the top of the script in
   `compositions/demo.html` (camera regions, cursor points, audit scroll) and snapshot again.
4. Encode the web copy and poster, then rebuild the frontend:

   ```sh
   ffmpeg -i renders/tenant-access-film.mp4 -c:v libx264 -preset slow -crf 26 -pix_fmt yuv420p \
     -movflags +faststart -an ../frontend/src/assets/film/tenant-access.mp4
   ffmpeg -ss 0.9 -i renders/tenant-access-film.mp4 -frames:v 1 poster.png
   # save poster.png as ../frontend/src/assets/film/poster.webp (quality ~82)
   ```

`assets/` and `renders/` are not committed.
