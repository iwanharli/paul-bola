import React from "react";
import ReactDOM from "react-dom/client";
import { createHashRouter, RouterProvider } from "react-router-dom";
import App from "./App.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import MatchList from "./pages/MatchList.jsx";
import MatchDetail from "./pages/MatchDetail.jsx";
import MatchHistory from "./pages/MatchHistory.jsx";
import HistoryDetail from "./pages/HistoryDetail.jsx";
import BracketPage from "./pages/BracketPage.jsx";
import Compare from "./pages/Compare.jsx";
import Teams from "./pages/Teams.jsx";
import TeamDetail from "./pages/TeamDetail.jsx";
import Players from "./pages/Players.jsx";
import PlayerDetail from "./pages/PlayerDetail.jsx";
import ModelLab from "./pages/ModelLab.jsx";
import DataQuality from "./pages/DataQuality.jsx";
import Narratives from "./pages/Narratives.jsx";
import NarrativeDetail from "./pages/NarrativeDetail.jsx";
import Sources from "./pages/Sources.jsx";
import SourceDetail from "./pages/SourceDetail.jsx";
import DataDictionary from "./pages/DataDictionary.jsx";
import Settings from "./pages/Settings.jsx";
import Changelog from "./pages/Changelog.jsx";
import SourceGaps from "./pages/SourceGaps.jsx";
import "./styles.css";

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
