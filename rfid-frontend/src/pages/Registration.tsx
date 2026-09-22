import { useState, useEffect, useRef } from 'react';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { vehiclesApi, authApi } from '@/services/api';
import { formatCnic } from '@/lib/cnic';
import { normalizePlate } from '@/lib/plate';
import type { MeResponse, TagScanLookup } from '@/services/api';
import {
  User,
  Car,
  CheckCircle,
  Loader2,
  ArrowRight,
  Search,
  UserPlus,
  ScanLine,
  XCircle,
  AlertTriangle,
} from 'lucide-react';

interface VehicleForm {
  plate_number: string;
  vehicle_type: string;
  tag_serial: string;
  initial_balance: string;
}

// Where tag_reader_agent.py publishes reads. Loopback only — it is the
// operator's own machine, and the agent holds no credentials.
const READER_AGENT_URL =
  (import.meta.env.VITE_READER_AGENT_URL as string) || 'http://127.0.0.1:8765';

const initialVehicleForm: VehicleForm = {
  plate_number: '',
  vehicle_type: 'car',
  tag_serial: '',
  initial_balance: '',
};

export default function Registration() {
  const { addToast } = useToast();
  const { user } = useAuth();
  // Admins and operators register vehicles for customers; anyone else can only
  // register their own.
  const canPickOwner = user?.role === 'admin' || user?.role === 'operator';

  const [step, setStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const [createdTagSerial, setCreatedTagSerial] = useState('');

  // Step 1 — owner mode
  const [ownerMode, setOwnerMode] = useState<'existing' | 'new'>('new');

  // Existing user search
  const [searchPhone, setSearchPhone] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [foundUser, setFoundUser] = useState<MeResponse | null>(null);

  // New user form
  const [newFullName, setNewFullName] = useState('');
  const [newPhone, setNewPhone] = useState('');
  const [newCnic, setNewCnic] = useState('');
  const [isRegistering, setIsRegistering] = useState(false);

  // Resolved owner (populated from either path)
  const [ownerId, setOwnerId] = useState(canPickOwner ? '' : user?.id?.toString() || '');
  const [ownerName, setOwnerName] = useState(canPickOwner ? '' : user?.full_name || '');
  const [ownerPhone, setOwnerPhone] = useState(canPickOwner ? '' : user?.phone || '');

  // Step 2
  const [vehicleForm, setVehicleForm] = useState<VehicleForm>(initialVehicleForm);
  const [errors, setErrors] = useState<Partial<VehicleForm>>({});
  const [availableTags, setAvailableTags] = useState<{ id: number; tag_serial: string; epc: string }[]>([]);

  // Scan-to-identify. The operator holds a tag whose serial is printed too
  // small to read reliably; the reader reports a TID instead, which means
  // nothing to them. This turns one into the other.
  const [scanValue, setScanValue] = useState('');
  // The reader is USB on this PC; the backend is remote. tag_reader_agent.py
  // publishes each read on loopback and we pick it up here, so the lookup runs
  // as the operator's own already-authenticated request — no API credentials
  // ever sit on a registration desk.
  const [readerOnline, setReaderOnline] = useState(false);
  const lastSeqRef = useRef<number | null>(null);
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<TagScanLookup | null>(null);
  const scanInputRef = useRef<HTMLInputElement>(null);
  const [loadingTags, setLoadingTags] = useState(false);

  useEffect(() => {
    if (step === 2) {
      setLoadingTags(true);
      vehiclesApi.availableTags()
        .then(setAvailableTags)
        .catch(() => addToast({ type: 'error', title: 'Error', message: 'Failed to load available tags.' }))
        .finally(() => setLoadingTags(false));
    }
  }, [step]);

  const updateVehicleField = (field: keyof VehicleForm, value: string) => {
    setVehicleForm((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) setErrors((prev) => ({ ...prev, [field]: undefined }));
  };

  const lookupScannedTag = async (raw: string) => {
    const value = raw.trim();
    if (!value) return;
    setScanning(true);
    setScanResult(null);
    try {
      // Readers vary in whether they report the chip TID or the EPC, so ask on
      // both keys and let the backend prefer the TID.
      const result = await vehiclesApi.scanLookup({ tid: value, epc: value });
      setScanResult(result);
      if (result.available && result.tag_serial) {
        updateVehicleField('tag_serial', result.tag_serial);
      }
    } catch (err: unknown) {
      addToast({
        type: 'error',
        title: 'Scan lookup failed',
        message: err instanceof Error ? err.message : 'Could not identify that tag',
      });
    } finally {
      setScanning(false);
      setScanValue('');
      // Straight back to the field so the next tag can be scanned without
      // reaching for the mouse.
      scanInputRef.current?.focus();
    }
  };

  // Poll the local agent for new reads. Deliberately tolerant: if the agent is
  // not running the page simply stays in manual-entry mode rather than erroring
  // at an operator who has no reader.
  const lookupRef = useRef(lookupScannedTag);
  useEffect(() => { lookupRef.current = lookupScannedTag; });

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const response = await fetch(`${READER_AGENT_URL}/tag`, { cache: 'no-store' });
        if (!response.ok) throw new Error('agent error');
        const data = await response.json();
        if (cancelled) return;
        setReaderOnline(true);
        // seq 0 means the agent is up but nothing has been read yet. On first
        // sight we only record where the counter is, so an old read left over
        // from a previous customer cannot auto-fill this form.
        if (lastSeqRef.current === null) {
          lastSeqRef.current = data.seq;
        } else if (data.seq > lastSeqRef.current) {
          lastSeqRef.current = data.seq;
          if (data.tid || data.epc) lookupRef.current(data.tid || data.epc);
        }
      } catch {
        if (!cancelled) setReaderOnline(false);
      }
    };
    tick();
    const id = setInterval(tick, 800);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  const validateStep2 = (): boolean => {
    const newErrors: Partial<VehicleForm> = {};
    if (!vehicleForm.plate_number.trim()) newErrors.plate_number = 'Plate number is required';
    if (!vehicleForm.tag_serial.trim()) newErrors.tag_serial = 'Tag serial is required';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSearchUser = async () => {
    if (!searchPhone.trim()) {
      addToast({ type: 'error', title: 'Phone Required', message: 'Enter a phone number to search.' });
      return;
    }
    setIsSearching(true);
    setFoundUser(null);
    setOwnerId('');
    try {
      const phone = searchPhone.replace(/\s/g, '');
      const results = await authApi.adminUsers({ search: phone });
      // Search is a substring match on phone or name; the owner must be this exact number.
      const u = results.find((r) => r.phone === phone);
      if (!u) {
        addToast({ type: 'error', title: 'Not Found', message: 'No user found with that phone number.' });
        return;
      }
      setFoundUser(u);
      setOwnerId(u.id.toString());
      setOwnerName(u.full_name);
      setOwnerPhone(u.phone);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Search failed';
      addToast({ type: 'error', title: 'Search Failed', message });
    } finally {
      setIsSearching(false);
    }
  };

  const handleRegisterNewUser = async () => {
    if (!newFullName.trim() || !newPhone.trim() || !newCnic.trim()) {
      addToast({ type: 'error', title: 'Validation Error', message: 'Name, phone, and CNIC are required.' });
      return;
    }
    setIsRegistering(true);
    setOwnerId('');
    try {
      await authApi.register({ full_name: newFullName.trim(), phone: newPhone.trim(), cnic: newCnic.trim() });
      // Fetch the newly created user by phone to get their DB id
      const results = await authApi.adminUsers({ search: newPhone.trim() });
      const u = results.find((r) => r.phone === newPhone.trim());
      if (!u) throw new Error('User created but could not be retrieved.');
      setOwnerId(u.id.toString());
      setOwnerName(u.full_name);
      setOwnerPhone(u.phone);
      addToast({ type: 'success', title: 'User Created', message: `Account created for ${u.full_name}.` });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Registration failed';
      addToast({ type: 'error', title: 'User Creation Failed', message });
    } finally {
      setIsRegistering(false);
    }
  };

  const handleStep1Next = () => {
    if (!ownerId) {
      const hint = ownerMode === 'existing'
        ? 'Please search and select a user first.'
        : 'Please create the user account first.';
      addToast({ type: 'error', title: 'Owner Required', message: hint });
      return;
    }
    setStep(2);
  };

  const handleStep2Next = () => {
    if (!validateStep2()) {
      addToast({ type: 'error', title: 'Validation Error', message: 'Please fill all required fields.' });
      return;
    }
    setStep(3);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      const created = await vehiclesApi.create({
        plate_number: vehicleForm.plate_number,
        vehicle_type: vehicleForm.vehicle_type,
        owner_id: parseInt(ownerId),
        tag_serial: vehicleForm.tag_serial,
        initial_balance: vehicleForm.initial_balance ? parseFloat(vehicleForm.initial_balance) : 0,
      });
      setCreatedTagSerial(created.tag?.tag_serial || vehicleForm.tag_serial);
      setShowSuccess(true);
      addToast({ type: 'success', title: 'M-Tag Registered', message: 'Vehicle registered successfully with M-Tag.' });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Registration failed';
      addToast({ type: 'error', title: 'Registration Failed', message });
    } finally {
      setIsSubmitting(false);
    }
  };

  const resetAll = () => {
    setShowSuccess(false);
    setStep(1);
    setOwnerMode('existing');
    setSearchPhone('');
    setFoundUser(null);
    setNewFullName('');
    setNewPhone('');
    setNewCnic('');
    setOwnerId(canPickOwner ? '' : user?.id?.toString() || '');
    setOwnerName(canPickOwner ? '' : user?.full_name || '');
    setOwnerPhone(canPickOwner ? '' : user?.phone || '');
    setVehicleForm(initialVehicleForm);
    setAvailableTags([]);
  };

  if (showSuccess) {
    return (
      <div className="flex items-center justify-center min-h-[60vh] animate-fade-in-up">
        <div className="bg-surface border border-line rounded-2xl skeu-card p-8 text-center max-w-md w-full">
          <div className="w-16 h-16 bg-success/10 rounded-full flex items-center justify-center mx-auto mb-4">
            <CheckCircle className="w-8 h-8 text-success" />
          </div>
          <h2 className="text-xl font-bold text-ink mb-2">Registration Complete!</h2>
          <p className="text-sm text-ink-muted mb-6">
            M-Tag registered. The vehicle can now use expressway toll plazas without stopping.
          </p>
          <div className="bg-elevated rounded-xl p-4 mb-6 text-left space-y-1">
            <p className="text-xs text-ink-muted uppercase tracking-wider mb-1">M-Tag Serial</p>
            <p className="text-lg font-mono font-bold text-ink">{createdTagSerial}</p>
            <p className="text-xs text-ink-muted">Plate: {vehicleForm.plate_number}</p>
            <p className="text-xs text-ink-muted">Owner: {ownerName} · {ownerPhone}</p>
            <p className="text-xs text-ink-muted">
              Balance: <span className="font-semibold text-success">PKR {vehicleForm.initial_balance ? parseFloat(vehicleForm.initial_balance).toLocaleString() : '0'}</span>
            </p>
          </div>
          <button
            onClick={resetAll}
            className="w-full py-3 bg-brand text-brand-on font-semibold rounded-xl hover:opacity-90 transition-opacity"
          >
            Register Another Vehicle
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto animate-fade-in-up">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-ink">ME-Tag Registration</h1>
        <p className="text-sm text-ink-muted mt-1">
          Register a new vehicle for Smart Expressway toll collection
        </p>
      </div>

      {/* Step indicator */}
      <div className="flex items-center gap-2 mb-8">
        {[1, 2, 3].map((s) => (
          <div key={s} className="flex items-center gap-2">
            <button
              onClick={() => { if (s < step) setStep(s); }}
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold transition-colors ${
                step === s
                  ? 'bg-brand text-brand-on'
                  : step > s
                  ? 'bg-brand text-brand-on cursor-pointer'
                  : 'bg-elevated text-ink-muted border border-line'
              }`}
            >
              {step > s ? <CheckCircle className="w-4 h-4" /> : s}
            </button>
            <span className={`text-xs font-medium ${step === s ? 'text-brand' : 'text-ink-muted'}`}>
              {s === 1 ? 'Owner' : s === 2 ? 'Vehicle & Tag' : 'Confirm'}
            </span>
            {s < 3 && <ArrowRight className="w-4 h-4 text-ink-subtle" />}
          </div>
        ))}
      </div>

      <div className="bg-surface border border-line rounded-xl skeu-card overflow-hidden">

        {/* ── Step 1: Owner ── */}
        {step === 1 && (
          <div className="p-6 animate-fade-in-up">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 bg-brand/10 rounded-lg">
                <User className="w-5 h-5 text-brand" />
              </div>
              <h2 className="text-lg font-semibold text-ink">Vehicle Owner</h2>
            </div>

            {!canPickOwner ? (
              <div className="bg-elevated rounded-xl p-5">
                <p className="text-xs text-ink-muted uppercase tracking-wider mb-1">Registering for</p>
                <p className="text-base font-semibold text-ink">{user?.full_name}</p>
                <p className="text-sm text-ink-muted">{user?.phone}</p>
                <p className="text-xs text-ink-subtle mt-1">User ID: {user?.id}</p>
              </div>
            ) : (
              <div className="space-y-5">
                {/* Mode toggle */}
                <div className="flex gap-2 p-1 bg-elevated rounded-xl w-fit">
                  <button
                    type="button"
                    onClick={() => { setOwnerMode('existing'); setOwnerId(''); setFoundUser(null); }}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                      ownerMode === 'existing'
                        ? 'bg-surface text-brand shadow-sm'
                        : 'text-ink-muted hover:text-ink'
                    }`}
                  >
                    <Search className="w-4 h-4" />
                    Existing User
                  </button>
                  <button
                    type="button"
                    onClick={() => { setOwnerMode('new'); setOwnerId(''); setFoundUser(null); }}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                      ownerMode === 'new'
                        ? 'bg-surface text-brand shadow-sm'
                        : 'text-ink-muted hover:text-ink'
                    }`}
                  >
                    <UserPlus className="w-4 h-4" />
                    New User
                  </button>
                </div>

                {/* Existing user search */}
                {ownerMode === 'existing' && (
                  <div className="space-y-3">
                    <div>
                      <label className="block text-sm font-medium text-ink mb-1.5">
                        Phone Number <span className="text-danger">*</span>
                      </label>
                      <div className="flex gap-2">
                        <div className="relative flex-1">
                          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-subtle" />
                          <input
                            type="tel"
                            value={searchPhone}
                            onChange={(e) => setSearchPhone(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleSearchUser()}
                            placeholder="03001234567"
                            className="w-full pl-10 pr-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
                          />
                        </div>
                        <button
                          type="button"
                          onClick={handleSearchUser}
                          disabled={isSearching}
                          className="flex items-center gap-2 px-5 py-3 bg-brand text-brand-on text-sm font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-60"
                        >
                          {isSearching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                          Find
                        </button>
                      </div>
                    </div>
                    {foundUser && (
                      <div className="bg-success/5 border border-success/20 rounded-xl p-4 flex items-center gap-3">
                        <CheckCircle className="w-5 h-5 text-success flex-shrink-0" />
                        <div>
                          <p className="text-sm font-semibold text-ink">{foundUser.full_name}</p>
                          <p className="text-xs text-ink-muted">{foundUser.phone} · ID: {foundUser.id}</p>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* New user form */}
                {ownerMode === 'new' && (
                  <div className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-ink mb-1.5">
                          Full Name <span className="text-danger">*</span>
                        </label>
                        <input
                          type="text"
                          value={newFullName}
                          onChange={(e) => setNewFullName(e.target.value)}
                          placeholder="Muhammad Ali"
                          className="w-full px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-ink mb-1.5">
                          Phone <span className="text-danger">*</span>
                        </label>
                        <input
                          type="tel"
                          value={newPhone}
                          onChange={(e) => setNewPhone(e.target.value)}
                          placeholder="03001234567"
                          className="w-full px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-ink mb-1.5">
                          CNIC <span className="text-danger">*</span>
                        </label>
                        <input
                          type="text"
                          value={newCnic}
                          onChange={(e) => setNewCnic(formatCnic(e.target.value))}
                          placeholder="35201-1234567-8"
                          className="w-full px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
                        />
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={handleRegisterNewUser}
                      disabled={isRegistering || !!ownerId}
                      className="flex items-center gap-2 px-5 py-3 bg-brand text-brand-on text-sm font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-60"
                    >
                      {isRegistering ? (
                        <><Loader2 className="w-4 h-4 animate-spin" />Creating...</>
                      ) : ownerId ? (
                        <><CheckCircle className="w-4 h-4" />User Created</>
                      ) : (
                        <><UserPlus className="w-4 h-4" />Create User Account</>
                      )}
                    </button>
                    {ownerId && ownerMode === 'new' && (
                      <div className="bg-success/5 border border-success/20 rounded-xl p-4 flex items-center gap-3">
                        <CheckCircle className="w-5 h-5 text-success flex-shrink-0" />
                        <div>
                          <p className="text-sm font-semibold text-ink">{ownerName}</p>
                          <p className="text-xs text-ink-muted">{ownerPhone} · ID: {ownerId}</p>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            <div className="flex justify-end mt-6">
              <button
                type="button"
                onClick={handleStep1Next}
                className="flex items-center gap-2 px-6 py-2.5 bg-brand text-brand-on text-sm font-medium rounded-xl hover:opacity-90 transition-opacity"
              >
                Next Step
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* ── Step 2: Vehicle & Tag ── */}
        {step === 2 && (
          <div className="p-6 animate-fade-in-up">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 bg-info/10 rounded-lg">
                <Car className="w-5 h-5 text-info" />
              </div>
              <h2 className="text-lg font-semibold text-ink">Vehicle & Tag Details</h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div>
                <label className="block text-sm font-medium text-ink mb-1.5">
                  Plate Number <span className="text-danger">*</span>
                </label>
                <input
                  type="text"
                  value={vehicleForm.plate_number}
                  onChange={(e) => updateVehicleField('plate_number', normalizePlate(e.target.value))}
                  placeholder="LHR1234"
                  className={`w-full px-4 py-3 bg-elevated border rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all ${
                    errors.plate_number ? 'border-danger' : 'border-line'
                  }`}
                />
                {errors.plate_number && <p className="text-xs text-danger mt-1">{errors.plate_number}</p>}
              </div>

              <div>
                <label className="block text-sm font-medium text-ink mb-1.5">
                  Vehicle Type <span className="text-danger">*</span>
                </label>
                <select
                  value={vehicleForm.vehicle_type}
                  onChange={(e) => updateVehicleField('vehicle_type', e.target.value)}
                  className="w-full px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
                >
                  <option value="car">Car</option>
                  <option value="truck">Truck</option>
                  <option value="bus">Bus</option>
                  <option value="motorcycle">Motorcycle</option>
                </select>
              </div>

              <div className="md:col-span-2">
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-sm font-medium text-ink">
                    Scan the tag <span className="text-ink-subtle font-normal">(recommended)</span>
                  </label>
                  <span
                    className={`inline-flex items-center gap-1.5 text-xs font-medium ${
                      readerOnline ? 'text-success' : 'text-ink-subtle'
                    }`}
                    title={
                      readerOnline
                        ? 'The local reader agent is running — place a tag on the reader.'
                        : 'Reader agent not detected. Type or paste a TID instead, or start it with: python tools/tag_reader_agent.py --serve'
                    }
                  >
                    <span
                      className={`w-1.5 h-1.5 rounded-full ${
                        readerOnline ? 'bg-success animate-pulse' : 'bg-ink-subtle'
                      }`}
                    />
                    {readerOnline ? 'Reader connected' : 'Reader not detected'}
                  </span>
                </div>
                <div className="relative">
                  <ScanLine className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-subtle" />
                  <input
                    ref={scanInputRef}
                    type="text"
                    value={scanValue}
                    onChange={(e) => setScanValue(e.target.value)}
                    onKeyDown={(e) => {
                      // Readers end a read with Enter. Submitting the whole form
                      // here would register the customer on a scan.
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        lookupScannedTag(scanValue);
                      }
                    }}
                    placeholder="Place the tag on the reader, or type its TID"
                    autoComplete="off"
                    spellCheck={false}
                    className="w-full pl-10 pr-24 py-3 bg-elevated border border-line rounded-xl text-sm font-mono text-ink placeholder:text-ink-subtle placeholder:font-sans outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => lookupScannedTag(scanValue)}
                    disabled={scanning || !scanValue.trim()}
                    className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1.5 px-3 py-1.5 bg-brand text-brand-on text-xs font-medium rounded-lg hover:opacity-90 transition-opacity disabled:opacity-40"
                  >
                    {scanning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
                    Identify
                  </button>
                </div>

                {scanResult && (
                  <div
                    className={`mt-2 flex items-start gap-2 px-3 py-2.5 rounded-xl border text-sm ${
                      scanResult.available
                        ? 'bg-success/10 border-success/20 text-success'
                        : scanResult.status === 'not_in_inventory'
                          ? 'bg-warning/10 border-warning/20 text-warning'
                          : 'bg-danger/10 border-danger/20 text-danger'
                    }`}
                  >
                    {scanResult.available
                      ? <CheckCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                      : scanResult.status === 'not_in_inventory'
                        ? <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                        : <XCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />}
                    <div className="min-w-0">
                      <p className="font-medium">{scanResult.message}</p>
                      {scanResult.tid && (
                        <p className="text-xs opacity-80 font-mono mt-0.5 break-all">TID {scanResult.tid}</p>
                      )}
                    </div>
                  </div>
                )}
                <p className="text-xs text-ink-subtle mt-1.5">
                  {readerOnline
                    ? "Place a tag on the reader — it identifies itself and fills the serial in below. The tag is only issued when you submit."
                    : "Type or paste the tag's TID. To read tags automatically, run the reader agent on this PC."}
                </p>
              </div>

              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-ink mb-1.5">
                  M-Tag Serial <span className="text-danger">*</span>
                </label>
                {loadingTags ? (
                  <div className="flex items-center gap-2 px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink-subtle">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Loading available tags…
                  </div>
                ) : (
                  <select
                    value={vehicleForm.tag_serial}
                    onChange={(e) => updateVehicleField('tag_serial', e.target.value)}
                    className={`w-full px-4 py-3 bg-elevated border rounded-xl text-sm text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all ${
                      errors.tag_serial ? 'border-danger' : 'border-line'
                    }`}
                  >
                    <option value="">— Select an unassigned tag —</option>
                    {availableTags.map((t) => (
                      <option key={t.id} value={t.tag_serial}>
                        {t.tag_serial}
                      </option>
                    ))}
                  </select>
                )}
                {!loadingTags && availableTags.length === 0 && (
                  <p className="text-xs text-ink-subtle mt-1">No unassigned tags in inventory.</p>
                )}
                {!loadingTags && availableTags.length > 0 && (
                  <p className="text-xs text-ink-subtle mt-1">Showing {availableTags.length} unassigned tag{availableTags.length > 1 ? 's' : ''}.</p>
                )}
                {errors.tag_serial && <p className="text-xs text-danger mt-1">{errors.tag_serial}</p>}
              </div>

              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-ink mb-1.5">
                  Initial Balance <span className="text-ink-subtle font-normal">(optional)</span>
                </label>
                <div className="relative">
                  <span className="absolute left-4 top-1/2 -translate-y-1/2 text-sm font-medium text-ink-subtle">PKR</span>
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={vehicleForm.initial_balance}
                    onChange={(e) => updateVehicleField('initial_balance', e.target.value)}
                    placeholder="0"
                    className="w-full pl-14 pr-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-success focus:ring-2 focus:ring-success/20 transition-all"
                  />
                </div>
                <p className="text-xs text-ink-subtle mt-1">Leave empty to start with Rs. 0 balance.</p>
              </div>
            </div>

            <div className="flex justify-between mt-6">
              <button type="button" onClick={() => setStep(1)} className="px-6 py-2.5 bg-elevated border border-line text-ink text-sm font-medium rounded-xl hover:bg-surface transition-colors">
                Back
              </button>
              <button type="button" onClick={handleStep2Next} className="flex items-center gap-2 px-6 py-2.5 bg-brand text-brand-on text-sm font-medium rounded-xl hover:opacity-90 transition-opacity">
                Next Step
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* ── Step 3: Confirm ── */}
        {step === 3 && (
          <form onSubmit={handleSubmit} className="p-6 animate-fade-in-up">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 bg-success/10 rounded-lg">
                <CheckCircle className="w-5 h-5 text-success" />
              </div>
              <h2 className="text-lg font-semibold text-ink">Confirm Registration</h2>
            </div>

            <div className="space-y-4">
              <div className="bg-elevated rounded-xl p-5">
                <h3 className="text-sm font-semibold text-ink-muted uppercase tracking-wider mb-3">Owner Details</h3>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-ink-muted">Name</span>
                    <span className="text-ink font-medium">{ownerName || '—'}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-ink-muted">Phone</span>
                    <span className="text-ink font-medium">{ownerPhone || '—'}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-ink-muted">User ID</span>
                    <span className="text-ink font-mono">{ownerId}</span>
                  </div>
                </div>
              </div>

              <div className="bg-elevated rounded-xl p-5">
                <h3 className="text-sm font-semibold text-ink-muted uppercase tracking-wider mb-3">Vehicle & Tag Details</h3>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-ink-muted">Plate Number</span>
                    <span className="text-ink font-mono font-bold">{vehicleForm.plate_number}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-ink-muted">Vehicle Type</span>
                    <span className="text-ink capitalize">{vehicleForm.vehicle_type}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-ink-muted">M-Tag Serial</span>
                    <span className="text-ink font-mono">{vehicleForm.tag_serial}</span>
                  </div>
                  <div className="flex justify-between text-sm pt-2 border-t border-line">
                    <span className="text-ink-muted">Initial Balance</span>
                    <span className={`font-semibold ${vehicleForm.initial_balance ? 'text-success' : 'text-ink-subtle'}`}>
                      PKR {vehicleForm.initial_balance ? parseFloat(vehicleForm.initial_balance).toLocaleString() : '0'}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex justify-between mt-8">
              <button type="button" onClick={() => setStep(2)} className="px-6 py-2.5 bg-elevated border border-line text-ink text-sm font-medium rounded-xl hover:bg-surface transition-colors">
                Back
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className="flex items-center gap-2 px-6 py-2.5 bg-brand text-brand-on text-sm font-semibold rounded-xl hover:bg-brand-strong active:bg-brand-strong transition-colors disabled:opacity-60"
              >
                {isSubmitting ? (
                  <><Loader2 className="w-4 h-4 animate-spin" />Registering...</>
                ) : (
                  'Complete Registration'
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
