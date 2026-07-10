import { useState, useEffect } from 'react';
import { useToast } from '@/context/ToastContext';
import {
  Loader2,
  Check,
  X,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  CheckCircle,
} from 'lucide-react';

interface InventoryItem {
  id: string;
  tag_serial: string;
  tid: string;
  vehicle_plate: string;
  vehicle_type: string;
  status: 'unregistered' | 'booth_assigned' | 'activated';
  booth_assigned_id?: number;
  created_at: string;
}

interface InventoryResponse {
  items: InventoryItem[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export default function BoothAssignmentPage() {
  const { addToast } = useToast();

  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const [selectedBooth, setSelectedBooth] = useState('');
  const [isAssigning, setIsAssigning] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const fetchUnregisteredInventory = async (page = 1) => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      params.append('page', page.toString());
      params.append('per_page', '50');
      params.append('status', 'unregistered');

      const response = await fetch(`${API_BASE}/api/v1/vehicles/inventory/?${params}`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
      });

      if (!response.ok) throw new Error('Failed to fetch inventory');

      const data = (await response.json()) as { data: InventoryResponse };
      setInventory(data.data.items);
      setCurrentPage(data.data.page);
      setTotalPages(data.data.pages);
    } catch (err: any) {
      addToast(err.message || 'Failed to fetch inventory', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUnregisteredInventory(1);
  }, []);

  const toggleItemSelection = (id: string) => {
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
      addToast('Please select at least one item', 'error');
      return;
    }

    if (!selectedBooth) {
      addToast('Please select a booth', 'error');
      return;
    }

    try {
      setIsAssigning(true);

      const response = await fetch(`${API_BASE}/api/v1/vehicles/inventory/assign-booth/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({
          inventory_ids: Array.from(selectedItems),
          booth_id: parseInt(selectedBooth),
          assigned_by: localStorage.getItem('user_phone') || 'system',
        }),
      });

      const result = await response.json();

      if (!response.ok) {
        addToast(result.message || 'Assignment failed', 'error');
        return;
      }

      addToast(`${result.data.assigned} tags assigned to Booth ${selectedBooth}`, 'success');
      setSelectedItems(new Set());
      setSelectedBooth('');
      fetchUnregisteredInventory(1);
    } catch (err: any) {
      addToast(err.message || 'Assignment failed', 'error');
    } finally {
      setIsAssigning(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Booth Assignment</h1>
          <p className="text-gray-600">Assign unregistered tags to specific booths</p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">Total Unregistered</p>
                <p className="text-2xl font-bold text-gray-900">{inventory.length}</p>
              </div>
              <AlertCircle className="text-gray-400" size={24} />
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">Selected</p>
                <p className="text-2xl font-bold text-blue-700">{selectedItems.size}</p>
              </div>
              <Check className="text-blue-400" size={24} />
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">Target Booth</p>
                <p className="text-2xl font-bold text-gray-900">
                  {selectedBooth ? `Booth ${selectedBooth}` : '-'}
                </p>
              </div>
              <CheckCircle className="text-green-400" size={24} />
            </div>
          </div>
        </div>

        {/* Action Bar */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Select Booth (1-7)
              </label>
              <select
                value={selectedBooth}
                onChange={(e) => setSelectedBooth(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
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
                className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium"
              >
                {isAssigning && <Loader2 className="animate-spin" size={18} />}
                Assign Selected
              </button>
            </div>
          </div>
        </div>

        {/* Table */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="animate-spin text-blue-600" size={32} />
            </div>
          ) : inventory.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12">
              <CheckCircle className="text-green-400 mb-2" size={32} />
              <p className="text-gray-600">All tags have been assigned!</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-100 border-b">
                    <tr>
                      <th className="px-6 py-3 text-left">
                        <input
                          type="checkbox"
                          checked={selectedItems.size === inventory.length && inventory.length > 0}
                          onChange={toggleSelectAll}
                          className="w-4 h-4 cursor-pointer"
                        />
                      </th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Tag Serial</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">TID</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Plate</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Type</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inventory.map((item) => (
                      <tr
                        key={item.id}
                        className={`border-b hover:bg-gray-50 ${
                          selectedItems.has(item.id) ? 'bg-blue-50' : ''
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
                        <td className="px-6 py-4 text-sm text-gray-900 font-mono">{item.tag_serial}</td>
                        <td className="px-6 py-4 text-sm text-gray-600 font-mono">{item.tid.substring(0, 8)}...</td>
                        <td className="px-6 py-4 text-sm text-gray-600">{item.vehicle_plate || '-'}</td>
                        <td className="px-6 py-4 text-sm text-gray-600 capitalize">{item.vehicle_type}</td>
                        <td className="px-6 py-4 text-sm text-gray-600">
                          {new Date(item.created_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              <div className="flex justify-between items-center px-6 py-4 bg-gray-50 border-t">
                <div className="text-sm text-gray-600">
                  Page {currentPage} of {totalPages}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => fetchUnregisteredInventory(currentPage - 1)}
                    disabled={currentPage === 1}
                    className="flex items-center gap-1 px-3 py-2 bg-gray-200 text-gray-800 rounded disabled:opacity-50"
                  >
                    <ChevronLeft size={18} />
                    Previous
                  </button>
                  <button
                    onClick={() => fetchUnregisteredInventory(currentPage + 1)}
                    disabled={currentPage >= totalPages}
                    className="flex items-center gap-1 px-3 py-2 bg-gray-200 text-gray-800 rounded disabled:opacity-50"
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
