const BASE = import.meta.env.VITE_API_URL ?? '';

export interface RetrievalMetrics {
  'Recall@1': number | null;
  'Recall@3': number | null;
  'Recall@5': number | null;
  'Precision@1': number | null;
  'Precision@3': number | null;
  'Precision@5': number | null;
  'MRR': number | null;
  [key: string]: number | null;
}

export interface ModeQuality {
  groundedness: number | null;
  relevancy: number | null;
  completeness: number | null;
  hallucination: number | null;
  count: number;
}

export interface AnalyticsSummary {
  total_queries: number;
  avg_response_time: number;
  avg_score: number;
  reformulation_rate: number;
  mode_distribution: Record<string, number>;
  top_sources: { source: string; count: number }[];
  // Generation quality (global averages)
  groundedness: number | null;
  relevancy: number | null;
  completeness: number | null;
  hallucination: number | null;
  // Per-mode quality breakdown
  per_mode_quality: Record<string, ModeQuality>;
  // Retrieval quality
  retrieval: Record<string, RetrievalMetrics>;
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
