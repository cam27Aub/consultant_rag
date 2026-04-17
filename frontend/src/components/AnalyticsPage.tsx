import { useEffect, useState } from 'react';
import { BarChart2, Clock, Database, RefreshCw, TrendingUp } from 'lucide-react';
import { fetchAnalytics } from '../lib/analyticsClient';
import type { AnalyticsPayload } from '../lib/analyticsClient';
import { Menu } from 'lucide-react';

interface AnalyticsPageProps {
  onToggleSidebar: () => void;
}

function KpiCard({
  label,
  value,
  sub,
  icon: Icon,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  icon: React.ElementType;
  accent: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-sparc-border p-5 flex items-start gap-4 shadow-sm">
      <div
        className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
        style={{ background: accent + '18' }}
      >
        <Icon className="w-5 h-5" style={{ color: accent }} />
      </div>
      <div>
        <p className="text-xs text-sparc-muted font-medium mb-0.5">{label}</p>
        <p className="text-2xl font-bold text-navy leading-none">{value}</p>
        {sub && <p className="text-xs text-sparc-muted mt-1">{sub}</p>}
      </div>
    </div>
  );
}

function ChartCard({ title, image }: { title: string; image: string | null }) {
  return (
    <div className="bg-white rounded-xl border border-sparc-border p-4 shadow-sm">
      <h3 className="text-sm font-semibold text-navy mb-3">{title}</h3>
      {image ? (
        <img
          src={`data:image/png;base64,${image}`}
          alt={title}
          className="w-full rounded-lg"
        />
      ) : (
        <div className="h-48 flex items-center justify-center text-sparc-muted text-sm">
          No data available
        </div>
      )}
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
      const result = await fetchAnalytics();
      setData(result);
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
          <button
            onClick={onToggleSidebar}
            className="lg:hidden p-1.5 rounded-lg hover:bg-gray-100"
          >
            <Menu className="w-5 h-5 text-sparc-text" />
          </button>
          <div>
            <h2 className="text-sm font-semibold text-navy">RAG Analytics</h2>
            <p className="text-xs text-sparc-muted">Query log performance dashboard</p>
          </div>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-navy border border-navy/20 rounded-lg hover:bg-navy/5 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-5">
        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 mb-5">
            {error}
          </div>
        )}

        {/* Loading skeleton */}
        {loading && !data && (
          <div className="space-y-5">
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="bg-white rounded-xl border border-sparc-border p-5 h-24 animate-pulse" />
              ))}
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="bg-white rounded-xl border border-sparc-border p-4 h-72 animate-pulse" />
              ))}
            </div>
          </div>
        )}

        {/* Content */}
        {!loading && s && (
          <div className="space-y-5 max-w-6xl mx-auto">
            {/* KPI Cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <KpiCard
                label="Total Queries"
                value={s.total_queries.toLocaleString()}
                sub="across all RAG modes"
                icon={Database}
                accent="#1F3564"
              />
              <KpiCard
                label="Avg Response Time"
                value={`${s.avg_response_time}s`}
                sub="per query"
                icon={Clock}
                accent="#2E74B5"
              />
              <KpiCard
                label="Avg Similarity Score"
                value={s.avg_score.toFixed(3)}
                sub="chunk retrieval quality"
                icon={BarChart2}
                accent="#C8A951"
              />
              <KpiCard
                label="Reformulation Rate"
                value={`${s.reformulation_rate}%`}
                sub="follow-up queries rewritten"
                icon={TrendingUp}
                accent="#059669"
              />
            </div>

            {/* Charts — 2×2 grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <ChartCard
                title={charts.mode_distribution?.title ?? 'Query Mode Distribution'}
                image={charts.mode_distribution?.image ?? null}
              />
              <ChartCard
                title={charts.response_time_trend?.title ?? 'Response Time Trend'}
                image={charts.response_time_trend?.image ?? null}
              />
              <ChartCard
                title={charts.score_by_mode?.title ?? 'Performance by RAG Mode'}
                image={charts.score_by_mode?.image ?? null}
              />
              <ChartCard
                title={charts.top_sources?.title ?? 'Most Queried Source Documents'}
                image={charts.top_sources?.image ?? null}
              />
            </div>

            {/* Top Sources Table */}
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
                          <tr
                            key={src.source}
                            className={i % 2 === 0 ? 'bg-white' : 'bg-sparc-bg'}
                          >
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
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && s?.total_queries === 0 && (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <BarChart2 className="w-12 h-12 text-sparc-muted mb-3 opacity-40" />
            <p className="text-sparc-muted text-sm">No query data yet.</p>
            <p className="text-sparc-muted text-xs mt-1">Run some queries through the RAG system to see analytics here.</p>
          </div>
        )}
      </div>
    </div>
  );
}
