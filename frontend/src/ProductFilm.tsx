import { useEffect, useRef, useState } from "react";
import { useLang } from "./i18n";
import { IconPause, IconPlay } from "./Icons";
import filmEn from "./assets/film/tenant-access-en.mp4";
import filmNo from "./assets/film/tenant-access-no.mp4";
import posterEn from "./assets/film/poster-en.webp";
import posterNo from "./assets/film/poster-no.webp";

const FILMS = { en: { src: filmEn, poster: posterEn }, no: { src: filmNo, poster: posterNo } };

/**
 * The 25-second product film in the page's language, made from the demo company with HyperFrames
 * (see film/README.md).
 * Muted and looping; it plays only while on screen and waits for a click when the visitor
 * prefers reduced motion.
 */
export default function ProductFilm() {
  const { lang, t } = useLang();
  const film = FILMS[lang];
  const videoRef = useRef<HTMLVideoElement>(null);
  const heldByVisitor = useRef(false);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    const video = videoRef.current;
    // A new language mounts a fresh, paused video.
    setPlaying(false);
    if (!video) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      heldByVisitor.current = true;
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (heldByVisitor.current) return;
        if (entry.isIntersecting) video.play().catch(() => undefined);
        else video.pause();
      },
      { threshold: 0.4 },
    );
    observer.observe(video);
    return () => observer.disconnect();
    // A language switch mounts a new video element (key below), so watch that one.
  }, [lang]);

  function toggle() {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      heldByVisitor.current = false;
      video.play().catch(() => undefined);
    } else {
      heldByVisitor.current = true;
      video.pause();
    }
  }

  const label = playing ? t("film.pause") : t("film.play");

  return (
    <figure className="film">
      <video
        key={lang}
        ref={videoRef}
        src={film.src}
        poster={film.poster}
        width={1920}
        height={1080}
        muted
        loop
        playsInline
        preload="metadata"
        aria-describedby="film-summary"
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
      />
      <figcaption id="film-summary" className="sr-only">
        {t("film.summary")}
      </figcaption>
      <button type="button" className="film-toggle" onClick={toggle} aria-label={label}>
        {playing ? <IconPause width={14} height={14} /> : <IconPlay width={14} height={14} />}
        <span className="film-toggle-label">{label}</span>
      </button>
    </figure>
  );
}
