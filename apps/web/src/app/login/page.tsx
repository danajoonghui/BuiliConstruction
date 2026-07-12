import type { Metadata } from 'next';
import { AuthShell } from '@/components/auth/auth-shell';
import { LoginForm } from '@/components/auth/login-form';

export const metadata: Metadata = { title: 'Sign in' };
export default function LoginPage() { return <AuthShell title="Welcome back" description="Sign in to continue to your project workspace."><LoginForm/></AuthShell>; }
