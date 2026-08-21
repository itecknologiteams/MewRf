import { useState, useEffect } from 'react';
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  PieChart, Pie, Cell,
} from 'recharts';
import {
  Download, TrendingUp, FileText, Wallet, MapPin, Loader2,
  ChevronDown, ChevronRight, Car, Building2, CalendarDays,
} from 'lucide-react';
import { useToast } from '@/context/ToastContext';
import { tollsApi } from '@/services/api';
import { formatPlazaId } from '@/lib/utils';
import type { StatsData, DailyReport, PlazaReport, LaneReport } from '@/services/api';

// Categorical ramp, assigned in fixed order. The vars re-step per theme (see
// index.css) so the marks stay legible on both the light and dark surface.
const COLORS = [
  'var(--chart-1)',
  'var(--chart-2)',
  'var(--chart-3)',
  'var(--chart-4)',
  'var(--chart-5)',
  'var(--chart-6)',
];

/**
 * Vertical gloss ramps for bar fills — the skeuomorphic half of the design
 * lives on cards and graphs, so bars get a domed, top-lit body instead of a
 * flat slab. Each id maps to one --chart-N slot and keeps that slot's hue.
 */
function ChartGloss({ ids, slots }: { ids: string[]; slots: number[] }) {
  return (
    <defs>
      {ids.map((id, i) => {
        const hue = `var(--chart-${slots[i]})`;
        // Mix toward white/black rather than fading opacity: an opacity ramp
        // lightens on a light surface and darkens on a dark one, so the dome
        // would light from below in one of the two themes.
        return (
          <linearGradient key={id} id={id} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={`color-mix(in srgb, ${hue} 80%, white)`} />
            <stop offset="50%" stopColor={hue} />
            <stop offset="100%" stopColor={`color-mix(in srgb, ${hue} 84%, black)`} />
          </linearGradient>
        );
      })}
    </defs>
  );
}

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

