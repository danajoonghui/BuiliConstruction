import { authApi } from './api';

declare global {
  interface Window {
    google?: { accounts: { id: { initialize(options: {client_id:string;callback:(response:{credential:string})=>void;auto_select?:boolean}):void; prompt(callback?:(notification:{isNotDisplayed:()=>boolean;getNotDisplayedReason:()=>string})=>void):void } } };
  }
}

let loading: Promise<void> | undefined;
function loadGoogleIdentity() {
  if (window.google?.accounts.id) return Promise.resolve();
  if (loading) return loading;
  loading = new Promise((resolve,reject) => {
    const existing = document.querySelector<HTMLScriptElement>('script[data-buili-google]');
    if (existing) { existing.addEventListener('load',()=>resolve(),{once:true}); existing.addEventListener('error',()=>reject(new Error('Google Identity failed to load')),{once:true}); return; }
    const script=document.createElement('script'); script.src='https://accounts.google.com/gsi/client'; script.async=true; script.defer=true; script.dataset.builiGoogle='true'; script.onload=()=>resolve(); script.onerror=()=>reject(new Error('Google Identity failed to load')); document.head.appendChild(script);
  }); return loading;
}

export async function signInWithGoogle(organizationName?:string) {
  const configured = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
  const capabilities = configured ? null : await authApi.capabilities();
  const clientId = configured || capabilities?.google_client_id;
  if (!clientId) throw new Error('Google sign-in is not configured for this environment.');
  await loadGoogleIdentity();
  return new Promise<void>((resolve,reject) => {
    window.google!.accounts.id.initialize({ client_id:clientId, auto_select:false, callback:async ({credential}) => { try { await authApi.exchangeGoogle(credential,organizationName); resolve(); } catch(error){ reject(error); } } });
    window.google!.accounts.id.prompt(notification => { if(notification.isNotDisplayed()) reject(new Error(`Google sign-in unavailable: ${notification.getNotDisplayedReason()}`)); });
  });
}
