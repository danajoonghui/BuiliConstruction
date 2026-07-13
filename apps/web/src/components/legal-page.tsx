import Link from 'next/link';
import { Brand } from '@/components/brand';

export function LegalPage({ eyebrow, title, updated, children }: { eyebrow: string; title: string; updated: string; children: React.ReactNode }) {
  return <main className="legal-page">
    <header><Link href="/" aria-label="BUILI home"><Brand/></Link><nav><Link href="/">Product</Link><Link href="/login">Sign in</Link></nav></header>
    <article><p className="eyebrow"><span/>{eyebrow}</p><h1>{title}</h1><p className="legal-updated">Last updated {updated}</p>{children}</article>
    <footer><Brand/><span>Construction verification, grounded in evidence.</span><nav><Link href="/privacy">Privacy</Link><Link href="/terms">Terms</Link><a href="mailto:privacy@builiconstruction.com">Contact</a></nav></footer>
  </main>;
}
