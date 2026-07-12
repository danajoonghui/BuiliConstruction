import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { Brand } from '@/components/brand';

export default function NotFound(){return <main className="error-page"><Brand/><span>404</span><h1>This view is not in the current set.</h1><p>The page may have moved or your project role may not have access.</p><Link className="button button--primary" href="/"><ArrowLeft/> Return to BUILI</Link></main>}
