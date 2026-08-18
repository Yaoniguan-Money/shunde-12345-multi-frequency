import { createBrowserRouter } from "react-router-dom";

import { App } from "./App";
import { ClusterDetailPage } from "./pages/ClusterDetailPage";
import { DashboardPage } from "./pages/DashboardPage";
import { EventsPage } from "./pages/EventsPage";
import { ImportsPage } from "./pages/ImportsPage";
import { WorkOrderDetailPage } from "./pages/WorkOrderDetailPage";
import { WorkOrdersPage } from "./pages/WorkOrdersPage";
import { AssistantPage } from "./pages/AssistantPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "events", element: <EventsPage /> },
      { path: "events/:clusterId", element: <ClusterDetailPage /> },
      {
        path: "work-orders",
        element: <WorkOrdersPage />,
      },
      {
        path: "work-orders/:workOrderId",
        element: <WorkOrderDetailPage />,
      },
      {
        path: "imports",
        element: <ImportsPage />,
      },
      { path: "assistant", element: <AssistantPage /> },
      {
        path: "*",
        element: <DashboardPage />,
      },
    ],
  },
]);
