import { useState } from 'react';
import { ArrowRight, Mail, Lock, Shield, User as UserIcon, GraduationCap, ShoppingBag, Wrench } from 'lucide-react';
import { Logo } from '../components/Logo';
import { useStore, MOCK_USER_IDS, type Role } from '../lib/store';

type Mode = 'login' | 'signup' | 'admin';

/** Turn a raw `"<status> <body>"` API error into something a person can act on.
 *  api.ts throws the verbatim response body, which for a 422 is a pydantic
 *  blob — previously shown to the user in an alert(). */
function friendlyAuthError(raw: string | undefined, mode: Mode): string {
  const text = raw || '';
  if (/Failed to fetch|NetworkError/i.test(text)) return "Can't reach the server. Is the API running?";
  if (text.startsWith('409')) return 'That email is already registered. Try signing in instead.';
  if (text.startsWith('401')) {
    return mode === 'admin' ? 'Those are not valid curator credentials.' : 'Incorrect email or password.';
  }
  if (text.startsWith('403')) return 'This account is suspended. Contact the curators.';
  if (text.startsWith('429')) return 'Too many attempts. Wait a moment and try again.';
  if (text.startsWith('422')) {
    if (/valid email|email address/i.test(text)) return 'That email address is not valid.';
    if (/password/i.test(text)) return 'That password is not accepted.';
    return 'Please check the details you entered.';
  }
  if (text.startsWith('400')) {
    const m = text.match(/"detail"\s*:\s*"([^"]+)"/);
    if (m) return m[1];
  }
  return 'Something went wrong signing you in. Please try again.';
}

function Wrap({ children, eyebrow, title, blurb, variant = 'paper' }: { children: React.ReactNode; eyebrow: string; title: React.ReactNode; blurb: string; variant?: 'paper' | 'ink' }) {
  return (
    <main className="min-h-[calc(100vh-64px)] grid lg:grid-cols-2">
      <div className={`hidden lg:flex flex-col justify-between p-12 relative overflow-hidden ${variant === 'ink' ? 'bg-text text-bg' : 'bg-surface-2'}`}>
        <Logo />
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] opacity-70">{eyebrow}</div>
          <h1 className="font-serif mt-3 leading-[0.95]">{title}</h1>
          <p className="mt-6 max-w-md opacity-75 leading-relaxed">{blurb}</p>
        </div>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] opacity-60">
          Vitrine · A boutique gallery for production software
        </div>
        {variant === 'ink' && (
          <div className="absolute inset-0 pointer-events-none opacity-10"
            style={{ background: 'radial-gradient(ellipse at 30% 70%, var(--accent), transparent 50%)' }} />
        )}
      </div>
      <div className="flex items-center justify-center p-6 lg:p-12">
        <div className="w-full max-w-md">{children}</div>
      </div>
    </main>
  );
}

