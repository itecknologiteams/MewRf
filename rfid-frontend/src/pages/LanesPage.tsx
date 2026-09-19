import { useState, useEffect, useMemo } from 'react';
import { tollsApi } from '@/services/api';
import { formatPlazaId } from '@/lib/utils';
import type { Plaza, Lane } from '@/types';
import { useToast } from '@/context/ToastContext';
import {
  MapPin,
  Search,
  Loader2,
  RefreshCw,
  Plus,
  X,
  ToggleLeft,
  ToggleRight,
  Trash2,
  Pencil,
  SignpostBig,
  LayoutGrid,
} from 'lucide-react';

/** A lane plus the plaza it belongs to — the nested API shape flattened so the
 *  table can be filtered and sorted across plazas. */
interface LaneRow extends Lane {
  plazaId: number;
  plazaName: string;
  plazaDisplayId: string;
  plazaActive: boolean;
}

export default function LanesPage() {
  const { addToast } = useToast();

  const [plazas, setPlazas] = useState<Plaza[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [plazaFilter, setPlazaFilter] = useState<number | 'all'>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all');

  // Add lane modal — single number or a contiguous range.
  const [showAddModal, setShowAddModal] = useState(false);
  const [addForm, setAddForm] = useState({
    plaza: '' as number | '',
    mode: 'single' as 'single' | 'range',
    lane_number: '',
    range_from: '',
    range_to: '',
    is_active: true,
  });
  const [isAdding, setIsAdding] = useState(false);

  // Edit lane modal
  const [editLane, setEditLane] = useState<LaneRow | null>(null);
  const [editForm, setEditForm] = useState({ lane_number: '', is_active: true });
  const [isSaving, setIsSaving] = useState(false);

  // Delete confirmation
  const [confirmDelete, setConfirmDelete] = useState<LaneRow | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Lanes being toggled — keyed so one slow request does not freeze the others.
  const [togglingIds, setTogglingIds] = useState<number[]>([]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const data = await tollsApi.adminPlazas();
      setPlazas(data);
    } catch (err: unknown) {
      addToast({
        type: 'error',
        title: 'Error',
        message: err instanceof Error ? err.message : 'Failed to load plazas',
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const allLanes = useMemo<LaneRow[]>(
    () =>
      plazas.flatMap((p) =>
        (p.lanes || []).map((l) => ({
          ...l,
          plazaId: p.id,
          plazaName: p.name,
          plazaDisplayId: formatPlazaId(p.plaza_id),
          plazaActive: p.is_active,
        }))
      ),
    [plazas]
  );

  const stats = useMemo(() => ({
    total: allLanes.length,
    active: allLanes.filter((l) => l.is_active).length,
    inactive: allLanes.filter((l) => !l.is_active).length,
    plazasWithoutLanes: plazas.filter((p) => !p.lanes || p.lanes.length === 0).length,
  }), [allLanes, plazas]);

  /** Plazas that survive the filters, each carrying only its matching lanes. A
   *  plaza with no matching lanes is still shown when it is the only plaza
   *  selected, so "this plaza has none yet" stays visible instead of the whole
   *  page reading as empty. */
  const groups = useMemo(() => {
    const s = search.trim().toLowerCase();
    return plazas
      .filter((p) => plazaFilter === 'all' || p.id === plazaFilter)
      .map((p) => {
        const lanes = (p.lanes || [])
          .filter((l) => statusFilter === 'all'
            || (statusFilter === 'active' ? l.is_active : !l.is_active))
          .filter((l) => {
            if (!s) return true;
            return (
              String(l.lane_number).includes(s)
              || p.name.toLowerCase().includes(s)
              || formatPlazaId(p.plaza_id).includes(s)
            );
          })
          .sort((a, b) => a.lane_number - b.lane_number);
        return { plaza: p, lanes };
      })
      .filter(({ lanes }) => lanes.length > 0 || plazaFilter !== 'all')
      .sort((a, b) => a.plaza.name.localeCompare(b.plaza.name));
  }, [plazas, plazaFilter, statusFilter, search]);

  const openAddModal = (plaza?: Plaza) => {
    setAddForm({
      plaza: plaza?.id ?? (plazaFilter !== 'all' ? plazaFilter : ''),
      mode: 'single',
      lane_number: '',
      range_from: '',
      range_to: '',
      is_active: true,
    });
    setShowAddModal(true);
  };

  const handleAddLanes = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!addForm.plaza) {
      addToast({ type: 'error', title: 'Validation Error', message: 'Select a plaza first.' });
      return;
    }

    let numbers: number[];
    if (addForm.mode === 'single') {
      const n = Number(addForm.lane_number);
      if (!addForm.lane_number || !Number.isInteger(n) || n < 1) {
        addToast({ type: 'error', title: 'Validation Error', message: 'Lane number must be a whole number of 1 or more.' });
        return;
      }
      numbers = [n];
    } else {
      const from = Number(addForm.range_from);
      const to = Number(addForm.range_to);
      if (!addForm.range_from || !addForm.range_to
        || !Number.isInteger(from) || !Number.isInteger(to) || from < 1 || to < 1) {
        addToast({ type: 'error', title: 'Validation Error', message: 'Enter a whole-number range starting at 1 or more.' });
        return;
      }
      if (to < from) {
        addToast({ type: 'error', title: 'Validation Error', message: 'The range must end at or after where it starts.' });
        return;
      }
      // A typo like 1–500 would fire 500 requests, so cap what one submit can do.
      if (to - from + 1 > 50) {
        addToast({ type: 'error', title: 'Validation Error', message: 'A range can add at most 50 lanes at a time.' });
        return;
      }
      numbers = Array.from({ length: to - from + 1 }, (_, i) => from + i);
    }

    const plazaId = Number(addForm.plaza);
    setIsAdding(true);
    // Sequential rather than parallel: the results are reported per lane number,
    // and a range is small enough that the extra round trips do not matter.
    const created: number[] = [];
    const failed: { lane: number; reason: string }[] = [];
    for (const lane_number of numbers) {
      try {
        await tollsApi.adminCreateLane(plazaId, { lane_number, is_active: addForm.is_active });
        created.push(lane_number);
      } catch (err: unknown) {
        failed.push({ lane: lane_number, reason: err instanceof Error ? err.message : 'Error' });
      }
    }
    setIsAdding(false);

    const plazaName = plazas.find((p) => p.id === plazaId)?.name ?? 'plaza';
    if (created.length) {
      addToast({
        type: 'success',
        title: created.length > 1 ? 'Lanes Added' : 'Lane Added',
        message: `Lane${created.length > 1 ? 's' : ''} ${created.join(', ')} added to ${plazaName}.`,
      });
    }
    if (failed.length) {
      addToast({
        type: 'error',
        title: created.length ? 'Some Lanes Skipped' : 'Failed',
        message: failed.map((f) => `Lane ${f.lane}: ${f.reason}`).join(' '),
      });
    }
    if (created.length) setShowAddModal(false);
    fetchData();
  };

  const handleToggleLane = async (lane: LaneRow) => {
    setTogglingIds((ids) => [...ids, lane.id]);
    try {
      await tollsApi.adminUpdateLane(lane.id, { is_active: !lane.is_active });
      addToast({
        type: 'success',
        title: 'Updated',
        message: `${lane.plazaName} lane ${lane.lane_number} is now ${!lane.is_active ? 'active' : 'inactive'}.`,
      });
      fetchData();
    } catch (err: unknown) {
      addToast({ type: 'error', title: 'Failed', message: err instanceof Error ? err.message : 'Error' });
    } finally {
      setTogglingIds((ids) => ids.filter((id) => id !== lane.id));
    }
  };

  const openEditLane = (lane: LaneRow) => {
    setEditLane(lane);
    setEditForm({ lane_number: String(lane.lane_number), is_active: lane.is_active });
  };

  const handleSaveLane = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editLane) return;
    const n = Number(editForm.lane_number);
    if (!editForm.lane_number || !Number.isInteger(n) || n < 1) {
      addToast({ type: 'error', title: 'Validation Error', message: 'Lane number must be a whole number of 1 or more.' });
      return;
    }
    setIsSaving(true);
    try {
      await tollsApi.adminUpdateLane(editLane.id, { lane_number: n, is_active: editForm.is_active });
      addToast({ type: 'success', title: 'Updated', message: `Lane ${n} saved.` });
      setEditLane(null);
      fetchData();
    } catch (err: unknown) {
      addToast({ type: 'error', title: 'Failed', message: err instanceof Error ? err.message : 'Error' });
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteLane = async () => {
    if (!confirmDelete) return;
    setIsDeleting(true);
    try {
      await tollsApi.adminDeleteLane(confirmDelete.id);
      addToast({
        type: 'success',
        title: 'Deleted',
        message: `Lane ${confirmDelete.lane_number} removed from ${confirmDelete.plazaName}.`,
      });
      setConfirmDelete(null);
      fetchData();
    } catch (err: unknown) {
      addToast({ type: 'error', title: 'Failed', message: err instanceof Error ? err.message : 'Error' });
    } finally {
      setIsDeleting(false);
    }
  };

  const inputClass = 'w-full px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all';

  return (
    <div className="animate-fade-in-up">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-ink">Lane Management</h1>
          <p className="text-sm text-ink-muted mt-1">
            Add and configure the lanes / booths that each plaza operates
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={fetchData}
            className="flex items-center gap-2 px-4 py-2.5 bg-elevated border border-line text-ink-muted text-sm font-medium rounded-xl hover:bg-surface transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
          <button
            onClick={() => openAddModal()}
            disabled={plazas.length === 0}
            className="flex items-center gap-2 px-4 py-2.5 bg-brand text-brand-on text-sm font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-60"
          >
            <Plus className="w-4 h-4" />
            Add Lane
          </button>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Total Lanes', value: stats.total, icon: SignpostBig, tone: 'text-ink' },
          { label: 'Active', value: stats.active, icon: ToggleRight, tone: 'text-success' },
          { label: 'Inactive', value: stats.inactive, icon: ToggleLeft, tone: 'text-ink-subtle' },
          { label: 'Plazas Without Lanes', value: stats.plazasWithoutLanes, icon: LayoutGrid, tone: 'text-ink' },
        ].map(({ label, value, icon: Icon, tone }) => (
          <div key={label} className="bg-surface border border-line rounded-xl skeu-card p-4">
            <div className="flex items-center gap-2 text-ink-muted mb-2">
              <Icon className="w-4 h-4" />
              <span className="text-xs font-medium uppercase tracking-wider">{label}</span>
            </div>
            <p className={`text-2xl font-bold ${tone}`}>{loading ? '—' : value}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="bg-surface border border-line rounded-xl skeu-card p-4 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="relative md:col-span-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-subtle" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search lane number or plaza..."
              className="w-full pl-10 pr-4 py-2.5 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
            />
          </div>
          <select
            value={plazaFilter}
            onChange={(e) => setPlazaFilter(e.target.value === 'all' ? 'all' : Number(e.target.value))}
            className="w-full px-4 py-2.5 bg-elevated border border-line rounded-xl text-sm text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
          >
            <option value="all">All plazas</option>
            {plazas.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({formatPlazaId(p.plaza_id)})
              </option>
            ))}
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as 'all' | 'active' | 'inactive')}
            className="w-full px-4 py-2.5 bg-elevated border border-line rounded-xl text-sm text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
          >
            <option value="all">All statuses</option>
            <option value="active">Active only</option>
            <option value="inactive">Inactive only</option>
          </select>
        </div>
      </div>

      {/* Lanes grouped by plaza */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-brand" />
        </div>
      ) : groups.length === 0 ? (
        <div className="bg-surface border border-line rounded-xl skeu-card p-12 text-center">
          <SignpostBig className="w-12 h-12 text-ink-subtle mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-ink mb-2">
            {plazas.length === 0 ? 'No plazas configured' : 'No lanes found'}
          </h3>
          <p className="text-sm text-ink-muted">
            {plazas.length === 0
              ? 'Create a plaza first, then come back to add its lanes.'
              : 'Try adjusting your search or filters.'}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {groups.map(({ plaza, lanes }) => (
            <div key={plaza.id} className="bg-surface border border-line rounded-xl skeu-card overflow-hidden">
              <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 border-b border-line">
                <div className="flex items-center gap-3">
                  <div className={`p-2.5 rounded-lg ${plaza.is_active ? 'bg-success/10' : 'bg-elevated'}`}>
                    <MapPin className={`w-5 h-5 ${plaza.is_active ? 'text-success' : 'text-ink-subtle'}`} />
                  </div>
                  <div>
                    <h3 className="text-base font-semibold text-ink">{plaza.name}</h3>
                    <p className="text-xs text-ink-muted font-mono mt-0.5">ID {formatPlazaId(plaza.plaza_id)}</p>
                  </div>
                  {!plaza.is_active && (
                    <span className="px-2.5 py-1 rounded-full text-xs font-medium border bg-elevated text-ink-subtle border-line">
                      Plaza inactive
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-ink-muted bg-elevated px-3 py-1 rounded-full">
                    {(plaza.lanes || []).filter((l) => l.is_active).length} active
                    {' / '}
                    {(plaza.lanes || []).length} lane{(plaza.lanes || []).length !== 1 ? 's' : ''}
                  </span>
                  <button
                    onClick={() => openAddModal(plaza)}
                    className="flex items-center gap-2 px-3 py-2 bg-elevated border border-line text-ink text-sm font-medium rounded-xl hover:bg-surface transition-colors"
                  >
                    <Plus className="w-4 h-4" />
                    Add Lane
                  </button>
                </div>
              </div>

              {lanes.length === 0 ? (
                <p className="px-5 py-6 text-sm text-ink-subtle text-center">
                  {(plaza.lanes || []).length === 0
                    ? 'No lanes added yet for this plaza.'
                    : 'No lanes match the current search or filters.'}
                </p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3 p-5">
                  {lanes.map((lane) => {
                    const row: LaneRow = {
                      ...lane,
                      plazaId: plaza.id,
                      plazaName: plaza.name,
                      plazaDisplayId: formatPlazaId(plaza.plaza_id),
                      plazaActive: plaza.is_active,
                    };
                    return (
                      <div
                        key={lane.id}
                        className={`flex items-center justify-between gap-3 p-3 rounded-xl border ${
                          lane.is_active ? 'border-success/20 bg-success/5' : 'border-line bg-elevated'
                        }`}
                      >
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-ink">Lane {lane.lane_number}</p>
                          <p className={`text-xs mt-0.5 ${lane.is_active ? 'text-success' : 'text-ink-subtle'}`}>
                            {lane.is_active ? 'Active' : 'Inactive'}
                          </p>
                        </div>
                        <div className="flex items-center gap-1 shrink-0">
                          <button
                            onClick={() => handleToggleLane(row)}
                            disabled={togglingIds.includes(lane.id)}
                            className="p-1.5 rounded-lg hover:bg-elevated text-ink-subtle transition-colors disabled:opacity-60"
                            title={lane.is_active ? 'Deactivate lane' : 'Activate lane'}
                          >
                            {togglingIds.includes(lane.id)
                              ? <Loader2 className="w-5 h-5 animate-spin" />
                              : lane.is_active
                                ? <ToggleRight className="w-5 h-5 text-success" />
                                : <ToggleLeft className="w-5 h-5" />}
                          </button>
                          <button
                            onClick={() => openEditLane(row)}
                            className="p-1.5 rounded-lg hover:bg-elevated text-ink-subtle transition-colors"
                            title="Edit lane"
                          >
                            <Pencil className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => setConfirmDelete(row)}
                            className="p-1.5 rounded-lg hover:bg-danger/10 text-ink-subtle hover:text-danger transition-colors"
                            title="Delete lane"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Add Lane Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in-up">
          <div className="bg-surface border border-line rounded-2xl skeu-card w-full max-w-md">
            <div className="flex items-center justify-between px-6 py-4 border-b border-line">
              <div>
                <h2 className="text-lg font-semibold text-ink">Add Lane / Booth</h2>
                <p className="text-xs text-ink-muted mt-0.5">Add one lane, or a run of consecutive lanes</p>
              </div>
              <button onClick={() => setShowAddModal(false)} className="p-1.5 rounded-lg hover:bg-elevated text-ink-subtle">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleAddLanes} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-ink mb-1.5">
                  Plaza <span className="text-danger">*</span>
                </label>
                <select
                  value={addForm.plaza}
                  onChange={(e) => setAddForm((f) => ({ ...f, plaza: e.target.value ? Number(e.target.value) : '' }))}
                  className={inputClass}
                >
                  <option value="">Select plaza</option>
                  {plazas.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({formatPlazaId(p.plaza_id)})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-2">
                {(['single', 'range'] as const).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => setAddForm((f) => ({ ...f, mode }))}
                    className={`py-2.5 text-sm font-medium rounded-xl border transition-colors ${
                      addForm.mode === mode
                        ? 'bg-brand text-brand-on border-brand'
                        : 'bg-elevated text-ink-muted border-line hover:bg-surface'
                    }`}
                  >
                    {mode === 'single' ? 'Single lane' : 'Range of lanes'}
                  </button>
                ))}
              </div>

              {addForm.mode === 'single' ? (
                <div>
                  <label className="block text-sm font-medium text-ink mb-1.5">
                    Lane Number <span className="text-danger">*</span>
                  </label>
                  <input
                    type="number"
                    min={1}
                    step={1}
                    value={addForm.lane_number}
                    onChange={(e) => setAddForm((f) => ({ ...f, lane_number: e.target.value }))}
                    placeholder="1"
                    className={inputClass}
                  />
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-ink mb-1.5">
                      From <span className="text-danger">*</span>
                    </label>
                    <input
                      type="number"
                      min={1}
                      step={1}
                      value={addForm.range_from}
                      onChange={(e) => setAddForm((f) => ({ ...f, range_from: e.target.value }))}
                      placeholder="1"
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-ink mb-1.5">
                      To <span className="text-danger">*</span>
                    </label>
                    <input
                      type="number"
                      min={1}
                      step={1}
                      value={addForm.range_to}
                      onChange={(e) => setAddForm((f) => ({ ...f, range_to: e.target.value }))}
                      placeholder="6"
                      className={inputClass}
                    />
                  </div>
                  <p className="col-span-2 text-xs text-ink-subtle">
                    Lane numbers that already exist at this plaza are skipped and reported.
                  </p>
                </div>
              )}

              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={addForm.is_active}
                  onChange={(e) => setAddForm((f) => ({ ...f, is_active: e.target.checked }))}
                  className="w-4 h-4 cursor-pointer accent-brand"
                />
                <span className="text-sm text-ink">Activate immediately</span>
              </label>

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="flex-1 py-2.5 bg-elevated border border-line text-ink text-sm font-medium rounded-xl hover:bg-surface transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isAdding}
                  className="flex-1 py-2.5 bg-brand text-brand-on text-sm font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-60 flex items-center justify-center gap-2"
                >
                  {isAdding ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                  {addForm.mode === 'range' ? 'Add Lanes' : 'Add Lane'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Lane Modal */}
      {editLane && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in-up">
          <div className="bg-surface border border-line rounded-2xl skeu-card w-full max-w-sm">
            <div className="flex items-center justify-between px-6 py-4 border-b border-line">
              <div>
                <h2 className="text-lg font-semibold text-ink">Edit Lane</h2>
                <p className="text-xs text-ink-muted mt-0.5">
                  {editLane.plazaName} · ID {editLane.plazaDisplayId}
                </p>
              </div>
              <button onClick={() => setEditLane(null)} className="p-1.5 rounded-lg hover:bg-elevated text-ink-subtle">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleSaveLane} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-ink mb-1.5">
                  Lane Number <span className="text-danger">*</span>
                </label>
                <input
                  type="number"
                  min={1}
                  step={1}
                  value={editForm.lane_number}
                  onChange={(e) => setEditForm((f) => ({ ...f, lane_number: e.target.value }))}
                  className={inputClass}
                />
                <p className="text-xs text-ink-subtle mt-1.5">
                  The number booth hardware reports for this lane — change it only if the lane was mislabelled.
                </p>
              </div>
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={editForm.is_active}
                  onChange={(e) => setEditForm((f) => ({ ...f, is_active: e.target.checked }))}
                  className="w-4 h-4 cursor-pointer accent-brand"
                />
                <span className="text-sm text-ink">Lane is active</span>
              </label>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setEditLane(null)}
                  className="flex-1 py-2.5 bg-elevated border border-line text-ink text-sm font-medium rounded-xl hover:bg-surface transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSaving}
                  className="flex-1 py-2.5 bg-brand text-brand-on text-sm font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-60 flex items-center justify-center gap-2"
                >
                  {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Pencil className="w-4 h-4" />}
                  Save
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Lane Confirm */}
      {confirmDelete && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 animate-fade-in-up"
          onClick={() => setConfirmDelete(null)}
        >
          <div className="bg-surface border border-line rounded-2xl skeu-card w-full max-w-sm p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-danger/10 rounded-full flex items-center justify-center">
                <Trash2 className="w-5 h-5 text-danger" />
              </div>
              <div>
                <p className="font-semibold text-ink">Delete Lane</p>
                <p className="text-xs text-ink-muted">
                  {confirmDelete.plazaName} · Lane {confirmDelete.lane_number}
                </p>
              </div>
            </div>
            <p className="text-sm text-ink-muted mb-5">
              This permanently removes the lane. Lanes with recorded traffic cannot be deleted — deactivate them instead.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setConfirmDelete(null)}
                className="flex-1 py-2.5 bg-elevated border border-line text-sm font-medium text-ink rounded-xl hover:bg-surface transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteLane}
                disabled={isDeleting}
                className="flex-1 py-2.5 bg-danger-solid text-white text-sm font-semibold rounded-xl hover:opacity-90 transition-opacity disabled:opacity-60 flex items-center justify-center gap-2"
              >
                {isDeleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
