import { Navigate, createBrowserRouter } from "react-router-dom";

import { App } from "./App";
import { ClusterDetailPage } from "./pages/ClusterDetailPage";
import { EventsListPage } from "./pages/EventsListPage";
import { ImportsPage } from "./pages/ImportsPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";
import { WorkOrderDetailPage } from "./pages/WorkOrderDetailPage";
import { WorkOrdersPage } from "./pages/WorkOrdersPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Navigate to="/events" replace /> },
      { path: "events", element: <EventsListPage /> },
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
      {
        path: "*",
        element: (
          <PlaceholderPage
            title="页面不存在"
            description="请求的路径不在当前路由范围内。请通过左侧导航跳转。"
          />
        ),
      },
    ],
  },
]);
