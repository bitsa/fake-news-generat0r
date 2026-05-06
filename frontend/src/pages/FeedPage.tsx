import { HealthStatus } from "../components/HealthStatus";
import { useHealth } from "../hooks/useHealth";

export function FeedPage() {
  const { data, isLoading, isError, error } = useHealth();

  return (
    <main className="mx-auto max-w-2xl p-6">
      <h1 className="mb-4 text-2xl font-bold">Fake News Generator</h1>
      {isLoading && <div>Loading...</div>}
      {isError && (
        <div
          role="alert"
          aria-live="assertive"
          className="rounded border border-red-300 bg-red-50 p-4 text-red-800"
        >
          Backend unreachable: {error?.message ?? "unknown error"}
        </div>
      )}
      {data && <HealthStatus health={data} />}
    </main>
  );
}
