import { Logo } from './Logo';
import { useStore } from '../lib/store';

export function Footer({ navigate }: { navigate: (hash: string) => void }) {
  const user = useStore((s) => s.user);
  const isSeller = user?.role === 'seller';
  const link = (h: string, label: string) => (
    <li><button onClick={() => navigate(h)} className="text-sm hover:text-accent transition-colors">{label}</button></li>
  );
  return (
    <footer className="border-t mt-12 relative z-10">
      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-10 py-14 grid sm:grid-cols-2 lg:grid-cols-5 gap-10">
        <div className="lg:col-span-2">
          <Logo />
          <p className="text-sm mt-4 leading-relaxed max-w-xs">
            A boutique gallery for production-ready software. Every piece live, framed, and ready to take home.
          </p>
          <div className="mt-6 hairline rounded-2xl bg-surface p-4 max-w-xs">
            <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">Newsletter</div>
            <div className="font-serif text-base mt-1">First Thursday, every month.</div>
            <form className="mt-3 flex gap-2" onSubmit={(e) => e.preventDefault()}>
              <input placeholder="you@studio.com" className="flex-1 hairline rounded-lg bg-bg px-3 h-9 text-sm outline-none focus:border-accent" />
              <button className="bg-text text-bg rounded-lg px-3 h-9 text-sm">Subscribe</button>
            </form>
          </div>
        </div>
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">Gallery</div>
          <ul className="mt-4 space-y-2">
            {link('/browse', 'Browse the collection')}
            {link('/browse', 'Top of the gallery')}
            {link('/browse', 'Best UI')}
            {link('/browse', 'Built this week')}
            {link('/concierge', 'Concierge')}
          </ul>
        </div>
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">{isSeller ? 'Makers' : 'Services'}</div>
          <ul className="mt-4 space-y-2">
            {isSeller && link('/sell', 'Sell a piece')}
            {isSeller && link('/pricing', 'Pricing & plans')}
            {isSeller && link('/dashboard', 'Studio dashboard')}
            {link('/services', 'Services')}
            {link('/whats-new', "What's New")}
          </ul>
        </div>
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">House</div>
          <ul className="mt-4 space-y-2">
            {link('/about', 'About Us')}
            {link('/press', 'Press')}
            {link('/contact', 'Contact')}
            {link('/admin-login', 'Curator sign-in')}
          </ul>
        </div>
      </div>
      <div className="border-t">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-10 py-5 flex flex-wrap items-center justify-between gap-3 text-xs text-text-muted font-mono uppercase tracking-wider">
          <div>© 2026 Vitrine · Curated in Dhaka, Bangladesh, Hosted In Google Cloud Platforms.</div>
          <div className="flex gap-5">
            <button onClick={() => navigate('/terms')} className="hover:text-text">Terms</button>
            <button onClick={() => navigate('/privacy')} className="hover:text-text">Privacy</button>
            <button onClick={() => navigate('/disclaimer')} className="hover:text-text">Disclaimer</button>
          </div>
        </div>
      </div>
    </footer>
  );
}
