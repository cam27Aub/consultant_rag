import { useEffect, useState, useRef } from 'react';
import { BarChart2, Clock, Database, RefreshCw, TrendingUp, CheckCircle, AlertTriangle, Target, Zap, Upload, Play, FileText, Loader2, Trash2 } from 'lucide-react';
import { Menu } from 'lucide-react';
import { fetchAnalytics } from '../lib/analyticsClient';
import type { AnalyticsPayload } from '../lib/analyticsClient';

const BASE = import.meta.env.VITE_API_URL ?? '';

interface DocFile { name: string; type: string; size_kb: number; }
type IngestStatus = 'idle' | 'running' | 'done' | 'error' | 'unknown';

function RAGManagement() {
  const [docs, setDocs] = useState<DocFile[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deletingFile, setDeletingFile] = useState<string | null>(null);
  const [ingestStatus, setIngestStatus] = useState<IngestStatus>('idle');
  const [ingestMsg, setIngestMsg] = useState('');
  const [uploadError, setUploadError] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadDocs = async () => {
    try {
      const res = await fetch(`${BASE}/documents`);
      const data = await res.json();
      setDocs(data.files ?? []);
    } catch { /* silent */ } finally {
      setLoadingDocs(false);
    }
  };

  const checkStatus = async () => {
    try {
      const res = await fetch(`${BASE}/ingest-status`);
      const data = await res.json();
      setIngestStatus(data.status as IngestStatus);
      setIngestMsg(data.message ?? '');
      if (data.status === 'done' || data.status === 'error') {
        if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
        if (data.status === 'done') loadDocs();
      }
    } catch { /* silent */ }
  };

  useEffect(() => {
    loadDocs();
    checkStatus();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    setUploadError('');
    const form = new FormData();
    Array.from(files).forEach(f => form.append('files', f));
    try {
      const res = await fetch(`${BASE}/upload-documents`, { method: 'POST', body: form });
      const data = await res.json();
      if (data.errors?.length) setUploadError(data.errors.join(' · '));
      // Check if any file failed GitHub commit
      const ghFailed = (data.saved ?? []).filter((s: { name: string; github: boolean }) => !s.github);
      if (ghFailed.length) {
        setUploadError(prev => [prev, `GitHub sync failed for: ${ghFailed.map((s: { name: string }) => s.name).join(', ')} — add GITHUB_TOKEN to Render env vars`].filter(Boolean).join(' · '));
      }
      await loadDocs();
    } catch (e) {
      setUploadError('Upload failed');
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = '';
    }
  };

  const handleDelete = async (filename: string) => {
    if (!window.confirm(`Delete "${filename}" from the RAG folder and GitHub?`)) return;
    setDeletingFile(filename);
    try {
      const res = await fetch(`${BASE}/documents/${encodeURIComponent(filename)}`, { method: 'DELETE' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setUploadError(`Delete failed: ${err.detail ?? res.statusText}`);
      } else {
        await loadDocs();
      }
    } catch {
      setUploadError('Delete request failed');
    } finally {
      setDeletingFile(null);
    }
  };

  const triggerIngest = () => {
    setIngestStatus('running');
    setIngestMsg('Starting ingestion pipeline…');

    // Fire-and-forget with a 10 s timeout — don't await so the UI never freezes.
    // Render free-tier cold starts can take 30 s; we optimistically start polling
    // and let the status file tell us what happened.
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 10_000);
    fetch(`${BASE}/ingest`, { method: 'POST', signal: ctrl.signal })
      .then(() => clearTimeout(timer))
      .catch(() => clearTimeout(timer)); // timeout / network error — polling will catch real status

    // Start polling immediately; backend writes "running" before the thread spawns
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(checkStatus, 3000);
  };

  const statusColor: Record<IngestStatus, string> = {
    idle: 'text-sparc-muted', running: 'text-blue-600',
    done: 'text-green-600', error: 'text-red-600', unknown: 'text-sparc-muted',
  };

  return (
    <div className="space-y-4">
      <p className="text-xs font-semibold text-sparc-muted uppercase tracking-widest">RAG Document Management</p>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* ── Upload panel ── */}
        <div className="bg-white rounded-xl border border-sparc-border shadow-sm p-5">
          <div className="flex items-center gap-2 mb-4">
            <Upload className="w-4 h-4 text-navy" />
            <h3 className="text-sm font-semibold text-navy">Add Files to RAG</h3>
          </div>

          <div
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={e => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files); }}
            onClick={() => fileInput.current?.click()}
            className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors mb-4
              ${dragOver ? 'border-navy bg-navy/5' : 'border-sparc-border hover:border-navy/40 hover:bg-sparc-bg'}`}
          >
            <Upload className="w-8 h-8 mx-auto mb-2 text-sparc-muted" />
            <p className="text-sm font-medium text-sparc-text">Drop files here or click to browse</p>
            <p className="text-xs text-sparc-muted mt-1">Supports PDF, PPTX, DOCX</p>
            <input ref={fileInput} type="file" multiple accept=".pdf,.pptx,.docx"
              className="hidden" onChange={e => handleFiles(e.target.files)} />
          </div>

          {uploading && (
            <div className="flex items-center gap-2 text-sm text-blue-600 mb-3">
              <Loader2 className="w-4 h-4 animate-spin" /> Uploading…
            </div>
          )}
          {uploadError && <p className="text-xs text-red-600 mb-3">{uploadError}</p>}

          <div>
            <p className="text-xs font-medium text-sparc-muted mb-2">
              Current documents ({loadingDocs ? '…' : docs.length})
            </p>
            {loadingDocs ? (
              <div className="space-y-1.5">{[...Array(3)].map((_, i) => (
                <div key={i} className="h-7 bg-gray-100 rounded animate-pulse" />
              ))}</div>
            ) : docs.length === 0 ? (
              <p className="text-xs text-sparc-muted italic">No documents yet — upload some files above.</p>
            ) : (
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {docs.map(doc => (
                  <div key={doc.name} className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-sparc-bg group">
                    <FileText className="w-3.5 h-3.5 text-navy shrink-0" />
                    <span className="text-xs text-sparc-text flex-1 truncate">{doc.name}</span>
                    <span className="text-[10px] text-sparc-muted shrink-0">{doc.type} · {doc.size_kb}KB</span>
                    <button
                      onClick={() => handleDelete(doc.name)}
                      disabled={deletingFile === doc.name}
                      title="Delete file"
                      className="ml-1 p-0.5 rounded text-sparc-muted hover:text-red-600 hover:bg-red-50 transition-colors disabled:opacity-40 opacity-0 group-hover:opacity-100 shrink-0"
                    >
                      {deletingFile === doc.name
                        ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        : <Trash2 className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── Ingest panel ── */}
        <div className="bg-white rounded-xl border border-sparc-border shadow-sm p-5">
          <div className="flex items-center gap-2 mb-4">
            <Play className="w-4 h-4 text-navy" />
            <h3 className="text-sm font-semibold text-navy">Ingest Documents</h3>
          </div>

          <p className="text-xs text-sparc-muted mb-5">
            Runs the full ingestion pipeline on all documents in the RAG folder: cracking, chunking, enrichment, embedding, and indexing into Azure AI Search.
          </p>

          <div className="space-y-3 mb-6 text-xs text-sparc-text">
            {['Document cracking (PDF, PPTX, DOCX)', 'Sentence chunking (400 words, 60-word overlap)',
              'Chunk enrichment (keywords, summary, project tag)', 'Azure OpenAI text-embedding-3-large (3072d)',
              'Azure AI Search index update'].map((step, i) => (
              <div key={i} className="flex items-center gap-2">
                <div className="w-5 h-5 rounded-full bg-navy/10 text-navy text-[10px] font-bold flex items-center justify-center shrink-0">{i + 1}</div>
                {step}
              </div>
            ))}
          </div>

          <button
            onClick={triggerIngest}
            disabled={ingestStatus === 'running' || docs.length === 0}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-navy text-white text-sm font-semibold hover:bg-navy-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed mb-4"
          >
            {ingestStatus === 'running'
              ? <><Loader2 className="w-4 h-4 animate-spin" /> Ingesting…</>
              : <><Play className="w-4 h-4" /> Run Ingestion</>}
          </button>

          {ingestMsg && (
            <div className={`text-xs rounded-lg px-3 py-2 ${
              ingestStatus === 'done' ? 'bg-green-50 text-green-700' :
              ingestStatus === 'error' ? 'bg-red-50 text-red-700' :
              ingestStatus === 'running' ? 'bg-blue-50 text-blue-700' :
              'bg-sparc-bg text-sparc-muted'
            }`}>
              <span className={`font-semibold mr-1 capitalize ${statusColor[ingestStatus]}`}>
                {ingestStatus}:
              </span>
              {ingestMsg}
            </div>
          )}

          {docs.length === 0 && (
            <p className="text-xs text-orange-500 mt-2 italic">Upload documents first before ingesting.</p>
          )}
        </div>
      </div>
    </div>
  );
}

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

  const load = async (bustCache = false) => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchAnalytics(bustCache));
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
            <p className="text-xs text-sparc-muted">Retrieval quality, Generation quality, Usage</p>
          </div>
        </div>
        <button onClick={() => load(true)} disabled={loading}
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

        {!loading && !error && !s && <RAGManagement />}

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
                <KpiCard label="Avg Retrieval Score" value={s.avg_score > 0 ? s.avg_score.toFixed(2) : '—'}
                  sub="Azure Search raw score (not 0–1)" icon={BarChart2} accent="#C8A951" />
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
                <KpiCard label="Hallucination Rate" value={s.hallucination !== null && s.hallucination !== undefined ? s.hallucination.toFixed(3) : '—'}
                  sub="0 = none · 1 = heavy (lower is better)" icon={AlertTriangle} accent="#DC2626"
                  note={s.hallucination === null ? 'run evaluation to populate' : undefined} />
              </div>
            </div>

            {/* ── Quality metrics breakdown ── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              {/* Per-Mode Quality Comparison */}
              <div className="bg-white rounded-xl border border-sparc-border p-5 shadow-sm">
                <h3 className="text-sm font-semibold text-navy mb-1">Quality by RAG Mode</h3>
                <p className="text-xs text-sparc-muted mb-4">Naive RAG vs Graph RAG — averaged across evaluated queries</p>
                {s.per_mode_quality && Object.keys(s.per_mode_quality).length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr>
                          <th className="text-left py-1.5 text-sparc-muted font-medium">Metric</th>
                          {Object.keys(s.per_mode_quality).map(mode => (
                            <th key={mode} className="text-center py-1.5 text-sparc-muted font-medium px-2">
                              {mode}
                              <span className="block text-[10px] text-sparc-muted font-normal">
                                ({s.per_mode_quality[mode].count} queries)
                              </span>
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {(['groundedness', 'relevancy', 'completeness', 'hallucination'] as const).map((key) => {
                          const meta: Record<string, { label: string; color: string }> = {
                            groundedness:  { label: 'Groundedness',    color: '#059669' },
                            relevancy:     { label: 'Relevancy',       color: '#2E74B5' },
                            completeness:  { label: 'Completeness',    color: '#C8A951' },
                            hallucination: { label: 'Hallucination ↓', color: '#DC2626' },
                          };
                          const { label, color } = meta[key];
                          return (
                          <tr key={key} className="border-t border-sparc-border">
                            <td className="py-2 text-sparc-text font-medium">{label}</td>
                            {Object.values(s.per_mode_quality).map((mq, i) => {
                              const val = mq[key];
                              return (
                                <td key={i} className="py-2 text-center px-2">
                                  {val !== null && val !== undefined ? (
                                    <span className="font-semibold" style={{ color }}>{(val as number).toFixed(3)}</span>
                                  ) : (
                                    <span className="text-sparc-muted">—</span>
                                  )}
                                </td>
                              );
                            })}
                          </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-xs text-sparc-muted italic mt-6 text-center">
                    No evaluated queries yet — use the RAG chat to generate data.
                  </p>
                )}
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

            {/* RAG Management */}
            <RAGManagement />
          </div>
        )}
      </div>
    </div>
  );
}
