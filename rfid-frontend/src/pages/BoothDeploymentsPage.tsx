import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { boothsApi } from '@/services/api';
import type { BoothDeployment, BoothDeployJob, BoothDeployJobSummary } from '@/services/api';
import { useToast } from '@/context/ToastContext';
import {
  Search,
  Loader2,
  RefreshCw,
  X,
  Trash2,
  Pencil,
  Server,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  WifiOff,
  Download,
  Terminal,
  History,
} from 'lucide-react';

type SyncState = 'up-to-date' | 'outdated' | 'unreachable' | 'unconfigured' | 'unknown';

const STATE_META: Record<SyncState, { label: string; className: string; Icon: typeof CheckCircle2 }> = {
  'up-to-date': {
    label: 'Up to date',
    className: 'bg-success/10 text-success border-success/20',
    Icon: CheckCircle2,
  },
  outdated: {
    label: 'Outdated',
    className: 'bg-warning/10 text-warning border-warning/20',
    Icon: AlertTriangle,
  },
  unreachable: {
    label: 'Unreachable',
    className: 'bg-danger/10 text-danger border-danger/20',
    Icon: WifiOff,
  },
  unconfigured: {
    label: 'No booth set',
    className: 'bg-elevated text-ink-subtle border-line',
    Icon: HelpCircle,
  },
  unknown: {
    label: 'Never checked',
    className: 'bg-elevated text-ink-subtle border-line',
    Icon: HelpCircle,
  },
};

/** What the cached last check says about this lane, relative to master.
 *
 *  'unknown' and 'unreachable' are deliberately distinct: one means we have
 *  never asked the booth, the other means we asked and it did not answer. An
 *  operator acts differently on each. */
function syncState(row: BoothDeployment, masterVersion: string): SyncState {
  if (!row.id || !row.host) return 'unconfigured';
  if (row.reachable === false) return 'unreachable';
  if (!row.reported_version) return 'unknown';
  return row.reported_version === masterVersion ? 'up-to-date' : 'outdated';
}

