// News feed view: header, filter rail, article cards, states (empty/loading/error).

const FeedHeader = ({ onRefresh, refreshing, lastScrape, onOpenAdmin, fakeMode, onCycleFakeMode, fakeLevel }) => (
  <header style={{
    position: 'sticky', top: 0, zIndex: 20,
    background: 'rgba(14,14,14,0.85)', backdropFilter: 'blur(12px)',
    borderBottom: '1px solid var(--line)',
  }}>
    <div style={{ maxWidth: 1240, margin: '0 auto', padding: '14px 28px', display: 'flex', alignItems: 'center', gap: 24 }}>
      <Logo size={22} />
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, color: 'var(--text-3)', fontFamily: 'var(--mono)', fontSize: 11, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
        <span style={{ width: 18, height: 1, background: 'var(--line-2)' }} />
        <span>Satirical news, generated</span>
      </div>
      <div style={{ flex: 1 }} />
      <button onClick={onCycleFakeMode} title="Toggle global fake/original" style={{
        display: 'inline-flex', alignItems: 'center', gap: 8,
        background: 'transparent', border: '1px solid var(--line)', color: 'var(--text-2)',
        borderRadius: 999, padding: '6px 12px', fontSize: 12, cursor: 'pointer', fontFamily: 'var(--sans)',
      }}>
        <span style={{
          width: 28, height: 16, borderRadius: 999, position: 'relative',
          background: fakeMode ? 'var(--accent)' : 'var(--bg-4)',
          border: '1px solid ' + (fakeMode ? 'var(--accent)' : 'var(--line-2)'),
          transition: 'all .2s',
        }}>
          <span style={{
            position: 'absolute', top: 1, left: fakeMode ? 13 : 1,
            width: 12, height: 12, borderRadius: 999, background: '#fff',
            transition: 'left .2s',
          }} />
        </span>
        <span>{fakeMode ? 'Showing satirical' : 'Showing originals'}</span>
      </button>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-3)' }}>
        last scrape <span style={{ color: 'var(--text-2)' }}>{relTime(lastScrape)}</span>
      </div>
      <Btn kind="secondary" size="sm" icon={<I.Settings size={14} />} onClick={onOpenAdmin}>Admin</Btn>
      <Btn kind="primary" size="sm" icon={refreshing ? <I.Loader size={14} className="pulse" /> : <I.Refresh size={14} />} onClick={onRefresh} disabled={refreshing}>
        {refreshing ? 'Scraping…' : 'Refresh feed'}
      </Btn>
    </div>
  </header>
);

const FilterRail = ({ counts, sourceFilter, setSourceFilter, sort, setSort, branding }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', padding: '20px 0' }}>
    <Tag>filter</Tag>
    <Chip active={sourceFilter === 'all'} onClick={() => setSourceFilter('all')} count={counts.all}>All sources</Chip>
    {SOURCES.map(s => (
      <Chip key={s.id} active={sourceFilter === s.id} onClick={() => setSourceFilter(s.id)}
            count={counts[s.id]} color={s.color}>
        {branding === 'monogram' ? s.short + ' — ' + s.name : s.name}
      </Chip>
    ))}
    <div style={{ flex: 1 }} />
    <Tag>sort</Tag>
    {[['recent', 'Most recent'], ['source', 'By source'], ['topic', 'By topic']].map(([k, label]) => (
      <button key={k} onClick={() => setSort(k)} style={{
        background: 'transparent', border: 'none', cursor: 'pointer',
        color: sort === k ? 'var(--text)' : 'var(--text-3)',
        fontFamily: 'var(--sans)', fontSize: 12, padding: '4px 8px',
        borderBottom: '1px solid ' + (sort === k ? 'var(--accent)' : 'transparent'),
      }}>{label}</button>
    ))}
  </div>
);

