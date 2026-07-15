import { useEffect, useRef, useState } from "react";
import BracketFlow from "../BracketFlow.jsx";
import { usePredictions } from "../data.js";
import { FullPageLoader, Pill, StatTile } from "../components.jsx";

export default function BracketPage() {
  const { data, error } = usePredictions();
  const frameRef = useRef(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    const syncFullscreen = () => {
      setIsFullscreen(Boolean(document.fullscreenElement));
    };
    document.addEventListener("fullscreenchange", syncFullscreen);
    return () => document.removeEventListener("fullscreenchange", syncFullscreen);
  }, []);

  if (error) return <div className="state">Gagal memuat bracket.</div>;
  if (!data) return <FullPageLoader text="Memuat bracket turnamen" />;

  const matches = data.bracket?.matches || [];
  const finished = matches.filter((match) => match.status === "finished").length;
  const upcoming = matches.length - finished;

  async function toggleFullscreen() {
    if (!frameRef.current) return;
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
      } else if (isFullscreen) {
        setIsFullscreen(false);
      } else {
        await frameRef.current.requestFullscreen();
      }
    } catch {
      setIsFullscreen((value) => !value);
    }
  }

  return (
    <>
      <div className="page-hero history-hero">
        <div>
          <Pill tone="live">Knockout map</Pill>
          <h1>Bracket turnamen</h1>
          <p className="page-sub">
            Peta knockout dari Round of 32 sampai final. Geser kanvas untuk melihat
            seluruh jalur pertandingan, atau buka fullscreen untuk layar yang lebih lega.
          </p>
        </div>
        <div className="hero-stats">
          <StatTile label="Matches" value={matches.length} />
          <StatTile label="Finished" value={finished} tone="home" />
          <StatTile label="Upcoming" value={upcoming} />
        </div>
      </div>

      <section ref={frameRef} className={`bracket-page-frame ${isFullscreen ? "is-fullscreen" : ""}`}>
        <div className="bracket-toolbar">
          <div>
            <span className="eyebrow">Interactive bracket</span>
            <strong>Round of 32 sampai Final</strong>
          </div>
          <button className="toolbar-button" type="button" onClick={toggleFullscreen}>
            <span aria-hidden="true">{isFullscreen ? "↙" : "⛶"}</span>
            {isFullscreen ? "Keluar fullscreen" : "Fullscreen"}
          </button>
        </div>
        <BracketFlow
          bracket={data.bracket}
          evaluation={data.history?.evaluation}
          showHeader={false}
          fullscreen={isFullscreen}
        />
      </section>
    </>
  );
}
