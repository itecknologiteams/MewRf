import { useState, useEffect } from 'react';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { authApi, vehiclesApi, accountsApi, paymentsApi } from '@/services/api';
import type { MeResponse } from '@/services/api';
import type { Account, ApiVehicle, TopupRequest } from '@/types';
import {
  Wallet,
  Zap,
  History,
  CreditCard,
  User,
  Phone,
  Shield,
  Loader2,
  CheckCircle,
  Car,
  RefreshCw,
  KeyRound,
  Eye,
  EyeOff,
} from 'lucide-react';
import CountUp from 'react-countup';

export default function Profile() {
  const { addToast } = useToast();
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<'wallet' | 'profile' | 'security'>('wallet');

  // Profile data
  const [profileData, setProfileData] = useState<MeResponse | null>(null);
  const [loadingProfile, setLoadingProfile] = useState(true);
  const profileInitials =
    (profileData?.full_name || user?.full_name || user?.name || 'User')
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((word) => word[0])
      .join('')
      .toUpperCase() || 'U';
  const [editName, setEditName] = useState('');
  const [isSavingProfile, setIsSavingProfile] = useState(false);

  // Vehicle/Account data
  const [vehicles, setVehicles] = useState<ApiVehicle[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<number | ''>('');
  const [loadingAccounts, setLoadingAccounts] = useState(true);

  // Topup
  const [rechargeAmount, setRechargeAmount] = useState('');
  const [isRecharging, setIsRecharging] = useState(false);

  // Topup history
  const [topupHistory, setTopupHistory] = useState<TopupRequest[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  useEffect(() => {
    const fetchProfile = async () => {
      setLoadingProfile(true);
      try {
        const me = await authApi.me();
        setProfileData(me);
        setEditName(me.full_name);
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Failed to load profile';
        addToast({ type: 'error', title: 'Error', message });
      } finally {
        setLoadingProfile(false);
      }
    };

    const fetchVehiclesAndAccounts = async () => {
      setLoadingAccounts(true);
      try {
        const vList = await vehiclesApi.list();
        setVehicles(vList);

        const fetchedAccounts: Account[] = [];
        for (const v of vList) {
          try {
            const acct = await accountsApi.byVehicle(v.id);
            fetchedAccounts.push(acct);
          } catch {
            // vehicle may not have account yet
          }
        }
        setAccounts(fetchedAccounts);
        if (fetchedAccounts.length > 0) {
          setSelectedAccountId(fetchedAccounts[0].id);
        }
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Failed to load vehicles';
        addToast({ type: 'error', title: 'Error', message });
      } finally {
        setLoadingAccounts(false);
      }
    };

    fetchProfile();
    fetchVehiclesAndAccounts();
  }, []);

  useEffect(() => {
    if (selectedAccountId && activeTab === 'wallet') {
      fetchTopupHistory(Number(selectedAccountId));
    }
  }, [selectedAccountId, activeTab]);

  const fetchTopupHistory = async (accountId: number) => {
    setLoadingHistory(true);
    try {
      const history = await paymentsApi.history(accountId);
      setTopupHistory(history);
    } catch {
      setTopupHistory([]);
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleRecharge = async () => {
    const amount = Number(rechargeAmount);
    if (!amount || amount < 100) {
      addToast({ type: 'error', title: 'Invalid Amount', message: 'Minimum recharge amount is PKR 100.' });
      return;
    }
    if (!selectedAccountId) {
      addToast({ type: 'error', title: 'No Account', message: 'Please select an account to recharge.' });
      return;
    }

    setIsRecharging(true);
    try {
      const topup = await paymentsApi.initiate({ account_id: Number(selectedAccountId), amount });
      // Simulate JazzCash callback
      await paymentsApi.callback({
        pp_TxnRefNo: String(topup.id),
        pp_ResponseCode: '000',
        topup_id: topup.id,
      });

      // Refresh accounts
      const vList = await vehiclesApi.list();
      const refreshedAccounts: Account[] = [];
      for (const v of vList) {
        try {
          const acct = await accountsApi.byVehicle(v.id);
          refreshedAccounts.push(acct);
        } catch {
          // ignore
        }
      }
      setAccounts(refreshedAccounts);
      setRechargeAmount('');
      fetchTopupHistory(Number(selectedAccountId));
      addToast({ type: 'success', title: 'Recharge Successful', message: `PKR ${amount.toLocaleString()} added to your wallet.` });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Recharge failed';
      addToast({ type: 'error', title: 'Recharge Failed', message });
    } finally {
      setIsRecharging(false);
    }
  };

  const handleSaveProfile = async () => {
    if (!editName.trim()) return;
    setIsSavingProfile(true);
    try {
      const updated = await authApi.updateMe({ full_name: editName });
      setProfileData(updated);
      addToast({ type: 'success', title: 'Profile Updated', message: 'Your name has been updated.' });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Update failed';
      addToast({ type: 'error', title: 'Update Failed', message });
    } finally {
      setIsSavingProfile(false);
    }
  };

  // Password change state
  const [pwForm, setPwForm] = useState({ old_password: '', new_password: '', confirm: '' });
  const [pwLoading, setPwLoading] = useState(false);
  const [showOld, setShowOld] = useState(false);
  const [showNew, setShowNew] = useState(false);

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (pwForm.new_password !== pwForm.confirm) {
      addToast({ type: 'error', title: 'Mismatch', message: 'New passwords do not match.' });
      return;
    }
    if (pwForm.new_password.length < 8) {
      addToast({ type: 'error', title: 'Too Short', message: 'New password must be at least 8 characters.' });
      return;
    }
    setPwLoading(true);
    try {
      await authApi.changePassword({ old_password: pwForm.old_password, new_password: pwForm.new_password });
      addToast({ type: 'success', title: 'Password Changed', message: 'Your password has been updated.' });
      setPwForm({ old_password: '', new_password: '', confirm: '' });
    } catch (err: unknown) {
      addToast({ type: 'error', title: 'Failed', message: err instanceof Error ? err.message : 'Password change failed' });
    } finally {
      setPwLoading(false);
    }
  };

  const selectedAccount = accounts.find((a) => a.id === selectedAccountId);
  const totalBalance = accounts.reduce((sum, a) => sum + parseFloat(a.balance || '0'), 0);

  return (
    <div className="animate-fade-in-up">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-ink">Profile & Wallet</h1>
        <p className="text-sm text-ink-muted mt-1">
          Manage your account and wallet balance
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-elevated p-1 rounded-xl w-fit mb-6 border border-line">
        {(['wallet', 'profile', 'security'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-5 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === tab
                ? 'bg-brand text-brand-on'
                : 'text-ink-muted hover:text-ink'
            }`}
          >
            <div className="flex items-center gap-2">
              {tab === 'wallet' && <Wallet className="w-4 h-4" />}
              {tab === 'profile' && <User className="w-4 h-4" />}
              {tab === 'security' && <KeyRound className="w-4 h-4" />}
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </div>
          </button>
        ))}
      </div>

      {activeTab === 'wallet' && (
        <div className="space-y-6">
          {/* Balance Card */}
          <div className="bg-gradient-to-br from-brand to-brand-strong rounded-2xl p-8 text-white shadow-lg">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
              <div>
                <p className="text-sm text-white/70 mb-1">Total Balance (All Vehicles)</p>
                <p className="text-4xl font-bold metric-ticker">
                  {loadingAccounts ? (
                    <span className="text-2xl">Loading...</span>
                  ) : (
                    <CountUp end={totalBalance} duration={1.5} prefix="PKR" separator="," decimals={2} />
                  )}
                </p>
                <p className="text-xs text-white/50 mt-2">{accounts.length} account{accounts.length !== 1 ? 's' : ''}</p>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <p className="text-xs text-white/70">Vehicles</p>
                  <p className="text-lg font-semibold">{vehicles.length}</p>
                </div>
                <div className="w-px h-10 bg-white/20" />
                <div className="text-right">
                  <p className="text-xs text-white/70">Role</p>
                  <p className="text-lg font-semibold capitalize">{user?.role || '—'}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Account Selector */}
          {accounts.length > 0 && (
            <div className="bg-surface border border-line rounded-xl skeu-card p-5">
              <div className="flex items-center gap-3 mb-4">
                <Car className="w-5 h-5 text-info" />
                <h3 className="text-base font-semibold text-ink">Select Account</h3>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {accounts.map((account) => (
                  <button
                    key={account.id}
                    onClick={() => setSelectedAccountId(account.id)}
                    className={`p-4 rounded-xl border text-left transition-all ${
                      selectedAccountId === account.id
                        ? 'bg-brand/10 border-brand/40'
                        : 'bg-elevated border-line hover:border-brand/20'
                    }`}
                  >
                    <p className="text-sm font-mono font-bold text-ink">{account.plate_number}</p>
                    <p className="text-xs text-ink-muted capitalize mt-0.5">{account.vehicle_type}</p>
                    <p className={`text-base font-semibold mt-2 ${
                      selectedAccountId === account.id ? 'text-brand' : 'text-ink'
                    }`}>
                      PKR {parseFloat(account.balance).toLocaleString()}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Recharge Section */}
          <div className="bg-surface border border-line rounded-xl skeu-card p-6">
            <div className="flex items-center gap-3 mb-5">
              <div className="p-2 bg-success/10 rounded-lg">
                <Zap className="w-5 h-5 text-success" />
              </div>
              <h3 className="text-base font-semibold text-ink">Recharge Wallet</h3>
            </div>

            {accounts.length === 0 ? (
              <p className="text-sm text-ink-muted">No accounts found. Register a vehicle first.</p>
            ) : (
              <>
                {accounts.length > 1 && (
                  <div className="mb-4">
                    <label className="block text-xs font-medium text-ink-muted mb-1.5">Recharge Account</label>
                    <select
                      value={selectedAccountId}
                      onChange={(e) => setSelectedAccountId(e.target.value ? Number(e.target.value) : '')}
                      className="w-full px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink outline-none focus:border-success"
                    >
                      {accounts.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.plate_number} — PKR {parseFloat(a.balance).toLocaleString()}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {selectedAccount && (
                  <p className="text-sm text-ink-muted mb-4">
                    Current balance: <span className="font-semibold text-ink">PKR {parseFloat(selectedAccount.balance).toLocaleString()}</span>
                  </p>
                )}

                <div className="flex flex-col sm:flex-row gap-4">
                  <div className="relative flex-1">
                    <span className="absolute left-4 top-1/2 -translate-y-1/2 text-sm text-ink-muted">PKR</span>
                    <input
                      type="number"
                      value={rechargeAmount}
                      onChange={(e) => setRechargeAmount(e.target.value)}
                      placeholder="Enter amount (min 100)"
                      min="100"
                      className="w-full pl-14 pr-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-success focus:ring-2 focus:ring-success/20 transition-all"
                    />
                  </div>
                  <div className="flex gap-2">
                    {[500, 1000, 2000].map((amount) => (
                      <button
                        key={amount}
                        type="button"
                        onClick={() => setRechargeAmount(amount.toString())}
                        className={`px-4 py-3 rounded-xl text-sm font-medium transition-colors ${
                          rechargeAmount === amount.toString()
                            ? 'bg-brand text-brand-on'
                            : 'bg-elevated border border-line text-ink-muted hover:text-ink'
                        }`}
                      >
                        {amount.toLocaleString()}
                      </button>
                    ))}
                  </div>
                  <button
                    onClick={handleRecharge}
                    disabled={isRecharging || !rechargeAmount || !selectedAccountId}
                    className="px-6 py-3 bg-brand text-brand-on text-sm font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  >
                    {isRecharging ? (
                      <>
                        <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        Processing...
                      </>
                    ) : (
                      <>
                        <CreditCard className="w-4 h-4" />
                        Recharge
                      </>
                    )}
                  </button>
                </div>
              </>
            )}
          </div>

          {/* Topup History */}
          {selectedAccountId && (
            <div className="bg-surface border border-line rounded-xl skeu-card overflow-hidden">
              <div className="flex items-center justify-between px-6 py-4 border-b border-line">
                <div className="flex items-center gap-2">
                  <History className="w-5 h-5 text-brand" />
                  <h3 className="text-base font-semibold text-ink">Recharge History</h3>
                </div>
                <button
                  onClick={() => fetchTopupHistory(Number(selectedAccountId))}
                  className="text-sm text-ink-muted hover:text-ink transition-colors"
                >
                  <RefreshCw className="w-4 h-4" />
                </button>
              </div>
              {loadingHistory ? (
                <div className="flex items-center justify-center py-10">
                  <Loader2 className="w-6 h-6 animate-spin text-brand" />
                </div>
              ) : topupHistory.length === 0 ? (
                <div className="px-6 py-10 text-center text-sm text-ink-muted">
                  No recharge history found
                </div>
              ) : (
                <div className="divide-y divide-line">
                  {topupHistory.map((topup) => (
                    <div key={topup.id} className="flex items-center justify-between px-6 py-4 hover:bg-elevated transition-colors">
                      <div className="flex items-center gap-4">
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                          topup.status === 'completed'
                            ? 'bg-success/10'
                            : topup.status === 'failed'
                            ? 'bg-danger/10'
                            : 'bg-warning/10'
                        }`}>
                          <CreditCard className={`w-5 h-5 ${
                            topup.status === 'completed'
                              ? 'text-success'
                              : topup.status === 'failed'
                              ? 'text-danger'
                              : 'text-warning'
                          }`} />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-ink">Wallet Recharge</p>
                          <p className="text-xs text-ink-muted">
                            {new Date(topup.requested_at).toLocaleDateString('en-PK', {
                              day: 'numeric',
                              month: 'short',
                              year: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-semibold text-success">
                          +PKR {parseFloat(topup.amount).toLocaleString()}
                        </p>
                        <span className={`text-xs font-medium capitalize ${
                          topup.status === 'completed'
                            ? 'text-success'
                            : topup.status === 'failed'
                            ? 'text-danger'
                            : 'text-warning'
                        }`}>
                          {topup.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {activeTab === 'security' && (
        <div className="max-w-md">
          <div className="bg-surface border border-line rounded-xl skeu-card p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2.5 bg-warning/10 rounded-lg">
                <KeyRound className="w-5 h-5 text-warning" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-ink">Change Password</h3>
                <p className="text-xs text-ink-muted">Use a strong password with 8+ characters</p>
              </div>
            </div>
            <form onSubmit={handleChangePassword} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-ink mb-1.5">Current Password</label>
                <div className="relative">
                  <input
                    type={showOld ? 'text' : 'password'}
                    value={pwForm.old_password}
                    onChange={(e) => setPwForm(f => ({ ...f, old_password: e.target.value }))}
                    placeholder="Enter current password"
                    className="w-full px-4 py-3 pr-10 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-warning focus:ring-2 focus:ring-warning/20 transition-all"
                  />
                  <button type="button" onClick={() => setShowOld(v => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-subtle">
                    {showOld ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-ink mb-1.5">New Password</label>
                <div className="relative">
                  <input
                    type={showNew ? 'text' : 'password'}
                    value={pwForm.new_password}
                    onChange={(e) => setPwForm(f => ({ ...f, new_password: e.target.value }))}
                    placeholder="Min 8 characters"
                    className="w-full px-4 py-3 pr-10 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-warning focus:ring-2 focus:ring-warning/20 transition-all"
                  />
                  <button type="button" onClick={() => setShowNew(v => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-subtle">
                    {showNew ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-ink mb-1.5">Confirm New Password</label>
                <input
                  type="password"
                  value={pwForm.confirm}
                  onChange={(e) => setPwForm(f => ({ ...f, confirm: e.target.value }))}
                  placeholder="Repeat new password"
                  className={`w-full px-4 py-3 bg-elevated border rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:ring-2 transition-all ${
                    pwForm.confirm && pwForm.confirm !== pwForm.new_password
                      ? 'border-danger focus:ring-danger/20'
                      : 'border-line focus:border-warning focus:ring-warning/20'
                  }`}
                />
                {pwForm.confirm && pwForm.confirm !== pwForm.new_password && (
                  <p className="text-xs text-danger mt-1">Passwords do not match</p>
                )}
              </div>
              <button
                type="submit"
                disabled={pwLoading || !pwForm.old_password || !pwForm.new_password || pwForm.new_password !== pwForm.confirm}
                className="w-full py-3 bg-warning/12 text-warning border border-warning/40 text-sm font-semibold rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {pwLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />}
                {pwLoading ? 'Updating…' : 'Update Password'}
              </button>
            </form>
          </div>
        </div>
      )}

      {activeTab === 'profile' && (
        <div className="max-w-2xl">
          <div className="bg-surface border border-line rounded-xl skeu-card overflow-hidden">
            {/* Profile Header */}
            <div className="relative h-32 bg-gradient-to-r from-brand to-brand-strong">
              <div className="absolute -bottom-12 left-6">
                <span
                  aria-hidden="true"
                  className="grid place-items-center w-24 h-24 rounded-full bg-elevated text-brand-ink dark:text-brand text-2xl font-bold border-4 border-surface ring-2 ring-brand/35"
                >
                  {profileInitials}
                </span>
              </div>
            </div>
            <div className="pt-16 px-6 pb-6">
              {loadingProfile ? (
                <div className="flex items-center gap-3">
                  <Loader2 className="w-5 h-5 animate-spin text-brand" />
                  <span className="text-sm text-ink-muted">Loading profile...</span>
                </div>
              ) : (
                <>
                  <h2 className="text-xl font-bold text-ink">{profileData?.full_name}</h2>
                  <p className="text-sm text-ink-muted capitalize">{profileData?.user_role} Account</p>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mt-6">
                    <div className="flex items-start gap-3">
                      <div className="p-2 bg-elevated rounded-lg">
                        <Shield className="w-4 h-4 text-brand" />
                      </div>
                      <div>
                        <p className="text-xs text-ink-muted uppercase tracking-wider">CNIC</p>
                        <p className="text-sm font-medium text-ink">{profileData?.cnic || '—'}</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <div className="p-2 bg-elevated rounded-lg">
                        <Phone className="w-4 h-4 text-info" />
                      </div>
                      <div>
                        <p className="text-xs text-ink-muted uppercase tracking-wider">Phone</p>
                        <p className="text-sm font-medium text-ink">{profileData?.phone || '—'}</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <div className="p-2 bg-elevated rounded-lg">
                        <Wallet className="w-4 h-4 text-warning" />
                      </div>
                      <div>
                        <p className="text-xs text-ink-muted uppercase tracking-wider">Total Balance</p>
                        <p className="text-sm font-medium text-ink">PKR {totalBalance.toLocaleString()}</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <div className="p-2 bg-elevated rounded-lg">
                        <Car className="w-4 h-4 text-success" />
                      </div>
                      <div>
                        <p className="text-xs text-ink-muted uppercase tracking-wider">Vehicles</p>
                        <p className="text-sm font-medium text-ink">{vehicles.length} registered</p>
                      </div>
                    </div>
                  </div>

                  {/* Edit Name */}
                  <div className="mt-6 pt-6 border-t border-line">
                    <h3 className="text-sm font-semibold text-ink mb-4">Edit Profile</h3>
                    <div className="flex gap-3">
                      <input
                        type="text"
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        placeholder="Full name"
                        className="flex-1 px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
                      />
                      <button
                        onClick={handleSaveProfile}
                        disabled={isSavingProfile || !editName.trim()}
                        className="flex items-center gap-2 px-5 py-3 bg-brand text-brand-on text-sm font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-60"
                      >
                        {isSavingProfile ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <CheckCircle className="w-4 h-4" />
                        )}
                        Save
                      </button>
                    </div>
                  </div>

                  {/* Account Statistics */}
                  <div className="mt-6 pt-6 border-t border-line">
                    <h3 className="text-sm font-semibold text-ink mb-4">Account Statistics</h3>
                    <div className="grid grid-cols-3 gap-4">
                      <div className="bg-elevated rounded-xl p-4 text-center">
                        <p className="text-xl font-bold text-brand">{vehicles.length}</p>
                        <p className="text-xs text-ink-muted mt-1">Vehicles</p>
                      </div>
                      <div className="bg-elevated rounded-xl p-4 text-center">
                        <p className="text-xl font-bold text-success">{accounts.length}</p>
                        <p className="text-xs text-ink-muted mt-1">Accounts</p>
                      </div>
                      <div className="bg-elevated rounded-xl p-4 text-center">
                        <p className="text-xl font-bold text-info capitalize">{profileData?.status || '—'}</p>
                        <p className="text-xs text-ink-muted mt-1">Status</p>
                      </div>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
