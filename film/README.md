# Landing film

The 25-second film on the landing page, in English and Norwegian, made with [HyperFrames](https://github.com/heygen-com/hyperframes)
(HTML rendered to video by seeking a GSAP timeline, so every render is the same). Everything in it is
the real product: screens are captured from the read-only demo company, nothing is drawn.

| File | What it is |
| --- | --- |
| `STORYLINES.md` | The three films considered and why "Someone leaves" was built |
| `SPEC.md` | Every size, colour, ease and shot timing as a number |
| `REVIEW.md` | What was checked, the weakest shot, warnings kept on purpose |
| `index.html` | Root composition: the demo scene, then the end card; the hosts pass `lang` |
| `compositions/demo.html` | The app window, camera, cursor and the four lines, in both languages |
| `compositions/endcard.html` | Mark, wordmark, "Explore the live demo" / "Utforsk live-demoen" |
| `scripts/capture.mjs` | Takes the seven screens for one language from a local backend, with `geo.json` |
| `scripts/render.sh` | Renders one language (`en` or `no`) |
| `scripts/setup.sh` | Fetches GSAP and the Schibsted Grotesk font into `assets/` |

## Remake it after a UI change

1. Run the backend locally against a database role without `BYPASSRLS`, with the built frontend in
   `backend/app/static` (the same setup `scripts/capture-demo.mjs` needs).
2. From `film/`:

   ```sh
   sh scripts/setup.sh
   export BASE=http://localhost:8000 FILM_DB_URL=postgresql://postgres@localhost:5432/access_dashboard
   FILM_LANG=en node scripts/capture.mjs
   FILM_LANG=no node scripts/capture.mjs
   npx hyperframes@0.8.225 check        # no errors; the two warnings in REVIEW.md are expected
   npx hyperframes@0.8.225 snapshot --at 2,5.3,10.3,12.9,18.9,24.5
   sh scripts/render.sh en              # renders/tenant-access-film-en.mp4
   sh scripts/render.sh no              # renders/tenant-access-film-no.mp4
   ```

   Studio and `check` show English. To preview Norwegian, change both `{"lang":"en"}` in
   `index.html` to `{"lang":"no"}` (and back).

   The capture script refuses to run unless both URLs are on localhost, because it edits the
   database for a moment (see the comment at its top).
3. If a layout moved, compare `assets/shots/<lang>/geo.json` with the points at the top of the
   script in `compositions/demo.html` (camera regions, cursor points, audit scroll; the policy pills
   and the Failed sign-in pill have a position per language) and snapshot again.
4. Encode the web copies and posters, then rebuild the frontend. For each language:

   ```sh
   ffmpeg -i renders/tenant-access-film-en.mp4 -c:v libx264 -preset slow -crf 26 -pix_fmt yuv420p \
     -movflags +faststart -an ../frontend/src/assets/film/tenant-access-en.mp4
   ffmpeg -ss 0.9 -i renders/tenant-access-film-en.mp4 -frames:v 1 poster.png
   # save poster.png as ../frontend/src/assets/film/poster-en.webp (quality ~82)
   ```

`assets/` and `renders/` are not committed.
