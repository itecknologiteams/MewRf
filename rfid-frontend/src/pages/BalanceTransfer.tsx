import { useState } from 'react';
import { useToast } from '@/context/ToastContext';
import { vehiclesApi, accountsApi } from '@/services/api';
import { normalizePlate } from '@/lib/plate';
import type { Account } from '@/types';
import {
  ArrowRightLeft,
  Car,
  Shield,
  CheckCircle,
  Loader2,
  AlertTriangle,
  ArrowRight,
  Search,
} from 'lucide-react';

interface VehicleInfo {
  id: number;
  plate_number: string;
  vehicle_type: string;
  balance: string;
}

async function lookupVehicle(plate: string): Promise<VehicleInfo> {
  const vehicle = await vehiclesApi.byPlate(normalizePlate(plate));
  const acct: Account = await accountsApi.byVehicle(vehicle.id);
  return {
    id: vehicle.id,
    plate_number: vehicle.plate_number,
    vehicle_type: vehicle.vehicle_type,
    balance: acct.balance,
  };
}

export default function BalanceTransfer() {
  const { addToast } = useToast();

  const [sourcePlate, setSourcePlate] = useState('');
  const [sourceLookupLoading, setSourceLookupLoading] = useState(false);
  const [sourceVehicleInfo, setSourceVehicleInfo] = useState<VehicleInfo | null>(null);
  const [sourceLookupError, setSourceLookupError] = useState('');

  const [targetPlate, setTargetPlate] = useState('');
  const [targetLookupLoading, setTargetLookupLoading] = useState(false);
  const [targetVehicleInfo, setTargetVehicleInfo] = useState<VehicleInfo | null>(null);
  const [targetLookupError, setTargetLookupError] = useState('');

  const [cnic, setCnic] = useState('');
  const [phone, setPhone] = useState('');
  const [name, setName] = useState('');

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [success, setSuccess] = useState<{
    transferred_amount: string;
    source_vehicle: string;
    target_vehicle: string;
    reference_id: string;
  } | null>(null);

  const handleLookupSource = async () => {
    setSourceLookupLoading(true);
    setSourceLookupError('');
    setSourceVehicleInfo(null);
    try {
      const info = await lookupVehicle(sourcePlate);
      if (targetVehicleInfo && info.id === targetVehicleInfo.id) {
        setSourceLookupError('Source and target vehicle cannot be the same.');
        return;
      }
      setSourceVehicleInfo(info);
    } catch {
      setSourceLookupError('Vehicle not found. Check the plate number and try again.');
    } finally {
      setSourceLookupLoading(false);
    }
  };

  const handleLookupTarget = async () => {
    setTargetLookupLoading(true);
    setTargetLookupError('');
    setTargetVehicleInfo(null);
    try {
      const info = await lookupVehicle(targetPlate);
      if (sourceVehicleInfo && info.id === sourceVehicleInfo.id) {
        setTargetLookupError('Source and target vehicle cannot be the same.');
        return;
      }
      setTargetVehicleInfo(info);
    } catch {
      setTargetLookupError('Vehicle not found. Check the plate number and try again.');
    } finally {
      setTargetLookupLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sourceVehicleInfo || !targetVehicleInfo) {
      addToast({ type: 'error', title: 'Validation Error', message: 'Please look up both source and target vehicles.' });
      return;
    }
    if (!cnic.trim() || !phone.trim() || !name.trim()) {
      addToast({ type: 'error', title: 'Validation Error', message: 'Please fill all KYC fields.' });
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await accountsApi.transferBalance({
        source_vehicle_id: sourceVehicleInfo.id,
        target_vehicle_id: targetVehicleInfo.id,
        cnic: cnic.trim(),
        phone: phone.trim(),
        name: name.trim(),
      });
      setSuccess(result);
      addToast({ type: 'success', title: 'Transfer Successful', message: `PKR ${result.transferred_amount} transferred.` });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Transfer failed';
      addToast({ type: 'error', title: 'Transfer Failed', message });
    } finally {
      setIsSubmitting(false);
    }
  };

  const reset = () => {
    setSuccess(null);
    setSourcePlate('');
    setSourceVehicleInfo(null);
    setSourceLookupError('');
    setTargetPlate('');
    setTargetVehicleInfo(null);
    setTargetLookupError('');
    setCnic('');
    setPhone('');
    setName('');
  };

  if (success) {
    return (
      <div className="flex items-center justify-center min-h-[60vh] animate-fade-in-up">
        <div className="bg-surface border border-line rounded-2xl skeu-card p-8 text-center max-w-md w-full">
          <div className="w-16 h-16 bg-success/10 rounded-full flex items-center justify-center mx-auto mb-4">
            <CheckCircle className="w-8 h-8 text-success" />
          </div>
          <h2 className="text-xl font-bold text-ink mb-2">Transfer Complete</h2>
          <p className="text-sm text-ink-muted mb-6">
            The full balance has been transferred and the source tag has been deactivated.
          </p>
          <div className="bg-elevated rounded-xl p-4 mb-6 text-left space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-ink-muted">Amount Transferred</span>
              <span className="font-bold text-success">PKR {parseFloat(success.transferred_amount).toLocaleString()}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-ink-muted">From</span>
              <span className="font-mono font-semibold text-ink">{success.source_vehicle}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-ink-muted">To</span>
              <span className="font-mono font-semibold text-ink">{success.target_vehicle}</span>
            </div>
            <div className="flex justify-between text-sm pt-2 border-t border-line">
              <span className="text-ink-muted">Reference ID</span>
              <span className="font-mono text-xs text-ink-subtle">{success.reference_id.slice(0, 16)}…</span>
            </div>
          </div>
          <button
            onClick={reset}
            className="w-full py-3 bg-brand text-brand-on font-semibold rounded-xl hover:opacity-90 transition-opacity"
          >
            New Transfer
          </button>
        </div>
      </div>
    );
  }

  const canSubmit =
    !!sourceVehicleInfo &&
    !!targetVehicleInfo &&
    cnic.trim() !== '' &&
    phone.trim() !== '' &&
    name.trim() !== '' &&
    !isSubmitting;

  return (
    <div className="max-w-2xl mx-auto animate-fade-in-up">
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-1">
          <ArrowRightLeft className="w-6 h-6 text-brand" />
          <h1 className="text-2xl font-bold text-ink">Balance Transfer</h1>
        </div>
        <p className="text-sm text-ink-muted mt-1">
          Transfer the full wallet balance from one vehicle to another. The source tag will be permanently deactivated.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Vehicle Selection */}
        <div className="bg-surface border border-line rounded-xl skeu-card p-6">
          <div className="flex items-center gap-3 mb-5">
            <div className="p-2 bg-brand/10 rounded-lg">
              <Car className="w-5 h-5 text-brand" />
            </div>
            <h2 className="text-base font-semibold text-ink">Select Vehicles</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] items-start gap-4">
            {/* Source */}
            <div className="min-w-0">
              <label className="block text-xs font-medium text-ink-muted uppercase tracking-wider mb-2">
                From (Source) — Plate Number
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={sourcePlate}
                  onChange={(e) => {
                    setSourcePlate(normalizePlate(e.target.value));
                    setSourceVehicleInfo(null);
                    setSourceLookupError('');
                  }}
                  onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleLookupSource())}
                  placeholder="e.g. ABC-123"
                  className="flex-1 min-w-0 px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-danger focus:ring-2 focus:ring-danger/20 transition-all uppercase"
                />
                <button
                  type="button"
                  onClick={handleLookupSource}
                  disabled={!sourcePlate.trim() || sourceLookupLoading}
                  className="shrink-0 px-4 py-3 bg-danger-solid text-white rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                >
                  {sourceLookupLoading
                    ? <Loader2 className="w-4 h-4 animate-spin" />
                    : <Search className="w-4 h-4" />}
                </button>
              </div>
              {sourceLookupError && (
                <p className="text-xs text-danger mt-1.5 pl-1">{sourceLookupError}</p>
              )}
              {sourceVehicleInfo && (
                <div className="mt-2 px-3 py-2 bg-danger/10 border border-danger/20 rounded-lg text-xs text-danger flex items-center gap-2">
                  <CheckCircle className="w-3.5 h-3.5 flex-shrink-0" />
                  <span>
                    <span className="font-semibold">{sourceVehicleInfo.plate_number}</span>
                    {' · '}{sourceVehicleInfo.vehicle_type}
                    {' · '}Balance: <span className="font-semibold">PKR {parseFloat(sourceVehicleInfo.balance).toLocaleString()}</span>
                  </span>
                </div>
              )}
            </div>

            <div className="hidden md:flex items-center justify-center pt-10">
              <ArrowRight className="w-5 h-5 text-ink-subtle" />
            </div>

            {/* Target */}
            <div className="min-w-0">
              <label className="block text-xs font-medium text-ink-muted uppercase tracking-wider mb-2">
                To (Target) — Plate Number
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={targetPlate}
                  onChange={(e) => {
                    setTargetPlate(normalizePlate(e.target.value));
                    setTargetVehicleInfo(null);
                    setTargetLookupError('');
                  }}
                  onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleLookupTarget())}
                  placeholder="e.g. XYZ-789"
                  className="flex-1 min-w-0 px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-success focus:ring-2 focus:ring-success/20 transition-all uppercase"
                />
                <button
                  type="button"
                  onClick={handleLookupTarget}
                  disabled={!targetPlate.trim() || targetLookupLoading}
                  className="shrink-0 px-4 py-3 bg-brand text-brand-on rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                >
                  {targetLookupLoading
                    ? <Loader2 className="w-4 h-4 animate-spin" />
                    : <Search className="w-4 h-4" />}
                </button>
              </div>
              {targetLookupError && (
                <p className="text-xs text-danger mt-1.5 pl-1">{targetLookupError}</p>
              )}
              {targetVehicleInfo && (
                <div className="mt-2 px-3 py-2 bg-success/10 border border-success/20 rounded-lg text-xs text-success flex items-center gap-2">
                  <CheckCircle className="w-3.5 h-3.5 flex-shrink-0" />
                  <span>
                    <span className="font-semibold">{targetVehicleInfo.plate_number}</span>
                    {' · '}{targetVehicleInfo.vehicle_type}
                    {' · '}Balance: <span className="font-semibold">PKR {parseFloat(targetVehicleInfo.balance).toLocaleString()}</span>
                  </span>
                </div>
              )}
            </div>
          </div>

          {sourceVehicleInfo && parseFloat(sourceVehicleInfo.balance) <= 0 && (
            <div className="mt-4 flex items-center gap-2 px-4 py-3 bg-warning/10 border border-warning/20 rounded-xl text-sm text-warning">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              Source account has no balance to transfer.
            </div>
          )}
        </div>

        {/* KYC Verification */}
        <div className="bg-surface border border-line rounded-xl skeu-card p-6">
          <div className="flex items-center gap-3 mb-5">
            <div className="p-2 bg-warning/10 rounded-lg">
              <Shield className="w-5 h-5 text-warning" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-ink">Identity Verification (KYC)</h2>
              <p className="text-xs text-ink-muted mt-0.5">Confirm identity to authorise the transfer</p>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-ink mb-1.5">
                Full Name <span className="text-danger">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Enter full name"
                className="w-full px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
              />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-ink mb-1.5">
                  CNIC <span className="text-danger">*</span>
                </label>
                <input
                  type="text"
                  value={cnic}
                  onChange={(e) => setCnic(e.target.value)}
                  placeholder="35201-1234567-8"
                  className="w-full px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-ink mb-1.5">
                  Phone <span className="text-danger">*</span>
                </label>
                <input
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="03001234567"
                  className="w-full px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Warning */}
        <div className="flex items-start gap-3 px-4 py-3 bg-danger/5 border border-danger/20 rounded-xl text-sm text-danger">
          <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>
            <strong>Irreversible action.</strong> The full balance will be transferred and the source tag will be permanently deactivated.
          </span>
        </div>

        <button
          type="submit"
          disabled={!canSubmit}
          className="w-full flex items-center justify-center gap-2 py-3.5 bg-brand text-brand-on font-semibold rounded-xl hover:bg-brand-strong active:bg-brand-strong transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Processing Transfer...
            </>
          ) : (
            <>
              <ArrowRightLeft className="w-4 h-4" />
              Confirm Transfer
            </>
          )}
        </button>
      </form>
    </div>
  );
}