const ArticleCard = ({ article, onOpen, fakeMode, fakeLevel, branding, featured }) => {
  const display = fakeMode ? article.fake : article.original;
  const tinted = fakeMode && fakeLevel === 'medium';
  return (
    <article onClick={() => onOpen(article)} style={{
      position: 'relative',
      background: tinted ? 'rgba(255,92,61,0.04)' : 'var(--bg-2)',
      border: '1px solid ' + (tinted ? 'rgba(255,92,61,0.18)' : 'var(--line)'),
      borderRadius: 'var(--radius)', padding: featured ? 28 : 22,
      cursor: 'pointer', transition: 'border-color .15s, transform .15s, background .15s',
      overflow: 'hidden',
    }}
    onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--line-2)'; }}
    onMouseLeave={(e) => { e.currentTarget.style.borderColor = tinted ? 'rgba(255,92,61,0.18)' : 'var(--line)'; }}
    >
      {fakeMode && fakeLevel === 'loud' && <FakeRibbon />}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
        <SourcePill source={article.source} branding={branding} />
        <span style={{ width: 3, height: 3, borderRadius: 999, background: 'var(--text-4)' }} />
        <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
          {article.topic}
        </span>
        <div style={{ flex: 1 }} />
        {fakeMode && <SatireBadge level={fakeLevel} />}
        <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-3)' }}>{relTime(article.publishedAt)}</span>
      </div>
      <h2 className="serif" style={{
        margin: 0, marginBottom: 10,
        fontSize: featured ? 32 : 22, lineHeight: 1.15, fontWeight: 600,
        color: 'var(--text)', letterSpacing: '-0.01em',
      }}>{display.title}</h2>
      <p className="clamp-3" style={{
        margin: 0, color: 'var(--text-2)', fontSize: featured ? 16 : 14,
        lineHeight: 1.55, fontFamily: 'var(--serif)',
      }}>{display.description}</p>
      <div style={{ marginTop: 16, display: 'flex', alignItems: 'center', gap: 14, color: 'var(--text-3)', fontSize: 12 }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <I.Chat size={13} /> Ask about this article
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <I.Diff size={13} /> Compare to original
        </span>
      </div>
    </article>
  );
};

const FeedSkeleton = () => (
  <div style={{ display: 'grid', gap: 16 }}>
    {[0, 1, 2, 3].map(i => (
      <div key={i} style={{ background: 'var(--bg-2)', border: '1px solid var(--line)', borderRadius: 'var(--radius)', padding: 22 }}>
        <div style={{ display: 'flex', gap: 12, marginBottom: 14 }}>
          <Skeleton w={120} h={10} />
          <Skeleton w={60} h={10} />
        </div>
        <Skeleton w="80%" h={22} style={{ marginBottom: 12 }} />
        <Skeleton w="100%" h={12} style={{ marginBottom: 6 }} />
        <Skeleton w="90%" h={12} style={{ marginBottom: 6 }} />
        <Skeleton w="60%" h={12} />
      </div>
    ))}
  </div>
);

const EmptyState = ({ onRefresh }) => (
  <div style={{
    border: '1px dashed var(--line-2)', borderRadius: 'var(--radius-lg)',
    padding: '64px 32px', textAlign: 'center', background: 'var(--bg-2)',
  }}>
    <div style={{ display: 'inline-flex', padding: 14, borderRadius: 999, background: 'var(--bg-3)', marginBottom: 18, color: 'var(--accent)' }}>
      <I.Sparkle size={22} />
    </div>
    <h3 className="display" style={{ margin: 0, fontSize: 32, letterSpacing: '0.01em' }}>NOTHING TO READ — YET</h3>
    <p style={{ margin: '8px auto 22px', maxWidth: 460, color: 'var(--text-2)', fontFamily: 'var(--serif)', fontSize: 15, lineHeight: 1.6 }}>
      The scraper hasn't run. Hit the button to pull the latest from NYT, NPR, and The Guardian — then we'll have an LLM make them weirder.
    </p>
    <Btn kind="primary" size="lg" icon={<I.Refresh size={16} />} onClick={onRefresh}>Run scrape now</Btn>
    <div style={{ marginTop: 22, display: 'flex', justifyContent: 'center', gap: 14, color: 'var(--text-3)', fontSize: 12, fontFamily: 'var(--mono)' }}>
      {SOURCES.map(s => (
        <span key={s.id} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 6, height: 6, borderRadius: 999, background: s.color }} />
          {s.feed}
        </span>
      ))}
    </div>
  </div>
);

