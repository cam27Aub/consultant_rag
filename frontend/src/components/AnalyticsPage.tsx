import { useEffect, useState } from 'react';
import { BarChart2, Clock, Database, RefreshCw, TrendingUp, CheckCircle, AlertTriangle, Target, Zap } from 'lucide-react';
import { Menu } from 'lucide-react';
import { fetchAnalytics } from '../lib/analyticsClient';
import type { AnalyticsPayload } from '../lib/analyticsClient';

interface AnalyticsPageProps {
  onToggleSidebar: () => void;
}

function KpiCard({
  label, value, sub, icon: Icon, accent, note,
}: {
  label: string; value: string; sub?: string; icon: React.ElementType; accent: string; note?: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-sparc-border p-5 flex items-start gap-4 shadow-sm">
      <div className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
        style={{ background: accent + '18' }}>
        <Icon className="w-5 h-5" style={{ color: accent }} />
      </div>
      <div className="min-w-0">
        <p className="text-xs text-sparc-muted font-medium mb-0.5">{label}</p>
        <p className="text-2xl font-bold text-navy leading-none">{value}</p>
        {sub && <p className="text-xs text-sparc-muted mt-1">{sub}</p>}
        {note && <p className="text-[10px] text-orange-500 mt-0.5 italic">{note}</p>}
      </div>
    </div>
  );
}

function MetricBadge({ label, value, color }: { label: string; value: number | null; color: string }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-sparc-border last:border-0">
      <span className="text-sm text-sparc-text">{label}</span>
      {value !== null && value !== undefined ? (
        <div className="flex items-center gap-2">
          <div className="w-24 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div className="h-full rounded-full" style={{ width: `${Math.min(value * 100, 100)}%`, background: color }} />
          </div>
          <span className="text-sm font-semibold w-12 text-right" style={{ color }}>{value.toFixed(3)}</span>
        </div>
      ) : (
        <span className="text-xs text-sparc-muted italic">no data</span>
      )}
    </div>
  );
}

function ChartCard({ title, image }: { title: string; image: string | null }) {
  return (
    <div className="bg-white rounded-xl border border-sparc-border p-4 shadow-sm">
      <h3 className="text-sm font-semibold text-navy mb-3">{title}</h3>
      {image ? (
        <img src={`data:image/png;base64,${image}`} alt={title} className="w-full rounded-lg" />
      ) : (
        <div className="h-48 flex items-center justify-center text-sparc-muted text-sm bg-sparc-bg rounded-lg">
          Chart unavailable
        </div>
      )}
    </div>
  );
}

