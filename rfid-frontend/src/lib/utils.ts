import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Render a plaza_id the way the operator writes it: 1 -> "001", 101 -> "101".
 *
 * plaza_id is stored and sent as an integer, so the leading zeros in the
 * operator's numbering ("001 Shahfaisal Main") exist only at display time.
 * Mirrors format_plaza_id() in mtag_backend/apps/tolls/plaza_registry.py —
 * keep the two in step.
 */
export function formatPlazaId(plazaId: number | null | undefined): string {
  if (plazaId === null || plazaId === undefined || Number.isNaN(plazaId)) return '';
  return String(plazaId).padStart(3, '0');
}