const ErrorBanner = ({ error, onRetry, onDismiss }) => (
  <div style={{
    background: 'rgba(226,106,106,0.08)', border: '1px solid rgba(226,106,106,0.3)',
    borderRadius: 'var(--radius)', padding: '14px 18px', marginBottom: 16,
    display: 'flex', alignItems: 'flex-start', gap: 14,
  }}>
    <I.Warn size={18} stroke="var(--bad)" />
    <div style={{ flex: 1 }}>
      <div style={{ fontWeight: 600, color: 'var(--text)', fontSize: 13, marginBottom: 2 }}>{error.title}</div>
      <div style={{ color: 'var(--text-2)', fontSize: 12 }}>{error.detail}</div>
    </div>
    <Btn kind="outline" size="sm" onClick={onRetry}>Retry</Btn>
    <button onClick={onDismiss} style={{ background: 'transparent', border: 'none', color: 'var(--text-3)', cursor: 'pointer' }}>
      <I.Close size={14} />
    </button>
  </div>
);

const Feed = ({ articles, onOpen, onRefresh, refreshing, lastScrape, onOpenAdmin,
                fakeMode, setFakeMode, fakeLevel, branding,
                phase, error, dismissError }) => {
  const [sourceFilter, setSourceFilter] = React.useState('all');
  const [sort, setSort] = React.useState('recent');

  const counts = React.useMemo(() => {
    const c = { all: articles.length };
    SOURCES.forEach(s => c[s.id] = articles.filter(a => a.source.id === s.id).length);
    return c;
  }, [articles]);

  const visible = React.useMemo(() => {
    let xs = sourceFilter === 'all' ? articles : articles.filter(a => a.source.id === sourceFilter);
    if (sort === 'recent') xs = [...xs].sort((a, b) => b.publishedAt - a.publishedAt);
    if (sort === 'source') xs = [...xs].sort((a, b) => a.source.name.localeCompare(b.source.name) || b.publishedAt - a.publishedAt);
    if (sort === 'topic')  xs = [...xs].sort((a, b) => a.topic.localeCompare(b.topic) || b.publishedAt - a.publishedAt);
    return xs;
  }, [articles, sourceFilter, sort]);

  return (
    <div data-screen-label="01 Feed">
      <FeedHeader onRefresh={onRefresh} refreshing={refreshing} lastScrape={lastScrape} onOpenAdmin={onOpenAdmin}
                  fakeMode={fakeMode} onCycleFakeMode={() => setFakeMode(!fakeMode)} fakeLevel={fakeLevel} />
      <main style={{ maxWidth: 1240, margin: '0 auto', padding: '32px 28px 80px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 24, marginBottom: 4 }}>
          <div>
            <Tag color="var(--accent)">The Front Page · {new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}</Tag>
            <h1 className="display" style={{ margin: '8px 0 0', fontSize: 64, lineHeight: 0.95, letterSpacing: '0.005em' }}>
              TODAY'S HEADLINES, <span style={{ color: 'var(--accent)' }}>SLIGHTLY OFF</span>
            </h1>
            <p className="serif" style={{ margin: '14px 0 0', maxWidth: 620, color: 'var(--text-2)', fontSize: 16, lineHeight: 1.55 }}>
              We pull real articles from {SOURCES.length} feeds, run them through a language model, and serve them back with the absurdity dial turned up. Every story links to the original.
            </p>
          </div>
          <div style={{ textAlign: 'right', color: 'var(--text-3)', fontFamily: 'var(--mono)', fontSize: 11, letterSpacing: '0.08em' }}>
            <div>{articles.length} ARTICLES IN FEED</div>
            <div style={{ marginTop: 4 }}>{SOURCES.length} SOURCES</div>
            <div style={{ marginTop: 4 }}>UPDATED {relTime(lastScrape).toUpperCase()}</div>
          </div>
        </div>

        <FilterRail counts={counts} sourceFilter={sourceFilter} setSourceFilter={setSourceFilter}
                    sort={sort} setSort={setSort} branding={branding} />

        {error && <ErrorBanner error={error} onRetry={onRefresh} onDismiss={dismissError} />}

        {phase === 'loading' && <FeedSkeleton />}
        {phase === 'empty' && <EmptyState onRefresh={onRefresh} />}
        {phase === 'ready' && (
          <div style={{ display: 'grid', gap: 16 }}>
            {visible.length > 0 && (
              <ArticleCard article={visible[0]} onOpen={onOpen} fakeMode={fakeMode} fakeLevel={fakeLevel} branding={branding} featured />
            )}
            <div style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))' }}>
              {visible.slice(1).map(a => (
                <ArticleCard key={a.id} article={a} onOpen={onOpen} fakeMode={fakeMode} fakeLevel={fakeLevel} branding={branding} />
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

window.Feed = Feed;