function RetrievalTable({ retrieval }: { retrieval: Record<string, Record<string, number | null>> }) {
  const systems = Object.keys(retrieval).filter(s => s !== 'overall');
  const metrics = ['Recall@1', 'Recall@3', 'Recall@5', 'Precision@1', 'Precision@3', 'Precision@5', 'MRR'];

  if (!systems.length) return null;

  return (
    <div className="bg-white rounded-xl border border-sparc-border shadow-sm overflow-hidden">
      <div className="px-5 py-3 border-b border-sparc-border">
        <h3 className="text-sm font-semibold text-navy">Retrieval Metrics by System</h3>
        <p className="text-xs text-sparc-muted mt-0.5">From evaluation comparison runs</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-navy text-white">
              <th className="text-left px-5 py-2.5 font-semibold text-xs">Metric</th>
              {systems.map(s => (
                <th key={s} className="text-center px-4 py-2.5 font-semibold text-xs capitalize">{s}</th>
              ))}
              {retrieval.overall && (
                <th className="text-center px-4 py-2.5 font-semibold text-xs text-yellow-300">Overall</th>
              )}
            </tr>
          </thead>
          <tbody>
            {metrics.map((m, i) => (
              <tr key={m} className={i % 2 === 0 ? 'bg-white' : 'bg-sparc-bg'}>
                <td className="px-5 py-2.5 font-medium text-sparc-text text-xs">{m}</td>
                {systems.map(s => {
                  const v = retrieval[s]?.[m];
                  return (
                    <td key={s} className="px-4 py-2.5 text-center">
                      {v !== null && v !== undefined ? (
                        <span className="font-semibold text-navy text-xs">{v.toFixed(3)}</span>
                      ) : (
                        <span className="text-sparc-muted text-xs">—</span>
                      )}
                    </td>
                  );
                })}
                {retrieval.overall && (
                  <td className="px-4 py-2.5 text-center">
                    {retrieval.overall[m] !== null && retrieval.overall[m] !== undefined ? (
                      <span className="font-bold text-xs" style={{ color: '#C8A951' }}>
                        {retrieval.overall[m]!.toFixed(3)}
                      </span>
                    ) : <span className="text-sparc-muted text-xs">—</span>}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function AnalyticsPage({ onToggleSidebar }: AnalyticsPageProps) {
  const [data, setData] = useState<AnalyticsPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchAnalytics());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analytics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const s = data?.summary;
  const charts = data?.charts ?? {};

  return (
    <div className="flex-1 flex flex-col bg-sparc-bg overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-sparc-border bg-white shrink-0">
        <div className="flex items-center gap-3">
          <button onClick={onToggleSidebar} className="lg:hidden p-1.5 rounded-lg hover:bg-gray-100">
            <Menu className="w-5 h-5 text-sparc-text" />
          </button>
          <div>
            <h2 className="text-sm font-semibold text-navy">RAG Analytics</h2>
            <p className="text-xs text-sparc-muted">Retrieval quality · Generation quality · Usage</p>
          </div>
        </div>
        <button onClick={load} disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-navy border border-navy/20 rounded-lg hover:bg-navy/5 transition-colors disabled:opacity-50">
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-5">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 mb-5">{error}</div>
        )}

        {loading && !data && (
          <div className="space-y-5">
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="bg-white rounded-xl border border-sparc-border p-5 h-24 animate-pulse" />
              ))}
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="bg-white rounded-xl border border-sparc-border p-4 h-72 animate-pulse" />
              ))}
            </div>
          </div>
        )}

        {!loading && s && (
          <div className="space-y-6 max-w-6xl mx-auto">

            {/* ── Row 1: Operational KPIs ── */}
            <div>
              <p className="text-xs font-semibold text-sparc-muted uppercase tracking-widest mb-3">Usage & Performance</p>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <KpiCard label="Total Queries" value={s.total_queries.toLocaleString()}
                  sub="logged queries" icon={Database} accent="#1F3564" />
                <KpiCard label="Avg Response Time" value={`${s.avg_response_time}s`}
                  sub="per query" icon={Clock} accent="#2E74B5" />
                <KpiCard label="Avg Similarity Score" value={s.avg_score > 0 ? s.avg_score.toFixed(3) : '—'}
                  sub="chunk retrieval quality" icon={BarChart2} accent="#C8A951" />
                <KpiCard label="Reformulation Rate" value={`${s.reformulation_rate}%`}
                  sub="follow-ups rewritten" icon={TrendingUp} accent="#059669" />
              </div>
            </div>

            {/* ── Row 2: Generation Quality KPIs ── */}
            <div>
              <p className="text-xs font-semibold text-sparc-muted uppercase tracking-widest mb-3">Generation Quality</p>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <KpiCard label="Groundedness" value={s.groundedness !== null && s.groundedness !== undefined ? s.groundedness.toFixed(3) : '—'}
                  sub="answer supported by context" icon={CheckCircle} accent="#059669"
                  note={s.groundedness === null ? 'run evaluation to populate' : undefined} />
                <KpiCard label="Relevancy" value={s.relevancy !== null && s.relevancy !== undefined ? s.relevancy.toFixed(3) : '—'}
                  sub="Q ↔ A similarity" icon={Target} accent="#2E74B5"
                  note={s.relevancy === null ? 'run evaluation to populate' : undefined} />
                <KpiCard label="Completeness" value={s.completeness !== null && s.completeness !== undefined ? s.completeness.toFixed(3) : '—'}
                  sub="keyword coverage" icon={Zap} accent="#C8A951"
                  note={s.completeness === null ? 'run evaluation to populate' : undefined} />
                <KpiCard label="Hallucination" value={s.hallucination !== null && s.hallucination !== undefined ? s.hallucination.toFixed(3) : '—'}
                  sub="lower is better" icon={AlertTriangle} accent="#DC2626"
                  note={s.hallucination === null ? 'run evaluation to populate' : undefined} />
              </div>
            </div>

            {/* ── Quality metrics breakdown ── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <div className="bg-white rounded-xl border border-sparc-border p-5 shadow-sm">
                <h3 className="text-sm font-semibold text-navy mb-1">Generation Quality Breakdown</h3>
                <p className="text-xs text-sparc-muted mb-4">Averaged across all evaluated queries</p>
                <MetricBadge label="Groundedness" value={s.groundedness ?? null} color="#059669" />
                <MetricBadge label="Relevancy" value={s.relevancy ?? null} color="#2E74B5" />
                <MetricBadge label="Completeness" value={s.completeness ?? null} color="#C8A951" />
                <MetricBadge label="Hallucination" value={s.hallucination ?? null} color="#DC2626" />
              </div>

              <ChartCard title={charts.quality_metrics?.title ?? 'Generation Quality Metrics'}
                image={charts.quality_metrics?.image ?? null} />
            </div>

            {/* ── Charts row 1 ── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <ChartCard title={charts.mode_distribution?.title ?? 'Query Mode Distribution'}
                image={charts.mode_distribution?.image ?? null} />
              <ChartCard title={charts.response_time_trend?.title ?? 'Response Time Trend'}
                image={charts.response_time_trend?.image ?? null} />
            </div>

            {/* ── Charts row 2 ── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <ChartCard title={charts.score_by_mode?.title ?? 'Performance by RAG Mode'}
                image={charts.score_by_mode?.image ?? null} />
              <ChartCard title={charts.top_sources?.title ?? 'Most Queried Source Documents'}
                image={charts.top_sources?.image ?? null} />
            </div>

            {/* ── Retrieval metrics chart (full width) ── */}
            <ChartCard title={charts.retrieval_metrics?.title ?? 'Retrieval Metrics by System'}
              image={charts.retrieval_metrics?.image ?? null} />

            {/* ── Retrieval metrics table ── */}
            {s.retrieval && Object.keys(s.retrieval).length > 0 && (
              <RetrievalTable retrieval={s.retrieval} />
            )}

            {/* ── Top Sources table ── */}
            {s.top_sources.length > 0 && (
              <div className="bg-white rounded-xl border border-sparc-border shadow-sm overflow-hidden">
                <div className="px-5 py-3 border-b border-sparc-border">
                  <h3 className="text-sm font-semibold text-navy">Source Document Breakdown</h3>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-navy text-white">
                        <th className="text-left px-5 py-2.5 font-semibold text-xs">#</th>
                        <th className="text-left px-5 py-2.5 font-semibold text-xs">Document</th>
                        <th className="text-right px-5 py-2.5 font-semibold text-xs">Times Retrieved</th>
                        <th className="text-right px-5 py-2.5 font-semibold text-xs">Share</th>
                      </tr>
                    </thead>
                    <tbody>
                      {s.top_sources.map((src, i) => {
                        const total = s.top_sources.reduce((a, b) => a + b.count, 0);
                        const pct = total > 0 ? ((src.count / total) * 100).toFixed(1) : '0';
                        return (
                          <tr key={src.source} className={i % 2 === 0 ? 'bg-white' : 'bg-sparc-bg'}>
                            <td className="px-5 py-2.5 text-sparc-muted text-xs">{i + 1}</td>
                            <td className="px-5 py-2.5 font-medium text-sparc-text">{src.source}</td>
                            <td className="px-5 py-2.5 text-right font-semibold text-navy">{src.count}</td>
                            <td className="px-5 py-2.5 text-right text-sparc-muted">{pct}%</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Empty state */}
            {s.total_queries === 0 && (
              <div className="flex flex-col items-center justify-center py-16 text-center bg-white rounded-xl border border-sparc-border">
                <BarChart2 className="w-12 h-12 text-sparc-muted mb-3 opacity-30" />
                <p className="text-sparc-text font-medium text-sm mb-1">No queries logged yet</p>
                <p className="text-sparc-muted text-xs max-w-xs">
                  Ingest your documents, run queries through the RAG system, then come back here to see analytics.
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
