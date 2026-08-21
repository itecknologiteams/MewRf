import { useState } from 'react';
import { useToast } from '@/context/ToastContext';
import { vehiclesApi, accountsApi } from '@/services/api';
import { normalizePlate } from '@/lib/plate';
import {
  Wallet,
  Search,
  CheckCircle,
  Loader2,
  ArrowRight,
  Car,
  Truck,
  Bus,
  Bike,
  Plus,
} from 'lucide-react';

const vehicleIcons: Record<string, React.ElementType> = {
  car: Car, truck: Truck, bus: Bus, motorcycle: Bike,
};

interface VehicleInfo {
  id: number;
  plate_number: string;
  vehicle_type: string;
  balance: string;
}

interface TopupResult {
  plate_number: string;
  vehicle_type: string;
  amount_added: string;
  balance_before: string;
  new_balance: string;
}

export default function TopupPage() {
  const { addToast } = useToast();

  const [plate, setPlate] = useState('');
  const [lookupLoading, setLookupLoading] = useState(false);
  const [vehicleInfo, setVehicleInfo] = useState<VehicleInfo | null>(null);
  const [lookupError, setLookupError] = useState('');

  const [amount, setAmount] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<TopupResult | null>(null);

  const handleLookup = async () => {
    const normalized = normalizePlate(plate);
    if (!normalized) return;
    setLookupLoading(true);
    setLookupError('');
    setVehicleInfo(null);
    setResult(null);
    setAmount('');
    try {
      const vehicle = await vehiclesApi.byPlate(normalized);
      const account = await accountsApi.byVehicle(vehicle.id);
      setVehicleInfo({
        id: vehicle.id,
        plate_number: vehicle.plate_number,
        vehicle_type: vehicle.vehicle_type,
        balance: account.balance,
      });
    } catch {
      setLookupError('Vehicle not found. Check the plate number and try again.');
    } finally {
      setLookupLoading(false);
    }
  };

  const handleTopup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!vehicleInfo || !amount || parseFloat(amount) <= 0) {
      addToast({ type: 'error', title: 'Validation Error', message: 'Enter a valid amount greater than zero.' });
      return;
    }
    setIsSubmitting(true);
    try {
      const res = await accountsApi.plateTopup(vehicleInfo.plate_number, parseFloat(amount));
      setResult(res);
      setVehicleInfo((prev) => prev ? { ...prev, balance: res.new_balance } : prev);
      setAmount('');
      addToast({ type: 'success', title: 'Balance Updated', message: `PKR ${parseFloat(res.amount_added).toLocaleString()} added to ${res.plate_number}.` });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Topup failed';
      addToast({ type: 'error', title: 'Topup Failed', message });
    } finally {
      setIsSubmitting(false);
    }
  };

  const reset = () => {
    setPlate('');
    setVehicleInfo(null);
    setLookupError('');
    setAmount('');
    setResult(null);
  };

  const VehicleIcon = vehicleInfo ? (vehicleIcons[vehicleInfo.vehicle_type] || Car) : Car;

  return (
    <div className="max-w-xl mx-auto animate-fade-in-up">
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-1">
          <Wallet className="w-6 h-6 text-success" />
          <h1 className="text-2xl font-bold text-ink">Balance Topup</h1>
        </div>
        <p className="text-sm text-ink-muted mt-1">
          Search a vehicle by plate number and add balance to its wallet.
        </p>
      </div>

      {/* Plate Search */}
      <div className="bg-surface border border-line rounded-xl skeu-card p-6 mb-5">
        <label className="block text-xs font-medium text-ink-muted uppercase tracking-wider mb-2">
          Vehicle Plate Number
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={plate}
            onChange={(e) => {
              setPlate(normalizePlate(e.target.value));
              setVehicleInfo(null);
              setLookupError('');
              setResult(null);
            }}
            onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleLookup())}
            placeholder="e.g. LHR1234"
            className="flex-1 min-w-0 px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-success focus:ring-2 focus:ring-success/20 transition-all uppercase"
          />
          <button
            type="button"
            onClick={handleLookup}
            disabled={!plate.trim() || lookupLoading}
            className="shrink-0 px-4 py-3 bg-brand text-brand-on rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
          >
            {lookupLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
          </button>
        </div>
        {lookupError && <p className="text-xs text-danger mt-2">{lookupError}</p>}
      </div>

      {/* Vehicle Card */}
      {vehicleInfo && (
        <div className="bg-surface border border-line rounded-xl skeu-card overflow-hidden mb-5 animate-fade-in-up">
          <div className="flex items-center gap-4 p-5 border-b border-line">
            <div className="p-3 bg-brand/10 rounded-xl">
              <VehicleIcon className="w-6 h-6 text-brand" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-lg font-bold font-mono text-ink">{vehicleInfo.plate_number}</p>
              <p className="text-sm text-ink-muted capitalize">{vehicleInfo.vehicle_type}</p>
            </div>
            <div className="text-right">
              <p className="text-xs text-ink-muted mb-0.5">Current Balance</p>
              <p className="text-xl font-bold text-success">
                PKR {parseFloat(vehicleInfo.balance).toLocaleString()}
              </p>
            </div>
          </div>

          {/* Topup form */}
          <form onSubmit={handleTopup} className="p-5 space-y-4">
            <div>
              <label className="block text-sm font-medium text-ink mb-1.5">
                Amount to Add <span className="text-danger">*</span>
              </label>
              <div className="relative">
                <span className="absolute left-4 top-1/2 -translate-y-1/2 text-sm font-medium text-ink-subtle">PKR</span>
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="500"
                  className="w-full pl-14 pr-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-success focus:ring-2 focus:ring-success/20 transition-all"
                  autoFocus
                />
              </div>
              {amount && parseFloat(amount) > 0 && (
                <p className="text-xs text-ink-subtle mt-1.5">
                  New balance will be:{' '}
                  <span className="font-semibold text-success">
                    PKR {(parseFloat(vehicleInfo.balance) + parseFloat(amount)).toLocaleString()}
                  </span>
                </p>
              )}
            </div>

            {/* Quick amount buttons */}
            <div className="flex gap-2 flex-wrap">
              {[500, 1000, 2000, 5000].map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => setAmount(String(preset))}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                    amount === String(preset)
                      ? 'bg-brand text-brand-on border-brand'
                      : 'bg-elevated border-line text-ink-muted hover:border-success hover:text-success'
                  }`}
                >
                  +{preset.toLocaleString()}
                </button>
              ))}
            </div>

            <div className="flex gap-3 pt-1">
              <button
                type="button"
                onClick={reset}
                className="flex-1 py-2.5 bg-elevated border border-line text-ink text-sm font-medium rounded-xl hover:bg-surface transition-colors"
              >
                Clear
              </button>
              <button
                type="submit"
                disabled={isSubmitting || !amount || parseFloat(amount) <= 0}
                className="flex-1 py-2.5 bg-brand text-brand-on text-sm font-semibold rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {isSubmitting
                  ? <><Loader2 className="w-4 h-4 animate-spin" />Processing…</>
                  : <><Plus className="w-4 h-4" />Add Balance</>}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Success receipt */}
      {result && (
        <div className="bg-surface border border-success/30 rounded-xl p-5 shadow-sm animate-fade-in-up">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-9 h-9 bg-success/10 rounded-full flex items-center justify-center">
              <CheckCircle className="w-5 h-5 text-success" />
            </div>
            <div>
              <p className="text-sm font-semibold text-ink">Topup Successful</p>
              <p className="text-xs text-ink-muted">{result.plate_number} · {result.vehicle_type}</p>
            </div>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-ink-muted">Amount Added</span>
              <span className="font-bold text-success">+ PKR {parseFloat(result.amount_added).toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-ink-muted">Previous Balance</span>
              <span className="text-ink">PKR {parseFloat(result.balance_before).toLocaleString()}</span>
            </div>
            <div className="flex justify-between pt-2 border-t border-line">
              <span className="font-medium text-ink">New Balance</span>
              <span className="font-bold text-success flex items-center gap-1">
                <ArrowRight className="w-3.5 h-3.5" />
                PKR {parseFloat(result.new_balance).toLocaleString()}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
