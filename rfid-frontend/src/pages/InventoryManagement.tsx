import { useState, useEffect } from 'react';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import {
  Upload,
  X,
  Loader2,
  Filter,
  RefreshCw,
  FileText,
  CheckCircle,
  Clock,
  AlertCircle,
  Download,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

interface InventoryItem {
  id: string;
  tag_serial: string;
  tid: string;
  vehicle_plate: string;
  vehicle_type: string;
  status: 'unregistered' | 'booth_assigned' | 'activated';
  booth_assigned_id?: number;
  first_activated_booth_id?: number;
  created_at: string;
}

interface InventoryResponse {
  items: InventoryItem[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

const statusColors: Record<string, string> = {
  unregistered: 'bg-gray-100 text-gray-800',
  booth_assigned: 'bg-blue-100 text-blue-800',
  activated: 'bg-green-100 text-green-800',
};

const statusLabels: Record<string, string> = {
  unregistered: 'Unregistered',
  booth_assigned: 'Booth Assigned',
  activated: 'Activated',
};

export default function InventoryManagement() {
  const { addToast } = useToast();
  const { user } = useAuth();

  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  const [boothFilter, setBoothFilter] = useState('All');
  const [typeFilter, setTypeFilter] = useState('All');
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<any>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [showFilters, setShowFilters] = useState(false);

  const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const fetchInventory = async (page = 1) => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      params.append('page', page.toString());
      params.append('per_page', '50');

      if (search) params.append('search', search);
      if (statusFilter !== 'All') params.append('status', statusFilter.toLowerCase());
      if (boothFilter !== 'All') params.append('booth_assigned_id', boothFilter);
      if (typeFilter !== 'All') params.append('vehicle_type', typeFilter.toLowerCase());

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
    fetchInventory(1);
  }, [search, statusFilter, boothFilter, typeFilter]);

  const handleUpload = async () => {
    if (!uploadFile) {
      addToast('Please select a file', 'error');
      return;
    }

    try {
      setIsUploading(true);
      setUploadResult(null);

      const formData = new FormData();
      formData.append('file', uploadFile);

      const response = await fetch(`${API_BASE}/api/v1/vehicles/inventory/upload/`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
        body: formData,
      });

      const result = await response.json();

      if (!response.ok) {
        addToast(result.message || 'Upload failed', 'error');
        return;
      }

      setUploadResult(result.data);
      addToast(`${result.data.added} tags added successfully`, 'success');
      setUploadFile(null);
      setTimeout(() => {
        setShowUploadModal(false);
        fetchInventory(1);
      }, 2000);
    } catch (err: any) {
      addToast(err.message || 'Upload failed', 'error');
    } finally {
      setIsUploading(false);
    }
  };

  const downloadTemplate = () => {
    const csv = 'tag_serial,tid,epc,vehicle_plate,vehicle_type,vehicle_color\nSER001,TID001,EPC001,LHR1234,car,white\n';
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'inventory_template.csv';
    a.click();
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Inventory Management</h1>
          <div className="flex gap-3">
            <button
              onClick={() => fetchInventory(currentPage)}
              className="flex items-center gap-2 px-4 py-2 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300"
            >
              <RefreshCw size={18} />
              Refresh
            </button>
            <button
              onClick={() => setShowUploadModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              <Upload size={18} />
              Upload CSV
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="font-semibold text-gray-900 flex items-center gap-2">
              <Filter size={20} />
              Filters
            </h2>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="text-blue-600 hover:text-blue-700"
            >
              {showFilters ? 'Hide' : 'Show'}
            </button>
          </div>

          {showFilters && (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Search</label>
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Tag serial or TID..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Status</label>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option>All</option>
                  <option value="unregistered">Unregistered</option>
                  <option value="booth_assigned">Booth Assigned</option>
                  <option value="activated">Activated</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Booth</label>
                <select
                  value={boothFilter}
                  onChange={(e) => setBoothFilter(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option>All</option>
                  {Array.from({ length: 7 }, (_, i) => (
                    <option key={i + 1} value={i + 1}>
                      Booth {i + 1}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Vehicle Type</label>
                <select
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option>All</option>
                  <option value="car">Car</option>
                  <option value="truck">Truck</option>
                  <option value="bus">Bus</option>
                  <option value="motorcycle">Motorcycle</option>
                </select>
              </div>
            </div>
          )}
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">Total Tags</p>
                <p className="text-2xl font-bold text-gray-900">{inventory.length}</p>
              </div>
              <FileText className="text-gray-400" size={24} />
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">Unregistered</p>
                <p className="text-2xl font-bold text-gray-700">
                  {inventory.filter((i) => i.status === 'unregistered').length}
                </p>
              </div>
              <AlertCircle className="text-gray-400" size={24} />
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm">Activated</p>
                <p className="text-2xl font-bold text-green-700">
                  {inventory.filter((i) => i.status === 'activated').length}
                </p>
              </div>
              <CheckCircle className="text-green-400" size={24} />
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
              <AlertCircle className="text-gray-400 mb-2" size={32} />
              <p className="text-gray-600">No inventory found</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-100 border-b">
                    <tr>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Tag Serial</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">TID</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Plate</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Type</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Status</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Booth</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inventory.map((item) => (
                      <tr key={item.id} className="border-b hover:bg-gray-50">
                        <td className="px-6 py-4 text-sm text-gray-900 font-mono">{item.tag_serial}</td>
                        <td className="px-6 py-4 text-sm text-gray-600 font-mono">{item.tid.substring(0, 8)}...</td>
                        <td className="px-6 py-4 text-sm text-gray-600">{item.vehicle_plate || '-'}</td>
                        <td className="px-6 py-4 text-sm text-gray-600 capitalize">{item.vehicle_type}</td>
                        <td className="px-6 py-4">
                          <span className={`px-3 py-1 rounded-full text-xs font-semibold ${statusColors[item.status]}`}>
                            {statusLabels[item.status]}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-600">
                          {item.status === 'activated' && item.first_activated_booth_id ? (
                            <span className="flex items-center gap-1">
                              <CheckCircle size={16} className="text-green-600" />
                              Booth {item.first_activated_booth_id}
                            </span>
                          ) : item.status === 'booth_assigned' ? (
                            <span className="flex items-center gap-1">
                              <Clock size={16} className="text-blue-600" />
                              Booth {item.booth_assigned_id}
                            </span>
                          ) : (
                            <span className="text-gray-400">-</span>
                          )}
                        </td>
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
                    onClick={() => fetchInventory(currentPage - 1)}
                    disabled={currentPage === 1}
                    className="flex items-center gap-1 px-3 py-2 bg-gray-200 text-gray-800 rounded disabled:opacity-50"
                  >
                    <ChevronLeft size={18} />
                    Previous
                  </button>
                  <button
                    onClick={() => fetchInventory(currentPage + 1)}
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

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-md w-full">
            <div className="flex justify-between items-center p-6 border-b">
              <h2 className="text-xl font-bold">Upload Inventory</h2>
              <button onClick={() => setShowUploadModal(false)} className="text-gray-500 hover:text-gray-700">
                <X size={24} />
              </button>
            </div>

            <div className="p-6">
              {uploadResult ? (
                <div className="space-y-4">
                  <div className="bg-green-50 border border-green-200 rounded p-4">
                    <p className="font-semibold text-green-900">Upload Successful!</p>
                    <p className="text-sm text-green-800 mt-1">Added: {uploadResult.added} tags</p>
                    {uploadResult.skipped > 0 && (
                      <p className="text-sm text-orange-800 mt-1">Skipped: {uploadResult.skipped} duplicates</p>
                    )}
                  </div>
                  {uploadResult.errors.length > 0 && (
                    <div className="bg-red-50 border border-red-200 rounded p-4">
                      <p className="font-semibold text-red-900 text-sm">Errors:</p>
                      <ul className="text-xs text-red-800 mt-2 space-y-1">
                        {uploadResult.errors.slice(0, 3).map((err: string, i: number) => (
                          <li key={i}>• {err}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">CSV File</label>
                    <input
                      type="file"
                      accept=".csv"
                      onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    />
                    <p className="text-xs text-gray-600 mt-2">
                      Required columns: tag_serial, tid, epc, vehicle_plate, vehicle_type, vehicle_color
                    </p>
                  </div>

                  <button
                    onClick={downloadTemplate}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-gray-100 text-gray-800 rounded-lg hover:bg-gray-200"
                  >
                    <Download size={18} />
                    Download Template
                  </button>

                  <div className="flex gap-3">
                    <button
                      onClick={() => setShowUploadModal(false)}
                      className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleUpload}
                      disabled={!uploadFile || isUploading}
                      className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                    >
                      {isUploading && <Loader2 className="animate-spin" size={18} />}
                      Upload
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
