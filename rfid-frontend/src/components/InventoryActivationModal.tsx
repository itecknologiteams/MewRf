import { useState, useEffect } from 'react';
import { X, Loader2, User, Phone, CreditCard, CheckCircle, Wallet } from 'lucide-react';
import { useToast } from '@/context/ToastContext';
import { accountsApi, type CashTopupResult, type TopupLookupResult } from '@/services/api';

interface InventoryActivationModalProps {
  tag: {
    tag_serial: string;
    tid: string;
    vehicle_plate?: string;
    vehicle_type?: string;
    booth_assigned_id?: number;
  };
  activationBoothId: number;
  onSuccess: (result: CashTopupResult) => void;
  onClose: () => void;
}

const PRESETS = [500, 1000, 2000, 5000];

// Format digits into CNIC XXXXX-XXXXXXX-X (UI only; digits-only sent to API).
const formatCnic = (raw: string) => {
  const d = raw.replace(/\D/g, '').slice(0, 13);
  if (d.length <= 5) return d;
  if (d.length <= 12) return `${d.slice(0, 5)}-${d.slice(5)}`;
  return `${d.slice(0, 5)}-${d.slice(5, 12)}-${d.slice(12)}`;
};

export default function InventoryActivationModal({
  tag,
  activationBoothId,
  onSuccess,
  onClose,
}: InventoryActivationModalProps) {
  const { addToast } = useToast();

  const [looking, setLooking] = useState(true);
  const [found, setFound] = useState(false);
  const [balance, setBalance] = useState<string | null>(null);

  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [cnic, setCnic] = useState('');
  const [vehicleReg, setVehicleReg] = useState('');
  const [amount, setAmount] = useState('');

  const [submitting, setSubmitting] = useState(false);
  const [receipt, setReceipt] = useState<CashTopupResult | null>(null);

  useEffect(() => {
    let active = true;
    if (!tag.tid) {
      setLooking(false);
      addToast({ type: 'error', title: 'Missing tag id', message: 'This tag has no chip TID; cannot activate.' });
      return;
    }
    (async () => {
      try {
        const r: TopupLookupResult = await accountsApi.topupLookup(tag.tid);
        if (!active) return;
        setFound(r.found);
        if (r.found) {
          setName(r.consumer_name ?? '');
          setPhone(r.phone ?? '');
          setCnic(r.cnic ? formatCnic(r.cnic) : '');
          setVehicleReg(r.plate ?? '');
          setBalance(r.balance ?? '0');
        }
      } catch {
        if (active) addToast({ type: 'error', title: 'Lookup failed', message: 'Could not look up the tag.' });
      } finally {
        if (active) setLooking(false);
      }
    })();
    return () => { active = false; };
  }, [tag.tid, addToast]);

  const submit = async () => {
    if (!amount || parseFloat(amount) <= 0) {
      addToast({ type: 'error', title: 'Validation', message: 'Enter a valid amount greater than zero.' });
      return;
    }
    if (!found && (!name.trim() || !phone.trim() || !vehicleReg.trim())) {
      addToast({ type: 'error', title: 'Validation', message: 'Name, phone and vehicle registration are required to register.' });
      return;
    }
    setSubmitting(true);
    try {
      const result = await accountsApi.cashTopup({
        tid: tag.tid,
        amount: String(parseFloat(amount)),
        epc: '',
        consumer_name: name.trim(),
        cnic: cnic.replace(/\D/g, ''),
        phone: phone.trim(),
        vehicle_reg: vehicleReg.trim(),
        activation_booth_id: activationBoothId,
      });
      setReceipt(result);
      addToast({ type: 'success', title: result.registered ? 'Registered & Activated' : 'Topped Up', message: `New balance PKR ${parseFloat(result.new_balance).toLocaleString()}.` });
      setTimeout(() => onSuccess(result), 1800);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Activation failed';
      addToast({ type: 'error', title: 'Failed', message });
    } finally {
      setSubmitting(false);
    }
  };

  const inputCls =
    'w-full px-3 py-2.5 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all disabled:opacity-60';

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-surface border border-line rounded-2xl skeu-card max-w-md w-full">
        {/* Header */}
        <div className="flex justify-between items-center p-6 border-b border-line">
          <div>
            <h2 className="text-lg font-bold text-ink">Activate Tag</h2>
            <p className="text-sm text-ink-muted mt-0.5 font-mono">{tag.tag_serial}</p>
          </div>
          <button
            onClick={onClose}
            disabled={submitting || !!receipt}
            className="p-1.5 rounded-lg text-ink-subtle hover:bg-elevated hover:text-ink transition-colors disabled:opacity-50"
          >
            <X size={20} />
          </button>
        </div>

        <div className="p-6">
          {looking ? (
            <div className="flex items-center justify-center py-10">
              <Loader2 className="animate-spin text-brand" size={28} />
            </div>
          ) : receipt ? (
            <div className="animate-fade-in-up">
              <div className="flex flex-col items-center text-center mb-4">
                <div className="w-12 h-12 rounded-full bg-success/10 flex items-center justify-center mb-2">
                  <CheckCircle className="text-success" size={28} />
                </div>
                <p className="font-semibold text-ink">
                  {receipt.registered ? 'Registered & Activated' : 'Topped Up'}
                </p>
              </div>
              {receipt.receipt && (
                <div className="space-y-2 text-sm bg-elevated rounded-xl p-4">
                  {([
                    ['Receipt', receipt.receipt.receipt_no],
                    ['Consumer', receipt.receipt.consumer_name],
                    ['Vehicle', receipt.receipt.vehicle_reg],
                    ['Amount', `PKR ${parseFloat(receipt.receipt.amount).toLocaleString()}`],
                    ['New Balance', `PKR ${parseFloat(receipt.receipt.balance_after).toLocaleString()}`],
                  ] as [string, string][]).map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span className="text-ink-muted">{k}</span>
                      <span className="font-medium text-ink">{v}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              {found ? (
                <div className="flex items-center justify-between bg-elevated rounded-xl px-4 py-3">
                  <div>
                    <p className="font-semibold text-ink">{name}</p>
                    <p className="text-xs text-ink-muted">{phone} · {vehicleReg}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-[10px] text-ink-muted uppercase tracking-wider">Balance</p>
                    <p className="font-bold text-success">
                      PKR {parseFloat(balance ?? '0').toLocaleString()}
                    </p>
                  </div>
                </div>
              ) : (
                <>
                  <div>
                    <label className="block text-sm font-medium text-ink mb-1"><User size={14} className="inline mr-1.5" />Customer Name</label>
                    <input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} placeholder="Full name" disabled={submitting} />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-ink mb-1"><Phone size={14} className="inline mr-1.5" />Phone</label>
                    <input className={inputCls} value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="03001234567" disabled={submitting} />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-ink mb-1"><CreditCard size={14} className="inline mr-1.5" />CNIC (optional)</label>
                    <input className={inputCls} value={cnic} onChange={(e) => setCnic(formatCnic(e.target.value))} placeholder="XXXXX-XXXXXXX-X" disabled={submitting} />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-ink mb-1">Vehicle Registration</label>
                    <input className={`${inputCls} uppercase`} value={vehicleReg} onChange={(e) => setVehicleReg(e.target.value)} placeholder="LEB1234" disabled={submitting} />
                  </div>
                </>
              )}

              <div>
                <label className="block text-sm font-medium text-ink mb-1"><Wallet size={14} className="inline mr-1.5" />Amount (Cash)</label>
                <input className={inputCls} type="number" min="1" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="500" disabled={submitting} />
                <div className="flex gap-2 flex-wrap mt-2">
                  {PRESETS.map((p) => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => setAmount(String(p))}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                        amount === String(p)
                          ? 'bg-brand text-brand-on border-brand'
                          : 'bg-elevated border-line text-ink-muted hover:border-success hover:text-success'
                      }`}
                    >
                      +{p.toLocaleString()}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex gap-3 pt-2">
                <button onClick={onClose} disabled={submitting} className="flex-1 py-2.5 bg-elevated border border-line text-ink text-sm font-medium rounded-xl hover:bg-surface transition-colors disabled:opacity-50">Cancel</button>
                <button onClick={submit} disabled={submitting} className="flex-1 py-2.5 bg-brand text-brand-on text-sm font-semibold rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2">
                  {submitting && <Loader2 className="animate-spin" size={16} />}
                  {found ? 'Top Up' : 'Register & Activate'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