export function AuthPage({ mode, onDone, onSwitch }: { mode: Mode; onDone: () => void; onSwitch: (m: Mode) => void }) {
  const signIn = useStore((s) => s.signIn);
  const [role, setRole] = useState<Role>('buyer');
  const [isStudent, setIsStudent] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [pw, setPw] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const finalRole: Role = mode === 'admin' ? 'admin' : role;

    const { api, USE_MOCKS } = await import('../lib/api');
    if (USE_MOCKS) {
      signIn({
        id: MOCK_USER_IDS[finalRole],
        name: name || email.split('@')[0] || (finalRole === 'buyer' ? 'June Park' : finalRole === 'seller' ? 'Atelier Foxglove' : 'Vitrine Curator'),
        email: email || (finalRole === 'buyer' ? 'june@vitrine.io' : finalRole === 'seller' ? 'maker@vitrine.io' : 'admin@vitrine.io'),
        role: finalRole,
        isStudent: finalRole === 'seller' ? isStudent : false,
        plan: finalRole === 'seller' ? 'free' : undefined,
      });
      onDone();
      return;
    }

    // NEVER substitute demo credentials for blank input. This previously fell
    // back to the seeded accounts, so submitting the curator form with two empty
    // fields signed the visitor in as admin@vitrine.io.
    const emailVal = email.trim();
    const passwordVal = pw;
    if (!emailVal || !passwordVal) {
      setError('Enter your email and password.');
      return;
    }

    setError('');
    setBusy(true);
    try {
      let tokens;

      if (mode === 'login') {
        tokens = await api.login({ email: emailVal, password: passwordVal });
      } else if (mode === 'signup') {
        tokens = await api.signup({
          email: emailVal,
          password: passwordVal,
          display_name: name.trim() || emailVal.split('@')[0],
          role: finalRole,
        });
      } else if (mode === 'admin') {
        tokens = await api.adminLogin({ email: emailVal, password: passwordVal });
      }

      if (tokens && tokens.access_token) {
        api.setTokens(tokens.access_token, tokens.refresh_token);
        // A seller who ticked "I'm a student" only gets the discount if the
        // backend can verify an academic email. Previously the checkbox was
        // dropped entirely in real mode, so it silently did nothing.
        if (mode === 'signup' && finalRole === 'seller' && isStudent) {
          try {
            await api.verifyStudent();
          } catch {
            setNotice('Account created — student status needs an academic email (.edu, .ac.bd…), so the discount was not applied.');
          }
        }
        const me = await api.me();
        signIn(me);
        // Load operational data from backend
        const store = useStore.getState();
        if ((store as any).loadData) {
          await (store as any).loadData();
        }
        onDone();
      }
    } catch (err: any) {
      setError(friendlyAuthError(err?.message, mode));
    } finally {
      setBusy(false);
    }
  };

  if (mode === 'admin') {
    return (
      <Wrap variant="ink" eyebrow="Restricted access" title={<>The back<br />of house.</>} blurb="Approve listings, review chats, monitor transactions. Only the curators step through this door.">
        <div className="flex items-center gap-2 mb-6">
          <span className="w-9 h-9 rounded-full grid place-items-center bg-text text-bg"><Shield size={14} /></span>
          <div>
            <div className="font-serif text-xl">Curator sign-in</div>
            <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted">Restricted area</div>
          </div>
        </div>
        <form onSubmit={submit} className="space-y-3">
          <Field icon={Mail} label="Curator email" value={email} onChange={setEmail} placeholder="curator@vitrine.studio" required />
          <Field icon={Lock} label="Password" type="password" value={pw} onChange={setPw} placeholder="••••••••••" required />
          <ErrorNote message={error} />
          <button disabled={busy} className="w-full bg-text text-bg rounded-xl h-11 font-medium inline-flex items-center justify-center gap-2 mt-4 disabled:opacity-60">
            {busy ? 'Checking…' : <>Enter the back of house <ArrowRight size={14} /></>}
          </button>
        </form>
        <p className="text-xs mt-6 text-text-muted">
          Not a curator? <button onClick={() => onSwitch('login')} className="underline">Buyer or seller sign-in →</button>
        </p>
      </Wrap>
    );
  }

  return (
    <Wrap
      eyebrow={mode === 'login' ? 'Welcome back' : 'Open an account'}
      title={mode === 'login' ? <>Step back<br />into the gallery.</> : <>A boutique<br />needs a guest list.</>}
      blurb={mode === 'login'
        ? 'Your library, AI reps, and saved pieces are right where you left them.'
        : 'Choose your role — buyers browse and bargain, makers list and ship. You can switch later.'}
    >
      <div className="flex items-center gap-2 mb-6">
        <span className="w-9 h-9 rounded-full grid place-items-center bg-surface-2"><UserIcon size={14} /></span>
        <div>
          <div className="font-serif text-xl">{mode === 'login' ? 'Sign in' : 'Create your account'}</div>
          <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted">Vitrine · No spam, ever</div>
        </div>
      </div>

      {mode === 'signup' && (
        <div className="mb-5">
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted mb-2">I want to</div>
          <div className="grid grid-cols-2 gap-2">
            <button type="button" onClick={() => setRole('buyer')} className={`hairline rounded-xl p-4 text-left transition-colors ${role === 'buyer' ? 'border-accent bg-surface-2/50' : 'hover:border-accent/60'}`}>
              <ShoppingBag size={16} className="text-accent" />
              <div className="font-serif text-base mt-2">Browse & buy</div>
              <div className="text-xs text-text-muted mt-0.5">Up to 2 AI reps</div>
            </button>
            <button type="button" onClick={() => setRole('seller')} className={`hairline rounded-xl p-4 text-left transition-colors ${role === 'seller' ? 'border-accent bg-surface-2/50' : 'hover:border-accent/60'}`}>
              <Wrench size={16} className="text-accent" />
              <div className="font-serif text-base mt-2">List my software</div>
              <div className="text-xs text-text-muted mt-0.5">2 free posts · grow with plans</div>
            </button>
          </div>
        </div>
      )}

      <form onSubmit={submit} className="space-y-3">
        {mode === 'signup' && <Field icon={UserIcon} label="Full name" value={name} onChange={setName} placeholder="June Park" />}
        <Field icon={Mail} label="Email" value={email} onChange={setEmail} placeholder="you@studio.com" required />
        <Field icon={Lock} type="password" label="Password" value={pw} onChange={setPw} placeholder="••••••••" required />

        {mode === 'signup' && role === 'seller' && (
          <label className="flex items-center gap-2.5 hairline rounded-xl px-4 py-3 cursor-pointer hover:border-accent transition-colors">
            <input type="checkbox" checked={isStudent} onChange={(e) => setIsStudent(e.target.checked)} className="accent-[var(--accent)]" />
            <GraduationCap size={14} className="text-accent" />
            <div className="text-sm">I'm a student — apply <span className="text-accent">25% off</span> any plan</div>
          </label>
        )}

        <ErrorNote message={error} />
        {notice && <p className="text-xs text-text-muted hairline rounded-xl px-3 py-2">{notice}</p>}

        <button disabled={busy} className="w-full bg-text text-bg rounded-xl h-11 font-medium inline-flex items-center justify-center gap-2 mt-2 disabled:opacity-60">
          {busy ? 'Please wait…' : <>{mode === 'login' ? 'Sign in' : 'Create account'} <ArrowRight size={14} /></>}
        </button>
      </form>

      <p className="text-xs mt-6 text-text-muted">
        {mode === 'login' ? (
          <>New here? <button onClick={() => onSwitch('signup')} className="underline text-text">Open an account →</button></>
        ) : (
          <>Already a guest? <button onClick={() => onSwitch('login')} className="underline text-text">Sign in →</button></>
        )}
      </p>
    </Wrap>
  );
}

function ErrorNote({ message }: { message: string }) {
  if (!message) return null;
  // Uses --danger like every other error surface in the app. The hardcoded
  // red-500 here was a different hue and did not shift for dark mode.
  return (
    <p role="alert" className="text-sm rounded-xl px-3 py-2 border border-danger/40 bg-danger/10 text-danger">
      {message}
    </p>
  );
}

function Field({ icon: Icon, label, value, onChange, type = 'text', placeholder, required }: { icon: any; label: string; value: string; onChange: (v: string) => void; type?: string; placeholder?: string; required?: boolean }) {
  return (
    <label className="block">
      <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted mb-1.5">{label}</div>
      <div className="hairline rounded-xl flex items-center gap-2 px-3 bg-surface focus-within:border-accent transition-colors">
        <Icon size={14} className="text-text-muted" />
        <input
          value={value} onChange={(e) => onChange(e.target.value)} type={type} placeholder={placeholder}
          required={required}
          className="flex-1 bg-transparent outline-none h-11 text-sm"
        />
      </div>
    </label>
  );
}
