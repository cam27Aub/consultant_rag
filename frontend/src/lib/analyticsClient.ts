const BASE = import.meta.env.VITE_API_URL ?? '';

export interface ModeQuality {
  faithfulness: number | null;
  answer_relevancy: number | null;
  context_precision: number | null;
  count: number;
}

export interface AnalyticsSummary {
  total_queries: number;
  avg_response_time: number;
  mode_distribution: Record<string, number>;
  top_sources: { source: string; count: number }[];
  // RAGAS generation quality (global averages)
  faithfulness: number | null;
  answer_relevancy: number | null;
  context_precision: number | null;
  // Per-mode quality breakdown
  per_mode_quality: Record<string, ModeQuality>;
}

export interface ChartData {
  title: string;
  image: string | null;
}

export interface AnalyticsPayload {
  summary: AnalyticsSummary;
  charts: Record<string, ChartData>;
}

export async function fetchAnalytics(bustCache = false): Promise<AnalyticsPayload> {
  const url = bustCache ? `${BASE}/analytics?refresh=true` : `${BASE}/analytics`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Analytics request failed: ${res.status}`);
  return res.json();
}