function fmtPKR(n: number): string {
  if (n >= 1_000_000) return `PKR ${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `PKR ${(n / 1_000).toFixed(1)}K`;
  return `PKR ${n.toLocaleString()}`;
}

// ─── Analytics Tab ────────────────────────────────────────────────────────────

function AnalyticsTab({ stats, onDownload }: { stats: StatsData; onDownload: () => void }) {
  const maxPlazaRevenue = Math.max(...stats.plaza_stats.map((p) => p.revenue), 1);

  const summaryCards = [
    { title: 'Total Revenue', value: fmtPKR(stats.total_revenue), sub: `${stats.completed_trips} completed trips`, icon: TrendingUp, color: 'var(--accent-emerald)' },
    { title: 'Total Trips', value: stats.total_trips.toLocaleString(), sub: `${stats.active_trips} active`, icon: FileText, color: 'var(--accent-blue)' },
    { title: 'Total Wallet Balance', value: fmtPKR(stats.total_balance), sub: `${stats.total_vehicles} accounts`, icon: Wallet, color: 'var(--accent-cyan)' },
    { title: 'Active Plazas', value: String(stats.active_plazas), sub: `${stats.plaza_stats.length} total plazas`, icon: MapPin, color: 'var(--accent-amber)' },
  ];

  return (
    <>
      <div className="flex justify-end mb-4">
        <button onClick={onDownload} className="flex items-center gap-2 px-4 py-2.5 bg-brand text-brand-on text-sm font-medium rounded-xl hover:opacity-90 transition-opacity">
          <Download className="w-4 h-4" />
          Download CSV
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
        {summaryCards.map((card) => {
          const Icon = card.icon;
          return (
            <div key={card.title} className="bg-surface border border-line rounded-xl skeu-card p-5">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2 rounded-lg" style={{ backgroundColor: `color-mix(in srgb, ${card.color} 12%, transparent)` }}>
                  <Icon className="w-5 h-5" style={{ color: card.color }} />
                </div>
                <span className="text-xs text-ink-muted">{card.sub}</span>
              </div>
              <p className="text-2xl font-bold text-ink">{card.value}</p>
              <p className="text-sm text-ink-muted mt-1">{card.title}</p>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="bg-surface border border-line rounded-xl skeu-card p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-base font-semibold text-ink">Monthly Toll Revenue</h3>
            <span className="text-xs text-success bg-success/10 px-2 py-1 rounded-full">Live</span>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={stats.monthly}>
              <ChartGloss ids={['g1', 'g2']} slots={[1, 2]} />
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-custom)" vertical={false} />
              <XAxis dataKey="month" stroke="var(--text-tertiary)" fontSize={12} />
              <YAxis stroke="var(--text-tertiary)" fontSize={12} />
              <Tooltip contentStyle={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-custom)', borderRadius: '12px', fontSize: '12px', color: 'var(--text-primary)' }} itemStyle={{ color: 'var(--text-primary)' }} labelStyle={{ color: 'var(--text-secondary)' }} />
              <Legend />
              <Bar dataKey="toll" name="Revenue (PKR)" fill="url(#g1)" radius={[4, 4, 0, 0]} maxBarSize={50} />
              <Bar dataKey="transactions" name="Trips" fill="url(#g2)" radius={[4, 4, 0, 0]} maxBarSize={50} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-surface border border-line rounded-xl skeu-card p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-base font-semibold text-ink">Daily Transactions (Last 7 Days)</h3>
            <span className="text-xs text-success bg-success/10 px-2 py-1 rounded-full">Live</span>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={stats.daily}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-custom)" />
              <XAxis dataKey="day" stroke="var(--text-tertiary)" fontSize={12} />
              <YAxis stroke="var(--text-tertiary)" fontSize={12} />
              <Tooltip contentStyle={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-custom)', borderRadius: '12px', fontSize: '12px', color: 'var(--text-primary)' }} itemStyle={{ color: 'var(--text-primary)' }} labelStyle={{ color: 'var(--text-secondary)' }} />
              <Legend />
              <Line type="monotone" dataKey="amount" name="Revenue (PKR)" stroke="var(--chart-1)" strokeWidth={2} dot={{ fill: 'var(--chart-1)', strokeWidth: 2, r: 4, stroke: 'var(--bg-surface)' }} activeDot={{ r: 6, fill: 'var(--chart-1)', stroke: 'var(--bg-surface)', strokeWidth: 2 }} />
              <Line type="monotone" dataKey="count" name="Trip Count" stroke="var(--chart-2)" strokeWidth={2} strokeDasharray="5 5" dot={{ fill: 'var(--chart-2)', strokeWidth: 2, r: 4, stroke: 'var(--bg-surface)' }} activeDot={{ r: 6, fill: 'var(--chart-2)', stroke: 'var(--bg-surface)', strokeWidth: 2 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-surface border border-line rounded-xl skeu-card p-6">
          <h3 className="text-base font-semibold text-ink mb-6">Plaza Revenue</h3>
          {stats.plaza_stats.length === 0 ? (
            <div className="flex items-center justify-center h-40 text-sm text-ink-muted">No plaza data yet</div>
          ) : (
            <div className="space-y-5">
              {stats.plaza_stats.sort((a, b) => b.revenue - a.revenue).map((plaza) => {
                const pct = Math.round((plaza.revenue / maxPlazaRevenue) * 100);
                return (
                  <div key={plaza.name}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-medium text-ink">{plaza.name}</span>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${plaza.is_active ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger'}`}>
                          {plaza.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </div>
                      <div className="text-right">
                        <span className="text-sm font-semibold text-ink">PKR {plaza.revenue.toLocaleString()}</span>
                        <span className="text-xs text-ink-muted ml-2">{plaza.trips} trips</span>
                      </div>
                    </div>
                    <div className="h-2.5 bg-elevated rounded-full overflow-hidden skeu-track">
                      <div
                        className="h-full rounded-full bg-brand skeu-meter transition-all duration-700"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="bg-surface border border-line rounded-xl skeu-card p-6">
          <h3 className="text-base font-semibold text-ink mb-6">Vehicle Distribution</h3>
          {stats.vehicle_type_breakdown.length === 0 ? (
            <div className="flex items-center justify-center h-40 text-sm text-ink-muted">No vehicles registered</div>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={stats.vehicle_type_breakdown} cx="50%" cy="50%" innerRadius={60} outerRadius={90} paddingAngle={4} dataKey="value">
                    {stats.vehicle_type_breakdown.map((_, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={COLORS[index % COLORS.length]}
                        stroke="var(--bg-surface)"
                        strokeWidth={2}
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-custom)', borderRadius: '12px', fontSize: '12px', color: 'var(--text-primary)' }} itemStyle={{ color: 'var(--text-primary)' }} labelStyle={{ color: 'var(--text-secondary)' }}
                    formatter={(value, _name, props) => [`${props.payload.count} (${value}%)`, props.payload.name]}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-2 mt-4">
                {stats.vehicle_type_breakdown.map((item, index) => (
                  <div key={item.name} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS[index % COLORS.length] }} />
                      <span className="text-sm text-ink-muted">{item.name}</span>
                    </div>
                    <span className="text-sm font-medium text-ink">{item.value}%</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}

// ─── Lane Row ─────────────────────────────────────────────────────────────────

function LaneRow({ lane, index }: { lane: LaneReport; index: number }) {
  const color = COLORS[index % COLORS.length];
  const typeEntries = Object.entries(lane.vehicle_types);

  return (
    <div className="px-4 py-3 rounded-xl bg-elevated border border-line">
      <div className="flex items-center gap-4">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg text-xs font-bold text-white flex-shrink-0" style={{ backgroundColor: color }}>
          {lane.lane_number ?? '?'}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-ink">
            {lane.lane_number ? `Booth ${lane.lane_number}` : 'Unassigned'}
            {!lane.is_active && (
              <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded-full bg-danger/10 text-danger font-medium">Inactive</span>
            )}
          </p>
          {typeEntries.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-1">
              {typeEntries.map(([type, count]) => (
                <span key={type} className="text-[10px] px-1.5 py-0.5 rounded-full bg-surface border border-line text-ink-muted">
                  {type}: {count}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="flex gap-4 flex-shrink-0 text-right">
          <div>
            <p className="text-sm font-semibold text-ink">{lane.entries.toLocaleString()}</p>
            <p className="text-[10px] text-ink-muted">entries</p>
          </div>
          <div>
            <p className="text-sm font-semibold text-ink">{lane.exits.toLocaleString()}</p>
            <p className="text-[10px] text-ink-muted">exits</p>
          </div>
          <div>
            <p className="text-sm font-bold" style={{ color: 'var(--accent-emerald)' }}>{fmtPKR(lane.revenue)}</p>
            <p className="text-[10px] text-ink-muted">collected</p>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Plaza Card ───────────────────────────────────────────────────────────────

function PlazaCard({ plaza, colorIndex, forceOpen }: { plaza: PlazaReport; colorIndex: number; forceOpen?: boolean }) {
  const [open, setOpen] = useState(false);
  const color = COLORS[colorIndex % COLORS.length];
  const isOpen = forceOpen !== undefined ? forceOpen : open;

  return (
    <div className="bg-surface border border-line rounded-xl skeu-card overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-4 px-5 py-4 text-left hover:bg-elevated transition-colors"
      >
        <div className="flex items-center justify-center w-10 h-10 rounded-xl flex-shrink-0" style={{ backgroundColor: `color-mix(in srgb, ${color} 16%, transparent)` }}>
          <Building2 className="w-5 h-5" style={{ color }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-sm font-semibold text-ink">{plaza.name}</p>
            <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium bg-elevated text-ink-muted border border-line">ID {formatPlazaId(plaza.plaza_id)}</span>
            {!plaza.is_active && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-danger/10 text-danger font-medium">Inactive</span>
            )}
          </div>
          <p className="text-xs text-ink-muted mt-0.5">{plaza.lanes.length} booth{plaza.lanes.length !== 1 ? 's' : ''}</p>
        </div>
        <div className="flex gap-4 flex-shrink-0 mr-2 text-right">
          <div className="hidden sm:block">
            <p className="text-sm font-semibold text-ink">{plaza.entries.toLocaleString()}</p>
            <p className="text-[10px] text-ink-muted">entries</p>
          </div>
          <div className="hidden sm:block">
            <p className="text-sm font-semibold text-ink">{plaza.exits.toLocaleString()}</p>
            <p className="text-[10px] text-ink-muted">exits</p>
          </div>
          <div>
            <p className="text-sm font-bold" style={{ color: 'var(--accent-emerald)' }}>{fmtPKR(plaza.revenue)}</p>
            <p className="text-[10px] text-ink-muted">collected</p>
          </div>
        </div>
        {isOpen
          ? <ChevronDown className="w-4 h-4 text-ink-muted flex-shrink-0" />
          : <ChevronRight className="w-4 h-4 text-ink-muted flex-shrink-0" />}
      </button>

      {isOpen && (
        <div className="px-5 pb-4 border-t border-line">
          {plaza.lanes.length === 0 ? (
            <p className="text-sm text-ink-muted py-4 text-center">No booth activity</p>
          ) : (
            <div className="pt-3 space-y-2">
              {plaza.lanes.map((lane, i) => (
                <LaneRow key={lane.id ?? 'unassigned'} lane={lane} index={i} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Daily Report Tab ─────────────────────────────────────────────────────────

function DailyReportTab() {
  const { addToast } = useToast();
  const [date, setDate] = useState(todayStr());
  const [report, setReport] = useState<DailyReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [allExpanded, setAllExpanded] = useState(false);

  useEffect(() => {
    setLoading(true);
    setReport(null);
    tollsApi
      .dailyReport(date)
      .then(setReport)
      .catch(() => addToast({ type: 'error', title: 'Error', message: 'Failed to load daily report' }))
      .finally(() => setLoading(false));
  }, [date]);

  const downloadCSV = () => {
    if (!report) return;
    const rows: (string | number)[][] = [
      ['Date', report.date],
      [],
      ['Plaza', 'Code', 'Booth', 'Entries', 'Exits', 'Revenue (PKR)', 'Vehicle Types'],
    ];
    for (const plaza of report.plazas) {
      if (plaza.lanes.length === 0) {
        rows.push([plaza.name, formatPlazaId(plaza.plaza_id), '', plaza.entries, plaza.exits, plaza.revenue, '']);
      } else {
        for (const lane of plaza.lanes) {
          const types = Object.entries(lane.vehicle_types).map(([t, c]) => `${t}:${c}`).join(' | ');
          rows.push([plaza.name, formatPlazaId(plaza.plaza_id), lane.lane_number ?? 'Unassigned', lane.entries, lane.exits, lane.revenue, types]);
        }
      }
    }
    rows.push([], ['TOTAL', '', '', report.totals.entries, report.totals.exits, report.totals.revenue, '']);
    const csv = rows.map((r) => r.map((v) => `"${v}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `booth-report-${date}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    addToast({ type: 'success', title: 'Downloaded', message: `Report for ${date} saved.` });
  };

  return (
    <>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
        <div className="flex items-center gap-3">
          <div className="relative">
            <CalendarDays className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted pointer-events-none" />
            <input
              type="date"
              value={date}
              max={todayStr()}
              onChange={(e) => setDate(e.target.value)}
              className="pl-9 pr-3 py-2 text-sm rounded-xl bg-surface border border-line text-ink focus:outline-none focus:ring-2 focus:ring-brand/40"
            />
          </div>
          {report && (
            <button
              onClick={() => setAllExpanded((v) => !v)}
              className="text-xs px-3 py-2 rounded-xl border border-line bg-surface text-ink-muted hover:text-ink transition-colors"
            >
              {allExpanded ? 'Collapse all' : 'Expand all'}
            </button>
          )}
        </div>
        <button
          onClick={downloadCSV}
          disabled={!report}
          className="flex items-center gap-2 px-4 py-2.5 bg-brand text-brand-on text-sm font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-40"
        >
          <Download className="w-4 h-4" />
          Download CSV
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48">
          <Loader2 className="w-8 h-8 animate-spin text-brand" />
        </div>
      ) : report ? (
        <>
          <div className="grid grid-cols-3 gap-4 mb-5">
            <div className="bg-surface border border-line rounded-xl skeu-card p-4 flex items-center gap-3">
              <div className="p-2 rounded-lg bg-brand/10">
                <Car className="w-5 h-5 text-brand" />
              </div>
              <div>
                <p className="text-xl font-bold text-ink">{report.totals.entries.toLocaleString()}</p>
                <p className="text-xs text-ink-muted">Total entries</p>
              </div>
            </div>
            <div className="bg-surface border border-line rounded-xl skeu-card p-4 flex items-center gap-3">
              <div className="p-2 rounded-lg bg-info/10">
                <FileText className="w-5 h-5 text-info" />
              </div>
              <div>
                <p className="text-xl font-bold text-ink">{report.totals.exits.toLocaleString()}</p>
                <p className="text-xs text-ink-muted">Total exits</p>
              </div>
            </div>
            <div className="bg-surface border border-line rounded-xl skeu-card p-4 flex items-center gap-3">
              <div className="p-2 rounded-lg bg-success/10">
                <TrendingUp className="w-5 h-5 text-success" />
              </div>
              <div>
                <p className="text-xl font-bold text-ink">{fmtPKR(report.totals.revenue)}</p>
                <p className="text-xs text-ink-muted">Total collection</p>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            {report.plazas.map((plaza, i) => (
              <PlazaCard key={plaza.id} plaza={plaza} colorIndex={i} forceOpen={allExpanded ? true : undefined} />
            ))}
          </div>

          {/* PlazaReport has no `trips` field — it reports entries/exits. The old
              `p.trips === 0` compared undefined to 0, so this never rendered. */}
          {report.plazas.every((p) => p.entries === 0 && p.exits === 0) && (
            <p className="text-center py-10 text-sm text-ink-muted">No trips recorded on {date}</p>
          )}
        </>
      ) : null}
    </>
  );
}

// ─── Main Reports page ────────────────────────────────────────────────────────

export default function Reports() {
  const { addToast } = useToast();
  const [activeTab, setActiveTab] = useState<'analytics' | 'daily'>('analytics');
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<StatsData | null>(null);

  useEffect(() => {
    tollsApi
      .stats()
      .then(setStats)
      .catch(() => addToast({ type: 'error', title: 'Error', message: 'Failed to load analytics' }))
      .finally(() => setLoading(false));
  }, []);

  const downloadAnalyticsCSV = () => {
    if (!stats) return;
    const rows = [
      ['Month', 'Revenue (PKR)', 'Transactions'],
      ...stats.monthly.map((m) => [m.month, m.toll.toFixed(2), m.transactions]),
      [],
      ['Day', 'Revenue (PKR)', 'Trip Count'],
      ...stats.daily.map((d) => [d.day, d.amount.toFixed(2), d.count]),
      [],
      ['Plaza', 'Revenue (PKR)', 'Trips'],
      ...stats.plaza_stats.map((p) => [p.name, p.revenue.toFixed(2), p.trips]),
    ];
    const csv = rows.map((r) => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `mtag-analytics-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    addToast({ type: 'success', title: 'Downloaded', message: 'Analytics CSV saved.' });
  };

  return (
    <div className="animate-fade-in-up">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-ink">Reports & Analytics</h1>
        <p className="text-sm text-ink-muted mt-1">Toll collection data across all plazas and booths</p>
      </div>

      <div className="flex gap-1 p-1 bg-elevated rounded-xl border border-line w-fit mb-6">
        {([
          { key: 'analytics' as const, label: 'Analytics' },
          { key: 'daily' as const, label: 'Daily Booth Report' },
        ]).map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-all ${
              activeTab === tab.key
                ? 'bg-surface text-ink shadow-sm border border-line'
                : 'text-ink-muted hover:text-ink'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'analytics' ? (
        loading ? (
          <div className="flex items-center justify-center min-h-[60vh]">
            <div className="flex flex-col items-center gap-4">
              <Loader2 className="w-10 h-10 animate-spin text-brand" />
              <p className="text-sm text-ink-muted">Loading analytics...</p>
            </div>
          </div>
        ) : stats ? (
          <AnalyticsTab stats={stats} onDownload={downloadAnalyticsCSV} />
        ) : null
      ) : (
        <DailyReportTab />
      )}
    </div>
  );
}
