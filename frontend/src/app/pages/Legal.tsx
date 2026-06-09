import { motion } from 'motion/react';

const CONTENT: Record<string, { eyebrow: string; title: string; updated: string; body: { h: string; p: string[] }[] }> = {
  terms: {
    eyebrow: 'Legal',
    title: 'Terms of service',
    updated: 'Updated June 6, 2026',
    body: [
      { h: '1 · The arrangement', p: [
        'Vitrine is a curated marketplace for software. By using it you agree to act in good faith, honor the licenses you receive, and not attempt to break the boutique we are running.',
        'These terms are designed to be readable, not weaponized. If a clause feels unclear, contact a curator — we will explain it.',
      ] },
      { h: '2 · Buyer rights', p: [
        'Every piece on Vitrine ships with a live, runnable preview. You may inspect any product for as long as you want before purchasing.',
        'After purchase, the license attached to the product governs your use. Vitrine escrows your payment until the seller delivers; if delivery does not happen within 7 days, you may request a full refund.',
      ] },
      { h: '3 · Seller obligations', p: [
        'Sellers warrant they own or have rights to the code they list, the live preview is theirs, and the spec sheet is honest.',
        'Misrepresentation, plagiarism, or stale demos are grounds for removal at curator discretion. Repeat offenses end the account.',
      ] },
      { h: '4 · AI representatives', p: [
        'Buyers may dispatch AI buying reps to negotiate on their behalf. A buyer may have up to two active reps at a time. Reps operate within the budget the buyer authorizes; the buyer is the principal.',
        'Sellers may converse with reps as they would with any buyer. We log every word for transparency.',
      ] },
      { h: '5 · Fees', p: [
        'Vitrine charges commission on each sale per the seller’s current plan. Free-tier sellers pay 12%; subscribed sellers pay 3–8%; enterprise listings ($10,000+) pay 2% flat. Students get 25% off any subscription.',
      ] },
    ],
  },
  privacy: {
    eyebrow: 'Legal',
    title: 'Privacy policy',
    updated: 'Updated June 6, 2026',
    body: [
      { h: '1 · What we collect', p: [
        'Account basics (name, email, role), what you list or buy, and the messages you send through Vitrine. We collect payment information through our processor — we never see your full card number.',
        'We do not buy data from third parties and we do not enrich your profile with web tracking.',
      ] },
      { h: '2 · How we use it', p: [
        'To run the marketplace, deliver your purchases, prevent fraud, and improve curation.',
        'We will never sell your information. We will share it only with the seller of a piece you bought, the buyer of a piece you sold, and law enforcement when legally compelled.',
      ] },
      { h: '3 · Your controls', p: [
        'Export everything we have on you at any time. Delete your account at any time. Disable AI features at any time.',
        'Email privacy@vitrine.studio for any privacy request — we respond within 5 business days.',
      ] },
    ],
  },
  disclaimer: {
    eyebrow: 'Legal',
    title: 'Disclaimer',
    updated: 'Updated June 6, 2026',
    body: [
      { h: 'Pieces are sold as-is', p: [
        'Every product on Vitrine is sold as-is, by the maker, under the license attached to the listing. Vitrine curates and verifies what we can — we do not author or maintain the software.',
        'Live previews are best-effort. We monitor demo health, but a demo being temporarily unavailable is not a defect of the underlying product.',
      ] },
      { h: 'AI recommendations are guidance, not contracts', p: [
        'The Concierge, the Pricing & Pitch Agent, and the Buyer Rep all produce suggestions. Final decisions rest with the human party — buyer or seller.',
      ] },
      { h: 'Enterprise listings', p: [
        'Listings priced at or above $10,000 typically include rollout services. Scope is defined in the listing’s spec sheet and the parties’ subsequent agreement. Vitrine escrows funds; it does not arbitrate scope disputes.',
      ] },
    ],
  },
  about: {
    eyebrow: 'House',
    title: 'About Vitrine',
    updated: 'Issue 06 · 2026',
    body: [
      { h: 'Why we exist', p: [
        'Software is sold in a hurry. Six cards in a grid, three feature bullets, a "Buy now" button that lands you in install instructions. We thought it deserved better — a vitrine, in the original sense: a glass case where you can see the object, turn it over, hold it under the light.',
        'So every piece on Vitrine ships with a live, runnable preview. Try it like a print, then take it home like a book.',
      ] },
      { h: 'How we curate', p: [
        'Two curators read every submission. We score on completeness, UI craft, demo health, reviews, recency, and engagement. The number you see — the Vitrine Score — is the aggregate, but our judgment is what frames the wall.',
      ] },
      { h: 'Where to find us', p: [
        'We work out of two small studios in Lisbon and Brooklyn. We answer email. We send a quiet newsletter on the first Thursday of every month.',
      ] },
    ],
  },
  press: {
    eyebrow: 'House',
    title: 'Press',
    updated: 'Issue 06 · 2026',
    body: [
      { h: 'Selected coverage', p: [
        '— "A boutique that happens to sell software." · Foundry Weekly',
        '— "The most considered software marketplace I have used in a decade." · The Atelier Letter',
        '— "Vitrine treats apps like the objects they are." · Type & Bits',
      ] },
      { h: 'Press kit', p: [
        'For brand assets, founder bios, or interview requests, email press@vitrine.studio. We respond within 48 hours.',
      ] },
    ],
  },
  contact: {
    eyebrow: 'House',
    title: 'Contact',
    updated: 'Always open',
    body: [
      { h: 'The front door', p: [
        'hello@vitrine.studio — for anything that doesn\'t fit a category. A human reads this within a day.',
      ] },
      { h: 'Specialized lines', p: [
        'curators@vitrine.studio — listing approvals and disputes.',
        'press@vitrine.studio — interviews, coverage, and brand assets.',
        'privacy@vitrine.studio — privacy and data requests.',
      ] },
    ],
  },
};

export function Legal({ kind }: { kind: keyof typeof CONTENT }) {
  const c = CONTENT[kind];
  return (
    <main className="max-w-[820px] mx-auto px-6 lg:px-10 pt-16 pb-24">
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-text-muted">{c.eyebrow}</div>
        <h1 className="font-serif mt-4">{c.title}</h1>
        <div className="font-mono text-[10px] uppercase tracking-wider text-text-muted mt-3">{c.updated}</div>
      </motion.div>

      <article className="mt-12 space-y-10">
        {c.body.map((s) => (
          <section key={s.h}>
            <h2 className="font-serif text-2xl">{s.h}</h2>
            <div className="mt-3 space-y-3">
              {s.p.map((p, i) => <p key={i} className="leading-relaxed">{p}</p>)}
            </div>
          </section>
        ))}
      </article>

      <hr className="editorial-rule my-16" />

      <p className="font-mono text-[10px] uppercase tracking-wider text-text-muted">© 2026 Vitrine Studio · Issued from Lisbon & Brooklyn</p>
    </main>
  );
}
