import { useEffect, useRef, useState } from "react";
import { useLang } from "./i18n";
import { IconPause, IconPlay } from "./Icons";
import film from "./assets/film/tenant-access.mp4";
import poster from "./assets/film/poster.webp";

/**
 * The 25-second product film, made from the demo company with HyperFrames (see film/README.md).
 * Muted and looping; it plays only while on screen and waits for a click when the visitor
 * prefers reduced motion.
 */
export default function ProductFilm() {
  const { t } = useLang();
  const videoRef = useRef<HTMLVideoElement>(null);
  const heldByVisitor = useRef(false);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    const video = videoRef.current;
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
  }, []);

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
        ref={videoRef}
        src={film}
        poster={poster}
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
