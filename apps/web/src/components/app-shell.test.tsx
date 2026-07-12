import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AppShell } from './app-shell';
import { useWorkspace } from './demo-mode';

const navigation = vi.hoisted(() => ({
  search: 'demo=1',
  router: { push: vi.fn(), replace: vi.fn(), refresh: vi.fn(), back: vi.fn() }
}));
const apiMocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), prime: vi.fn(), clear: vi.fn() }));

vi.mock('next/navigation', () => ({
  usePathname: () => '/app/issues/BUI-1042',
  useRouter: () => navigation.router,
  useSearchParams: () => new URLSearchParams(navigation.search)
}));
vi.mock('next/link', () => ({ default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => <a href={href} {...props}>{children}</a> }));
vi.mock('next/image', () => ({ default: ({priority: _priority, ...props}: React.ImgHTMLAttributes<HTMLImageElement> & {priority?:boolean}) => <img {...props} /> }));
vi.mock('@/lib/api', () => ({
  api: { get: apiMocks.get, post: apiMocks.post },
  primeCsrfToken: apiMocks.prime,
  clearCsrfToken: apiMocks.clear
}));

function WorkspaceProbe() {
  const workspace = useWorkspace();
  return <span>{workspace.demo ? `demo:${workspace.projectId}` : `live:${workspace.projectId}`}</span>;
}

describe('AppShell demo session', () => {
  beforeEach(() => {
    navigation.search = 'demo=1';
    apiMocks.get.mockReset();
    apiMocks.post.mockReset();
    sessionStorage.clear();
    localStorage.clear();
  });

  it('keeps an explicit demo route isolated from authenticated API loading after hydration', async () => {
    const view = render(<AppShell><WorkspaceProbe /></AppShell>);

    expect(await screen.findByText('demo:cooper')).toBeInTheDocument();
    expect(apiMocks.get).not.toHaveBeenCalled();

    navigation.search = '';
    view.rerender(<AppShell><WorkspaceProbe /></AppShell>);

    await waitFor(() => expect(screen.getByText('demo:cooper')).toBeInTheDocument());
    expect(apiMocks.get).not.toHaveBeenCalled();
    expect(navigation.router.replace).not.toHaveBeenCalled();
  });

  it('honors a project selected from the project directory', async () => {
    navigation.search = 'demo=1&project=vertex';
    render(<AppShell><WorkspaceProbe /></AppShell>);

    expect(await screen.findByText('demo:vertex')).toBeInTheDocument();
    expect(screen.getAllByText('Vertex Lab Fit-out').length).toBeGreaterThan(0);
  });
});
