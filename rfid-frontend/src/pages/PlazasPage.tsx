import { useState, useEffect, useMemo } from 'react';
import { tollsApi } from '@/services/api';
import { formatPlazaId } from '@/lib/utils';
import type { Plaza, TollRate, Lane, VehicleCategory } from '@/types';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import {
  MapPin,
  Search,
  ChevronDown,
  ChevronUp,
  Loader2,
  RefreshCw,
  Activity,
  Plus,
  X,
  ToggleLeft,
  ToggleRight,
  DollarSign,
  Trash2,
  Pencil,
} from 'lucide-react';

export default function PlazasPage() {
  const { addToast } = useToast();
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  const [plazas, setPlazas] = useState<Plaza[]>([]);
  const [rates, setRates] = useState<TollRate[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingRates, setLoadingRates] = useState(true);
  const [search, setSearch] = useState('');
  const [expandedPlaza, setExpandedPlaza] = useState<string | null>(null);

  // Add Plaza modal
  const [showPlazaModal, setShowPlazaModal] = useState(false);
  const [plazaForm, setPlazaForm] = useState({ name: '', plaza_id: '', latitude: '', longitude: '' });
  const [isCreatingPlaza, setIsCreatingPlaza] = useState(false);

  // Add Lane modal
  const [laneTarget, setLaneTarget] = useState<Plaza | null>(null);
  const [laneForm, setLaneForm] = useState({ lane_number: '' });
  const [isCreatingLane, setIsCreatingLane] = useState(false);

  // Add/Edit Rate modal
  const [showRateModal, setShowRateModal] = useState(false);
  const [editingRateId, setEditingRateId] = useState<string | null>(null);
  const [categories, setCategories] = useState<VehicleCategory[]>([]);
  const [rateForm, setRateForm] = useState({
    from_plaza: '',
    to_plaza: '',
    category: 1,
    fare: '',
  });
  const [isCreatingRate, setIsCreatingRate] = useState(false);

  // Edit plaza name
  const [editPlaza, setEditPlaza] = useState<Plaza | null>(null);
  const [editPlazaName, setEditPlazaName] = useState('');
  const [isSavingPlaza, setIsSavingPlaza] = useState(false);

  // Delete confirmation
  const [confirmDeletePlaza, setConfirmDeletePlaza] = useState<Plaza | null>(null);
  const [confirmDeleteRate, setConfirmDeleteRate] = useState<TollRate | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    setLoadingRates(true);
    try {
      const [plazasData, ratesData, categoriesData] = await Promise.allSettled([
        isAdmin ? tollsApi.adminPlazas() : tollsApi.plazas(),
        tollsApi.rates(),
        tollsApi.vehicleCategories(),
      ]);
      if (plazasData.status === 'fulfilled') setPlazas(plazasData.value);
      else addToast({ type: 'error', title: 'Error', message: 'Failed to load plazas' });
      if (ratesData.status === 'fulfilled') setRates(ratesData.value);
      else addToast({ type: 'error', title: 'Error', message: 'Failed to load fares' });
      // Categories drive the fare editor's dropdown; without them a fare cannot
      // be created, so surface the failure rather than showing an empty select.
      if (categoriesData.status === 'fulfilled') setCategories(categoriesData.value);
      else addToast({ type: 'error', title: 'Error', message: 'Failed to load vehicle categories' });
    } finally {
      setLoading(false);
      setLoadingRates(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const filteredPlazas = useMemo(() => {
    const s = search.toLowerCase();
    return plazas.filter(p => p.name.toLowerCase().includes(s) || String(p.plaza_id).includes(s) || formatPlazaId(p.plaza_id).includes(s));
  }, [plazas, search]);

  const toggleExpand = (id: string) => setExpandedPlaza(expandedPlaza === id ? null : id);

  const handleCreatePlaza = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!plazaForm.name.trim() || !plazaForm.plaza_id.trim()) {
      addToast({ type: 'error', title: 'Validation Error', message: 'Name and plaza ID are required.' });
      return;
    }
    const plazaIdNumber = Number(plazaForm.plaza_id);
    if (!Number.isInteger(plazaIdNumber) || plazaIdNumber < 0) {
      addToast({ type: 'error', title: 'Validation Error', message: 'Plaza ID must be a whole number.' });
      return;
    }
    setIsCreatingPlaza(true);
    try {
      await tollsApi.adminCreatePlaza({
        name: plazaForm.name.trim(),
        plaza_id: plazaIdNumber,
        latitude: plazaForm.latitude || undefined,
        longitude: plazaForm.longitude || undefined,
        is_active: true,
      });
      addToast({ type: 'success', title: 'Plaza Created', message: `${plazaForm.name} added.` });
      setShowPlazaModal(false);
      setPlazaForm({ name: '', plaza_id: '', latitude: '', longitude: '' });
      fetchData();
    } catch (err: unknown) {
      addToast({ type: 'error', title: 'Failed', message: err instanceof Error ? err.message : 'Error' });
    } finally {
      setIsCreatingPlaza(false);
    }
  };

  const handleAddLane = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!laneTarget || !laneForm.lane_number) {
      addToast({ type: 'error', title: 'Validation Error', message: 'Lane number is required.' });
      return;
    }
    setIsCreatingLane(true);
    try {
      await tollsApi.adminCreateLane(laneTarget.id, {
        lane_number: parseInt(laneForm.lane_number),
        is_active: true,
      });
      addToast({ type: 'success', title: 'Lane Added', message: `Lane ${laneForm.lane_number} added to ${laneTarget.name}.` });
      setLaneTarget(null);
      setLaneForm({ lane_number: '' });
      fetchData();
    } catch (err: unknown) {
      addToast({ type: 'error', title: 'Failed', message: err instanceof Error ? err.message : 'Error' });
    } finally {
      setIsCreatingLane(false);
    }
  };

  const handleTogglePlaza = async (plaza: Plaza) => {
    try {
      await tollsApi.adminUpdatePlaza(plaza.id, { is_active: !plaza.is_active });
      addToast({ type: 'success', title: 'Updated', message: `${plaza.name} is now ${!plaza.is_active ? 'active' : 'inactive'}.` });
      fetchData();
    } catch (err: unknown) {
      addToast({ type: 'error', title: 'Failed', message: err instanceof Error ? err.message : 'Error' });
    }
  };

  const handleSavePlazaName = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editPlaza || !editPlazaName.trim()) return;
    setIsSavingPlaza(true);
    try {
      await tollsApi.adminUpdatePlaza(editPlaza.id, { name: editPlazaName.trim() });
      addToast({ type: 'success', title: 'Updated', message: 'Plaza name updated.' });
      setEditPlaza(null);
      fetchData();
    } catch (err: unknown) {
      addToast({ type: 'error', title: 'Failed', message: err instanceof Error ? err.message : 'Error' });
    } finally {
      setIsSavingPlaza(false);
    }
  };

  const handleDeletePlaza = async () => {
    if (!confirmDeletePlaza) return;
    setIsDeleting(true);
    try {
      await tollsApi.adminDeletePlaza(confirmDeletePlaza.id);
      addToast({ type: 'success', title: 'Deleted', message: `${confirmDeletePlaza.name} removed.` });
      setConfirmDeletePlaza(null);
      fetchData();
    } catch (err: unknown) {
      addToast({ type: 'error', title: 'Failed', message: err instanceof Error ? err.message : 'Error' });
    } finally {
      setIsDeleting(false);
    }
  };

  const handleDeleteRate = async () => {
    if (!confirmDeleteRate) return;
    setIsDeleting(true);
    try {
      await tollsApi.adminDeleteRate(confirmDeleteRate.id);
      addToast({ type: 'success', title: 'Deleted', message: 'Toll rate removed.' });
      setConfirmDeleteRate(null);
      fetchData();
    } catch (err: unknown) {
      addToast({ type: 'error', title: 'Failed', message: err instanceof Error ? err.message : 'Error' });
    } finally {
      setIsDeleting(false);
    }
  };

  const closeRateModal = () => {
    setShowRateModal(false);
    setEditingRateId(null);
    setRateForm({ from_plaza: '', to_plaza: '', category: categories[0]?.category_index ?? 1, fare: '' });
  };

  const openEditRate = (rate: TollRate) => {
    setEditingRateId(rate.id);
    setRateForm({
      from_plaza: rate.from_plaza,
      to_plaza: rate.to_plaza,
      category: rate.category,
      fare: rate.fare,
    });
    setShowRateModal(true);
  };

  const handleSaveRate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rateForm.from_plaza || !rateForm.to_plaza || !rateForm.fare) {
      addToast({ type: 'error', title: 'Validation Error', message: 'All fields are required.' });
      return;
    }
    setIsCreatingRate(true);
    try {
      if (editingRateId) {
        await tollsApi.adminUpdateRate(editingRateId, rateForm);
        addToast({ type: 'success', title: 'Rate Updated', message: 'Toll rate has been updated.' });
      } else {
        await tollsApi.adminCreateRate(rateForm);
        addToast({ type: 'success', title: 'Rate Created', message: 'Toll rate has been configured.' });
      }
      closeRateModal();
      fetchData();
    } catch (err: unknown) {
      addToast({ type: 'error', title: 'Failed', message: err instanceof Error ? err.message : 'Error' });
    } finally {
      setIsCreatingRate(false);
    }
  };

  return (
    <div className="animate-fade-in-up">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Plazas & Rates</h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            {plazas.length} plazas configured in the system
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={fetchData}
            className="flex items-center gap-2 px-4 py-2.5 bg-[var(--bg-elevated)] border border-[var(--border-custom)] text-[var(--text-secondary)] text-sm font-medium rounded-xl hover:bg-[var(--bg-surface)] transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
          {isAdmin && (
            <button
              onClick={() => setShowPlazaModal(true)}
              className="flex items-center gap-2 px-4 py-2.5 bg-[var(--accent-blue)] text-white text-sm font-medium rounded-xl hover:opacity-90 transition-opacity"
            >
              <Plus className="w-4 h-4" />
              Add Plaza
            </button>
          )}
        </div>
      </div>

      {/* Search */}
      <div className="bg-[var(--bg-surface)] border border-[var(--border-custom)] rounded-xl p-4 mb-6 shadow-sm">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-tertiary)]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by plaza name or ID..."
            className="w-full pl-10 pr-4 py-2.5 bg-[var(--bg-elevated)] border border-[var(--border-custom)] rounded-xl text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] outline-none focus:border-[var(--accent-blue)] focus:ring-2 focus:ring-[var(--accent-blue)]/20 transition-all"
          />
        </div>
      </div>

      {/* Plazas */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-[var(--accent-blue)]" />
        </div>
      ) : filteredPlazas.length === 0 ? (
        <div className="bg-[var(--bg-surface)] border border-[var(--border-custom)] rounded-xl p-12 text-center shadow-sm mb-8">
          <MapPin className="w-12 h-12 text-[var(--text-tertiary)] mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-2">No plazas found</h3>
          <p className="text-sm text-[var(--text-secondary)]">
            {search ? 'Try adjusting your search.' : 'No plazas configured yet.'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8">
          {filteredPlazas.map((plaza) => (
            <div key={plaza.id} className="bg-[var(--bg-surface)] border border-[var(--border-custom)] rounded-xl shadow-sm overflow-hidden">
              <div className="p-5">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3">
                    <div className={`p-2.5 rounded-lg mt-0.5 ${plaza.is_active ? 'bg-[var(--accent-emerald)]/10' : 'bg-[var(--bg-elevated)]'}`}>
                      <MapPin className={`w-5 h-5 ${plaza.is_active ? 'text-[var(--accent-emerald)]' : 'text-[var(--text-tertiary)]'}`} />
                    </div>
                    <div>
                      <h3 className="text-base font-semibold text-[var(--text-primary)]">{plaza.name}</h3>
                      <p className="text-xs text-[var(--text-secondary)] font-mono mt-0.5">ID {formatPlazaId(plaza.plaza_id)}</p>
                      {(plaza.latitude || plaza.longitude) && (
                        <p className="text-xs text-[var(--text-tertiary)] mt-1">{plaza.latitude}, {plaza.longitude}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`px-2.5 py-1 rounded-full text-xs font-medium border ${
                      plaza.is_active
                        ? 'bg-[var(--accent-emerald)]/10 text-[var(--accent-emerald)] border-[var(--accent-emerald)]/20'
                        : 'bg-[var(--bg-elevated)] text-[var(--text-tertiary)] border-[var(--border-custom)]'
                    }`}>
                      {plaza.is_active ? 'Active' : 'Inactive'}
                    </span>
                    {isAdmin && (
                      <>
                        <button
                          onClick={() => { setEditPlaza(plaza); setEditPlazaName(plaza.name); }}
                          className="p-1.5 rounded-lg hover:bg-[var(--bg-elevated)] text-[var(--text-tertiary)] transition-colors"
                          title="Edit name"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleTogglePlaza(plaza)}
                          className="p-1.5 rounded-lg hover:bg-[var(--bg-elevated)] text-[var(--text-tertiary)] transition-colors"
                          title={plaza.is_active ? 'Deactivate' : 'Activate'}
                        >
                          {plaza.is_active
                            ? <ToggleRight className="w-5 h-5 text-[var(--accent-emerald)]" />
                            : <ToggleLeft className="w-5 h-5" />
                          }
                        </button>
                        <button
                          onClick={() => setConfirmDeletePlaza(plaza)}
                          className="p-1.5 rounded-lg hover:bg-[var(--accent-rose)]/10 text-[var(--text-tertiary)] hover:text-[var(--accent-rose)] transition-colors"
                          title="Delete plaza"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-4 mt-4">
                  <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                    <Activity className="w-3.5 h-3.5" />
                    <span>{plaza.lanes?.length || 0} lanes</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-[var(--accent-emerald)]">
                    <span className="w-2 h-2 rounded-full bg-[var(--accent-emerald)]" />
                    <span>{plaza.lanes?.filter((l: Lane) => l.is_active).length || 0} active</span>
                  </div>
                  {isAdmin && (
                    <button
                      onClick={() => { setLaneTarget(plaza); setLaneForm({ lane_number: '' }); }}
                      className="flex items-center gap-1 text-xs text-[var(--accent-blue)] hover:underline"
                    >
                      <Plus className="w-3 h-3" />
                      Add Lane
                    </button>
                  )}
                  <button
                    onClick={() => toggleExpand(plaza.id)}
                    className="ml-auto flex items-center gap-1 text-xs text-[var(--accent-blue)] hover:underline"
                  >
                    {expandedPlaza === plaza.id
                      ? <>Hide Lanes <ChevronUp className="w-3.5 h-3.5" /></>
                      : <>View Lanes <ChevronDown className="w-3.5 h-3.5" /></>
                    }
                  </button>
                </div>
              </div>

              {expandedPlaza === plaza.id && (
                <div className="border-t border-[var(--border-custom)] bg-[var(--bg-elevated)] animate-fade-in-up">
                  <div className="px-5 py-3">
                    <p className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3">Lanes / Booths</p>
                    {plaza.lanes && plaza.lanes.length > 0 ? (
                      <div className="grid grid-cols-2 gap-2">
                        {plaza.lanes.map((lane: Lane) => (
                          <div
                            key={lane.id}
                            className={`flex items-center justify-between p-3 rounded-lg border ${
                              lane.is_active
                                ? 'border-[var(--accent-emerald)]/20 bg-[var(--accent-emerald)]/5'
                                : 'border-[var(--border-custom)] bg-[var(--bg-body)]'
                            }`}
                          >
                            <div>
                              <p className="text-sm font-semibold text-[var(--text-primary)]">Booth {lane.lane_number}</p>
                            </div>
                            <span className={`text-xs font-medium ${lane.is_active ? 'text-[var(--accent-emerald)]' : 'text-[var(--text-tertiary)]'}`}>
                              {lane.is_active ? 'Active' : 'Off'}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-[var(--text-tertiary)] py-2">No lanes added yet.</p>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Toll Rates Table */}
      <div className="bg-[var(--bg-surface)] border border-[var(--border-custom)] rounded-xl shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-6 py-5 border-b border-[var(--border-custom)]">
          <div>
            <h3 className="text-base font-semibold text-[var(--text-primary)]">Toll Rates</h3>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              Rate is looked up by entry plaza → exit plaza + vehicle type at exit.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-[var(--text-secondary)] bg-[var(--bg-elevated)] px-3 py-1 rounded-full">
              {rates.length} rate{rates.length !== 1 ? 's' : ''}
            </span>
            {isAdmin && (
              <button
                onClick={() => { setEditingRateId(null); setShowRateModal(true); }}
                className="flex items-center gap-2 px-4 py-2 bg-[var(--accent-emerald)] text-white text-sm font-medium rounded-xl hover:opacity-90 transition-opacity"
              >
                <Plus className="w-4 h-4" />
                Add Rate
              </button>
            )}
          </div>
        </div>
        {loadingRates ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-[var(--accent-blue)]" />
          </div>
        ) : rates.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <p className="text-sm text-[var(--text-secondary)]">No toll rates configured.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-[var(--bg-elevated)]">
                  <th className="text-left px-6 py-3 text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">From Plaza</th>
                  <th className="text-left px-6 py-3 text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">To Plaza</th>
                  <th className="text-left px-6 py-3 text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Category</th>
                  <th className="text-right px-6 py-3 text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Fare (PKR)</th>
                  <th className="text-left px-6 py-3 text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Updated</th>
                  {isAdmin && <th className="px-6 py-3" />}
                </tr>
              </thead>
              <tbody>
                {rates.map((rate) => (
                  <tr key={rate.id} className="border-b border-[var(--border-custom)] hover:bg-[var(--bg-elevated)] transition-colors">
                    <td className="px-6 py-4 text-sm text-[var(--text-primary)]">{rate.from_plaza_display_id} {rate.from_plaza_name}</td>
                    <td className="px-6 py-4 text-sm text-[var(--text-secondary)]">{rate.to_plaza_display_id} {rate.to_plaza_name}</td>
                    <td className="px-6 py-4">
                      <span className="text-xs bg-[var(--bg-elevated)] text-[var(--text-secondary)] px-2.5 py-1 rounded-full border border-[var(--border-custom)] capitalize">
                        {rate.category_name}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm font-semibold text-[var(--text-primary)] text-right">
                      {parseFloat(rate.fare).toLocaleString()}
                    </td>
                    <td className="px-6 py-4 text-sm text-[var(--text-secondary)]">
                      {rate.updated_at ? new Date(rate.updated_at).toLocaleDateString('en-PK') : '—'}
                    </td>
                    {isAdmin && (
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => openEditRate(rate)}
                            className="p-1.5 rounded-lg hover:bg-[var(--bg-elevated)] text-[var(--text-tertiary)] transition-colors"
                            title="Edit rate"
                          >
                            <Pencil className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => setConfirmDeleteRate(rate)}
                            className="p-1.5 rounded-lg hover:bg-[var(--accent-rose)]/10 text-[var(--text-tertiary)] hover:text-[var(--accent-rose)] transition-colors"
                            title="Delete rate"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add Plaza Modal */}
      {showPlazaModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in-up">
          <div className="bg-[var(--bg-surface)] border border-[var(--border-custom)] rounded-2xl shadow-2xl w-full max-w-md">
            <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-custom)]">
              <h2 className="text-lg font-semibold text-[var(--text-primary)]">Add New Plaza</h2>
              <button onClick={() => setShowPlazaModal(false)} className="p-1.5 rounded-lg hover:bg-[var(--bg-elevated)] text-[var(--text-tertiary)]">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleCreatePlaza} className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2">
                  <label className="block text-sm font-medium text-[var(--text-primary)] mb-1.5">
                    Plaza Name <span className="text-[var(--accent-rose)]">*</span>
                  </label>
                  <input
                    type="text"
                    value={plazaForm.name}
                    onChange={(e) => setPlazaForm(p => ({ ...p, name: e.target.value }))}
                    placeholder="e.g. Lahore Toll Plaza"
                    className="w-full px-4 py-3 bg-[var(--bg-elevated)] border border-[var(--border-custom)] rounded-xl text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] outline-none focus:border-[var(--accent-blue)] focus:ring-2 focus:ring-[var(--accent-blue)]/20 transition-all"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-[var(--text-primary)] mb-1.5">
                    Plaza ID <span className="text-[var(--accent-rose)]">*</span>
                  </label>
                  <input
                    type="number"
                    min={0}
                    step={1}
                    value={plazaForm.plaza_id}
                    onChange={(e) => setPlazaForm(p => ({ ...p, plaza_id: e.target.value }))}
                    placeholder="3"
                    className="w-full px-4 py-3 bg-[var(--bg-elevated)] border border-[var(--border-custom)] rounded-xl text-sm font-mono text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] outline-none focus:border-[var(--accent-blue)] focus:ring-2 focus:ring-[var(--accent-blue)]/20 transition-all"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-[var(--text-primary)] mb-1.5">Latitude</label>
                  <input
                    type="text"
                    value={plazaForm.latitude}
                    onChange={(e) => setPlazaForm(p => ({ ...p, latitude: e.target.value }))}
                    placeholder="31.5204"
                    className="w-full px-4 py-3 bg-[var(--bg-elevated)] border border-[var(--border-custom)] rounded-xl text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] outline-none focus:border-[var(--accent-blue)] focus:ring-2 focus:ring-[var(--accent-blue)]/20 transition-all"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-[var(--text-primary)] mb-1.5">Longitude</label>
                  <input
                    type="text"
                    value={plazaForm.longitude}
                    onChange={(e) => setPlazaForm(p => ({ ...p, longitude: e.target.value }))}
                    placeholder="74.3587"
                    className="w-full px-4 py-3 bg-[var(--bg-elevated)] border border-[var(--border-custom)] rounded-xl text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] outline-none focus:border-[var(--accent-blue)] focus:ring-2 focus:ring-[var(--accent-blue)]/20 transition-all"
                  />
                </div>
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowPlazaModal(false)} className="flex-1 py-2.5 bg-[var(--bg-elevated)] border border-[var(--border-custom)] text-[var(--text-primary)] text-sm font-medium rounded-xl hover:bg-[var(--bg-surface)] transition-colors">
                  Cancel
                </button>
                <button type="submit" disabled={isCreatingPlaza} className="flex-1 py-2.5 bg-[var(--accent-blue)] text-white text-sm font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-60 flex items-center justify-center gap-2">
                  {isCreatingPlaza ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                  Create Plaza
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Rate Modal */}
      {showRateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in-up">
          <div className="bg-[var(--bg-surface)] border border-[var(--border-custom)] rounded-2xl shadow-2xl w-full max-w-lg">
            <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-custom)]">
              <div className="flex items-center gap-2">
                <DollarSign className="w-5 h-5 text-[var(--accent-emerald)]" />
                <h2 className="text-lg font-semibold text-[var(--text-primary)]">{editingRateId ? 'Edit Toll Rate' : 'Add Toll Rate'}</h2>
              </div>
              <button onClick={closeRateModal} className="p-1.5 rounded-lg hover:bg-[var(--bg-elevated)] text-[var(--text-tertiary)]">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleSaveRate} className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-[var(--text-primary)] mb-1.5">
                    Entry Plaza <span className="text-[var(--accent-rose)]">*</span>
                  </label>
                  <select
                    value={rateForm.from_plaza}
                    onChange={(e) => setRateForm(f => ({ ...f, from_plaza: e.target.value }))}
                    className="w-full px-4 py-3 bg-[var(--bg-elevated)] border border-[var(--border-custom)] rounded-xl text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)] focus:ring-2 focus:ring-[var(--accent-blue)]/20 transition-all"
                  >
                    <option value="">Select plaza</option>
                    {plazas.map(p => <option key={p.id} value={p.id}>{p.name} ({formatPlazaId(p.plaza_id)})</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-[var(--text-primary)] mb-1.5">
                    Exit Plaza <span className="text-[var(--accent-rose)]">*</span>
                  </label>
                  <select
                    value={rateForm.to_plaza}
                    onChange={(e) => setRateForm(f => ({ ...f, to_plaza: e.target.value }))}
                    className="w-full px-4 py-3 bg-[var(--bg-elevated)] border border-[var(--border-custom)] rounded-xl text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)] focus:ring-2 focus:ring-[var(--accent-blue)]/20 transition-all"
                  >
                    <option value="">Select plaza</option>
                    {plazas.filter(p => p.id !== rateForm.from_plaza).map(p => (
                      <option key={p.id} value={p.id}>{p.name} ({formatPlazaId(p.plaza_id)})</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-[var(--text-primary)] mb-1.5">
                    Vehicle Category <span className="text-[var(--accent-rose)]">*</span>
                  </label>
                  <select
                    value={rateForm.category}
                    onChange={(e) => setRateForm(f => ({ ...f, category: Number(e.target.value) }))}
                    className="w-full px-4 py-3 bg-[var(--bg-elevated)] border border-[var(--border-custom)] rounded-xl text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)] focus:ring-2 focus:ring-[var(--accent-blue)]/20 transition-all"
                  >
                    {categories.map(c => (
                      <option key={c.category_index} value={c.category_index}>
                        {c.category_index}. {c.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-[var(--text-primary)] mb-1.5">
                    Fare (PKR) <span className="text-[var(--accent-rose)]">*</span>
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={rateForm.fare}
                    onChange={(e) => setRateForm(f => ({ ...f, fare: e.target.value }))}
                    placeholder="500.00"
                    className="w-full px-4 py-3 bg-[var(--bg-elevated)] border border-[var(--border-custom)] rounded-xl text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] outline-none focus:border-[var(--accent-blue)] focus:ring-2 focus:ring-[var(--accent-blue)]/20 transition-all"
                  />
                </div>
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={closeRateModal} className="flex-1 py-2.5 bg-[var(--bg-elevated)] border border-[var(--border-custom)] text-[var(--text-primary)] text-sm font-medium rounded-xl hover:bg-[var(--bg-surface)] transition-colors">
                  Cancel
                </button>
                <button type="submit" disabled={isCreatingRate} className="flex-1 py-2.5 bg-[var(--accent-emerald)] text-white text-sm font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-60 flex items-center justify-center gap-2">
                  {isCreatingRate ? <Loader2 className="w-4 h-4 animate-spin" /> : (editingRateId ? <Pencil className="w-4 h-4" /> : <Plus className="w-4 h-4" />)}
                  {editingRateId ? 'Update Rate' : 'Save Rate'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Plaza Name Modal */}
      {editPlaza && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in-up">
          <div className="bg-[var(--bg-surface)] border border-[var(--border-custom)] rounded-2xl shadow-2xl w-full max-w-sm">
            <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-custom)]">
              <h2 className="text-lg font-semibold text-[var(--text-primary)]">Edit Plaza Name</h2>
              <button onClick={() => setEditPlaza(null)} className="p-1.5 rounded-lg hover:bg-[var(--bg-elevated)] text-[var(--text-tertiary)]">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleSavePlazaName} className="p-6 space-y-4">
              <input
                type="text"
                value={editPlazaName}
                onChange={(e) => setEditPlazaName(e.target.value)}
                placeholder="Plaza name"
                className="w-full px-4 py-3 bg-[var(--bg-elevated)] border border-[var(--border-custom)] rounded-xl text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)] focus:ring-2 focus:ring-[var(--accent-blue)]/20 transition-all"
              />
              <div className="flex gap-3">
                <button type="button" onClick={() => setEditPlaza(null)} className="flex-1 py-2.5 bg-[var(--bg-elevated)] border border-[var(--border-custom)] text-[var(--text-primary)] text-sm font-medium rounded-xl hover:bg-[var(--bg-surface)] transition-colors">Cancel</button>
                <button type="submit" disabled={isSavingPlaza || !editPlazaName.trim()} className="flex-1 py-2.5 bg-[var(--accent-blue)] text-white text-sm font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-60 flex items-center justify-center gap-2">
                  {isSavingPlaza ? <Loader2 className="w-4 h-4 animate-spin" /> : <Pencil className="w-4 h-4" />}
                  Save
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Plaza Confirm */}
      {confirmDeletePlaza && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 animate-fade-in-up" onClick={() => setConfirmDeletePlaza(null)}>
          <div className="bg-[var(--bg-surface)] border border-[var(--border-custom)] rounded-2xl shadow-2xl w-full max-w-sm p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-[var(--accent-rose)]/10 rounded-full flex items-center justify-center">
                <Trash2 className="w-5 h-5 text-[var(--accent-rose)]" />
              </div>
              <div>
                <p className="font-semibold text-[var(--text-primary)]">Delete Plaza</p>
                <p className="text-xs text-[var(--text-secondary)]">{confirmDeletePlaza.name}</p>
              </div>
            </div>
            <p className="text-sm text-[var(--text-secondary)] mb-5">This will permanently remove the plaza. Plazas with recorded trips cannot be deleted — deactivate them instead.</p>
            <div className="flex gap-3">
              <button onClick={() => setConfirmDeletePlaza(null)} className="flex-1 py-2.5 bg-[var(--bg-elevated)] border border-[var(--border-custom)] text-sm font-medium text-[var(--text-primary)] rounded-xl hover:bg-[var(--bg-surface)] transition-colors">Cancel</button>
              <button onClick={handleDeletePlaza} disabled={isDeleting} className="flex-1 py-2.5 bg-[var(--accent-rose)] text-white text-sm font-semibold rounded-xl hover:opacity-90 transition-opacity disabled:opacity-60 flex items-center justify-center gap-2">
                {isDeleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Rate Confirm */}
      {confirmDeleteRate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 animate-fade-in-up" onClick={() => setConfirmDeleteRate(null)}>
          <div className="bg-[var(--bg-surface)] border border-[var(--border-custom)] rounded-2xl shadow-2xl w-full max-w-sm p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-[var(--accent-rose)]/10 rounded-full flex items-center justify-center">
                <Trash2 className="w-5 h-5 text-[var(--accent-rose)]" />
              </div>
              <div>
                <p className="font-semibold text-[var(--text-primary)]">Delete Toll Rate</p>
                <p className="text-xs text-[var(--text-secondary)]">{confirmDeleteRate.from_plaza_name} → {confirmDeleteRate.to_plaza_name} · {confirmDeleteRate.category_name}</p>
              </div>
            </div>
            <p className="text-sm text-[var(--text-secondary)] mb-5">This rate will be permanently removed. New toll trips will not find a rate for this route until a new one is added.</p>
            <div className="flex gap-3">
              <button onClick={() => setConfirmDeleteRate(null)} className="flex-1 py-2.5 bg-[var(--bg-elevated)] border border-[var(--border-custom)] text-sm font-medium text-[var(--text-primary)] rounded-xl hover:bg-[var(--bg-surface)] transition-colors">Cancel</button>
              <button onClick={handleDeleteRate} disabled={isDeleting} className="flex-1 py-2.5 bg-[var(--accent-rose)] text-white text-sm font-semibold rounded-xl hover:opacity-90 transition-opacity disabled:opacity-60 flex items-center justify-center gap-2">
                {isDeleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Lane Modal */}
      {laneTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in-up">
          <div className="bg-[var(--bg-surface)] border border-[var(--border-custom)] rounded-2xl shadow-2xl w-full max-w-sm">
            <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-custom)]">
              <div>
                <h2 className="text-lg font-semibold text-[var(--text-primary)]">Add Lane / Booth</h2>
                <p className="text-xs text-[var(--text-secondary)] mt-0.5">{laneTarget.name}</p>
              </div>
              <button onClick={() => setLaneTarget(null)} className="p-1.5 rounded-lg hover:bg-[var(--bg-elevated)] text-[var(--text-tertiary)]">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleAddLane} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-[var(--text-primary)] mb-1.5">
                  Lane Number <span className="text-[var(--accent-rose)]">*</span>
                </label>
                <input
                  type="number"
                  min={1}
                  value={laneForm.lane_number}
                  onChange={(e) => setLaneForm(p => ({ ...p, lane_number: e.target.value }))}
                  placeholder="1"
                  className="w-full px-4 py-3 bg-[var(--bg-elevated)] border border-[var(--border-custom)] rounded-xl text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] outline-none focus:border-[var(--accent-blue)] focus:ring-2 focus:ring-[var(--accent-blue)]/20 transition-all"
                />
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setLaneTarget(null)} className="flex-1 py-2.5 bg-[var(--bg-elevated)] border border-[var(--border-custom)] text-[var(--text-primary)] text-sm font-medium rounded-xl hover:bg-[var(--bg-surface)] transition-colors">
                  Cancel
                </button>
                <button type="submit" disabled={isCreatingLane} className="flex-1 py-2.5 bg-[var(--accent-emerald)] text-white text-sm font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-60 flex items-center justify-center gap-2">
                  {isCreatingLane ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                  Add Lane
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