function relativeTime(iso?: string | null): string {
  if (!iso) return 'never';
  const seconds = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

const inputClass =
  'w-full px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all';

export default function BoothDeploymentsPage() {
  const { addToast } = useToast();

  const [masterVersion, setMasterVersion] = useState('');
  const [rows, setRows] = useState<BoothDeployment[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [stateFilter, setStateFilter] = useState<'all' | SyncState>('all');

  // Configure-machine modal
  const [editRow, setEditRow] = useState<BoothDeployment | null>(null);
  const [form, setForm] = useState({ host: '', ssh_port: '22', ssh_user: '' });
  const [isSaving, setIsSaving] = useState(false);

  const [confirmRemove, setConfirmRemove] = useState<BoothDeployment | null>(null);
  const [isRemoving, setIsRemoving] = useState(false);
  const [confirmUpdateAll, setConfirmUpdateAll] = useState(false);
  const [isQueueingAll, setIsQueueingAll] = useState(false);

  // Job transcript drawer
  const [openJob, setOpenJob] = useState<BoothDeployJob | null>(null);
  const [history, setHistory] = useState<BoothDeployJobSummary[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  // Lanes with a job queued from this page, so the buttons disable immediately
  // rather than waiting for the next poll to reflect it.
  const [queueing, setQueueing] = useState<number[]>([]);

  const fetchData = useCallback(async (opts?: { quiet?: boolean }) => {
    if (!opts?.quiet) setLoading(true);
    try {
      const data = await boothsApi.deployments();
      setMasterVersion(data.master_version);
      setRows(data.booths);
    } catch (err: unknown) {
      if (!opts?.quiet) {
        addToast({
          type: 'error',
          title: 'Error',
          message: err instanceof Error ? err.message : 'Failed to load booth deployments',
        });
      }
    } finally {
      if (!opts?.quiet) setLoading(false);
    }
  }, [addToast]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const anyJobRunning = useMemo(() => rows.some((r) => r.active_job), [rows]);

  // Poll only while something is actually in flight. A deploy takes minutes, so
  // the page has to refresh itself, but polling an idle page all day would hit
  // master 21 rows at a time for nothing.
  // Held in a ref so a new fetchData identity does not restart the interval
  // mid-deploy; assigned in an effect rather than during render.
  const fetchRef = useRef(fetchData);
  useEffect(() => { fetchRef.current = fetchData; }, [fetchData]);
  useEffect(() => {
    if (!anyJobRunning) return;
    const id = setInterval(() => fetchRef.current({ quiet: true }), 4000);
    return () => clearInterval(id);
  }, [anyJobRunning]);

  // Keep the open transcript live while its job runs.
  useEffect(() => {
    if (!openJob || openJob.status === 'succeeded' || openJob.status === 'failed') return;
    const id = setInterval(async () => {
      try {
        setOpenJob(await boothsApi.job(openJob.id));
      } catch {
        // Transient — the next tick retries, and the drawer keeps what it has.
      }
    }, 3000);
    return () => clearInterval(id);
  }, [openJob]);

  const counts = useMemo(() => {
    const tally: Record<SyncState, number> = {
      'up-to-date': 0, outdated: 0, unreachable: 0, unconfigured: 0, unknown: 0,
    };
    rows.forEach((r) => { tally[syncState(r, masterVersion)] += 1; });
    return tally;
  }, [rows, masterVersion]);

  const filtered = useMemo(() => {
    const s = search.trim().toLowerCase();
    return rows.filter((r) => {
      if (stateFilter !== 'all' && syncState(r, masterVersion) !== stateFilter) return false;
      if (!s) return true;
      return (
        String(r.lane_number).includes(s)
        || r.plaza_name.toLowerCase().includes(s)
        || r.host.toLowerCase().includes(s)
        || r.reported_version.toLowerCase().includes(s)
      );
    });
  }, [rows, search, stateFilter, masterVersion]);

  const openEditor = (row: BoothDeployment) => {
    setEditRow(row);
    setForm({
      host: row.host || '',
      ssh_port: String(row.ssh_port ?? 22),
      ssh_user: row.ssh_user || '',
    });
  };

  const handleSaveMachine = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editRow) return;
    if (!form.host.trim()) {
      addToast({ type: 'error', title: 'Validation Error', message: 'A booth needs an IP or hostname.' });
      return;
    }
    const port = Number(form.ssh_port);
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      addToast({ type: 'error', title: 'Validation Error', message: 'SSH port must be between 1 and 65535.' });
      return;
    }
    setIsSaving(true);
    try {
      await boothsApi.saveMachine({
        lane: editRow.lane,
        host: form.host.trim(),
        ssh_port: port,
        ssh_user: form.ssh_user.trim(),
      });
      addToast({ type: 'success', title: 'Saved', message: `Lane ${editRow.lane_number} points at ${form.host.trim()}.` });
      setEditRow(null);
      fetchData();
    } catch (err: unknown) {
      addToast({ type: 'error', title: 'Failed', message: err instanceof Error ? err.message : 'Error' });
    } finally {
      setIsSaving(false);
    }
  };

  const handleRemoveMachine = async () => {
    if (!confirmRemove?.id) return;
    setIsRemoving(true);
    try {
      await boothsApi.deleteMachine(confirmRemove.id);
      addToast({ type: 'success', title: 'Removed', message: `Lane ${confirmRemove.lane_number} no longer has a booth machine.` });
      setConfirmRemove(null);
      fetchData();
    } catch (err: unknown) {
      addToast({ type: 'error', title: 'Failed', message: err instanceof Error ? err.message : 'Error' });
    } finally {
      setIsRemoving(false);
    }
  };

  const queue = async (row: BoothDeployment, action: 'check' | 'update') => {
    if (!row.id) return;
    setQueueing((ids) => [...ids, row.id as number]);
    try {
      const job = await boothsApi.queueJob(row.id, action);
      addToast({
        type: 'success',
        title: action === 'check' ? 'Check queued' : 'Update queued',
        message: `Lane ${row.lane_number} — watch the log for progress.`,
      });
      if (action === 'update') setOpenJob(job);
      fetchData({ quiet: true });
    } catch (err: unknown) {
      addToast({ type: 'error', title: 'Failed', message: err instanceof Error ? err.message : 'Error' });
    } finally {
      setQueueing((ids) => ids.filter((id) => id !== row.id));
    }
  };

  const updateAllTargets = useMemo(
    () => rows.filter((row) => row.id && !row.active_job),
    [rows],
  );

  const handleUpdateAll = async () => {
    if (updateAllTargets.length === 0) return;
    setIsQueueingAll(true);
    const targetIds = updateAllTargets.map((row) => row.id as number);
    setQueueing((ids) => Array.from(new Set([...ids, ...targetIds])));
    try {
      const results = await Promise.allSettled(
        updateAllTargets.map((row) => boothsApi.queueJob(row.id as number, 'update')),
      );
      const queued = results.filter((result) => result.status === 'fulfilled').length;
      const failed = results.length - queued;
      addToast({
        type: failed ? 'error' : 'success',
        title: failed ? 'Some updates failed to queue' : 'Updates queued',
        message: failed
          ? `${queued} booth${queued === 1 ? '' : 's'} queued, ${failed} failed.`
          : `${queued} booth${queued === 1 ? '' : 's'} queued for update.`,
      });
      const firstJob = results.find(
        (result): result is PromiseFulfilledResult<BoothDeployJob> => result.status === 'fulfilled',
      );
      if (firstJob) setOpenJob(firstJob.value);
      setConfirmUpdateAll(false);
      fetchData({ quiet: true });
    } finally {
      setIsQueueingAll(false);
      setQueueing((ids) => ids.filter((id) => !targetIds.includes(id)));
    }
  };

  const openHistory = async () => {
    setShowHistory(true);
    try {
      setHistory(await boothsApi.jobHistory());
    } catch (err: unknown) {
      addToast({ type: 'error', title: 'Failed', message: err instanceof Error ? err.message : 'Error' });
    }
  };

  const outdated = rows.filter((r) => syncState(r, masterVersion) === 'outdated');

  return (
    <div className="animate-fade-in-up">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-ink">Booth Code Updates</h1>
          <p className="text-sm text-ink-muted mt-1">
            Master is running{' '}
            <span className="font-mono font-semibold text-ink">{masterVersion || '—'}</span>
            {' · '}
            {outdated.length === 0
              ? 'every configured booth matches'
              : `${outdated.length} booth${outdated.length > 1 ? 's are' : ' is'} behind`}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setConfirmUpdateAll(true)}
            disabled={updateAllTargets.length === 0 || isQueueingAll}
            className="flex items-center gap-2 px-4 py-2.5 bg-brand text-brand-on text-sm font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50"
            title={updateAllTargets.length === 0 ? 'No configured idle booths to update' : 'Queue updates for every configured booth'}
          >
            {isQueueingAll ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            Update All
          </button>
          <button
            onClick={openHistory}
            className="flex items-center gap-2 px-4 py-2.5 bg-elevated border border-line text-ink-muted text-sm font-medium rounded-xl hover:bg-surface transition-colors"
          >
            <History className="w-4 h-4" />
            History
          </button>
          <button
            onClick={() => fetchData()}
            className="flex items-center gap-2 px-4 py-2.5 bg-elevated border border-line text-ink-muted text-sm font-medium rounded-xl hover:bg-surface transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
        {(Object.keys(STATE_META) as SyncState[]).map((state) => {
          const { label, Icon } = STATE_META[state];
          return (
            <button
              key={state}
              onClick={() => setStateFilter(stateFilter === state ? 'all' : state)}
              className={`text-left bg-surface border rounded-xl skeu-card p-4 transition-colors ${
                stateFilter === state ? 'border-brand' : 'border-line hover:bg-elevated'
              }`}
            >
              <div className="flex items-center gap-2 text-ink-muted mb-2">
                <Icon className="w-4 h-4" />
                <span className="text-xs font-medium uppercase tracking-wider truncate">{label}</span>
              </div>
              <p className="text-2xl font-bold text-ink">{loading ? '—' : counts[state]}</p>
            </button>
          );
        })}
      </div>

      {/* Search */}
      <div className="bg-surface border border-line rounded-xl skeu-card p-4 mb-6">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-subtle" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by lane, plaza, host or version..."
            className="w-full pl-10 pr-4 py-2.5 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
          />
        </div>
      </div>

      {/* Table */}
      <div className="bg-surface border border-line rounded-xl skeu-card overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-brand" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="px-6 py-16 text-center">
            <Server className="w-12 h-12 text-ink-subtle mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-ink mb-2">
              {rows.length === 0 ? 'No lanes configured' : 'No booths match'}
            </h3>
            <p className="text-sm text-ink-muted">
              {rows.length === 0
                ? 'Add lanes in Lane Management first — each lane is one booth machine.'
                : 'Try adjusting the search or the status filter.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-elevated">
                  <th className="text-left px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">Lane</th>
                  <th className="text-left px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">Booth Host</th>
                  <th className="text-left px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">Version</th>
                  <th className="text-left px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">Status</th>
                  <th className="text-left px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">PM2</th>
                  <th className="text-left px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">Checked</th>
                  <th className="px-6 py-3" />
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => {
                  const state = syncState(row, masterVersion);
                  const { label, className, Icon } = STATE_META[state];
                  const job = row.active_job;
                  const busy = Boolean(job) || queueing.includes(row.id ?? -1);
                  return (
                    <tr key={row.lane} className="border-b border-line hover:bg-elevated transition-colors">
                      <td className="px-6 py-4">
                        <p className="text-sm font-semibold text-ink">Lane {row.lane_number}</p>
                        <p className="text-xs text-ink-muted mt-0.5">
                          {row.plaza_name} · {row.plaza_display_id}
                        </p>
                      </td>
                      <td className="px-6 py-4">
                        {row.host ? (
                          <>
                            <p className="text-sm font-mono text-ink">{row.host}</p>
                            <p className="text-xs text-ink-subtle mt-0.5">
                              {row.ssh_user_effective}@:{row.ssh_port}
                            </p>
                          </>
                        ) : (
                          <span className="text-xs text-ink-subtle">not configured</span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-sm font-mono text-ink">{row.reported_version || '—'}</span>
                        {state === 'outdated' && (
                          <p className="text-xs text-ink-subtle mt-0.5">master {masterVersion}</p>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${className}`}>
                          <Icon className="w-3.5 h-3.5" />
                          {label}
                        </span>
                        {row.last_error && state === 'unreachable' && (
                          <p className="text-xs text-ink-subtle mt-1 max-w-[16rem] truncate" title={row.last_error}>
                            {row.last_error.split('\n').filter(Boolean).pop()}
                          </p>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-xs text-ink-muted">{row.pm2_summary || '—'}</span>
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-xs text-ink-muted">{relativeTime(row.last_checked_at)}</span>
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex items-center justify-end gap-1">
                          {job ? (
                            <button
                              onClick={async () => setOpenJob(await boothsApi.job(job.id))}
                              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-brand/10 text-brand text-xs font-medium hover:bg-brand/20 transition-colors"
                            >
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              {job.action === 'check' ? 'Checking' : 'Updating'}
                            </button>
                          ) : (
                            <>
                              <button
                                onClick={() => queue(row, 'check')}
                                disabled={!row.id || busy}
                                className="px-3 py-1.5 rounded-lg bg-elevated border border-line text-ink-muted text-xs font-medium hover:bg-surface transition-colors disabled:opacity-40"
                                title={row.id ? 'Read the version this booth is running' : 'Configure the booth host first'}
                              >
                                Check
                              </button>
                              <button
                                onClick={() => queue(row, 'update')}
                                disabled={!row.id || busy}
                                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-opacity disabled:opacity-40 ${
                                  state === 'outdated'
                                    ? 'bg-brand text-brand-on hover:opacity-90'
                                    : 'bg-elevated border border-line text-ink-muted hover:bg-surface'
                                }`}
                                title="Push master's code to this booth and restart PM2"
                              >
                                <Download className="w-3.5 h-3.5" />
                                Update
                              </button>
                            </>
                          )}
                          <button
                            onClick={() => openEditor(row)}
                            className="p-1.5 rounded-lg hover:bg-surface text-ink-subtle transition-colors"
                            title={row.id ? 'Edit booth host' : 'Set booth host'}
                          >
                            <Pencil className="w-4 h-4" />
                          </button>
                          {row.id && (
                            <button
                              onClick={() => setConfirmRemove(row)}
                              className="p-1.5 rounded-lg hover:bg-danger/10 text-ink-subtle hover:text-danger transition-colors"
                              title="Remove booth host"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Configure machine modal */}
      {editRow && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in-up">
          <div className="bg-surface border border-line rounded-2xl skeu-card w-full max-w-md">
            <div className="flex items-center justify-between px-6 py-4 border-b border-line">
              <div>
                <h2 className="text-lg font-semibold text-ink">Booth Machine</h2>
                <p className="text-xs text-ink-muted mt-0.5">
                  {editRow.plaza_name} · Lane {editRow.lane_number}
                </p>
              </div>
              <button onClick={() => setEditRow(null)} className="p-1.5 rounded-lg hover:bg-elevated text-ink-subtle">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleSaveMachine} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-ink mb-1.5">
                  LAN IP or hostname <span className="text-danger">*</span>
                </label>
                <input
                  type="text"
                  value={form.host}
                  onChange={(e) => setForm((f) => ({ ...f, host: e.target.value }))}
                  placeholder="192.168.79.58"
                  className={inputClass}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-ink mb-1.5">SSH port</label>
                  <input
                    type="number"
                    min={1}
                    max={65535}
                    value={form.ssh_port}
                    onChange={(e) => setForm((f) => ({ ...f, ssh_port: e.target.value }))}
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-ink mb-1.5">SSH user</label>
                  <input
                    type="text"
                    value={form.ssh_user}
                    onChange={(e) => setForm((f) => ({ ...f, ssh_user: e.target.value }))}
                    placeholder={editRow.ssh_user_effective || 'default'}
                    className={inputClass}
                  />
                </div>
              </div>
              <p className="text-xs text-ink-subtle">
                Leave the user blank to use master's configured default. The SSH password is
                never stored here — master reads it from its own <span className="font-mono">.env</span>.
              </p>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setEditRow(null)}
                  className="flex-1 py-2.5 bg-elevated border border-line text-ink text-sm font-medium rounded-xl hover:bg-surface transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSaving}
                  className="flex-1 py-2.5 bg-brand text-brand-on text-sm font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-60 flex items-center justify-center gap-2"
                >
                  {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Server className="w-4 h-4" />}
                  Save
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Remove machine confirm */}
      {confirmRemove && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 animate-fade-in-up" onClick={() => setConfirmRemove(null)}>
          <div className="bg-surface border border-line rounded-2xl skeu-card w-full max-w-sm p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-danger/10 rounded-full flex items-center justify-center">
                <Trash2 className="w-5 h-5 text-danger" />
              </div>
              <div>
                <p className="font-semibold text-ink">Remove Booth Machine</p>
                <p className="text-xs text-ink-muted">Lane {confirmRemove.lane_number} · {confirmRemove.host}</p>
              </div>
            </div>
            <p className="text-sm text-ink-muted mb-5">
              This only forgets the address and its deploy history here. Nothing on the booth
              itself is changed or stopped.
            </p>
            <div className="flex gap-3">
              <button onClick={() => setConfirmRemove(null)} className="flex-1 py-2.5 bg-elevated border border-line text-sm font-medium text-ink rounded-xl hover:bg-surface transition-colors">
                Cancel
              </button>
              <button
                onClick={handleRemoveMachine}
                disabled={isRemoving}
                className="flex-1 py-2.5 bg-danger-solid text-white text-sm font-semibold rounded-xl hover:opacity-90 transition-opacity disabled:opacity-60 flex items-center justify-center gap-2"
              >
                {isRemoving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                Remove
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Update all confirm */}
      {confirmUpdateAll && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 animate-fade-in-up" onClick={() => !isQueueingAll && setConfirmUpdateAll(false)}>
          <div className="bg-surface border border-line rounded-2xl skeu-card w-full max-w-sm p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-brand/10 rounded-full flex items-center justify-center">
                <Download className="w-5 h-5 text-brand" />
              </div>
              <div>
                <p className="font-semibold text-ink">Update All Booths?</p>
                <p className="text-xs text-ink-muted">
                  {updateAllTargets.length} configured booth{updateAllTargets.length === 1 ? '' : 's'} will be queued.
                </p>
              </div>
            </div>
            <p className="text-sm text-ink-muted mb-5">
              This will ask every idle configured booth to download the latest code from master/GitHub and restart its PM2 services.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setConfirmUpdateAll(false)}
                disabled={isQueueingAll}
                className="flex-1 py-2.5 bg-elevated border border-line text-sm font-medium text-ink rounded-xl hover:bg-surface transition-colors disabled:opacity-60"
              >
                Cancel
              </button>
              <button
                onClick={handleUpdateAll}
                disabled={isQueueingAll || updateAllTargets.length === 0}
                className="flex-1 py-2.5 bg-brand text-brand-on text-sm font-semibold rounded-xl hover:opacity-90 transition-opacity disabled:opacity-60 flex items-center justify-center gap-2"
              >
                {isQueueingAll ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                Okay, Update
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Job transcript */}
      {openJob && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in-up" onClick={() => setOpenJob(null)}>
          <div className="bg-surface border border-line rounded-2xl skeu-card w-full max-w-3xl flex flex-col max-h-[85vh]" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-line">
              <div className="flex items-center gap-3">
                <Terminal className="w-5 h-5 text-brand" />
                <div>
                  <h2 className="text-lg font-semibold text-ink">
                    Lane {openJob.lane_number} · {openJob.action === 'check' ? 'Version check' : 'Code update'}
                  </h2>
                  <p className="text-xs text-ink-muted mt-0.5">
                    {openJob.from_version || '—'} → {openJob.to_version || '—'}
                    {openJob.exit_code !== null && ` · exit ${openJob.exit_code}`}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
                  openJob.status === 'succeeded' ? 'bg-success/10 text-success border-success/20'
                    : openJob.status === 'failed' ? 'bg-danger/10 text-danger border-danger/20'
                    : 'bg-brand/10 text-brand border-brand/20'
                }`}>
                  {(openJob.status === 'pending' || openJob.status === 'running') && (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  )}
                  {openJob.status}
                </span>
                <button onClick={() => setOpenJob(null)} className="p-1.5 rounded-lg hover:bg-elevated text-ink-subtle">
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>
            <div className="p-6 overflow-auto">
              <pre className="text-xs font-mono text-ink-muted whitespace-pre-wrap break-words bg-elevated border border-line rounded-xl p-4">
                {openJob.log || (openJob.status === 'pending'
                  ? 'Waiting for the deploy worker to pick this up…'
                  : 'Running…')}
              </pre>
            </div>
          </div>
        </div>
      )}

      {/* History */}
      {showHistory && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in-up" onClick={() => setShowHistory(false)}>
          <div className="bg-surface border border-line rounded-2xl skeu-card w-full max-w-3xl flex flex-col max-h-[85vh]" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-line">
              <h2 className="text-lg font-semibold text-ink">Deploy History</h2>
              <button onClick={() => setShowHistory(false)} className="p-1.5 rounded-lg hover:bg-elevated text-ink-subtle">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="overflow-auto">
              {history.length === 0 ? (
                <p className="px-6 py-12 text-sm text-ink-muted text-center">Nothing has been deployed from here yet.</p>
              ) : (
                <table className="w-full">
                  <thead>
                    <tr className="bg-elevated">
                      <th className="text-left px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">When</th>
                      <th className="text-left px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">Lane</th>
                      <th className="text-left px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">Action</th>
                      <th className="text-left px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">Versions</th>
                      <th className="text-left px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">By</th>
                      <th className="text-left px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((job) => (
                      <tr
                        key={job.id}
                        onClick={async () => { setShowHistory(false); setOpenJob(await boothsApi.job(job.id)); }}
                        className="border-b border-line hover:bg-elevated transition-colors cursor-pointer"
                      >
                        <td className="px-6 py-3 text-xs text-ink-muted">{relativeTime(job.requested_at)}</td>
                        <td className="px-6 py-3 text-sm text-ink">Lane {job.lane_number}</td>
                        <td className="px-6 py-3 text-xs text-ink-muted capitalize">{job.action}</td>
                        <td className="px-6 py-3 text-xs font-mono text-ink-muted">
                          {job.from_version || '—'} → {job.to_version || '—'}
                        </td>
                        <td className="px-6 py-3 text-xs text-ink-muted">{job.requested_by_name || '—'}</td>
                        <td className="px-6 py-3">
                          <span className={`px-2.5 py-1 rounded-full text-xs font-medium border ${
                            job.status === 'succeeded' ? 'bg-success/10 text-success border-success/20'
                              : job.status === 'failed' ? 'bg-danger/10 text-danger border-danger/20'
                              : 'bg-brand/10 text-brand border-brand/20'
                          }`}>
                            {job.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
