import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useAuth } from '@/context/AuthContext';
import { useToast } from '@/context/ToastContext';
import { Eye, EyeOff, Loader2, Phone } from 'lucide-react';
import { BrandLogo } from '@/components/BrandLogo';

export default function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const { addToast } = useToast();
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!phone || !password) {
      setError('Please fill in all fields');
      return;
    }
    if (!/^03\d{9}$/.test(phone.replace(/\s/g, ''))) {
      setError('Please enter a valid Pakistani phone number (03XXXXXXXXX)');
      return;
    }

    setIsLoading(true);
    const success = await login(phone.replace(/\s/g, ''), password);
    setIsLoading(false);

    if (success) {
      addToast({ type: 'success', title: 'Welcome back!', message: 'You have successfully signed in.' });
      navigate('/dashboard');
    } else {
      setError('Invalid phone number or password. Please try again.');
      addToast({ type: 'error', title: 'Authentication failed', message: 'Invalid credentials.' });
    }
  };

  return (
    <div className="relative min-h-screen bg-canvas flex items-center justify-center p-4 overflow-hidden">
      {/* Brand wash — two soft orange pools behind the card. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-40 -left-32 h-96 w-96 rounded-full bg-brand/10 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-48 -right-32 h-[28rem] w-[28rem] rounded-full bg-brand/[0.07] blur-3xl"
      />

      <div className="relative w-full max-w-md">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <BrandLogo className="h-16 mb-5" />
          <h1 className="text-2xl font-bold text-ink text-center">Smart Expressway</h1>
          <p className="text-sm text-ink-muted mt-1">Toll Management System</p>
        </div>

        {/* Login Card */}
        <div className="bg-surface border border-line rounded-2xl skeu-card overflow-hidden">
          <div className="h-[3px] road-rule" aria-hidden="true" />
          <div className="p-8">
          <h2 className="text-lg font-semibold text-ink mb-1">Sign In</h2>
          <p className="text-sm text-ink-muted mb-6">
            Enter your credentials to access the dashboard
          </p>

          {error && (
            <div
              role="alert"
              className="mb-4 p-3 rounded-lg bg-danger/10 border border-danger/20 text-sm text-danger"
            >
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-ink mb-1.5">
                Phone Number
              </label>
              <div className="relative">
                <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-subtle" />
                <input
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="03001234567"
                  className="w-full pl-10 pr-4 py-3 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-ink mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  className="w-full px-4 py-3 pr-12 bg-elevated border border-line rounded-xl text-sm text-ink placeholder:text-ink-subtle outline-none focus:border-brand focus:ring-2 focus:ring-brand/35 transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-subtle hover:text-ink-muted transition-colors"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 py-3 bg-brand text-brand-on font-semibold rounded-xl hover:bg-brand-strong active:bg-brand-strong transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Signing in...
                </>
              ) : (
                'Sign In'
              )}
            </button>
          </form>

            <div className="mt-6 pt-4 border-t border-line text-center">
              <p className="text-xs text-ink-muted">
                Government of Pakistan - National Highway Authority
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
