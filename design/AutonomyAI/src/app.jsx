// Top-level app: state machine, routing between feed/article, tweaks integration.

const DEFAULTS = /*EDITMODE-BEGIN*/{
  "layout": "split",
  "fakeLevel": "medium",
  "branding": "dot",
  "fakeMode": true,
  "startInEmpty": false
}/*EDITMODE-END*/;

const App = () => {
  const [tweaks, setTweak] = useTweaks(DEFAULTS);

  // Routing
  const [route, setRoute] = React.useState({ name: 'feed' }); // feed | article
  // Phase: empty | loading | ready
  const [phase, setPhase] = React.useState(tweaks.startInEmpty ? 'empty' : 'ready');
  const [articles, setArticles] = React.useState(tweaks.startInEmpty ? [] : ARTICLES);
  const [refreshing, setRefreshing] = React.useState(false);
  const [lastScrape, setLastScrape] = React.useState(Date.now() - 5 * 60 * 1000);
  const [error, setError] = React.useState(null);
  const [adminOpen, setAdminOpen] = React.useState(false);
  const [scrapeState, setScrapeState] = React.useState({ busy: false, sources: {}, log: [] });

  // chat history per article id
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
      setTimeout(() => {
        log('info', 'Fetching ' + s.feed);
      }, 200 + i * 250);
      setTimeout(() => {
        setScrapeState(st => ({ ...st, sources: { ...st.sources, [s.id]: { phase: 'scraped', scraped: 6, transformed: 0 } } }));
        log('ok', s.short + ' · 6 articles scraped');
      }, 800 + i * 350);
      setTimeout(() => {
        setScrapeState(st => ({ ...st, sources: { ...st.sources, [s.id]: { phase: 'transforming', scraped: 6, transformed: 0 } } }));
        log('info', s.short + ' · queued for transform');
      }, 1100 + i * 350);
      // gradual transformed counter
      [1, 2, 3, 4, 5, 6].forEach((n, k) => {
        setTimeout(() => {
          setScrapeState(st => ({
            ...st,
            sources: { ...st.sources, [s.id]: { ...(st.sources[s.id] || {}), phase: n === 6 ? 'done' : 'transforming', scraped: 6, transformed: n } },
          }));
        }, 1400 + i * 350 + k * 220);
      });
      setTimeout(() => {
        log('ok', s.short + ' · transform complete');
      }, 1400 + i * 350 + 6 * 220);
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

  // Build the chat node (used by all 3 layouts)
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
          fakeMode={tweaks.fakeMode}
          setFakeMode={(v) => setTweak('fakeMode', v)}
          fakeLevel={tweaks.fakeLevel}
          branding={tweaks.branding}
        />
      )}
      {route.name === 'article' && currentArticle && (
        <ArticleDetail
          article={currentArticle}
          onBack={backToFeed}
          fakeLevel={tweaks.fakeLevel}
          layout={tweaks.layout}
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

      <TweaksPanel title="Tweaks">
        <TweakSection title="Layout">
          <TweakSelect label="Article + chat layout" value={tweaks.layout}
            onChange={(v) => setTweak('layout', v)}
            options={[
              { value: 'split', label: 'Split — chat docked right' },
              { value: 'drawer', label: 'Drawer — chat slides in' },
              { value: 'stacked', label: 'Stacked — chat below article' },
            ]} />
        </TweakSection>
        <TweakSection title="Fake/satire treatment">
          <TweakRadio label="Loudness" value={tweaks.fakeLevel}
            onChange={(v) => setTweak('fakeLevel', v)}
            options={[
              { value: 'subtle', label: 'Subtle' },
              { value: 'medium', label: 'Medium' },
              { value: 'loud', label: 'Loud' },
            ]} />
          <TweakToggle label="Show satirical version by default" value={tweaks.fakeMode} onChange={(v) => setTweak('fakeMode', v)} />
        </TweakSection>
        <TweakSection title="Source branding">
          <TweakRadio label="In feed cards" value={tweaks.branding}
            onChange={(v) => setTweak('branding', v)}
            options={[
              { value: 'dot', label: 'Dot + name' },
              { value: 'monogram', label: 'Monogram' },
              { value: 'text', label: 'Text only' },
            ]} />
        </TweakSection>
        <TweakSection title="Demo states">
          <TweakButton onClick={() => { setArticles([]); setPhase('empty'); }}>Show empty state</TweakButton>
          <TweakButton onClick={() => { setPhase('loading'); setTimeout(() => { setArticles(ARTICLES); setPhase('ready'); }, 1500); }}>Show loading skeleton</TweakButton>
          <TweakButton onClick={() => setError({ title: 'Scrape failed for The Guardian', detail: 'Connection timed out after 10s. The feed may be temporarily unavailable.' })}>Trigger error banner</TweakButton>
          <TweakButton onClick={() => { setArticles(ARTICLES); setPhase('ready'); setError(null); }}>Reset to ready</TweakButton>
        </TweakSection>
      </TweaksPanel>
    </>
  );
};

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
