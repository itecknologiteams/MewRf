import { useState, useEffect } from 'react';
import { useToast } from '@/context/ToastContext';
import { inventoryApi } from '@/services/inventoryApi';
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

const statusColors: Record<string, string> = {
  unregistered: 'bg-[var(--bg-elevated)] text-[var(--text-secondary)]',
  booth_assigned: 'bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]',
  activated: 'bg-[var(--accent-emerald)]/10 text-[var(--accent-emerald)]',
};

const statusLabels: Record<string, string> = {
  unregistered: 'Unregistered',
  booth_assigned: 'Booth Assigned',
  activated: 'Activated',
};

export default function InventoryManagement() {
  const { addToast } = useToast();

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

  const fetchInventory = async (page = 1) => {
    try {
      setLoading(true);
      const data = await inventoryApi.list({
        page,
        per_page: 50,
        search: search || undefined,
        status: statusFilter !== 'All' ? statusFilter.toLowerCase() : undefined,
        booth_assigned_id: boothFilter !== 'All' ? boothFilter : undefined,
        vehicle_type: typeFilter !== 'All' ? typeFilter.toLowerCase() : undefined,
      });
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
    fetchInventory(1);
  }, [search, statusFilter, boothFilter, typeFilter]);

  const handleUpload = async () => {
    if (!uploadFile) {
      addToast({ type: 'error', title: 'Validation', message: 'Please select a file' });
      return;
    }
    try {
      setIsUploading(true);
      setUploadResult(null);
      const data = await inventoryApi.upload(uploadFile);
      setUploadResult(data);
      addToast({ type: 'success', title: 'Uploaded', message: `${data.added} tags added successfully` });
      setUploadFile(null);
      setTimeout(() => {
        setShowUploadModal(false);
        fetchInventory(1);
      }, 2000);
    } catch (err: any) {
      addToast({ type: 'error', title: 'Upload Failed', message: err.message || 'Upload failed' });
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
    <div className="animate-fade-in-up">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold text-[var(--text-primary)]">Inventory Management</h1>
          <div className="flex gap-3">
            <button
              onClick={() => fetchInventory(currentPage)}
              className="flex items-center gap-2 px-4 py-2 bg-[var(--bg-elevated)] text-[var(--text-primary)] rounded-xl hover:bg-[var(--bg-elevated)]"
            >
              <RefreshCw size={18} />
              Refresh
            </button>
            <button
              onClick={() => setShowUploadModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-[var(--accent-blue)] text-white rounded-xl hover:opacity-90"
            >
              <Upload size={18} />
              Upload CSV
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-[var(--bg-surface)] rounded-xl shadow-sm p-6 mb-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="font-semibold text-[var(--text-primary)] flex items-center gap-2">
              <Filter size={20} />
              Filters
            </h2>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="text-[var(--accent-blue)] hover:text-[var(--accent-blue)]"
            >
              {showFilters ? 'Hide' : 'Show'}
            </button>
          </div>

          {showFilters && (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">Search</label>
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Tag serial or TID..."
                  className="w-full px-3 py-2 border border-[var(--border-custom)] rounded-xl focus:ring-2 focus:ring-[var(--accent-blue)]/20 focus:border-[var(--accent-blue)]"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">Status</label>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="w-full px-3 py-2 border border-[var(--border-custom)] rounded-xl focus:ring-2 focus:ring-[var(--accent-blue)]/20 focus:border-[var(--accent-blue)]"
                >
                  <option>All</option>
                  <option value="unregistered">Unregistered</option>
                  <option value="booth_assigned">Booth Assigned</option>
                  <option value="activated">Activated</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">Booth</label>
                <select
                  value={boothFilter}
                  onChange={(e) => setBoothFilter(e.target.value)}
                  className="w-full px-3 py-2 border border-[var(--border-custom)] rounded-xl focus:ring-2 focus:ring-[var(--accent-blue)]/20 focus:border-[var(--accent-blue)]"
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
                <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">Vehicle Type</label>
                <select
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                  className="w-full px-3 py-2 border border-[var(--border-custom)] rounded-xl focus:ring-2 focus:ring-[var(--accent-blue)]/20 focus:border-[var(--accent-blue)]"
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
          <div className="bg-[var(--bg-surface)] rounded-xl shadow-sm p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[var(--text-secondary)] text-sm">Total Tags</p>
                <p className="text-2xl font-bold text-[var(--text-primary)]">{inventory.length}</p>
              </div>
              <FileText className="text-[var(--text-tertiary)]" size={24} />
            </div>
          </div>

          <div className="bg-[var(--bg-surface)] rounded-xl shadow-sm p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[var(--text-secondary)] text-sm">Unregistered</p>
                <p className="text-2xl font-bold text-[var(--text-secondary)]">
                  {inventory.filter((i) => i.status === 'unregistered').length}
                </p>
              </div>
              <AlertCircle className="text-[var(--text-tertiary)]" size={24} />
            </div>
          </div>

          <div className="bg-[var(--bg-surface)] rounded-xl shadow-sm p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[var(--text-secondary)] text-sm">Activated</p>
                <p className="text-2xl font-bold text-[var(--accent-emerald)]">
                  {inventory.filter((i) => i.status === 'activated').length}
                </p>
              </div>
              <CheckCircle className="text-[var(--accent-emerald)]" size={24} />
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
              <AlertCircle className="text-[var(--text-tertiary)] mb-2" size={32} />
              <p className="text-[var(--text-secondary)]">No inventory found</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-[var(--bg-elevated)] border-b border-[var(--border-custom)]">
                    <tr>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-[var(--text-primary)]">Tag Serial</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-[var(--text-primary)]">TID</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-[var(--text-primary)]">Plate</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-[var(--text-primary)]">Type</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-[var(--text-primary)]">Status</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-[var(--text-primary)]">Booth</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-[var(--text-primary)]">Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inventory.map((item) => (
                      <tr key={item.id} className="border-b border-[var(--border-custom)] hover:bg-[var(--bg-elevated)]">
                        <td className="px-6 py-4 text-sm text-[var(--text-primary)] font-mono">{item.tag_serial}</td>
                        <td className="px-6 py-4 text-sm text-[var(--text-secondary)] font-mono">{item.tid.substring(0, 8)}...</td>
                        <td className="px-6 py-4 text-sm text-[var(--text-secondary)]">{item.vehicle_plate || '-'}</td>
                        <td className="px-6 py-4 text-sm text-[var(--text-secondary)] capitalize">{item.vehicle_type}</td>
                        <td className="px-6 py-4">
                          <span className={`px-3 py-1 rounded-full text-xs font-semibold ${statusColors[item.status]}`}>
                            {statusLabels[item.status]}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-[var(--text-secondary)]">
                          {item.status === 'activated' && item.first_activated_booth_id ? (
                            <span className="flex items-center gap-1">
                              <CheckCircle size={16} className="text-[var(--accent-emerald)]" />
                              Booth {item.first_activated_booth_id}
                            </span>
                          ) : item.status === 'booth_assigned' ? (
                            <span className="flex items-center gap-1">
                              <Clock size={16} className="text-[var(--accent-blue)]" />
                              Booth {item.booth_assigned_id}
                            </span>
                          ) : (
                            <span className="text-[var(--text-tertiary)]">-</span>
                          )}
                        </td>
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
                    onClick={() => fetchInventory(currentPage - 1)}
                    disabled={currentPage === 1}
                    className="flex items-center gap-1 px-3 py-2 bg-[var(--bg-elevated)] text-[var(--text-primary)] rounded disabled:opacity-50"
                  >
                    <ChevronLeft size={18} />
                    Previous
                  </button>
                  <button
                    onClick={() => fetchInventory(currentPage + 1)}
                    disabled={currentPage >= totalPages}
                    className="flex items-center gap-1 px-3 py-2 bg-[var(--bg-elevated)] text-[var(--text-primary)] rounded disabled:opacity-50"
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
          <div className="bg-[var(--bg-surface)] border border-[var(--border-custom)] rounded-xl max-w-md w-full">
            <div className="flex justify-between items-center p-6 border-b border-[var(--border-custom)]">
              <h2 className="text-xl font-bold text-[var(--text-primary)]">Upload Inventory</h2>
              <button onClick={() => setShowUploadModal(false)} className="text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]">
                <X size={24} />
              </button>
            </div>

            <div className="p-6">
              {uploadResult ? (
                <div className="space-y-4">
                  <div className="bg-[var(--accent-emerald)]/10 border border-[var(--accent-emerald)]/30 rounded-xl p-4">
                    <p className="font-semibold text-[var(--accent-emerald)]">Upload Successful!</p>
                    <p className="text-sm text-[var(--accent-emerald)] mt-1">Added: {uploadResult.added} tags</p>
                    {uploadResult.skipped > 0 && (
                      <p className="text-sm text-[var(--accent-amber)] mt-1">Skipped: {uploadResult.skipped} duplicates</p>
                    )}
                  </div>
                  {uploadResult.errors.length > 0 && (
                    <div className="bg-[var(--accent-rose)]/10 border border-[var(--accent-rose)]/30 rounded-xl p-4">
                      <p className="font-semibold text-[var(--accent-rose)] text-sm">Errors:</p>
                      <ul className="text-xs text-[var(--accent-rose)] mt-2 space-y-1">
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
                    <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">CSV File</label>
                    <input
                      type="file"
                      accept=".csv"
                      onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                      className="w-full px-3 py-2 border border-[var(--border-custom)] rounded-xl"
                    />
                    <p className="text-xs text-[var(--text-secondary)] mt-2">
                      Required columns: tag_serial, tid, epc, vehicle_plate, vehicle_type, vehicle_color
                    </p>
                  </div>

                  <button
                    onClick={downloadTemplate}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-[var(--bg-elevated)] text-[var(--text-primary)] rounded-xl hover:bg-[var(--bg-elevated)]"
                  >
                    <Download size={18} />
                    Download Template
                  </button>

                  <div className="flex gap-3">
                    <button
                      onClick={() => setShowUploadModal(false)}
                      className="flex-1 px-4 py-2 border border-[var(--border-custom)] text-[var(--text-secondary)] rounded-xl hover:bg-[var(--bg-elevated)]"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleUpload}
                      disabled={!uploadFile || isUploading}
                      className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-[var(--accent-blue)] text-white rounded-xl hover:opacity-90 disabled:opacity-50"
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
