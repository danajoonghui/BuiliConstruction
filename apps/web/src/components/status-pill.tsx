import { Circle } from 'lucide-react';

export function StatusPill({ children, tone = 'neutral' }: { children: React.ReactNode; tone?: 'green' | 'amber' | 'red' | 'blue' | 'neutral' }) {
  return <span className={`status-pill status-pill--${tone}`}><Circle size={6} fill="currentColor" aria-hidden />{children}</span>;
}

export function Discipline({ value }: { value: string }) {
  return <span className={`discipline discipline--${value.toLowerCase()}`}><i aria-hidden />{value}</span>;
}
