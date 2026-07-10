import { useState } from 'react';
import { X, Loader2, User, Phone, DollarSign, AlertCircle, CheckCircle } from 'lucide-react';
import { useToast } from '@/context/ToastContext';
import { inventoryApi } from '@/services/inventoryApi';

interface InventoryActivationModalProps {
  tag: {
    tag_serial: string;
    tid: string;
    vehicle_plate?: string;
    vehicle_type?: string;
    booth_assigned_id?: number;
  };
  activationBoothId: number;
  onSuccess: (account: any) => void;
  onClose: () => void;
}

export default function InventoryActivationModal({
  tag,
  activationBoothId,
  onSuccess,
  onClose,
}: InventoryActivationModalProps) {
  const { addToast } = useToast();
  const [activeTab, setActiveTab] = useState<'quick' | 'existing'>('quick');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  // Quick create form
  const [quickForm, setQuickForm] = useState({
    customer_name: '',
    customer_phone: '',
    initial_topup: 0,
    payment_method: 'CASH',
  });

  // Link existing form
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<string | null>(null);
  const [searching, setSearching] = useState(false);

  const handleQuickCreate = async () => {
    if (!quickForm.customer_name.trim()) {
      addToast('Please enter customer name', 'error');
      return;
    }
    if (!quickForm.customer_phone.trim()) {
      addToast('Please enter customer phone', 'error');
      return;
    }

    try {
      setLoading(true);
      const result = await inventoryApi.activateQuick({
        tag_serial: tag.tag_serial,
        tid: tag.tid,
        customer_name: quickForm.customer_name,
        customer_phone: quickForm.customer_phone,
        initial_topup: quickForm.initial_topup,
        payment_method: quickForm.payment_method,
        activation_booth_id: activationBoothId,
      });

      setSuccess(true);
      addToast('Tag activated successfully!', 'success');
      setTimeout(() => {
        onSuccess(result);
      }, 1500);
    } catch (err: any) {
      addToast(err.message || 'Activation failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }

    try {
      setSearching(true);
      const results = await inventoryApi.searchAccounts(searchQuery);
      setSearchResults(results);
    } catch (err: any) {
      addToast('Search failed', 'error');
    } finally {
      setSearching(false);
    }
  };

  const handleLinkExisting = async () => {
    if (!selectedAccount) {
      addToast('Please select an account', 'error');
      return;
    }

    try {
      setLoading(true);
      const result = await inventoryApi.activateExisting({
        tag_serial: tag.tag_serial,
        tid: tag.tid,
        account_id: selectedAccount,
        activation_booth_id: activationBoothId,
      });

      setSuccess(true);
      addToast('Tag linked successfully!', 'success');
      setTimeout(() => {
        onSuccess(result);
      }, 1500);
    } catch (err: any) {
      addToast(err.message || 'Linking failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-md w-full">
        {/* Header */}
        <div className="flex justify-between items-center p-6 border-b">
          <div>
            <h2 className="text-xl font-bold">Activate Tag</h2>
            <p className="text-sm text-gray-600 mt-1">Tag: {tag.tag_serial}</p>
          </div>
          <button
            onClick={onClose}
            disabled={loading || success}
            className="text-gray-500 hover:text-gray-700 disabled:opacity-50"
          >
            <X size={24} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {success ? (
            <div className="flex flex-col items-center justify-center py-6">
              <CheckCircle className="text-green-600 mb-3" size={48} />
              <p className="text-center font-semibold text-gray-900">Tag Activated!</p>
              <p className="text-center text-sm text-gray-600 mt-1">Redirecting...</p>
            </div>
          ) : (
            <>
              {/* Tabs */}
              <div className="flex gap-2 mb-6">
                <button
                  onClick={() => setActiveTab('quick')}
                  className={`flex-1 py-2 px-3 rounded-lg font-medium text-sm transition-colors ${
                    activeTab === 'quick'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                  disabled={loading}
                >
                  Quick Create
                </button>
                <button
                  onClick={() => setActiveTab('existing')}
                  className={`flex-1 py-2 px-3 rounded-lg font-medium text-sm transition-colors ${
                    activeTab === 'existing'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                  disabled={loading}
                >
                  Link Existing
                </button>
              </div>

              {/* Quick Create Tab */}
              {activeTab === 'quick' && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      <User size={16} className="inline mr-2" />
                      Customer Name
                    </label>
                    <input
                      type="text"
                      value={quickForm.customer_name}
                      onChange={(e) => setQuickForm({ ...quickForm, customer_name: e.target.value })}
                      placeholder="Enter customer name"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                      disabled={loading}
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      <Phone size={16} className="inline mr-2" />
                      Phone Number
                    </label>
                    <input
                      type="tel"
                      value={quickForm.customer_phone}
                      onChange={(e) => setQuickForm({ ...quickForm, customer_phone: e.target.value })}
                      placeholder="03001234567"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                      disabled={loading}
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      <DollarSign size={16} className="inline mr-2" />
                      Initial Top-up (Optional)
                    </label>
                    <input
                      type="number"
                      value={quickForm.initial_topup}
                      onChange={(e) => setQuickForm({ ...quickForm, initial_topup: parseFloat(e.target.value) || 0 })}
                      placeholder="0"
                      min="0"
                      step="100"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                      disabled={loading}
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Payment Method
                    </label>
                    <select
                      value={quickForm.payment_method}
                      onChange={(e) => setQuickForm({ ...quickForm, payment_method: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                      disabled={loading}
                    >
                      <option value="CASH">Cash</option>
                      <option value="CARD">Card</option>
                      <option value="TRANSFER">Transfer</option>
                    </select>
                  </div>

                  <div className="flex gap-3 pt-4">
                    <button
                      onClick={onClose}
                      disabled={loading}
                      className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleQuickCreate}
                      disabled={loading}
                      className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                    >
                      {loading && <Loader2 className="animate-spin" size={18} />}
                      Activate
                    </button>
                  </div>
                </div>
              )}

              {/* Link Existing Tab */}
              {activeTab === 'existing' && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Search Customer
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Phone or name..."
                        className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                        disabled={loading || searching}
                        onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                      />
                      <button
                        onClick={handleSearch}
                        disabled={loading || searching || !searchQuery.trim()}
                        className="px-4 py-2 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300 disabled:opacity-50"
                      >
                        {searching ? <Loader2 className="animate-spin" size={18} /> : 'Search'}
                      </button>
                    </div>
                  </div>

                  {searchResults.length > 0 ? (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Select Account
                      </label>
                      <div className="space-y-2 max-h-48 overflow-y-auto">
                        {searchResults.map((account) => (
                          <button
                            key={account.id}
                            onClick={() => setSelectedAccount(account.id)}
                            className={`w-full p-3 rounded-lg border-2 text-left transition-colors ${
                              selectedAccount === account.id
                                ? 'border-blue-600 bg-blue-50'
                                : 'border-gray-200 hover:border-gray-300'
                            }`}
                            disabled={loading}
                          >
                            <p className="font-semibold text-gray-900">{account.user.full_name}</p>
                            <p className="text-sm text-gray-600">{account.user.phone}</p>
                            <p className="text-sm text-gray-600">Balance: Rs. {account.balance}</p>
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : searchQuery.trim() ? (
                    <div className="flex items-center gap-2 p-3 bg-gray-50 border border-gray-200 rounded-lg">
                      <AlertCircle size={18} className="text-gray-500" />
                      <p className="text-sm text-gray-600">No accounts found</p>
                    </div>
                  ) : null}

                  <div className="flex gap-3 pt-4">
                    <button
                      onClick={onClose}
                      disabled={loading}
                      className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleLinkExisting}
                      disabled={loading || !selectedAccount}
                      className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                    >
                      {loading && <Loader2 className="animate-spin" size={18} />}
                      Link
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
