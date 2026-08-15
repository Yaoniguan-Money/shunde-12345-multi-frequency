import { Navigate, createBrowserRouter } from "react-router-dom";

import { App } from "./App";
import { ClusterDetailPage } from "./pages/ClusterDetailPage";
import { EventsListPage } from "./pages/EventsListPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";

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
        element: (
          <PlaceholderPage
            title="工单中心"
            description="工单中心（按工单维度浏览、检索原始工单与派生事件）将在后续阶段上线。"
          />
        ),
      },
      {
        path: "work-orders/:workOrderId",
        element: (
          <PlaceholderPage
            title="工单详情"
            description="单个工单的原始字段、AI 事件拆解与归属多频事件详情将在后续阶段上线。"
          />
        ),
      },
      {
        path: "imports",
        element: (
          <PlaceholderPage
            title="数据导入与 AI 研判"
            description="Excel 导入预览、字段映射、AI 研判任务触发与进度查看将在后续阶段上线。"
          />
        ),
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
