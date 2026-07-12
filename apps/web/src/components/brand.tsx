import Image from 'next/image';
import Link from 'next/link';

export function Brand({ compact = false, href = '/' }: { compact?: boolean; href?: string }) {
  return (
    <Link href={href} className={`brand ${compact ? 'brand--compact' : ''}`} aria-label="BUILI home">
      <Image src="/favicon.png" alt="" width={34} height={34} priority />
      {!compact && <span>BUILI</span>}
    </Link>
  );
}
