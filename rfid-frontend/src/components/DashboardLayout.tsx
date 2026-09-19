import { Outlet, useLocation, useNavigate } from 'react-router';
import { useState, useEffect, useRef } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useTheme } from '@/context/ThemeContext';
import { BrandLogo, BrandLockup } from '@/components/BrandLogo';
import {
  LayoutDashboard,
  CreditCard,
  Car,
  History,
  BarChart3,
  User,
  LogOut,
  Menu,
  Search,
  Bell,
  Sun,
  Moon,
  ChevronDown,
  MapPin,
  Route,
  Users,
  Gauge,
  ArrowRightLeft,
  Wallet,
  Package,
  Tags,
  SignpostBig,
  Server,
} from 'lucide-react';

interface NavItem {
  path: string;
  label: string;
  icon: React.ElementType;
  adminOnly?: boolean;
}

const navItems: NavItem[] = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/register', label: 'ME-Tag Registration', icon: CreditCard },
  { path: '/vehicles', label: 'Vehicles', icon: Car },
  { path: '/operations', label: 'Toll Operations', icon: Gauge },
  { path: '/trips', label: 'Trip History', icon: Route },
  { path: '/transactions', label: 'Transactions', icon: History },
  { path: '/topup', label: 'Balance Topup', icon: Wallet },
  { path: '/transfer', label: 'Balance Transfer', icon: ArrowRightLeft },
  { path: '/plazas', label: 'Plazas & Rates', icon: MapPin },
  { path: '/reports', label: 'Reports', icon: BarChart3 },
  { path: '/profile', label: 'Profile', icon: User },
  { path: '/admin/users', label: 'User Management', icon: Users, adminOnly: true },
  { path: '/admin/inventory', label: 'Inventory Management', icon: Package, adminOnly: true },
  { path: '/admin/booth-assignment', label: 'Booth Assignment', icon: Tags, adminOnly: true },
  { path: '/admin/lanes', label: 'Lane Management', icon: SignpostBig, adminOnly: true },
  { path: '/admin/booth-updates', label: 'Booth Code Updates', icon: Server, adminOnly: true },
];

