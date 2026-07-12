'use client';
import Link from 'next/link';
import { FormEvent, useState } from 'react';
import { ArrowLeft, CheckCircle2, LoaderCircle } from 'lucide-react';
import { AuthShell } from '@/components/auth/auth-shell';
import { authApi } from '@/lib/api';

export default function ForgotPasswordPage() {
  const[loading,setLoading]=useState(false);const[sent,setSent]=useState(false);const[error,setError]=useState('');
  async function submit(event:FormEvent<HTMLFormElement>){event.preventDefault();setLoading(true);setError('');try{const data=new FormData(event.currentTarget);await authApi.forgotPassword(String(data.get('email')));setSent(true)}catch(cause){setError(cause instanceof Error?cause.message:'The reset request could not be sent.')}finally{setLoading(false)}}
  return <AuthShell title="Reset your password" description="We will send a secure reset link to your work email.">{sent?<div className="password-sent"><CheckCircle2/><b>Check your inbox</b><p>If an account exists for that address, a reset link is on its way.</p></div>:<form className="auth-form" method="post" action="/forgot-password" onSubmit={submit}><label>Email address<input name="email" type="email" autoComplete="email" placeholder="you@company.com" required/></label>{error&&<p className="form-error">{error}</p>}<button className="button button--primary button--large button--full" disabled={loading}>{loading?<><LoaderCircle className="spin"/> Sending...</>:'Send reset link'}</button></form>}<p className="auth-switch"><Link href="/login"><ArrowLeft size={14}/> Return to sign in</Link></p></AuthShell>;
}
