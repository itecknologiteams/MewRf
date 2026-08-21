import { useState, useEffect } from 'react';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { vehiclesApi, authApi } from '@/services/api';
import { normalizePlate } from '@/lib/plate';
import type { ApiVehicle } from '@/types';
import {
  Search,
  Plus,
  Pencil,
  Car,
  Truck,
  Bus,
  Bike,
  X,
  CheckCircle,
  Loader2,
  Filter,
  RefreshCw,
  Tag,
  Upload,
  AlertTriangle,
  ShieldOff,
  ShieldCheck,
} from 'lucide-react';

const PAGE_SIZE = 12;

const vehicleIcons: Record<string, React.ElementType> = {
  car: Car,
  truck: Truck,
  bus: Bus,
  motorcycle: Bike,
};

const getVehicleIcon = (type: string) => vehicleIcons[type?.toLowerCase()] || Car;

export default function Vehicles() {
  const { addToast } = useToast();
  const { user } = useAuth();

  const [vehicles, setVehicles] = useState<ApiVehicle[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('All');
  const [statusFilter, setStatusFilter] = useState('All');
  const [showModal, setShowModal] = useState(false);
  const [editingVehicle, setEditingVehicle] = useState<ApiVehicle | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showFilters, setShowFilters] = useState(false);

  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<{ added: number; skipped: number; errors: string[]; skipped_serials: string[] } | null>(null);

  // Single tag add
  const [showAddTagModal, setShowAddTagModal] = useState(false);
  const [addTagForm, setAddTagForm] = useState({ tag_serial: '', tid: '', epc: '' });
  const [isAddingTag, setIsAddingTag] = useState(false);

  // Suspend/activate
  const [suspendTarget, setSuspendTarget] = useState<ApiVehicle | null>(null);
  const [isSuspending, setIsSuspending] = useState(false);

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);

  const [reissueVehicle, setReissueVehicle] = useState<ApiVehicle | null>(null);
  const [reissueForm, setReissueForm] = useState({ tag_serial: '' });
  const [isReissuing, setIsReissuing] = useState(false);
  const [reissueTags, setReissueTags] = useState<{ id: number; tag_serial: string; epc: string }[]>([]);
  const [reissueTagsLoading, setReissueTagsLoading] = useState(false);
  const [showReissueConfirm, setShowReissueConfirm] = useState(false);

  const [form, setForm] = useState({
    plate_number: '',
    vehicle_type: 'car',
    owner_id: '',
    owner_name: '',
    tag_serial: '',
    status: 'active',
  });

  const fetchVehicles = async (plate?: string) => {
    setLoading(true);
    try {
      const data = await vehiclesApi.list(plate ? { plate } : undefined);
      setVehicles(data as ApiVehicle[]);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load vehicles';
      addToast({ type: 'error', title: 'Error', message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVehicles();
  }, []);

  const handleAddTag = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!addTagForm.tag_serial.trim()) {
      addToast({ type: 'error', title: 'Required', message: 'Tag serial is required.' });
      return;
    }
    setIsAddingTag(true);
    try {
      await vehiclesApi.addTag({
        tag_serial: addTagForm.tag_serial.trim(),
        tid: addTagForm.tid.trim(),
        epc: addTagForm.epc.trim(),
      });
      addToast({ type: 'success', title: 'Tag Added', message: `${addTagForm.tag_serial} added to inventory.` });
      setShowAddTagModal(false);
      setAddTagForm({ tag_serial: '', tid: '', epc: '' });
    } catch (err: unknown) {
      addToast({ type: 'error', title: 'Failed', message: err instanceof Error ? err.message : 'Could not add tag' });
    } finally {
      setIsAddingTag(false);
    }
  };

  const handleSuspendToggle = async () => {
    if (!suspendTarget) return;
    setIsSuspending(true);
    const isSuspended = suspendTarget.status === 'suspended';
    try {
      const updated = isSuspended
        ? await vehiclesApi.activate(suspendTarget.id)
        : await vehiclesApi.suspend(suspendTarget.id);
      setVehicles((prev) => prev.map((v) => (v.id === updated.id ? { ...v, ...updated } : v)));
      addToast({ type: 'success', title: isSuspended ? 'Activated' : 'Suspended', message: `${suspendTarget.plate_number} has been ${isSuspended ? 'activated' : 'suspended'}.` });
      setSuspendTarget(null);
    } catch (err: unknown) {
      addToast({ type: 'error', title: 'Failed', message: err instanceof Error ? err.message : 'Operation failed' });
    } finally {
      setIsSuspending(false);
    }
  };

  const filteredVehicles = vehicles.filter((v) => {
    const s = search.toLowerCase();
    const matchesSearch =
      v.plate_number.toLowerCase().includes(s) ||
      v.owner_name?.toLowerCase().includes(s) ||
      v.owner_phone?.toLowerCase().includes(s) ||
      v.tag?.tag_serial?.toLowerCase().includes(s);
    const matchesType = typeFilter === 'All' || v.vehicle_type.toLowerCase() === typeFilter.toLowerCase();
    const matchesStatus = statusFilter === 'All' || v.status.toLowerCase() === statusFilter.toLowerCase();
    return matchesSearch && matchesType && matchesStatus;
  });

  const totalPages = Math.ceil(filteredVehicles.length / PAGE_SIZE);
  const pagedVehicles = filteredVehicles.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  const openAdd = () => {
    setEditingVehicle(null);
    setForm({
      plate_number: '',
      vehicle_type: 'car',
      owner_id: user?.id?.toString() || '',
      owner_name: '',
      tag_serial: '',
      status: 'active',
    });
    setShowModal(true);
  };

  const openEdit = (vehicle: ApiVehicle) => {
    setEditingVehicle(vehicle);
    setForm({
      plate_number: vehicle.plate_number,
      vehicle_type: vehicle.vehicle_type,
      owner_id: vehicle.owner_id?.toString() || '',
      owner_name: vehicle.owner_name || '',
      tag_serial: vehicle.tag?.tag_serial || '',
      status: vehicle.status,
    });
    setShowModal(true);
  };

  const handleUpload = async () => {
    if (!uploadFile) return;
    setIsUploading(true);
    setUploadResult(null);
    try {
      const result = await vehiclesApi.uploadTagInventory(uploadFile);
      setUploadResult(result);
      addToast({ type: 'success', title: 'Upload Complete', message: `${result.added} tag(s) added, ${result.skipped} skipped.` });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Upload failed';
      addToast({ type: 'error', title: 'Upload Failed', message });
    } finally {
      setIsUploading(false);
    }
  };

  const openReissue = async (vehicle: ApiVehicle) => {
    setReissueVehicle(vehicle);
    setReissueForm({ tag_serial: '' });
    setShowReissueConfirm(false);
    setReissueTagsLoading(true);
    try {
      const tags = await vehiclesApi.availableTags();
      setReissueTags(tags);
    } catch {
      addToast({ type: 'error', title: 'Error', message: 'Failed to load available tags.' });
    } finally {
      setReissueTagsLoading(false);
    }
  };

  const handleReissueConfirm = async () => {
    if (!reissueVehicle || !reissueForm.tag_serial) return;
    setIsReissuing(true);
    try {
      await vehiclesApi.reissueTag(reissueVehicle.id, { tag_serial: reissueForm.tag_serial });
      addToast({ type: 'success', title: 'Tag Reissued', message: 'New tag assigned. Previous tag permanently deactivated.' });
      setReissueVehicle(null);
      setReissueForm({ tag_serial: '' });
      setShowReissueConfirm(false);
      fetchVehicles();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Reissue failed';
      addToast({ type: 'error', title: 'Reissue Failed', message });
    } finally {
      setIsReissuing(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingVehicle && (!form.plate_number || !form.tag_serial)) {
      addToast({ type: 'error', title: 'Validation Error', message: 'Please fill all required fields.' });
      return;
    }
    if (!editingVehicle && !form.owner_id) {
      addToast({ type: 'error', title: 'Validation Error', message: 'Owner ID is required.' });
      return;
    }

    setIsSubmitting(true);
    try {
      if (editingVehicle) {
        if (!form.plate_number.trim()) {
          addToast({ type: 'error', title: 'Validation Error', message: 'Plate number is required.' });
          setIsSubmitting(false);
          return;
        }
        // Update the owner's name first (separate User entity) if it changed.
        const newName = form.owner_name.trim();
        if (form.owner_id && newName && newName !== (editingVehicle.owner_name || '')) {
          await authApi.adminUpdateUser(parseInt(form.owner_id), { full_name: newName });
        }
        await vehiclesApi.update(editingVehicle.id, {
          plate_number: form.plate_number.trim(),
          status: form.status,
        });
        addToast({ type: 'success', title: 'Vehicle Updated', message: 'Vehicle details updated successfully.' });
      } else {
        await vehiclesApi.create({
          plate_number: form.plate_number,
          vehicle_type: form.vehicle_type,
          owner_id: parseInt(form.owner_id),
          tag_serial: form.tag_serial,
        });
        addToast({ type: 'success', title: 'Vehicle Added', message: 'New vehicle registered successfully.' });
      }
      setShowModal(false);
      fetchVehicles();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Operation failed';
      addToast({ type: 'error', title: 'Error', message });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="animate-fade-in-up">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-ink">Vehicle Management</h1>
          <p className="text-sm text-ink-muted mt-1">
            {vehicles.length} vehicles registered in the system
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => fetchVehicles()}
            className="flex items-center gap-2 px-4 py-2.5 bg-elevated border border-line text-ink-muted text-sm font-medium rounded-xl hover:bg-surface transition-colors self-start"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
          {user?.role === 'admin' && (
            <>
              <button
                onClick={() => { setShowAddTagModal(true); setAddTagForm({ tag_serial: '', tid: '', epc: '' }); }}
                className="flex items-center gap-2 px-4 py-2.5 bg-info text-white text-sm font-medium rounded-xl hover:opacity-90 transition-opacity self-start"
              >
                <Tag className="w-4 h-4" />
                Add Tag
              </button>
              <button
                onClick={() => { setShowUploadModal(true); setUploadFile(null); setUploadResult(null); }}
                className="flex items-center gap-2 px-4 py-2.5 bg-brand text-brand-on text-sm font-medium rounded-xl hover:opacity-90 transition-opacity self-start"
              >
                <Upload className="w-4 h-4" />
                Upload Tags
              </button>
            </>
          )}
          <button
            onClick={openAdd}
            className="flex items-center gap-2 px-4 py-2.5 bg-brand text-brand-on text-sm font-medium rounded-xl hover:opacity-90 transition-opacity self-start"
          >
            <Plus className="w-4 h-4" />
            Add Vehicle
          </button>
        </div>
      </div>

      {/* Search & Filters */}
      <div className="bg-surface border border-line rounded-xl skeu-card p-4 mb-6">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-subtle" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by plate, owner, tag serial..."
              className="w-full pl-10 pr-4 py-2.5 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
            />
          </div>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-2 px-4 py-2.5 border rounded-xl text-sm font-medium transition-colors ${
              showFilters
                ? 'bg-brand/10 border-brand/30 text-brand'
                : 'bg-elevated border-line text-ink-muted'
            }`}
          >
            <Filter className="w-4 h-4" />
            Filters
          </button>
        </div>

        {showFilters && (
          <div className="flex flex-wrap gap-3 mt-3 pt-3 border-t border-line animate-fade-in-up">
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="px-3 py-2 bg-elevated border border-line rounded-lg text-sm text-ink outline-none"
            >
              <option value="All">All Types</option>
              <option value="car">Car</option>
              <option value="truck">Truck</option>
              <option value="bus">Bus</option>
              <option value="motorcycle">Motorcycle</option>
            </select>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 bg-elevated border border-line rounded-lg text-sm text-ink outline-none"
            >
              <option value="All">All Status</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="suspended">Suspended</option>
            </select>
            <button
              onClick={() => {
                setTypeFilter('All');
                setStatusFilter('All');
                setSearch('');
              }}
              className="px-3 py-2 text-sm text-danger hover:bg-danger/10 rounded-lg transition-colors"
            >
              Clear Filters
            </button>
          </div>
        )}
      </div>

      {/* Loading */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-brand" />
        </div>
      ) : filteredVehicles.length === 0 ? (
        <div className="bg-surface border border-line rounded-xl skeu-card p-12 text-center">
          <Car className="w-12 h-12 text-ink-subtle mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-ink mb-2">No vehicles found</h3>
          <p className="text-sm text-ink-muted">
            Try adjusting your search or filters, or add a new vehicle.
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {pagedVehicles.map((vehicle) => {
              const Icon = getVehicleIcon(vehicle.vehicle_type);
              const isSuspended = vehicle.status === 'suspended';
              const statusColor =
                vehicle.status === 'active'
                  ? 'bg-success/10 text-success border-success/20'
                  : vehicle.status === 'suspended'
                  ? 'bg-warning/10 text-warning border-warning/20'
                  : 'bg-danger/10 text-danger border-danger/20';
              const iconColor =
                vehicle.status === 'active' ? 'text-success' : 'text-danger';
              const iconBg =
                vehicle.status === 'active' ? 'bg-success/10' : 'bg-danger/10';
              return (
                <div
                  key={vehicle.id}
                  className="bg-surface border border-line rounded-xl skeu-card skeu-lift p-5 hover:border-brand/20 transition-all duration-200"
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className={`p-2.5 rounded-lg ${iconBg}`}>
                        <Icon className={`w-5 h-5 ${iconColor}`} />
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-ink">{vehicle.plate_number}</h3>
                        <p className="text-xs text-ink-muted capitalize">{vehicle.vehicle_type}</p>
                      </div>
                    </div>
                    <span className={`px-2.5 py-1 rounded-full text-xs font-medium border capitalize ${statusColor}`}>
                      {vehicle.status}
                    </span>
                  </div>

                  <div className="space-y-2 mb-4">
                    <div className="flex justify-between text-sm">
                      <span className="text-ink-muted">Owner</span>
                      <span className="text-ink font-medium">{vehicle.owner_name || '—'}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-ink-muted">M-Tag Serial</span>
                      <span className="text-ink font-mono text-xs">{vehicle.tag?.tag_serial || '—'}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-ink-muted">Tag Valid</span>
                      <span className={`text-xs font-medium ${vehicle.tag?.is_valid ? 'text-success' : 'text-danger'}`}>
                        {vehicle.tag ? (vehicle.tag.is_valid ? 'Valid' : 'Expired/Suspended') : 'No Tag'}
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-ink-muted">Registered</span>
                      <span className="text-ink">
                        {vehicle.registered_at ? new Date(vehicle.registered_at).toLocaleDateString('en-PK') : '—'}
                      </span>
                    </div>
                  </div>

                  <div className="flex gap-2 pt-3 border-t border-line">
                    {user?.role === 'admin' && (
                      <button
                        onClick={() => setSuspendTarget(vehicle)}
                        className={`flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg text-xs font-medium border transition-colors ${
                          isSuspended
                            ? 'text-success border-success/30 hover:bg-success/10'
                            : 'text-warning border-warning/30 hover:bg-warning/10'
                        }`}
                      >
                        {isSuspended ? <ShieldCheck className="w-3.5 h-3.5" /> : <ShieldOff className="w-3.5 h-3.5" />}
                        {isSuspended ? 'Activate' : 'Suspend'}
                      </button>
                    )}
                    <button
                      onClick={() => openReissue(vehicle)}
                      className="flex-1 flex items-center justify-center gap-1.5 py-2 bg-elevated border border-line rounded-lg text-sm text-ink-muted hover:text-warning hover:border-warning/30 transition-colors"
                    >
                      <Tag className="w-3.5 h-3.5" />
                      Reissue Tag
                    </button>
                    <button
                      onClick={() => openEdit(vehicle)}
                      className="flex items-center justify-center gap-1.5 py-2 px-3 bg-elevated border border-line rounded-lg text-sm text-ink-muted hover:text-brand hover:border-brand/30 transition-colors"
                    >
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-6">
              <p className="text-sm text-ink-muted">
                Showing {(currentPage - 1) * PAGE_SIZE + 1}–{Math.min(currentPage * PAGE_SIZE, filteredVehicles.length)} of {filteredVehicles.length} vehicles
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  className="px-4 py-2 bg-surface border border-line text-sm text-ink-muted rounded-xl hover:bg-elevated transition-colors disabled:opacity-40"
                >
                  Previous
                </button>
                <button
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                  className="px-4 py-2 bg-surface border border-line text-sm text-ink-muted rounded-xl hover:bg-elevated transition-colors disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Reissue Tag Modal */}
      {reissueVehicle && !showReissueConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in-up">
          <div className="bg-surface border border-line rounded-2xl skeu-card w-full max-w-md">
            <div className="flex items-center justify-between px-6 py-4 border-b border-line">
              <h2 className="text-lg font-semibold text-ink">Reissue Tag</h2>
              <button
                onClick={() => setReissueVehicle(null)}
                className="p-1.5 rounded-lg hover:bg-elevated text-ink-subtle transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <p className="text-sm text-ink-muted">
                Replacing tag for <span className="font-mono font-semibold text-ink">{reissueVehicle.plate_number}</span>.
                The current tag will be permanently deactivated.
              </p>
              <div>
                <label className="block text-sm font-medium text-ink mb-1.5">
                  Select New Tag <span className="text-danger">*</span>
                </label>
                {reissueTagsLoading ? (
                  <div className="flex items-center gap-2 px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink-subtle">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Loading available tags…
                  </div>
                ) : (
                  <select
                    value={reissueForm.tag_serial}
                    onChange={(e) => setReissueForm({ tag_serial: e.target.value })}
                    className="w-full px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink outline-none focus:border-warning focus:ring-2 focus:ring-warning/20 transition-all"
                  >
                    <option value="">— Select an unassigned tag —</option>
                    {reissueTags.map((t) => (
                      <option key={t.id} value={t.tag_serial}>
                        {t.tag_serial}
                      </option>
                    ))}
                  </select>
                )}
                {!reissueTagsLoading && reissueTags.length === 0 && (
                  <p className="text-xs text-ink-subtle mt-1">No unassigned tags in inventory.</p>
                )}
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setReissueVehicle(null)}
                  className="flex-1 py-2.5 bg-elevated border border-line text-ink text-sm font-medium rounded-xl hover:bg-surface transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={!reissueForm.tag_serial}
                  onClick={() => setShowReissueConfirm(true)}
                  className="flex-1 py-2.5 bg-warning/12 text-warning border border-warning/40 text-sm font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  <Tag className="w-4 h-4" />
                  Reissue
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Reissue Confirm Modal */}
      {reissueVehicle && showReissueConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in-up">
          <div className="bg-surface border border-line rounded-2xl skeu-card w-full max-w-sm">
            <div className="p-6 text-center space-y-4">
              <div className="w-14 h-14 bg-warning/10 rounded-full flex items-center justify-center mx-auto">
                <Tag className="w-7 h-7 text-warning" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-ink mb-1">Confirm Tag Reissue</h2>
                <p className="text-sm text-ink-muted">
                  Once this tag is reissued, the previous tag will be permanently disabled and cannot be assigned again.
                </p>
              </div>
              <div className="bg-elevated rounded-xl p-3 text-left space-y-1.5 text-sm">
                <div className="flex justify-between">
                  <span className="text-ink-muted">Vehicle</span>
                  <span className="font-mono font-semibold text-ink">{reissueVehicle.plate_number}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ink-muted">Current tag</span>
                  <span className="font-mono text-xs text-danger">{reissueVehicle.tag?.tag_serial || '—'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ink-muted">New tag</span>
                  <span className="font-mono text-xs text-success">{reissueForm.tag_serial}</span>
                </div>
              </div>
              <p className="text-xs text-ink-subtle">Are you sure you want to continue?</p>
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => setShowReissueConfirm(false)}
                  className="flex-1 py-2.5 bg-elevated border border-line text-ink text-sm font-medium rounded-xl hover:bg-surface transition-colors"
                >
                  Go Back
                </button>
                <button
                  type="button"
                  disabled={isReissuing}
                  onClick={handleReissueConfirm}
                  className="flex-1 py-2.5 bg-warning/12 text-warning border border-warning/40 text-sm font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-60 flex items-center justify-center gap-2"
                >
                  {isReissuing ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                  Yes, Reissue
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Upload Tags Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in-up">
          <div className="bg-surface border border-line rounded-2xl skeu-card w-full max-w-md">
            <div className="flex items-center justify-between px-6 py-4 border-b border-line">
              <h2 className="text-lg font-semibold text-ink">Upload Tag Inventory</h2>
              <button
                onClick={() => setShowUploadModal(false)}
                className="p-1.5 rounded-lg hover:bg-elevated text-ink-subtle transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <p className="text-sm text-ink-muted">
                Upload a CSV file exported from the RFID scanner. Columns required: <span className="font-mono text-xs bg-elevated px-1.5 py-0.5 rounded">TID</span> and <span className="font-mono text-xs bg-elevated px-1.5 py-0.5 rounded">EPC</span>. Tags that already exist will be skipped automatically.
              </p>

              {/* File picker */}
              <label className={`flex flex-col items-center justify-center gap-3 w-full h-32 border-2 border-dashed rounded-xl cursor-pointer transition-colors ${
                uploadFile
                  ? 'border-success bg-success/5'
                  : 'border-line hover:border-brand hover:bg-brand/5'
              }`}>
                <input
                  type="file"
                  accept=".csv"
                  className="hidden"
                  onChange={(e) => { setUploadFile(e.target.files?.[0] || null); setUploadResult(null); }}
                />
                {uploadFile ? (
                  <>
                    <CheckCircle className="w-6 h-6 text-success" />
                    <span className="text-sm font-medium text-ink">{uploadFile.name}</span>
                    <span className="text-xs text-ink-subtle">{(uploadFile.size / 1024).toFixed(1)} KB — click to change</span>
                  </>
                ) : (
                  <>
                    <Upload className="w-6 h-6 text-ink-subtle" />
                    <span className="text-sm text-ink-muted">Click to browse CSV file</span>
                  </>
                )}
              </label>

              {/* Result */}
              {uploadResult && (
                <div className="space-y-2">
                  <div className="flex gap-3">
                    <div className="flex-1 bg-success/10 border border-success/20 rounded-xl p-3 text-center">
                      <p className="text-2xl font-bold text-success">{uploadResult.added}</p>
                      <p className="text-xs text-ink-muted mt-0.5">Added</p>
                    </div>
                    <div className="flex-1 bg-warning/10 border border-warning/20 rounded-xl p-3 text-center">
                      <p className="text-2xl font-bold text-warning">{uploadResult.skipped}</p>
                      <p className="text-xs text-ink-muted mt-0.5">Already Existed</p>
                    </div>
                  </div>
                  {uploadResult.errors.length > 0 && (
                    <div className="flex items-start gap-2 px-3 py-2 bg-danger/10 border border-danger/20 rounded-lg text-xs text-danger">
                      <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                      <span>{uploadResult.errors.join(', ')}</span>
                    </div>
                  )}
                </div>
              )}

              <div className="flex gap-3 pt-1">
                <button
                  type="button"
                  onClick={() => setShowUploadModal(false)}
                  className="flex-1 py-2.5 bg-elevated border border-line text-ink text-sm font-medium rounded-xl hover:bg-surface transition-colors"
                >
                  {uploadResult ? 'Close' : 'Cancel'}
                </button>
                {!uploadResult && (
                  <button
                    type="button"
                    disabled={!uploadFile || isUploading}
                    onClick={handleUpload}
                    className="flex-1 py-2.5 bg-brand text-brand-on text-sm font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  >
                    {isUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                    {isUploading ? 'Uploading…' : 'Upload'}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in-up">
          <div className="bg-surface border border-line rounded-2xl skeu-card w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between px-6 py-4 border-b border-line">
              <h2 className="text-lg font-semibold text-ink">
                {editingVehicle ? 'Edit Vehicle' : 'Add Vehicle'}
              </h2>
              <button
                onClick={() => setShowModal(false)}
                className="p-1.5 rounded-lg hover:bg-elevated text-ink-subtle transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="p-6 space-y-5">
              {!editingVehicle && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-ink mb-1.5">
                      Plate Number <span className="text-danger">*</span>
                    </label>
                    <input
                      type="text"
                      value={form.plate_number}
                      onChange={(e) => setForm((p) => ({ ...p, plate_number: normalizePlate(e.target.value) }))}
                      placeholder="LHR1234"
                      className="w-full px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-ink mb-1.5">
                        Vehicle Type <span className="text-danger">*</span>
                      </label>
                      <select
                        value={form.vehicle_type}
                        onChange={(e) => setForm((p) => ({ ...p, vehicle_type: e.target.value }))}
                        className="w-full px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
                      >
                        <option value="car">Car</option>
                        <option value="truck">Truck</option>
                        <option value="bus">Bus</option>
                        <option value="motorcycle">Motorcycle</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-ink mb-1.5">
                        Owner ID <span className="text-danger">*</span>
                      </label>
                      <input
                        type="number"
                        value={form.owner_id}
                        onChange={(e) => setForm((p) => ({ ...p, owner_id: e.target.value }))}
                        placeholder="User ID"
                        className="w-full px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-ink mb-1.5">
                      Tag Serial <span className="text-danger">*</span>
                    </label>
                    <input
                      type="text"
                      value={form.tag_serial}
                      onChange={(e) => setForm((p) => ({ ...p, tag_serial: e.target.value }))}
                      placeholder="MTAG-XXXXXXXX"
                      className="w-full px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
                    />
                  </div>
                </>
              )}

              {editingVehicle && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-ink mb-1.5">
                      Plate Number <span className="text-danger">*</span>
                    </label>
                    <input
                      type="text"
                      value={form.plate_number}
                      onChange={(e) => setForm((p) => ({ ...p, plate_number: normalizePlate(e.target.value) }))}
                      placeholder="LHR1234"
                      className="w-full px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-ink mb-1.5">
                      Customer Name
                    </label>
                    <input
                      type="text"
                      value={form.owner_name}
                      onChange={(e) => setForm((p) => ({ ...p, owner_name: e.target.value }))}
                      placeholder="Owner full name"
                      className="w-full px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
                    />
                    <p className="text-xs text-ink-subtle mt-1">Updates the tag owner's name.</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-ink mb-1.5">
                      Status
                    </label>
                    <select
                      value={form.status}
                      onChange={(e) => setForm((p) => ({ ...p, status: e.target.value }))}
                      className="w-full px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
                    >
                      <option value="active">Active</option>
                      <option value="inactive">Inactive</option>
                    </select>
                  </div>
                </>
              )}

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="flex-1 py-2.5 bg-elevated border border-line text-ink text-sm font-medium rounded-xl hover:bg-surface transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="flex-1 py-2.5 bg-brand text-brand-on text-sm font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-60 flex items-center justify-center gap-2"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Saving...
                    </>
                  ) : editingVehicle ? (
                    <>
                      <CheckCircle className="w-4 h-4" />
                      Update
                    </>
                  ) : (
                    <>
                      <Plus className="w-4 h-4" />
                      Add Vehicle
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Tag Modal */}
      {showAddTagModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in-up">
          <div className="bg-surface border border-line rounded-2xl skeu-card w-full max-w-md">
            <div className="flex items-center justify-between px-6 py-4 border-b border-line">
              <h2 className="text-lg font-semibold text-ink">Add Tag to Inventory</h2>
              <button
                onClick={() => setShowAddTagModal(false)}
                className="p-1.5 rounded-lg hover:bg-elevated text-ink-subtle transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleAddTag} className="p-6 space-y-4">
              <p className="text-sm text-ink-muted">
                Add a single RFID tag to the unassigned inventory. It can then be assigned to a vehicle during registration or reissue.
              </p>
              <div>
                <label className="block text-sm font-medium text-ink mb-1.5">
                  Tag Serial <span className="text-danger">*</span>
                </label>
                <input
                  type="text"
                  value={addTagForm.tag_serial}
                  onChange={(e) => setAddTagForm((p) => ({ ...p, tag_serial: e.target.value }))}
                  placeholder="MTAG-XXXXXXXX"
                  className="w-full px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-info focus:ring-2 focus:ring-info/20 transition-all font-mono"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-ink mb-1.5">
                  TID <span className="text-ink-subtle text-xs font-normal">(chip TID — used at the gate)</span>
                </label>
                <input
                  type="text"
                  value={addTagForm.tid}
                  onChange={(e) => setAddTagForm((p) => ({ ...p, tid: e.target.value }))}
                  placeholder="E28011052000704A8F9F0AE3"
                  className="w-full px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-info focus:ring-2 focus:ring-info/20 transition-all font-mono"
                />
                <p className="text-xs text-ink-subtle mt-1">The reader matches tags by TID. Leave empty only if the chip TID isn't known yet.</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-ink mb-1.5">
                  EPC <span className="text-ink-subtle text-xs font-normal">(optional)</span>
                </label>
                <input
                  type="text"
                  value={addTagForm.epc}
                  onChange={(e) => setAddTagForm((p) => ({ ...p, epc: e.target.value }))}
                  placeholder="Electronic Product Code"
                  className="w-full px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-info focus:ring-2 focus:ring-info/20 transition-all font-mono"
                />
              </div>
              <div className="flex gap-3 pt-1">
                <button
                  type="button"
                  onClick={() => setShowAddTagModal(false)}
                  className="flex-1 py-2.5 bg-elevated border border-line text-ink text-sm font-medium rounded-xl hover:bg-surface transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isAddingTag}
                  className="flex-1 py-2.5 bg-info text-white text-sm font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-60 flex items-center justify-center gap-2"
                >
                  {isAddingTag ? <Loader2 className="w-4 h-4 animate-spin" /> : <Tag className="w-4 h-4" />}
                  {isAddingTag ? 'Adding…' : 'Add Tag'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Suspend / Activate Confirmation Modal */}
      {suspendTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in-up">
          <div className="bg-surface border border-line rounded-2xl skeu-card w-full max-w-sm">
            <div className="p-6 text-center space-y-4">
              <div className={`w-14 h-14 rounded-full flex items-center justify-center mx-auto ${
                suspendTarget.status === 'suspended'
                  ? 'bg-success/10'
                  : 'bg-warning/10'
              }`}>
                {suspendTarget.status === 'suspended'
                  ? <ShieldCheck className="w-7 h-7 text-success" />
                  : <ShieldOff className="w-7 h-7 text-warning" />
                }
              </div>
              <div>
                <h2 className="text-lg font-bold text-ink mb-1">
                  {suspendTarget.status === 'suspended' ? 'Activate Vehicle?' : 'Suspend Vehicle?'}
                </h2>
                <p className="text-sm text-ink-muted">
                  {suspendTarget.status === 'suspended'
                    ? 'The vehicle and its M-Tag will be re-enabled. It will be able to pass through toll plazas again.'
                    : 'The vehicle and its M-Tag will be blocked. It will be denied entry at all toll plazas until reactivated.'}
                </p>
              </div>
              <div className="bg-elevated rounded-xl p-3 text-left space-y-1.5 text-sm">
                <div className="flex justify-between">
                  <span className="text-ink-muted">Plate</span>
                  <span className="font-mono font-semibold text-ink">{suspendTarget.plate_number}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ink-muted">M-Tag</span>
                  <span className="font-mono text-xs text-ink">{suspendTarget.tag?.tag_serial || '—'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-ink-muted">Current Status</span>
                  <span className={`text-xs font-medium capitalize ${
                    suspendTarget.status === 'active' ? 'text-success' : 'text-warning'
                  }`}>{suspendTarget.status}</span>
                </div>
              </div>
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => setSuspendTarget(null)}
                  disabled={isSuspending}
                  className="flex-1 py-2.5 bg-elevated border border-line text-ink text-sm font-medium rounded-xl hover:bg-surface transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={isSuspending}
                  onClick={handleSuspendToggle}
                  className={`flex-1 py-2.5 text-white text-sm font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-60 flex items-center justify-center gap-2 ${
                    suspendTarget.status === 'suspended' ? 'bg-success' : 'bg-warning'
                  }`}
                >
                  {isSuspending ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                  {isSuspending
                    ? 'Processing…'
                    : suspendTarget.status === 'suspended'
                    ? 'Yes, Activate'
                    : 'Yes, Suspend'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
