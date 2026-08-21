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
  id: number;
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
  unregistered: 'bg-elevated text-ink-muted',
  booth_assigned: 'bg-brand/10 text-brand',
  activated: 'bg-success/10 text-success',
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
          <h1 className="text-3xl font-bold text-ink">Inventory Management</h1>
          <div className="flex gap-3">
            <button
              onClick={() => fetchInventory(currentPage)}
              className="flex items-center gap-2 px-4 py-2 bg-elevated text-ink rounded-xl hover:bg-elevated"
            >
              <RefreshCw size={18} />
              Refresh
            </button>
            <button
              onClick={() => setShowUploadModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-brand text-brand-on rounded-xl hover:opacity-90"
            >
              <Upload size={18} />
              Upload CSV
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-surface rounded-xl p-6 mb-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="font-semibold text-ink flex items-center gap-2">
              <Filter size={20} />
              Filters
            </h2>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="text-brand hover:text-brand"
            >
              {showFilters ? 'Hide' : 'Show'}
            </button>
          </div>

          {showFilters && (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <label className="block text-sm font-medium text-ink-muted mb-2">Search</label>
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Tag serial or TID..."
                  className="w-full px-3 py-2 border border-line rounded-xl focus:ring-2 focus:ring-brand/35 focus:border-brand"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-ink-muted mb-2">Status</label>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="w-full px-3 py-2 border border-line rounded-xl focus:ring-2 focus:ring-brand/35 focus:border-brand"
                >
                  <option>All</option>
                  <option value="unregistered">Unregistered</option>
                  <option value="booth_assigned">Booth Assigned</option>
                  <option value="activated">Activated</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-ink-muted mb-2">Booth</label>
                <select
                  value={boothFilter}
                  onChange={(e) => setBoothFilter(e.target.value)}
                  className="w-full px-3 py-2 border border-line rounded-xl focus:ring-2 focus:ring-brand/35 focus:border-brand"
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
                <label className="block text-sm font-medium text-ink-muted mb-2">Vehicle Type</label>
                <select
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                  className="w-full px-3 py-2 border border-line rounded-xl focus:ring-2 focus:ring-brand/35 focus:border-brand"
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
          <div className="bg-surface rounded-xl shadow-sm p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-ink-muted text-sm">Total Tags</p>
                <p className="text-2xl font-bold text-ink">{inventory.length}</p>
              </div>
              <FileText className="text-ink-subtle" size={24} />
            </div>
          </div>

          <div className="bg-surface rounded-xl shadow-sm p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-ink-muted text-sm">Unregistered</p>
                <p className="text-2xl font-bold text-ink-muted">
                  {inventory.filter((i) => i.status === 'unregistered').length}
                </p>
              </div>
              <AlertCircle className="text-ink-subtle" size={24} />
            </div>
          </div>

          <div className="bg-surface rounded-xl shadow-sm p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-ink-muted text-sm">Activated</p>
                <p className="text-2xl font-bold text-success">
                  {inventory.filter((i) => i.status === 'activated').length}
                </p>
              </div>
              <CheckCircle className="text-success" size={24} />
            </div>
          </div>
        </div>

        {/* Table */}
        <div className="bg-surface rounded-xl shadow-sm overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="animate-spin text-brand" size={32} />
            </div>
          ) : inventory.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12">
              <AlertCircle className="text-ink-subtle mb-2" size={32} />
              <p className="text-ink-muted">No inventory found</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-elevated border-b border-line">
                    <tr>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-ink">Tag Serial</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-ink">TID</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-ink">Plate</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-ink">Type</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-ink">Status</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-ink">Booth</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-ink">Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inventory.map((item) => (
                      <tr key={item.id} className="border-b border-line hover:bg-elevated">
                        <td className="px-6 py-4 text-sm text-ink font-mono">{item.tag_serial}</td>
                        <td className="px-6 py-4 text-sm text-ink-muted font-mono">{item.tid.substring(0, 8)}...</td>
                        <td className="px-6 py-4 text-sm text-ink-muted">{item.vehicle_plate || '-'}</td>
                        <td className="px-6 py-4 text-sm text-ink-muted capitalize">{item.vehicle_type}</td>
                        <td className="px-6 py-4">
                          <span className={`px-3 py-1 rounded-full text-xs font-semibold ${statusColors[item.status]}`}>
                            {statusLabels[item.status]}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-ink-muted">
                          {item.status === 'activated' && item.first_activated_booth_id ? (
                            <span className="flex items-center gap-1">
                              <CheckCircle size={16} className="text-success" />
                              Booth {item.first_activated_booth_id}
                            </span>
                          ) : item.status === 'booth_assigned' ? (
                            <span className="flex items-center gap-1">
                              <Clock size={16} className="text-brand" />
                              Booth {item.booth_assigned_id}
                            </span>
                          ) : (
                            <span className="text-ink-subtle">-</span>
                          )}
                        </td>
                        <td className="px-6 py-4 text-sm text-ink-muted">
                          {new Date(item.created_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              <div className="flex justify-between items-center px-6 py-4 bg-elevated border-t border-line">
                <div className="text-sm text-ink-muted">
                  Page {currentPage} of {totalPages}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => fetchInventory(currentPage - 1)}
                    disabled={currentPage === 1}
                    className="flex items-center gap-1 px-3 py-2 bg-elevated text-ink rounded disabled:opacity-50"
                  >
                    <ChevronLeft size={18} />
                    Previous
                  </button>
                  <button
                    onClick={() => fetchInventory(currentPage + 1)}
                    disabled={currentPage >= totalPages}
                    className="flex items-center gap-1 px-3 py-2 bg-elevated text-ink rounded disabled:opacity-50"
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
          <div className="bg-surface border border-line rounded-xl skeu-card max-w-md w-full">
            <div className="flex justify-between items-center p-6 border-b border-line">
              <h2 className="text-xl font-bold text-ink">Upload Inventory</h2>
              <button onClick={() => setShowUploadModal(false)} className="text-ink-subtle hover:text-ink-muted">
                <X size={24} />
              </button>
            </div>

            <div className="p-6">
              {uploadResult ? (
                <div className="space-y-4">
                  <div className="bg-success/10 border border-success/30 rounded-xl p-4">
                    <p className="font-semibold text-success">Upload Successful!</p>
                    <p className="text-sm text-success mt-1">Added: {uploadResult.added} tags</p>
                    {uploadResult.skipped > 0 && (
                      <p className="text-sm text-warning mt-1">Skipped: {uploadResult.skipped} duplicates</p>
                    )}
                  </div>
                  {uploadResult.errors.length > 0 && (
                    <div className="bg-danger/10 border border-danger/30 rounded-xl p-4">
                      <p className="font-semibold text-danger text-sm">Errors:</p>
                      <ul className="text-xs text-danger mt-2 space-y-1">
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
                    <label className="block text-sm font-medium text-ink-muted mb-2">CSV File</label>
                    <input
                      type="file"
                      accept=".csv"
                      onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                      className="w-full px-3 py-2 border border-line rounded-xl"
                    />
                    <p className="text-xs text-ink-muted mt-2">
                      Required columns: tag_serial, tid, epc, vehicle_plate, vehicle_type, vehicle_color
                    </p>
                  </div>

                  <button
                    onClick={downloadTemplate}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-elevated text-ink rounded-xl hover:bg-elevated"
                  >
                    <Download size={18} />
                    Download Template
                  </button>

                  <div className="flex gap-3">
                    <button
                      onClick={() => setShowUploadModal(false)}
                      className="flex-1 px-4 py-2 border border-line text-ink-muted rounded-xl hover:bg-elevated"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleUpload}
                      disabled={!uploadFile || isUploading}
                      className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-brand text-brand-on rounded-xl hover:opacity-90 disabled:opacity-50"
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
