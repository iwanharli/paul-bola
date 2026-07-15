import { useMemo, useState } from "react";
import { FullPageLoader, Pill, StatTile } from "../components.jsx";
import { pct0, usePredictions } from "../data.js";

const MODELS = ["gpt-5.6-terra", "gpt-5.2-pro", "gpt-5.2", "gpt-4.1"];

export default function Settings() {
  const { data, error } = usePredictions();
  const [marketWeight, setMarketWeight] = useState(75);
  const [timeDecay, setTimeDecay] = useState(68);
  const [narrativeDepth, setNarrativeDepth] = useState("sharp");
  const [targetModel, setTargetModel] = useState(MODELS[0]);
  const [utc7, setUtc7] = useState(true);
  const [showRisk, setShowRisk] = useState(true);

  if (error) return <div className="state">Gagal memuat settings.</div>;
  if (!data) return <FullPageLoader text="Memuat settings" />;

  const preview = useMemo(() => {
    const modelWeight = 100 - marketWeight;
    return [
      ["Model weight", `${modelWeight}%`],
      ["Market weight", `${marketWeight}%`],
      ["Time decay", `${timeDecay}%`],
      ["Narrative depth", narrativeDepth],
      ["Target model", targetModel],
      ["Timezone", utc7 ? "UTC+7" : "Source time"],
      ["Risk notes", showRisk ? "enabled" : "disabled"],
    ];
  }, [marketWeight, narrativeDepth, showRisk, targetModel, timeDecay, utc7]);

  return (
    <>
      <div className="page-hero history-hero">
        <div>
          <Pill tone="live">Admin</Pill>
          <h1>Settings</h1>
          <p className="page-sub">
            Panel konsep untuk mengatur bobot model, preferensi narasi AI, dan
            tampilan waktu. Saat ini belum menulis ke backend.
          </p>
        </div>
        <div className="hero-stats">
          <StatTile label="Active model" value={data.model?.name || "-"} />
          <StatTile label="Best held-out" value={bestHeldout(data)} tone="home" />
          <StatTile label="Narrative model" value={targetModel} />
        </div>
      </div>

      <div className="settings-layout">
        <section className="panel settings-panel">
          <h2>Model weights</h2>
          <SettingRange label="Market blend" value={marketWeight} setValue={setMarketWeight} />
          <SettingRange label="Time decay" value={timeDecay} setValue={setTimeDecay} />
        </section>

        <section className="panel settings-panel">
          <h2>Narrative AI</h2>
          <label className="setting-field">
            <span>Target model</span>
            <select value={targetModel} onChange={(event) => setTargetModel(event.target.value)}>
              {MODELS.map((model) => <option key={model}>{model}</option>)}
            </select>
          </label>
          <label className="setting-field">
            <span>Depth</span>
            <select value={narrativeDepth} onChange={(event) => setNarrativeDepth(event.target.value)}>
              <option value="sharp">Sharp match memo</option>
              <option value="short">Short preview</option>
              <option value="broadcast">Broadcast style</option>
            </select>
          </label>
          <button className={`filter-toggle ${showRisk ? "active" : ""}`} onClick={() => setShowRisk((value) => !value)}>
            Risk notes
          </button>
          <button className={`filter-toggle ${utc7 ? "active" : ""}`} onClick={() => setUtc7((value) => !value)}>
            UTC+7 time
          </button>
        </section>

        <section className="panel settings-preview">
          <h2>Active config preview</h2>
          <div className="settings-preview-list">
            {preview.map(([label, value]) => (
              <div key={label}>
                <span>{label}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}

function SettingRange({ label, value, setValue }) {
  return (
    <label className="setting-range">
      <span>{label}</span>
      <input
        min="0"
        max="100"
        type="range"
        value={value}
        onChange={(event) => setValue(Number(event.target.value))}
      />
      <strong>{value}%</strong>
    </label>
  );
}

function bestHeldout(data) {
  const rows = data.model?.heldout || [];
  if (!rows.length) return "-";
  const best = [...rows].sort((a, b) => (b.acc || 0) - (a.acc || 0))[0];
  return `${pct0(best.acc || 0)} acc`;
}
