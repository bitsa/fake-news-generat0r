// Top-level app — LOCKED variant.
// Decisions: layout=split, fakeLevel=medium, branding=dot. No tweaks panel.

const App = () => {
  const FAKE_LEVEL = 'medium';
  const BRANDING = 'dot';
  const LAYOUT = 'split';

  // Routing
  const [route, setRoute] = React.useState({ name: 'feed' });
  const [phase, setPhase] = React.useState('ready'); // empty | loading | ready
  const [articles, setArticles] = React.useState(ARTICLES);
  const [refreshing, setRefreshing] = React.useState(false);
  const [lastScrape, setLastScrape] = React.useState(Date.now() - 5 * 60 * 1000);
  const [error, setError] = React.useState(null);
  const [adminOpen, setAdminOpen] = React.useState(false);
  const [fakeMode, setFakeMode] = React.useState(true);
  const [scrapeState, setScrapeState] = React.useState({ busy: false, sources: {}, log: [] });

  const [chatStore, setChatStore] = React.useState(() => {
    const s = {};
    Object.entries(CHAT_SEEDS).forEach(([idx, seeds]) => {
      const a = ARTICLES[+idx];
      if (!a) return;
      s[a.id] = seeds.map((m, i) => ({
        id: 'm_' + a.id + '_' + i,
        ...m,
        t: Date.now() + (m.t || 0) * 60000,
      }));
    });
    return s;
  });

  const setHistoryFor = (articleId) => (updater) => {
    setChatStore(prev => ({
      ...prev,
      [articleId]: typeof updater === 'function' ? updater(prev[articleId] || []) : updater,
    }));
  };

  const log = (level, msg) => setScrapeState(s => ({
    ...s,
    log: [...(s.log || []), { t: new Date().toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }), level, msg }].slice(-30),
  }));

  const runScrape = () => {
    if (refreshing) return;
    setError(null);
    setRefreshing(true);
    setScrapeState(s => ({ ...s, busy: true, sources: SOURCES.reduce((acc, sx) => ({ ...acc, [sx.id]: { phase: 'scraping', scraped: 0, transformed: 0 } }), {}) }));
    log('info', 'POST /api/scrape — starting');

    SOURCES.forEach((s, i) => {
      setTimeout(() => log('info', 'Fetching ' + s.feed), 200 + i * 250);
      setTimeout(() => {
        setScrapeState(st => ({ ...st, sources: { ...st.sources, [s.id]: { phase: 'scraped', scraped: 6, transformed: 0 } } }));
        log('ok', s.short + ' · 6 articles scraped');
      }, 800 + i * 350);
      setTimeout(() => {
        setScrapeState(st => ({ ...st, sources: { ...st.sources, [s.id]: { phase: 'transforming', scraped: 6, transformed: 0 } } }));
        log('info', s.short + ' · queued for transform');
      }, 1100 + i * 350);
      [1, 2, 3, 4, 5, 6].forEach((n, k) => {
        setTimeout(() => {
          setScrapeState(st => ({
            ...st,
            sources: { ...st.sources, [s.id]: { ...(st.sources[s.id] || {}), phase: n === 6 ? 'done' : 'transforming', scraped: 6, transformed: n } },
          }));
        }, 1400 + i * 350 + k * 220);
      });
      setTimeout(() => log('ok', s.short + ' · transform complete'), 1400 + i * 350 + 6 * 220);
    });

    setTimeout(() => {
      setArticles(ARTICLES);
      setPhase('ready');
      setLastScrape(Date.now());
      setRefreshing(false);
      setScrapeState(s => ({ ...s, busy: false }));
      log('ok', 'Pipeline complete · 18 articles in feed');
    }, 1400 + (SOURCES.length - 1) * 350 + 6 * 220 + 600);
  };

  const dismissError = () => setError(null);
  const openArticle = (a) => { setRoute({ name: 'article', id: a.id }); window.scrollTo(0, 0); };
  const backToFeed = () => { setRoute({ name: 'feed' }); window.scrollTo(0, 0); };
  const currentArticle = route.name === 'article' ? articles.find(a => a.id === route.id) : null;

  const chatNode = currentArticle ? (
    <ChatPanel
      article={currentArticle}
      history={chatStore[currentArticle.id] || []}
      setHistory={setHistoryFor(currentArticle.id)}
    />
  ) : null;

  return (
    <>
      {route.name === 'feed' && (
        <Feed
          articles={articles}
          phase={phase}
          error={error}
          dismissError={dismissError}
          onOpen={openArticle}
          onRefresh={runScrape}
          refreshing={refreshing}
          lastScrape={lastScrape}
          onOpenAdmin={() => setAdminOpen(true)}
          fakeMode={fakeMode}
          setFakeMode={setFakeMode}
          fakeLevel={FAKE_LEVEL}
          branding={BRANDING}
        />
      )}
      {route.name === 'article' && currentArticle && (
        <ArticleDetail
          article={currentArticle}
          onBack={backToFeed}
          fakeLevel={FAKE_LEVEL}
          layout={LAYOUT}
          chatNode={chatNode}
        />
      )}

      <AdminModal
        open={adminOpen}
        onClose={() => setAdminOpen(false)}
        onRunScrape={runScrape}
        onRunTransform={() => { log('info', 'POST /api/transform — re-running on existing rows'); }}
        scrapeState={scrapeState}
      />
    </>
  );
};

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
