import type { SourceId } from "../types/api";

export interface Source {
  id: SourceId;
  name: string;
  color: string;
}

export const SOURCES: Record<SourceId, Source> = {
  NYT: { id: "NYT", name: "The New York Times", color: "var(--nyt)" },
  NPR: { id: "NPR", name: "NPR News", color: "var(--npr)" },
  Guardian: { id: "Guardian", name: "The Guardian", color: "var(--grd)" },
};
