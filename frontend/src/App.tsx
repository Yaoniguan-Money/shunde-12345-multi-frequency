import { useQuery } from "@tanstack/react-query";

import { fetchLiveness } from "./api/health";
import "./styles.css";

export function App() {
  const health = useQuery({
    queryKey: ["backend-liveness"],
    queryFn: ({ signal }) => fetchLiveness(signal),
    retry: false,
  });

  const backendState = health.isPending
    ? "连接中"
    : health.isSuccess
      ? "后端在线"
      : "后端未连接";

  return (
    <main>
      <p className="eyebrow">PHASE 1 · REPOSITORY HARDENING</p>
      <h1>顺德 12345 多频工单智能研判</h1>
      <p className="description">
        当前仅提供工程骨架与真实健康检查。导入、实体归一和同事件研判将在后续阶段实现。
      </p>
      <dl>
        <div>
          <dt>前端</dt>
          <dd>已启动</dd>
        </div>
        <div>
          <dt>后端</dt>
          <dd>{backendState}</dd>
        </div>
      </dl>
    </main>
  );
}

