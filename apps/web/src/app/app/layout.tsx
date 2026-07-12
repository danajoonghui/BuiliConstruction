import type { Metadata } from 'next';
import { AppShell } from '@/components/app-shell';

export const metadata: Metadata = { title: 'Workspace' };
export default function ProductLayout({ children }: { children: React.ReactNode }) { return <AppShell>{children}</AppShell>; }
