import { useState, useEffect, useMemo } from 'react';
import { authApi } from '@/services/api';
import type { MeResponse } from '@/services/api';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useNavigate } from 'react-router';
import {
  Users,
  Search,
  Filter,
  Loader2,
  RefreshCw,
  X,
  CheckCircle,
  Shield,
  XCircle,
} from 'lucide-react';

const ROLE_OPTIONS = ['all', 'user', 'operator', 'admin'];
const STATUS_OPTIONS = ['all', 'active', 'inactive', 'blocked'];

export default function AdminUsersPage() {
  const { addToast } = useToast();
  const { user } = useAuth();
  const navigate = useNavigate();

  const isAdmin = user?.role === 'admin';

  const [users, setUsers] = useState<MeResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [showFilters, setShowFilters] = useState(false);

  // Edit modal
  const [editUser, setEditUser] = useState<MeResponse | null>(null);
  const [editRole, setEditRole] = useState('');
  const [editStatus, setEditStatus] = useState('');
  const [saving, setSaving] = useState(false);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (roleFilter !== 'all') params.role = roleFilter;
      if (statusFilter !== 'all') params.status = statusFilter;
      const data = await authApi.adminUsers(params);
      setUsers(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load users';
      addToast({ type: 'error', title: 'Error', message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!isAdmin) return;
    fetchUsers();
  }, [isAdmin, roleFilter, statusFilter]);

  if (!isAdmin) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
        <XCircle className="w-16 h-16 text-danger mb-4" />
        <h2 className="text-xl font-bold text-ink mb-2">Access Restricted</h2>
        <p className="text-sm text-ink-muted mb-6">
          User Management is only available to admins.
        </p>
        <button
          onClick={() => navigate('/dashboard')}
          className="px-6 py-2.5 bg-brand text-brand-on text-sm font-medium rounded-xl hover:opacity-90 transition-opacity"
        >
          Go to Dashboard
        </button>
      </div>
    );
  }

  const filtered = useMemo(() => {
    const s = search.toLowerCase();
    return users.filter((u) => {
      const matchSearch =
        u.full_name?.toLowerCase().includes(s) ||
        u.phone?.toLowerCase().includes(s) ||
        u.cnic?.toLowerCase().includes(s);
      return matchSearch;
    });
  }, [users, search]);

  const openEdit = (u: MeResponse) => {
    setEditUser(u);
    setEditRole(u.user_role);
    setEditStatus(u.status);
  };

  const handleSave = async () => {
    if (!editUser) return;
    setSaving(true);
    try {
      await authApi.adminUpdateUser(editUser.id, {
        user_role: editRole,
        status: editStatus,
      } as Partial<MeResponse>);
      setUsers((prev) =>
        prev.map((u) =>
          u.id === editUser.id ? { ...u, user_role: editRole, status: editStatus } : u
        )
      );
      addToast({ type: 'success', title: 'User Updated', message: 'User details updated successfully.' });
      setEditUser(null);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Update failed';
      addToast({ type: 'error', title: 'Update Failed', message });
    } finally {
      setSaving(false);
    }
  };

  const getRoleBadge = (role: string) => {
    switch (role) {
      case 'admin': return 'bg-danger/10 text-danger border-danger/20';
      case 'operator': return 'bg-warning/10 text-warning border-warning/20';
      default: return 'bg-brand/10 text-brand border-brand/20';
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active': return 'bg-success/10 text-success border-success/20';
      case 'blocked': return 'bg-danger/10 text-danger border-danger/20';
      default: return 'bg-elevated text-ink-muted border-line';
    }
  };

  return (
    <div className="animate-fade-in-up">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Users className="w-6 h-6 text-brand" />
            <h1 className="text-2xl font-bold text-ink">User Management</h1>
          </div>
          <p className="text-sm text-ink-muted mt-1">
            {loading ? 'Loading...' : `${filtered.length} users found`}
          </p>
        </div>
        <button
          onClick={fetchUsers}
          className="flex items-center gap-2 px-4 py-2.5 bg-elevated border border-line text-ink-muted text-sm font-medium rounded-xl hover:bg-surface transition-colors self-start"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="bg-surface border border-line rounded-xl skeu-card p-4 mb-6">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-subtle" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by name, phone, or CNIC..."
              className="w-full pl-10 pr-4 py-2.5 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
            />
          </div>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-2 px-4 py-2.5 border rounded-xl text-sm font-medium transition-colors ${
              showFilters
                ? 'bg-brand/10 border-brand/30 text-brand'
                : 'bg-elevated border-line text-ink-muted'
            }`}
          >
            <Filter className="w-4 h-4" />
            Filters
          </button>
        </div>

        {showFilters && (
          <div className="flex flex-wrap gap-3 mt-3 pt-3 border-t border-line animate-fade-in-up">
            <div>
              <label className="block text-xs font-medium text-ink-muted mb-1.5">Role</label>
              <select
                value={roleFilter}
                onChange={(e) => setRoleFilter(e.target.value)}
                className="px-3 py-2 bg-elevated border border-line rounded-lg text-sm text-ink outline-none"
              >
                {ROLE_OPTIONS.map((r) => (
                  <option key={r} value={r}>{r === 'all' ? 'All Roles' : r.charAt(0).toUpperCase() + r.slice(1)}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-ink-muted mb-1.5">Status</label>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-3 py-2 bg-elevated border border-line rounded-lg text-sm text-ink outline-none"
              >
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>{s === 'all' ? 'All Status' : s.charAt(0).toUpperCase() + s.slice(1)}</option>
                ))}
              </select>
            </div>
            <button
              onClick={() => { setRoleFilter('all'); setStatusFilter('all'); setSearch(''); }}
              className="self-end px-3 py-2 text-sm text-danger hover:bg-danger/10 rounded-lg transition-colors"
            >
              Clear
            </button>
          </div>
        )}
      </div>

      {/* Table */}
      <div className="bg-surface border border-line rounded-xl skeu-card overflow-hidden">
        <div className="overflow-x-auto">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="w-8 h-8 animate-spin text-brand" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <Users className="w-12 h-12 text-ink-subtle mx-auto mb-4" />
              <h3 className="text-base font-semibold text-ink mb-2">No users found</h3>
              <p className="text-sm text-ink-muted">Try adjusting your search or filters.</p>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="bg-elevated">
                  <th className="text-left px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">Name</th>
                  <th className="text-left px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">Phone</th>
                  <th className="text-left px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">CNIC</th>
                  <th className="text-center px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">Role</th>
                  <th className="text-center px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">Status</th>
                  <th className="text-left px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">Created</th>
                  <th className="text-center px-6 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((u) => (
                  <tr
                    key={u.id}
                    className="border-b border-line hover:bg-elevated transition-colors cursor-pointer"
                    onClick={() => openEdit(u)}
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-brand/10 flex items-center justify-center">
                          <span className="text-xs font-semibold text-brand">
                            {u.full_name?.charAt(0).toUpperCase()}
                          </span>
                        </div>
                        <span className="text-sm font-medium text-ink">{u.full_name}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm font-mono text-ink-muted">{u.phone}</td>
                    <td className="px-6 py-4 text-sm font-mono text-ink-muted">{u.cnic || '—'}</td>
                    <td className="px-6 py-4 text-center">
                      <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border capitalize ${getRoleBadge(u.user_role)}`}>
                        {u.user_role}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-center">
                      <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border capitalize ${getStatusBadge(u.status)}`}>
                        {u.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-ink-muted">
                      {u.created_at ? new Date(u.created_at).toLocaleDateString('en-PK') : '—'}
                    </td>
                    <td className="px-6 py-4 text-center">
                      <button
                        onClick={(e) => { e.stopPropagation(); openEdit(u); }}
                        className="text-xs text-brand hover:underline"
                      >
                        Edit
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Edit Modal */}
      {editUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in-up">
          <div className="bg-surface border border-line rounded-2xl skeu-card w-full max-w-md">
            <div className="flex items-center justify-between px-6 py-4 border-b border-line">
              <div className="flex items-center gap-3">
                <Shield className="w-5 h-5 text-brand" />
                <h2 className="text-lg font-semibold text-ink">Edit User</h2>
              </div>
              <button
                onClick={() => setEditUser(null)}
                className="p-1.5 rounded-lg hover:bg-elevated text-ink-subtle transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-5">
              {/* User info */}
              <div className="bg-elevated rounded-xl p-4">
                <h3 className="text-base font-semibold text-ink">{editUser.full_name}</h3>
                <p className="text-sm text-ink-muted">{editUser.phone}</p>
                {editUser.cnic && <p className="text-xs text-ink-subtle mt-1">{editUser.cnic}</p>}
              </div>

              {/* Role */}
              <div>
                <label className="block text-sm font-medium text-ink mb-1.5">Role</label>
                <select
                  value={editRole}
                  onChange={(e) => setEditRole(e.target.value)}
                  className="w-full px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
                >
                  <option value="user">User</option>
                  <option value="operator">Operator</option>
                  <option value="admin">Admin</option>
                </select>
              </div>

              {/* Status */}
              <div>
                <label className="block text-sm font-medium text-ink mb-1.5">Status</label>
                <select
                  value={editStatus}
                  onChange={(e) => setEditStatus(e.target.value)}
                  className="w-full px-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
                >
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                  <option value="blocked">Blocked</option>
                </select>
              </div>

              {/* Actions */}
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setEditUser(null)}
                  className="flex-1 py-2.5 bg-elevated border border-line text-ink text-sm font-medium rounded-xl hover:bg-surface transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={saving}
                  className="flex-1 py-2.5 bg-brand text-brand-on text-sm font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-60 flex items-center justify-center gap-2"
                >
                  {saving ? (
                    <><Loader2 className="w-4 h-4 animate-spin" />Saving...</>
                  ) : (
                    <><CheckCircle className="w-4 h-4" />Save Changes</>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
