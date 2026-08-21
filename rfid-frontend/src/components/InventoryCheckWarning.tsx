import { AlertTriangle, Info } from 'lucide-react';

interface InventoryCheckWarningProps {
  status: 'booth_mismatch' | 'not_assigned' | 'activation_required' | null;
  boothAssignedId?: number;
  currentBoothId: number;
}

export default function InventoryCheckWarning({
  status,
  boothAssignedId,
  currentBoothId,
}: InventoryCheckWarningProps) {
  if (!status) return null;

  const warnings = {
    booth_mismatch: {
      icon: AlertTriangle,
      title: 'Booth Mismatch',
      message: `This tag is assigned to Booth ${boothAssignedId}, not Booth ${currentBoothId}. It cannot be activated at this booth.`,
      accent: 'var(--accent-rose)',
    },
    not_assigned: {
      icon: AlertTriangle,
      title: 'Not Assigned',
      message: `This tag has not been assigned to any booth yet. Please assign it first from the Booth Assignment page.`,
      accent: 'var(--accent-amber)',
    },
    activation_required: {
      icon: Info,
      title: 'Activation Required',
      message: `This tag is assigned to your booth but has not been activated yet. Please complete the activation.`,
      accent: 'var(--accent-blue)',
    },
  };

  const warning = warnings[status];
  if (!warning) return null;

  const Icon = warning.icon;

  return (
    <div
      className="p-4 rounded-xl border flex gap-3 bg-surface shadow-sm"
      style={{ borderColor: warning.accent }}
    >
      <Icon className="flex-shrink-0" size={20} style={{ color: warning.accent }} />
      <div>
        <h4 className="font-semibold" style={{ color: warning.accent }}>{warning.title}</h4>
        <p className="text-sm text-ink-muted">{warning.message}</p>
      </div>
    </div>
  );
}
