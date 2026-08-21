import { useState, useEffect, useMemo } from 'react';
import { tollsApi, vehiclesApi } from '@/services/api';
import type { TollTrip, ApiVehicle } from '@/types';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import {
  Route,
  Search,
  Filter,
  Loader2,
  RefreshCw,
  Calendar,
  XCircle,
  RotateCcw,
} from 'lucide-react';

const STATUS_OPTIONS = ['All', 'active', 'completed', 'failed'];

const statusBadge = (status: string) => {
  switch (status) {
    case 'active':
      return 'bg-brand/10 text-brand border-brand/20';
    case 'completed':
      return 'bg-success/10 text-success border-success/20';
    case 'failed':
      return 'bg-danger/10 text-danger border-danger/20';
    default:
      return 'bg-elevated text-ink-muted border-line';
  }
};

function formatDuration(minutes?: number): string {
  if (!minutes) return '—';
  if (minutes < 60) return `${minutes}m`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${h}h ${m}m`;
}

const PAGE_SIZE = 15;

export default function TripsPage() {
  const { addToast } = useToast();
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  const [trips, setTrips] = useState<TollTrip[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('All');
  const [search, setSearch] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [closingTripId, setClosingTripId] = useState<number | null>(null);
  const [confirmClose, setConfirmClose] = useState<TollTrip | null>(null);
  const [refundTarget, setRefundTarget] = useState<TollTrip | null>(null);
  const [isRefunding, setIsRefunding] = useState(false);
  const [refundedTripIds, setRefundedTripIds] = useState<Set<number>>(new Set());

  // For non-admin: vehicle selector
  const [vehicles, setVehicles] = useState<ApiVehicle[]>([]);
  const [selectedVehicle, setSelectedVehicle] = useState<number | ''>('');

  useEffect(() => {
    if (!isAdmin) {
      vehiclesApi
        .list()
        .then((data) => {
          setVehicles(data);
          if (data.length > 0) setSelectedVehicle(data[0].id);
        })
        .catch(() => addToast({ type: 'error', title: 'Error', message: 'Failed to load vehicles' }));
    }
  }, [isAdmin]);

  useEffect(() => {
    fetchTrips();
  }, [isAdmin, selectedVehicle, statusFilter]);

  const fetchTrips = async () => {
    if (!isAdmin && !selectedVehicle) return;
    setLoading(true);
    try {
      let data: TollTrip[];
      if (isAdmin) {
        data = await tollsApi.adminTrips(statusFilter !== 'All' ? { status: statusFilter } : undefined);
      } else {
        data = await tollsApi.trips(selectedVehicle as number);
      }
      setTrips(data);
      setCurrentPage(1);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load trips';
      addToast({ type: 'error', title: 'Error', message });
    } finally {
      setLoading(false);
    }
  };

  const handleRefundTrip = async (trip: TollTrip) => {
    setIsRefunding(true);
    try {
      await tollsApi.refundTrip(trip.id);
      setRefundedTripIds((prev) => new Set([...prev, trip.id]));
      addToast({ type: 'success', title: 'Refund Processed', message: `PKR ${parseFloat(trip.charge_amount!).toLocaleString()} refunded to ${trip.plate_number}.` });
      setRefundTarget(null);
    } catch (err: unknown) {
      addToast({ type: 'error', title: 'Refund Failed', message: err instanceof Error ? err.message : 'Refund failed' });
    } finally {
      setIsRefunding(false);
    }
  };

  const handleCloseTrip = async (trip: TollTrip) => {
    setClosingTripId(trip.id);
    setConfirmClose(null);
    try {
      const updated = await tollsApi.closeTrip(trip.id);
      setTrips((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      addToast({ type: 'success', title: 'Trip Closed', message: `Trip for ${updated.plate_number} has been force-closed.` });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to close trip';
      addToast({ type: 'error', title: 'Error', message });
    } finally {
      setClosingTripId(null);
    }
  };

  const filtered = useMemo(() => {
    const s = search.toLowerCase();
    return trips.filter((t) => {
      const matchSearch =
        t.plate_number?.toLowerCase().includes(s) ||
        t.entry_plaza_name?.toLowerCase().includes(s) ||
        t.exit_plaza_name?.toLowerCase().includes(s);
      const matchStatus =
        statusFilter === 'All' || !isAdmin || t.status === statusFilter;
      return matchSearch && matchStatus;
    });
  }, [trips, search, statusFilter, isAdmin]);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paginatedTrips = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  return (
    <div className="animate-fade-in-up">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Route className="w-6 h-6 text-brand" />
            <h1 className="text-2xl font-bold text-ink">Trip History</h1>
          </div>
          <p className="text-sm text-ink-muted mt-1">
            {loading ? 'Loading...' : `${filtered.length} trips found`}
          </p>
        </div>
        <button
          onClick={fetchTrips}
          className="flex items-center gap-2 px-4 py-2.5 bg-elevated border border-line text-ink-muted text-sm font-medium rounded-xl hover:bg-surface transition-colors self-start"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="bg-surface border border-line rounded-xl skeu-card p-4 mb-6">
        <div className="flex flex-col sm:flex-row gap-3">
          {/* Vehicle selector for non-admin */}
          {!isAdmin && vehicles.length > 0 && (
            <select
              value={selectedVehicle}
              onChange={(e) => setSelectedVehicle(e.target.value ? Number(e.target.value) : '')}
              className="px-4 py-2.5 bg-elevated border border-line rounded-xl text-sm text-ink outline-none focus:border-brand"
            >
              {vehicles.map((v) => (
                <option key={v.id} value={v.id}>{v.plate_number}</option>
              ))}
            </select>
          )}

          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-subtle" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by plate or plaza..."
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
            <div>
              <label className="block text-xs font-medium text-ink-muted mb-1.5">Status</label>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-3 py-2 bg-elevated border border-line rounded-lg text-sm text-ink outline-none"
              >
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>{s === 'All' ? 'All Status' : s.charAt(0).toUpperCase() + s.slice(1)}</option>
                ))}
              </select>
            </div>
            <button
              onClick={() => { setStatusFilter('All'); setSearch(''); }}
              className="self-end px-3 py-2 text-sm text-danger hover:bg-danger/10 rounded-lg transition-colors"
            >
              Clear
            </button>
          </div>
        )}
      </div>

      {/* Table */}
      <div className="bg-surface border border-line rounded-xl skeu-card overflow-hidden">
        <div className="overflow-x-auto">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="w-8 h-8 animate-spin text-brand" />
            </div>
          ) : paginatedTrips.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <Calendar className="w-12 h-12 text-ink-subtle mx-auto mb-4" />
              <h3 className="text-base font-semibold text-ink mb-2">No trips found</h3>
              <p className="text-sm text-ink-muted">
                {search || statusFilter !== 'All'
                  ? 'Try adjusting your filters.'
                  : 'No trips recorded yet.'}
              </p>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="bg-elevated">
                  <th className="text-left px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">Plate</th>
                  <th className="text-left px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">Entry Plaza</th>
                  <th className="text-left px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">Exit Plaza</th>
                  <th className="text-left px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">Entry Time</th>
                  <th className="text-left px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">Exit Time</th>
                  <th className="text-center px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">Duration</th>
                  <th className="text-right px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">Charge / Balance</th>
                  <th className="text-center px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">Status</th>
                  {isAdmin && <th className="px-6 py-3" />}
                </tr>
              </thead>
              <tbody>
                {paginatedTrips.map((trip) => (
                  <tr
                    key={trip.id}
                    className="border-b border-line hover:bg-elevated transition-colors"
                  >
                    <td className="px-6 py-4 text-sm font-mono font-semibold text-ink">
                      {trip.plate_number}
                    </td>
                    <td className="px-6 py-4 text-sm text-ink">{trip.entry_plaza_name}</td>
                    <td className="px-6 py-4 text-sm text-ink-muted">
                      {trip.exit_plaza_name || <span className="text-ink-subtle">In Transit</span>}
                    </td>
                    <td className="px-6 py-4 text-sm text-ink-muted">
                      {new Date(trip.entry_time).toLocaleDateString('en-PK', {
                        day: 'numeric',
                        month: 'short',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </td>
                    <td className="px-6 py-4 text-sm text-ink-muted">
                      {trip.exit_time
                        ? new Date(trip.exit_time).toLocaleDateString('en-PK', {
                            day: 'numeric',
                            month: 'short',
                            hour: '2-digit',
                            minute: '2-digit',
                          })
                        : <span className="text-ink-subtle">—</span>}
                    </td>
                    <td className="px-6 py-4 text-sm text-ink-muted text-center">
                      {formatDuration(trip.duration_minutes)}
                    </td>
                    <td className="px-6 py-4 text-right">
                      {trip.charge_amount
                        ? (
                          <div>
                            <p className="text-sm font-semibold text-danger">
                              − PKR {parseFloat(trip.charge_amount).toLocaleString()}
                            </p>
                            {trip.balance_after && (
                              <p className="text-xs text-ink-muted mt-0.5">
                                bal: PKR {parseFloat(trip.balance_after).toLocaleString()}
                              </p>
                            )}
                          </div>
                        )
                        : <span className="text-sm text-ink-subtle">—</span>}
                    </td>
                    <td className="px-6 py-4 text-center">
                      <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border capitalize ${statusBadge(trip.status)}`}>
                        {trip.status}
                      </span>
                    </td>
                    {isAdmin && (
                      <td className="px-4 py-4 text-center">
                        <div className="flex items-center gap-1.5 justify-center">
                          {trip.status === 'active' && (
                            <button
                              onClick={() => setConfirmClose(trip)}
                              disabled={closingTripId === trip.id}
                              className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-danger border border-danger/30 rounded-lg hover:bg-danger/10 transition-colors disabled:opacity-50"
                            >
                              {closingTripId === trip.id
                                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                : <XCircle className="w-3.5 h-3.5" />}
                              Close
                            </button>
                          )}
                          {trip.status === 'completed' && trip.charge_amount && parseFloat(trip.charge_amount) > 0 && (
                            refundedTripIds.has(trip.id) ? (
                              <span className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-ink-subtle border border-line rounded-lg">
                                <RotateCcw className="w-3.5 h-3.5" />
                                Refunded
                              </span>
                            ) : (
                              <button
                                onClick={() => setRefundTarget(trip)}
                                className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-warning border border-warning/30 rounded-lg hover:bg-warning/10 transition-colors"
                              >
                                <RotateCcw className="w-3.5 h-3.5" />
                                Refund
                              </button>
                            )
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-6 py-4 border-t border-line">
            <p className="text-sm text-ink-muted">
              Page {currentPage} of {totalPages} ({filtered.length} trips)
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="px-4 py-2 bg-elevated border border-line text-sm text-ink-muted rounded-lg hover:bg-surface transition-colors disabled:opacity-50"
              >
                Previous
              </button>
              <button
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="px-4 py-2 bg-elevated border border-line text-sm text-ink-muted rounded-lg hover:bg-surface transition-colors disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Refund confirmation modal */}
      {refundTarget && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setRefundTarget(null)}>
          <div
            className="bg-surface border border-line rounded-2xl skeu-card p-6 w-full max-w-sm animate-fade-in-up"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-warning/10 rounded-full flex items-center justify-center">
                <RotateCcw className="w-5 h-5 text-warning" />
              </div>
              <div>
                <p className="font-semibold text-ink">Refund Toll Charge</p>
                <p className="text-xs text-ink-muted">{refundTarget.plate_number}</p>
              </div>
            </div>
            <div className="bg-elevated rounded-xl p-3 mb-4 space-y-1.5 text-sm">
              <div className="flex justify-between">
                <span className="text-ink-muted">Entry</span>
                <span className="text-ink">{refundTarget.entry_plaza_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-muted">Exit</span>
                <span className="text-ink">{refundTarget.exit_plaza_name || '—'}</span>
              </div>
              <div className="flex justify-between pt-1 border-t border-line">
                <span className="font-medium text-ink">Amount to refund</span>
                <span className="font-bold text-warning">
                  PKR {parseFloat(refundTarget.charge_amount!).toLocaleString()}
                </span>
              </div>
            </div>
            <p className="text-sm text-ink-muted mb-5">
              This will credit the toll charge back to the vehicle's M-Tag wallet. This action cannot be undone.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setRefundTarget(null)}
                disabled={isRefunding}
                className="flex-1 py-2.5 bg-elevated border border-line text-sm font-medium text-ink rounded-xl hover:bg-surface transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={() => handleRefundTrip(refundTarget)}
                disabled={isRefunding}
                className="flex-1 py-2.5 bg-warning/12 text-warning border border-warning/40 text-sm font-semibold rounded-xl hover:opacity-90 transition-opacity disabled:opacity-60 flex items-center justify-center gap-2"
              >
                {isRefunding ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                {isRefunding ? 'Processing…' : 'Confirm Refund'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Force-close confirmation modal */}
      {confirmClose && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setConfirmClose(null)}>
          <div
            className="bg-surface border border-line rounded-2xl skeu-card p-6 w-full max-w-sm animate-fade-in-up"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-danger/10 rounded-full flex items-center justify-center">
                <XCircle className="w-5 h-5 text-danger" />
              </div>
              <div>
                <p className="font-semibold text-ink">Force Close Trip</p>
                <p className="text-xs text-ink-muted">{confirmClose.plate_number}</p>
              </div>
            </div>
            <p className="text-sm text-ink-muted mb-5">
              This will mark the trip as <strong>Failed</strong> without charging the vehicle. The gate may not have recorded an exit. Continue?
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setConfirmClose(null)}
                className="flex-1 py-2.5 bg-elevated border border-line text-sm font-medium text-ink rounded-xl hover:bg-surface transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleCloseTrip(confirmClose)}
                className="flex-1 py-2.5 bg-danger-solid text-white text-sm font-semibold rounded-xl hover:opacity-90 transition-opacity"
              >
                Force Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
