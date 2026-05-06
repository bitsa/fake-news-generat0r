import type { HealthResponse } from "../types/api";

export interface HealthStatusProps {
  health: HealthResponse;
}

export function HealthStatus({ health }: HealthStatusProps) {
  const ok = health.status === "ok";
  return (
    <div className="rounded border p-4">
      <div className="text-lg font-semibold">
        Status:{" "}
        <span role="status" aria-live="polite" className={ok ? "text-green-600" : "text-red-600"}>{health.status}</span>
      </div>
    </div>
  );
}
