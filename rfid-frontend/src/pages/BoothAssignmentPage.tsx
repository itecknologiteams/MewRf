import { useState, useEffect } from 'react';
import { useToast } from '@/context/ToastContext';
import { inventoryApi } from '@/services/inventoryApi';
import {
  Loader2,
  Check,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  CheckCircle,
} from 'lucide-react';

interface InventoryItem {
  id: number;
  tag_serial: string;
  tid: string;
  vehicle_plate: string;
  vehicle_type: string;
  status: 'unregistered' | 'booth_assigned' | 'activated';
  booth_assigned_id?: number;
  created_at: string;
}

export default function BoothAssignmentPage() {
  const { addToast } = useToast();

  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedItems, setSelectedItems] = useState<Set<number>>(new Set());
  const [selectedBooth, setSelectedBooth] = useState('');
  const [isAssigning, setIsAssigning] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  const fetchUnregisteredInventory = async (page = 1) => {
    try {
      setLoading(true);
      const data = await inventoryApi.list({ page, per_page: 50, status: 'unregistered' });
      setInventory(data.items);
      setCurrentPage(data.page);
      setTotalPages(data.pages);
    } catch (err: any) {
      addToast({ type: 'error', title: 'Error', message: err.message || 'Failed to fetch inventory' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUnregisteredInventory(1);
  }, []);

  const toggleItemSelection = (id: number) => {
    const newSelected = new Set(selectedItems);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedItems(newSelected);
  };

  const toggleSelectAll = () => {
    if (selectedItems.size === inventory.length) {
      setSelectedItems(new Set());
    } else {
      setSelectedItems(new Set(inventory.map((item) => item.id)));
    }
  };

  const handleAssign = async () => {
    if (selectedItems.size === 0) {
      addToast({ type: 'error', title: 'Validation', message: 'Please select at least one item' });
      return;
    }
    if (!selectedBooth) {
      addToast({ type: 'error', title: 'Validation', message: 'Please select a booth' });
      return;
    }
    try {
      setIsAssigning(true);
      const data = await inventoryApi.assignBooth({
        inventory_ids: Array.from(selectedItems),
        booth_id: parseInt(selectedBooth),
      });
      addToast({ type: 'success', title: 'Assigned', message: `${data.assigned} tags assigned to Booth ${selectedBooth}` });
      setSelectedItems(new Set());
      setSelectedBooth('');
      fetchUnregisteredInventory(1);
    } catch (err: any) {
      addToast({ type: 'error', title: 'Assignment Failed', message: err.message || 'Assignment failed' });
    } finally {
      setIsAssigning(false);
    }
  };

  return (
    <div className="animate-fade-in-up">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-[var(--text-primary)] mb-2">Booth Assignment</h1>
          <p className="text-[var(--text-secondary)]">Assign unregistered tags to specific booths</p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-[var(--bg-surface)] rounded-xl shadow-sm p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[var(--text-secondary)] text-sm">Total Unregistered</p>
                <p className="text-2xl font-bold text-[var(--text-primary)]">{inventory.length}</p>
              </div>
              <AlertCircle className="text-[var(--text-tertiary)]" size={24} />
            </div>
          </div>

          <div className="bg-[var(--bg-surface)] rounded-xl shadow-sm p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[var(--text-secondary)] text-sm">Selected</p>
                <p className="text-2xl font-bold text-[var(--accent-blue)]">{selectedItems.size}</p>
              </div>
              <Check className="text-[var(--accent-blue)]" size={24} />
            </div>
          </div>

          <div className="bg-[var(--bg-surface)] rounded-xl shadow-sm p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[var(--text-secondary)] text-sm">Target Booth</p>
                <p className="text-2xl font-bold text-[var(--text-primary)]">
                  {selectedBooth ? `Booth ${selectedBooth}` : '-'}
                </p>
              </div>
              <CheckCircle className="text-[var(--accent-emerald)]" size={24} />
            </div>
          </div>
        </div>

        {/* Action Bar */}
        <div className="bg-[var(--bg-surface)] rounded-xl shadow-sm p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                Select Booth (1-7)
              </label>
              <select
                value={selectedBooth}
                onChange={(e) => setSelectedBooth(e.target.value)}
                className="w-full px-3 py-2 border border-[var(--border-custom)] rounded-xl focus:ring-2 focus:ring-[var(--accent-blue)]/20 focus:border-[var(--accent-blue)]"
              >
                <option value="">Choose booth...</option>
                {Array.from({ length: 7 }, (_, i) => (
                  <option key={i + 1} value={i + 1}>
                    Booth {i + 1}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-end">
              <button
                onClick={handleAssign}
                disabled={selectedItems.size === 0 || !selectedBooth || isAssigning}
                className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-[var(--accent-blue)] text-white rounded-xl hover:opacity-90 disabled:opacity-50 font-medium"
              >
                {isAssigning && <Loader2 className="animate-spin" size={18} />}
                Assign Selected
              </button>
            </div>
          </div>
        </div>

        {/* Table */}
        <div className="bg-[var(--bg-surface)] rounded-xl shadow-sm overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="animate-spin text-[var(--accent-blue)]" size={32} />
            </div>
          ) : inventory.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12">
              <CheckCircle className="text-[var(--accent-emerald)] mb-2" size={32} />
              <p className="text-[var(--text-secondary)]">All tags have been assigned!</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-[var(--bg-elevated)] border-b border-[var(--border-custom)]">
                    <tr>
                      <th className="px-6 py-3 text-left">
                        <input
                          type="checkbox"
                          checked={selectedItems.size === inventory.length && inventory.length > 0}
                          onChange={toggleSelectAll}
                          className="w-4 h-4 cursor-pointer"
                        />
                      </th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-[var(--text-primary)]">Tag Serial</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-[var(--text-primary)]">TID</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-[var(--text-primary)]">Plate</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-[var(--text-primary)]">Type</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-[var(--text-primary)]">Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inventory.map((item) => (
                      <tr
                        key={item.id}
                        className={`border-b border-[var(--border-custom)] hover:bg-[var(--bg-elevated)] ${
                          selectedItems.has(item.id) ? 'bg-[var(--accent-blue)]/10' : ''
                        }`}
                      >
                        <td className="px-6 py-4">
                          <input
                            type="checkbox"
                            checked={selectedItems.has(item.id)}
                            onChange={() => toggleItemSelection(item.id)}
                            className="w-4 h-4 cursor-pointer"
                          />
                        </td>
                        <td className="px-6 py-4 text-sm text-[var(--text-primary)] font-mono">{item.tag_serial}</td>
                        <td className="px-6 py-4 text-sm text-[var(--text-secondary)] font-mono">{item.tid.substring(0, 8)}...</td>
                        <td className="px-6 py-4 text-sm text-[var(--text-secondary)]">{item.vehicle_plate || '-'}</td>
                        <td className="px-6 py-4 text-sm text-[var(--text-secondary)] capitalize">{item.vehicle_type}</td>
                        <td className="px-6 py-4 text-sm text-[var(--text-secondary)]">
                          {new Date(item.created_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              <div className="flex justify-between items-center px-6 py-4 bg-[var(--bg-elevated)] border-t border-[var(--border-custom)]">
                <div className="text-sm text-[var(--text-secondary)]">
                  Page {currentPage} of {totalPages}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => fetchUnregisteredInventory(currentPage - 1)}
                    disabled={currentPage === 1}
                    className="flex items-center gap-1 px-3 py-2 bg-[var(--bg-elevated)] text-[var(--text-primary)] rounded hover:bg-[var(--bg-surface)] disabled:opacity-50"
                  >
                    <ChevronLeft size={18} />
                    Previous
                  </button>
                  <button
                    onClick={() => fetchUnregisteredInventory(currentPage + 1)}
                    disabled={currentPage >= totalPages}
                    className="flex items-center gap-1 px-3 py-2 bg-[var(--bg-elevated)] text-[var(--text-primary)] rounded hover:bg-[var(--bg-surface)] disabled:opacity-50"
                  >
                    Next
                    <ChevronRight size={18} />
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
