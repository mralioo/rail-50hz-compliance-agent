import { Navigate, createBrowserRouter } from "react-router-dom";
import { Landing } from "./pages/Landing";
import { Dashboard } from "./pages/Dashboard";
import { CadViewer } from "./pages/CadViewer";
import { Workspace } from "./pages/Workspace";
import { JobSources } from "./pages/JobSources";
import { JobWorkflow } from "./pages/JobWorkflow";
import { JobCraftsman } from "./pages/JobCraftsman";
import { JobFindings } from "./pages/JobFindings";
import { Settings } from "./pages/Settings";
import { DebugConsole } from "./pages/DebugConsole";
import { RoadmapPage } from "./pages/RoadmapPage";
import { NotFound } from "./pages/NotFound";

export const router = createBrowserRouter([
  { path: "/", element: <Landing /> },
  { path: "/app", element: <Navigate to="/app/dashboard" replace /> },
  { path: "/app/dashboard", element: <Dashboard /> },
  { path: "/app/viewer", element: <CadViewer /> },
  { path: "/app/jobs/:jobId", element: <Navigate to="console" replace /> },
  { path: "/app/jobs/:jobId/console", element: <Workspace /> },
  { path: "/app/jobs/:jobId/sources", element: <JobSources /> },
  { path: "/app/jobs/:jobId/workflow", element: <JobWorkflow /> },
  { path: "/app/jobs/:jobId/craftsman", element: <JobCraftsman /> },
  { path: "/app/jobs/:jobId/findings", element: <JobFindings /> },
  { path: "/app/settings", element: <Settings /> },
  { path: "/app/debug", element: <DebugConsole /> },
  { path: "/app/roadmap/:slug", element: <RoadmapPage /> },
  { path: "*", element: <NotFound /> },
]);
