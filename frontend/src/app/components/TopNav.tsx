import { useEffect, useState } from 'react';
import { Search, Sparkles, User as UserIcon, LogOut, LayoutDashboard, Tag, Menu, X, Store } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { Logo } from './Logo';
import { ThemeToggle } from './ThemeToggle';
import { Typewriter } from './Typewriter';
import { useStore } from '../lib/store';

type Route = 'home' | 'browse' | 'product' | 'concierge' | 'sell' | 'dashboard' | 'pricing' | 'login' | 'whats-new' | 'services' | 'about' | 'profile';

export function TopNav({ route, navigate, onConcierge }: { route: Route; navigate: (r: Route) => void; onConcierge: () => void }) {
  const { user, signOut } = useStore();
  const [menuOpen, setMenuOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const isSeller = user?.role === 'seller';

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => { setMobileOpen(false); }, [route]);

  const goAndClose = (r: Route) => { setMobileOpen(false); navigate(r); };

  const link = (id: Route, label: string) => (
    <button
      onClick={() => navigate(id)}
      className={`relative text-sm transition-colors ${route === id ? 'text-text' : 'text-text-muted hover:text-text'}`}
    >
      {label}
      {route === id && <span className="absolute -bottom-1.5 left-0 right-0 h-px bg-accent" />}
    </button>
  );

  return (
    <header
      className={`sticky top-0 z-40 transition-all duration-300 ${
        scrolled || mobileOpen ? 'bg-bg/90 backdrop-blur-md border-b' : 'bg-transparent border-b border-transparent'
      }`}
      style={{ borderColor: scrolled || mobileOpen ? 'var(--border-c)' : 'transparent' }}
    >
      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-10 h-16 flex items-center justify-between gap-3 sm:gap-6">
        <div className="flex items-center gap-6 lg:gap-10 min-w-0">
          <button onClick={() => navigate('home')} className="shrink-0"><Logo /></button>
          <nav className="hidden md:flex items-center gap-7">
            {link('browse', 'Gallery')}
            {link('whats-new', "What's New")}
            {link('services', 'Services')}
            {link('about', 'About Us')}
            {isSeller && link('sell', 'Sell')}
            {user && link('dashboard', 'Dashboard')}
          </nav>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onConcierge}
            className="hidden lg:flex items-center gap-2 text-xs text-text-soft hairline rounded-full px-3 h-9 hover:border-accent hover:text-text active:border-accent transition-colors min-w-[220px]"
          >
            <Search size={13} className="shrink-0" />
            <Typewriter
              words={[
                'Describe what you need…',
                'A telehealth admin dashboard…',
                'Fintech analytics with charts…',
                'Headless storefront with Stripe…',
              ]}
              className="text-xs"
            />
          </button>
          <button
            onClick={onConcierge}
            aria-label="Concierge"
            className="hidden sm:flex items-center gap-1.5 h-9 px-3 rounded-full text-xs hairline hover:border-accent hover:text-accent active:border-accent transition-colors"
          >
            <Sparkles size={13} className="text-accent" /> <span className="hidden lg:inline">Concierge</span>
          </button>
          <button
            onClick={onConcierge}
            aria-label="Search"
            className="sm:hidden hairline rounded-full w-9 h-9 grid place-items-center"
          >
            <Search size={14} />
          </button>
          <ThemeToggle />

          {user ? (
            <div className="relative hidden sm:block">
              <button
                onClick={() => setMenuOpen((s) => !s)}
                className="hairline rounded-full h-9 pr-3 pl-1 flex items-center gap-2 hover:border-accent active:border-accent transition-colors"
              >
                <span className="w-7 h-7 rounded-full grid place-items-center gold-gradient text-[var(--accent-ink)] text-xs font-serif">{user.name[0]}</span>
                <span className="text-xs hidden md:inline">{user.name.split(' ')[0]}</span>
              </button>
              {menuOpen && (
                <div onMouseLeave={() => setMenuOpen(false)} className="absolute right-0 top-11 w-56 bg-surface hairline rounded-xl overflow-hidden shadow-2xl">
                  <div className="px-4 py-3 border-b">
                    <div className="font-serif text-sm">{user.name}</div>
                    <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted mt-0.5">{user.role}</div>
                  </div>
                  <button onClick={() => { setMenuOpen(false); navigate('dashboard'); }} className="w-full text-left px-4 py-2.5 text-sm hover:bg-surface-2 flex items-center gap-2"><LayoutDashboard size={13} /> Dashboard</button>
                  <button onClick={() => { setMenuOpen(false); navigate('profile'); }} className="w-full text-left px-4 py-2.5 text-sm hover:bg-surface-2 flex items-center gap-2"><UserIcon size={13} /> Profile & Settings</button>
                  {isSeller && <button onClick={() => { setMenuOpen(false); navigate('sell'); }} className="w-full text-left px-4 py-2.5 text-sm hover:bg-surface-2 flex items-center gap-2"><Store size={13} /> Sell</button>}
                  <button onClick={() => { setMenuOpen(false); navigate('pricing'); }} className="w-full text-left px-4 py-2.5 text-sm hover:bg-surface-2 flex items-center gap-2"><Tag size={13} /> Pricing</button>
                  <button onClick={() => { setMenuOpen(false); signOut(); navigate('home'); }} className="w-full text-left px-4 py-2.5 text-sm hover:bg-surface-2 flex items-center gap-2 border-t text-danger"><LogOut size={13} /> Sign out</button>
                </div>
              )}
            </div>
          ) : (
            <button onClick={() => navigate('login')} className="hidden sm:flex hairline rounded-full h-9 px-4 text-xs hover:border-accent transition-colors items-center gap-1.5">
              <UserIcon size={12} /> Sign in
            </button>
          )}

          {/* Mobile menu toggle */}
          <button
            onClick={() => setMobileOpen((s) => !s)}
            aria-label="Menu"
            className="md:hidden hairline rounded-full w-9 h-9 grid place-items-center"
          >
            {mobileOpen ? <X size={14} /> : <Menu size={14} />}
          </button>
        </div>
      </div>

      {/* Mobile drawer */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className="md:hidden overflow-hidden border-t bg-bg/95 backdrop-blur"
          >
            <nav className="px-4 py-4 flex flex-col">
              {user && (
                <div className="hairline rounded-xl p-3 flex items-center gap-3 mb-3">
                  <span className="w-9 h-9 rounded-full grid place-items-center gold-gradient text-[var(--accent-ink)] text-sm font-serif">{user.name[0]}</span>
                  <div className="min-w-0">
                    <div className="font-serif text-sm truncate">{user.name}</div>
                    <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted">{user.role}</div>
                  </div>
                </div>
              )}
              <MobileLink onClick={() => goAndClose('browse')} active={route === 'browse'} label="Gallery" />
              <MobileLink onClick={() => goAndClose('whats-new')} active={route === 'whats-new'} label="What's New" />
              <MobileLink onClick={() => goAndClose('services')} active={route === 'services'} label="Services" />
              <MobileLink onClick={() => goAndClose('about')} active={route === 'about'} label="About Us" />
              {isSeller && <MobileLink onClick={() => goAndClose('sell')} active={route === 'sell'} label="Sell" />}
              {user && <MobileLink onClick={() => goAndClose('dashboard')} active={route === 'dashboard'} label="Dashboard" icon={<LayoutDashboard size={14} />} />}
              <div className="border-t my-2" />
              {user ? (
                <button onClick={() => { setMobileOpen(false); signOut(); navigate('home'); }} className="text-left px-3 py-3 text-sm rounded-lg text-danger flex items-center gap-2"><LogOut size={14} /> Sign out</button>
              ) : (
                <button onClick={() => goAndClose('login')} className="bg-text text-bg rounded-xl h-11 mt-1 text-sm font-medium inline-flex items-center justify-center gap-2"><UserIcon size={13} /> Sign in</button>
              )}
            </nav>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}

function MobileLink({ onClick, active, label, icon }: { onClick: () => void; active: boolean; label: string; icon?: React.ReactNode }) {
  return (
    <button onClick={onClick} className={`text-left px-3 py-3 text-sm rounded-lg flex items-center justify-between ${active ? 'bg-surface-2 text-text' : 'text-text-soft'}`}>
      <span className="flex items-center gap-2">{icon}{label}</span>
      {active && <span className="w-1.5 h-1.5 rounded-full bg-accent" />}
    </button>
  );
}
