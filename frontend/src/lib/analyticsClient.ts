const BASE = import.meta.env.VITE_API_URL ?? '';

export interface AnalyticsSummary {
  total_queries: number;
  avg_response_time: number;
  avg_score: number;
  reformulation_rate: number;
  mode_distribution: Record<string, number>;
  top_sources: { source: string; count: number }[];
}

export interface ChartData {
  title: string;
  image: string | null;
}

export interface AnalyticsPayload {
  summary: AnalyticsSummary;
  charts: Record<string, ChartData>;
}

export async function fetchAnalytics(): Promise<AnalyticsPayload> {
  const res = await fetch(`${BASE}/analytics`);
  if (!res.ok) throw new Error(`Analytics request failed: ${res.status}`);
  return res.json();
}
