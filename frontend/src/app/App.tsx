import { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { TopNav } from './components/TopNav';
import { Footer } from './components/Footer';
import { PreviewFrame } from './components/PreviewFrame';
import { ConciergePanel } from './components/ConciergePanel';
import { BargainModal, RequestFeaturesModal, CheckoutModal } from './components/Modals';
import { Home } from './pages/Home';
import { Browse } from './pages/Browse';
import { ProductPage } from './pages/ProductPage';
import { Sell } from './pages/Sell';
import { AuthPage } from './pages/Auth';
import { Pricing } from './pages/Pricing';
import { Legal } from './pages/Legal';
import { BuyerDashboard } from './pages/dashboards/BuyerDashboard';
import { SellerDashboard } from './pages/dashboards/SellerDashboard';
import { AdminDashboard } from './pages/dashboards/AdminDashboard';
import { useTheme } from './lib/theme';
import { useStore } from './lib/store';
import type { Product } from './lib/mockData';

type Route =
  | { name: 'home' }
  | { name: 'browse' }
  | { name: 'product'; slug: string }
  | { name: 'sell' }
  | { name: 'pricing' }
  | { name: 'dashboard' }
  | { name: 'login' }
  | { name: 'signup' }
  | { name: 'admin-login' }
  | { name: 'concierge' }
  | { name: 'legal'; kind: 'terms' | 'privacy' | 'disclaimer' | 'about' | 'press' | 'contact' };

function parseHash(): Route {
  const h = window.location.hash.replace(/^#\/?/, '');
  if (!h) return { name: 'home' };
  if (h === 'browse') return { name: 'browse' };
  if (h === 'sell') return { name: 'sell' };
  if (h === 'pricing') return { name: 'pricing' };
  if (h === 'dashboard') return { name: 'dashboard' };
  if (h === 'login') return { name: 'login' };
  if (h === 'signup') return { name: 'signup' };
  if (h === 'admin-login') return { name: 'admin-login' };
  if (h === 'concierge') return { name: 'concierge' };
  if (['terms', 'privacy', 'disclaimer', 'about', 'press', 'contact'].includes(h))
    return { name: 'legal', kind: h as any };
  if (h.startsWith('p/')) return { name: 'product', slug: h.slice(2) };
  return { name: 'home' };
}

export default function App() {
  useTheme();
  const { user, loadSession } = useStore();
  const [route, setRoute] = useState<Route>(() => parseHash());

  useEffect(() => {
    loadSession().catch(console.error);
  }, [loadSession]);
  const [previewing, setPreviewing] = useState<Product | null>(null);
  const [concierge, setConcierge] = useState(false);
  const [bargain, setBargain] = useState<Product | null>(null);
  const [features, setFeatures] = useState<Product | null>(null);
  const [checkout, setCheckout] = useState<{ p: Product; tier: number } | null>(null);

  useEffect(() => {
    const onHash = () => {
      setRoute(parseHash());
      window.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior });
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  useEffect(() => {
    if (route.name === 'concierge') setConcierge(true);
  }, [route.name]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { setPreviewing(null); setBargain(null); setFeatures(null); setCheckout(null); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const go = useCallback((h: string) => { window.location.hash = h.startsWith('/') ? h : `/${h}`; }, []);

  const navigate = (name: any) => {
    if (name === 'dashboard' && !user) return go('/login');
    go(`/${name === 'home' ? '' : name}`);
  };

  const openProduct = (slug: string) => go(`/p/${slug}`);

  const requireBuyer = (cb: () => void) => {
    if (!user) return go('/login');
    if (user.role !== 'buyer') return; // sellers/admins can't dispatch reps
    cb();
  };

  const renderDashboard = () => {
    if (!user) return null;
    if (user.role === 'buyer') return <BuyerDashboard />;
    if (user.role === 'seller') return <SellerDashboard goToPricing={() => go('/pricing')} goToSell={() => go('/sell')} />;
    return <AdminDashboard />;
  };

  return (
    <div className="relative min-h-screen text-text" style={{ background: 'var(--bg)' }}>
      <div className="relative z-10 flex flex-col min-h-screen">
        {route.name !== 'login' && route.name !== 'signup' && route.name !== 'admin-login' && (
          <TopNav
            route={route.name as any}
            navigate={navigate}
            onConcierge={() => setConcierge(true)}
          />
        )}

        <AnimatePresence mode="wait">
          <motion.div
            key={route.name + ('slug' in route ? route.slug : '') + ('kind' in route ? route.kind : '')}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
            className="flex-1"
          >
            {(route.name === 'home' || route.name === 'concierge') && (
              <Home
                onOpenProduct={openProduct}
                onPreview={setPreviewing}
                onConcierge={() => setConcierge(true)}
                onBrowse={() => navigate('browse')}
                onBargain={(p) => requireBuyer(() => setBargain(p))}
              />
            )}
            {route.name === 'browse' && (
              <Browse onOpenProduct={openProduct} onPreview={setPreviewing} onBargain={(p) => requireBuyer(() => setBargain(p))} />
            )}
            {route.name === 'product' && (
              <ProductPage
                slug={route.slug}
                onOpenProduct={openProduct}
                onPreview={setPreviewing}
                onBargain={(p) => requireBuyer(() => setBargain(p))}
                onRequestFeatures={(p) => { if (!user) return go('/login'); setFeatures(p); }}
                onCheckout={(p, tier) => { if (!user) return go('/login'); setCheckout({ p, tier }); }}
              />
            )}
            {route.name === 'sell' && <Sell onDone={() => navigate('home')} />}
            {route.name === 'pricing' && <Pricing onAuth={() => go('/login')} />}
            {route.name === 'dashboard' && renderDashboard()}
            {route.name === 'login' && <AuthPage mode="login" onDone={() => go('/dashboard')} onSwitch={(m) => go(`/${m === 'admin' ? 'admin-login' : m}`)} />}
            {route.name === 'signup' && <AuthPage mode="signup" onDone={() => go('/dashboard')} onSwitch={(m) => go(`/${m === 'admin' ? 'admin-login' : m}`)} />}
            {route.name === 'admin-login' && <AuthPage mode="admin" onDone={() => go('/dashboard')} onSwitch={(m) => go(`/${m}`)} />}
            {route.name === 'legal' && <Legal kind={route.kind} />}
          </motion.div>
        </AnimatePresence>

        {route.name !== 'login' && route.name !== 'signup' && route.name !== 'admin-login' && (
          <Footer navigate={go} />
        )}
      </div>

      <PreviewFrame
        open={!!previewing}
        url={previewing?.demoUrl ?? ''}
        productName={previewing?.name ?? ''}
        onClose={() => setPreviewing(null)}
      />
      <ConciergePanel
        open={concierge}
        onClose={() => setConcierge(false)}
        onOpenProduct={(slug) => { setConcierge(false); openProduct(slug); }}
      />
      <BargainModal
        open={!!bargain}
        onClose={() => setBargain(null)}
        product={bargain}
        onOpenInbox={() => go('/dashboard')}
      />
      <RequestFeaturesModal
        open={!!features}
        onClose={() => setFeatures(null)}
        product={features}
      />
      <CheckoutModal
        open={!!checkout}
        onClose={() => setCheckout(null)}
        product={checkout?.p ?? null}
        tierIndex={checkout?.tier ?? 0}
      />
    </div>
  );
}
