import { AlertTriangle, AlertCircle, Info } from 'lucide-react';

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
      color: 'text-red-600',
      bgColor: 'bg-red-50',
      borderColor: 'border-red-200',
      iconColor: 'text-red-500',
    },
    not_assigned: {
      icon: AlertTriangle,
      title: 'Not Assigned',
      message: `This tag has not been assigned to any booth yet. Please assign it first from the Booth Assignment page.`,
      color: 'text-orange-600',
      bgColor: 'bg-orange-50',
      borderColor: 'border-orange-200',
      iconColor: 'text-orange-500',
    },
    activation_required: {
      icon: Info,
      title: 'Activation Required',
      message: `This tag is assigned to your booth but has not been activated yet. Please complete the activation.`,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
      borderColor: 'border-blue-200',
      iconColor: 'text-blue-500',
    },
  };

  const warning = warnings[status];
  if (!warning) return null;

  const Icon = warning.icon;

  return (
    <div
      className={`p-4 rounded-lg border ${warning.bgColor} ${warning.borderColor} flex gap-3`}
    >
      <Icon className={`${warning.iconColor} flex-shrink-0`} size={20} />
      <div>
        <h4 className={`font-semibold ${warning.color}`}>{warning.title}</h4>
        <p className={`text-sm ${warning.color} opacity-90`}>{warning.message}</p>
      </div>
    </div>
  );
}
