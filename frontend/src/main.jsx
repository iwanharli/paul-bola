import React, { lazy } from "react";
import ReactDOM from "react-dom/client";
import { createHashRouter, RouterProvider } from "react-router-dom";
import App from "./App.jsx";
import "./styles.css";

// Route pages are lazy-loaded so each becomes its own chunk -- the initial
// load no longer ships every page's code (the big pages like Bracket, which
// pulls @xyflow/react, only download when visited). App.jsx's <Suspense>
// shows a loader while a chunk fetches.
const Dashboard = lazy(() => import("./pages/Dashboard.jsx"));
const MatchList = lazy(() => import("./pages/MatchList.jsx"));
const MatchDetail = lazy(() => import("./pages/MatchDetail.jsx"));
const MatchHistory = lazy(() => import("./pages/MatchHistory.jsx"));
const HistoryDetail = lazy(() => import("./pages/HistoryDetail.jsx"));
const BracketPage = lazy(() => import("./pages/BracketPage.jsx"));
const Compare = lazy(() => import("./pages/Compare.jsx"));
const Teams = lazy(() => import("./pages/Teams.jsx"));
const TeamDetail = lazy(() => import("./pages/TeamDetail.jsx"));
const Players = lazy(() => import("./pages/Players.jsx"));
const PlayerDetail = lazy(() => import("./pages/PlayerDetail.jsx"));
const ModelLab = lazy(() => import("./pages/ModelLab.jsx"));
const DataQuality = lazy(() => import("./pages/DataQuality.jsx"));
const Narratives = lazy(() => import("./pages/Narratives.jsx"));
const NarrativeDetail = lazy(() => import("./pages/NarrativeDetail.jsx"));
const Sources = lazy(() => import("./pages/Sources.jsx"));
const SourceDetail = lazy(() => import("./pages/SourceDetail.jsx"));
const DataDictionary = lazy(() => import("./pages/DataDictionary.jsx"));
const Settings = lazy(() => import("./pages/Settings.jsx"));
const Changelog = lazy(() => import("./pages/Changelog.jsx"));
const SourceGaps = lazy(() => import("./pages/SourceGaps.jsx"));

const router = createHashRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: "forecast", element: <MatchList /> },
      { path: "match/:id", element: <MatchDetail /> },
      { path: "forecast/match/:id", element: <MatchDetail /> },
      { path: "history", element: <MatchHistory /> },
      { path: "history/:matchId", element: <HistoryDetail /> },
      { path: "bracket", element: <BracketPage /> },
      { path: "compare", element: <Compare /> },
      { path: "teams", element: <Teams /> },
      { path: "teams/:teamId", element: <TeamDetail /> },
      { path: "players", element: <Players /> },
      { path: "players/:playerId", element: <PlayerDetail /> },
      { path: "model-lab", element: <ModelLab /> },
      { path: "data-quality", element: <DataQuality /> },
      { path: "narratives", element: <Narratives /> },
      { path: "narratives/:matchId", element: <NarrativeDetail /> },
      { path: "sources", element: <Sources /> },
      { path: "sources/:source", element: <SourceDetail /> },
      { path: "data-dictionary", element: <DataDictionary /> },
      { path: "settings", element: <Settings /> },
      { path: "changelog", element: <Changelog /> },
      { path: "source-gaps", element: <SourceGaps /> },
    ],
  },
]);

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
);