export default function DashboardLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { isDark, toggleTheme } = useTheme();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);

  const isAdmin = user?.role === 'admin';
  // Operators get the registration page alone (see App.tsx): no sidebar, no
  // search, no links out.
  const isOperator = user?.role === 'operator';
  const displayName = user?.full_name || user?.name || 'User';
  const initials =
    displayName
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((word) => word[0])
      .join('')
      .toUpperCase() || 'U';

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (profileRef.current && !profileRef.current.contains(event.target as Node)) {
        setProfileOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  const visibleNavItems = navItems.filter((item) => !item.adminOnly || isAdmin);

  return (
    <div className="min-h-screen bg-canvas">
      {!isOperator && (
      <>
      {/* Sidebar */}
      <aside
        className={`fixed top-0 left-0 z-40 h-full w-[280px] flex flex-col bg-surface border-r border-line transform transition-transform duration-300 ease-out ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        <div className="shrink-0 px-5 py-5 border-b border-line">
          <BrandLockup />
        </div>

        <nav className="flex-1 min-h-0 overflow-y-auto p-4 space-y-1">
          {visibleNavItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                aria-current={isActive ? 'page' : undefined}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200 relative group overflow-hidden ${
                  isActive
                    ? 'bg-brand/10 text-brand-ink dark:text-brand'
                    : 'text-ink-muted hover:bg-elevated hover:text-ink'
                }`}
              >
                {isActive && (
                  <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-7 bg-brand rounded-r-full" />
                )}
                <Icon
                  className={`w-5 h-5 shrink-0 transition-colors ${
                    isActive ? 'text-brand' : 'text-ink-subtle group-hover:text-ink-muted'
                  }`}
                />
                <span className="truncate">{item.label}</span>
                {item.adminOnly && (
                  <span className="ml-auto shrink-0 text-[10px] font-semibold bg-role/15 text-role px-1.5 py-0.5 rounded-full">
                    Admin
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        <div className="shrink-0 p-4 border-t border-line">
          <button
            onClick={logout}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-ink-muted hover:bg-danger/10 hover:text-danger transition-colors duration-200"
          >
            <LogOut className="w-5 h-5" />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      </>
      )}

      {/* Main content */}
      <div className={isOperator ? undefined : 'lg:ml-[280px]'}>
        {/* Top navbar */}
        <header className="sticky top-0 z-20 h-16 bg-surface/85 backdrop-blur-xl border-b border-line flex items-center justify-between px-4 lg:px-8">
          <div className="flex items-center gap-3 min-w-0">
            {!isOperator && (
              <button
                onClick={() => setSidebarOpen(true)}
                aria-label="Open navigation"
                className="lg:hidden p-2 rounded-lg text-ink-muted hover:bg-elevated transition-colors"
              >
                <Menu className="w-5 h-5" />
              </button>
            )}
            {/* The sidebar lockup is off-screen on mobile (and absent for operators), so the mark rides here. */}
            <BrandLogo className={isOperator ? 'h-6' : 'h-6 lg:hidden'} />
            <div className="hidden md:flex items-center gap-2 rounded-full bg-success/10 pl-2 pr-3 py-1 text-xs font-medium text-success">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-success"></span>
              </span>
              Live System Active
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Search */}
            <div className={isOperator ? 'hidden' : 'relative'}>
              <button
                onClick={() => setSearchOpen(!searchOpen)}
                aria-label="Search"
                aria-expanded={searchOpen}
                className="p-2 rounded-lg text-ink-muted hover:bg-elevated hover:text-brand transition-colors"
              >
                <Search className="w-5 h-5" />
              </button>
              {searchOpen && (
                <div className="absolute right-0 top-full mt-2 w-72 bg-surface border border-line rounded-xl skeu-card p-3 animate-fade-in-up">
                  <input
                    autoFocus
                    type="text"
                    placeholder="Search transactions, vehicles..."
                    className="w-full px-3 py-2 bg-elevated border border-line rounded-lg text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-brand focus:ring-2 focus:ring-brand/35"
                  />
                </div>
              )}
            </div>

            {/* Theme toggle */}
            <button
              onClick={toggleTheme}
              aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
              className="p-2 rounded-lg text-ink-muted hover:bg-elevated hover:text-brand transition-colors"
            >
              {isDark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>

            {/* Notifications */}
            {!isOperator && (
              <button
                aria-label="Notifications"
                className="relative p-2 rounded-lg text-ink-muted hover:bg-elevated hover:text-brand transition-colors"
              >
                <Bell className="w-5 h-5" />
                <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-danger rounded-full ring-2 ring-surface" />
              </button>
            )}

            {/* Profile */}
            <div className="relative" ref={profileRef}>
              <button
                onClick={() => setProfileOpen(!profileOpen)}
                aria-label="Account menu"
                aria-expanded={profileOpen}
                className="flex items-center gap-2 p-1.5 rounded-xl hover:bg-elevated transition-colors"
              >
                <span
                  aria-hidden="true"
                  className="w-8 h-8 rounded-full bg-brand text-brand-on grid place-items-center text-xs font-bold ring-2 ring-brand/25"
                >
                  {initials}
                </span>
                <ChevronDown className="w-4 h-4 text-ink-subtle hidden sm:block" />
              </button>

              {profileOpen && (
                <div className="absolute right-0 top-full mt-2 w-56 bg-surface border border-line rounded-xl skeu-card py-2 animate-fade-in-up">
                  <div className="px-4 py-3 border-b border-line">
                    <p className="text-sm font-semibold text-ink truncate">{displayName}</p>
                    <p className="text-xs text-ink-muted">{user?.phone}</p>
                    {user?.role && (
                      <span className="inline-block mt-1.5 text-[10px] font-semibold bg-brand/10 text-brand-ink dark:text-brand px-2 py-0.5 rounded-full capitalize">
                        {user.role}
                      </span>
                    )}
                  </div>
                  {!isOperator && (
                    <button
                      onClick={() => {
                        navigate('/profile');
                        setProfileOpen(false);
                      }}
                      className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-ink-muted hover:bg-elevated hover:text-ink transition-colors"
                    >
                      <User className="w-4 h-4" />
                      Profile
                    </button>
                  )}
                  <button
                    onClick={() => {
                      toggleTheme();
                      setProfileOpen(false);
                    }}
                    className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-ink-muted hover:bg-elevated hover:text-ink transition-colors"
                  >
                    {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
                    {isDark ? 'Light Mode' : 'Dark Mode'}
                  </button>
                  <div className="border-t border-line mt-1 pt-1">
                    <button
                      onClick={() => {
                        logout();
                        setProfileOpen(false);
                      }}
                      className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-danger hover:bg-danger/10 transition-colors"
                    >
                      <LogOut className="w-4 h-4" />
                      Sign Out
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="p-4 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
