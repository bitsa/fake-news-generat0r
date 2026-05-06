// Article detail screen. Supports 3 layouts (driven by tweak):
//   'split'    - article on left, chat docked right
//   'drawer'   - article full width, chat slides in from right
//   'stacked'  - article on top, chat below

const ToggleSwitch = ({ value, onChange, leftLabel, rightLabel, leftHint, rightHint }) => (
  <div style={{
    display: 'inline-flex', alignItems: 'stretch',
    background: 'var(--bg-3)', border: '1px solid var(--line)',
    borderRadius: 999, padding: 3, position: 'relative',
  }}>
    {[
      { k: 'fake', label: leftLabel, hint: leftHint },
      { k: 'orig', label: rightLabel, hint: rightHint },
    ].map(opt => {
      const active = value === opt.k;
      return (
        <button key={opt.k} onClick={() => onChange(opt.k)} style={{
          background: active ? (opt.k === 'fake' ? 'var(--accent)' : 'var(--bg-4)') : 'transparent',
          color: active ? (opt.k === 'fake' ? 'var(--accent-ink)' : 'var(--text)') : 'var(--text-2)',
          border: 'none', cursor: 'pointer', borderRadius: 999,
          padding: '7px 16px', fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 600,
          display: 'inline-flex', alignItems: 'center', gap: 8, transition: 'all .15s',
        }}>
          {opt.label}
          <span style={{ fontFamily: 'var(--mono)', fontSize: 10, opacity: 0.7, fontWeight: 400 }}>{opt.hint}</span>
        </button>
      );
    })}
  </div>
);

// Word-level inline diff, naive but readable.
function diffTokens(a, b) {
  const ax = a.split(/(\s+)/), bx = b.split(/(\s+)/);
  // longest-common-subsequence on tokens
  const m = ax.length, n = bx.length;
  const dp = Array.from({ length: m + 1 }, () => new Int32Array(n + 1));
  for (let i = m - 1; i >= 0; i--) for (let j = n - 1; j >= 0; j--) {
    dp[i][j] = ax[i] === bx[j] ? dp[i+1][j+1] + 1 : Math.max(dp[i+1][j], dp[i][j+1]);
  }
  const out = []; let i = 0, j = 0;
  while (i < m && j < n) {
    if (ax[i] === bx[j]) { out.push({ t: 'eq', v: ax[i] }); i++; j++; }
    else if (dp[i+1][j] >= dp[i][j+1]) { out.push({ t: 'del', v: ax[i] }); i++; }
    else { out.push({ t: 'add', v: bx[j] }); j++; }
  }
  while (i < m) out.push({ t: 'del', v: ax[i++] });
  while (j < n) out.push({ t: 'add', v: bx[j++] });
  return out;
}

const InlineDiff = ({ original, fake }) => {
  const tokens = React.useMemo(() => diffTokens(original, fake), [original, fake]);
  return (
    <div className="serif" style={{ fontSize: 15, lineHeight: 1.7, color: 'var(--text-2)' }}>
      {tokens.map((t, i) => {
        if (t.t === 'eq') return <span key={i}>{t.v}</span>;
        if (t.t === 'del') return <span key={i} style={{
          color: 'var(--bad)', background: 'rgba(226,106,106,0.1)',
          textDecoration: 'line-through', textDecorationColor: 'rgba(226,106,106,0.5)',
        }}>{t.v}</span>;
        return <span key={i} style={{ color: 'var(--accent)', background: 'rgba(255,92,61,0.1)' }}>{t.v}</span>;
      })}
    </div>
  );
};

const ArticleBody = ({ article, view, fakeLevel }) => {
  const isFake = view === 'fake';
  const display = isFake ? article.fake : article.original;
  return (
    <div style={{ position: 'relative' }} className="fadein" key={view}>
      {isFake && fakeLevel === 'loud' && <FakeRibbon />}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18 }}>
        <SourcePill source={article.source} branding="monogram" size="lg" />
        <span style={{ width: 3, height: 3, borderRadius: 999, background: 'var(--text-4)' }} />
        <Tag>{article.topic}</Tag>
        <span style={{ width: 3, height: 3, borderRadius: 999, background: 'var(--text-4)' }} />
        <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-3)' }}>{fmtTime(article.publishedAt)}</span>
        {isFake && <><span style={{ width: 3, height: 3, borderRadius: 999, background: 'var(--text-4)' }} /><SatireBadge level={fakeLevel === 'subtle' ? 'medium' : fakeLevel} /></>}
      </div>
      <h1 className="serif" style={{
        margin: 0, fontSize: 48, lineHeight: 1.08, letterSpacing: '-0.015em', fontWeight: 600,
        color: 'var(--text)',
      }}>{display.title}</h1>
      <p className="serif" style={{
        margin: '20px 0 0', fontSize: 19, lineHeight: 1.55, color: 'var(--text-2)',
        borderLeft: '2px solid ' + (isFake ? 'var(--accent)' : 'var(--line-2)'),
        paddingLeft: 18,
      }}>{display.description}</p>
      <div style={{ marginTop: 28, display: 'flex', alignItems: 'center', gap: 16, color: 'var(--text-3)', fontSize: 12 }}>
        <a href={article.url} target="_blank" rel="noreferrer" style={{
          display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--text-2)',
          textDecoration: 'none', borderBottom: '1px solid var(--line-2)', paddingBottom: 2,
        }}>
          <I.External size={13} /> View original on {article.source.name}
        </a>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <I.Clock size={13} /> Scraped {relTime(article.scrapedAt)}
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <I.Sparkle size={13} stroke="var(--accent)" /> Transformed {relTime(article.transformedAt)}
        </span>
      </div>
    </div>
  );
};

const ArticleDetail = ({ article, onBack, fakeLevel, layout, chatNode }) => {
  const [view, setView] = React.useState('fake'); // 'fake' | 'orig' | 'diff'
  const [drawerOpen, setDrawerOpen] = React.useState(false);

  const articlePane = (
    <div style={{ background: 'var(--bg-2)', border: '1px solid var(--line)', borderRadius: 'var(--radius-lg)', padding: '36px 40px', overflow: 'hidden', position: 'relative' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28, gap: 16, flexWrap: 'wrap' }}>
        <Btn kind="ghost" size="sm" icon={<I.ArrowLeft size={14} />} onClick={onBack}>Back to feed</Btn>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}>
          <ToggleSwitch
            value={view === 'diff' ? 'fake' : view}
            onChange={(v) => setView(v)}
            leftLabel="Satirical" leftHint="GPT-4"
            rightLabel="Original" rightHint="Source"
          />
          <button onClick={() => setView('diff')} style={{
            background: view === 'diff' ? 'var(--bg-4)' : 'transparent',
            color: view === 'diff' ? 'var(--text)' : 'var(--text-2)',
            border: '1px solid var(--line)', borderRadius: 999, padding: '7px 14px',
            cursor: 'pointer', fontSize: 12, display: 'inline-flex', alignItems: 'center', gap: 7,
          }}>
            <I.Diff size={13} /> Diff
          </button>
        </div>
      </div>

      {view === 'diff' ? (
        <div className="fadein">
          <Tag>What changed</Tag>
          <h2 className="serif" style={{ margin: '8px 0 24px', fontSize: 28, fontWeight: 600 }}>Original → Satirical</h2>
          <div style={{ display: 'grid', gap: 28 }}>
            <div>
              <Tag color="var(--text-3)">Title</Tag>
              <div style={{ marginTop: 8 }}>
                <InlineDiff original={article.original.title} fake={article.fake.title} />
              </div>
            </div>
            <div>
              <Tag color="var(--text-3)">Description</Tag>
              <div style={{ marginTop: 8 }}>
                <InlineDiff original={article.original.description} fake={article.fake.description} />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 18, fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--text-3)' }}>
              <span><span style={{ color: 'var(--bad)' }}>━</span> removed from original</span>
              <span><span style={{ color: 'var(--accent)' }}>━</span> added by model</span>
            </div>
          </div>
        </div>
      ) : (
        <ArticleBody article={article} view={view} fakeLevel={fakeLevel} />
      )}
    </div>
  );

  if (layout === 'split') {
    return (
      <div data-screen-label="02 Article (split)" style={{ maxWidth: 1320, margin: '0 auto', padding: '24px 28px 60px', display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 420px', gap: 20 }}>
        {articlePane}
        <aside style={{ position: 'sticky', top: 80, alignSelf: 'start', height: 'calc(100vh - 100px)' }}>
          {chatNode}
        </aside>
      </div>
    );
  }

  if (layout === 'stacked') {
    return (
      <div data-screen-label="02 Article (stacked)" style={{ maxWidth: 880, margin: '0 auto', padding: '24px 28px 60px', display: 'grid', gap: 20 }}>
        {articlePane}
        <div style={{ height: 560 }}>{chatNode}</div>
      </div>
    );
  }

  // drawer
  return (
    <div data-screen-label="02 Article (drawer)" style={{ maxWidth: 880, margin: '0 auto', padding: '24px 28px 60px', position: 'relative' }}>
      {articlePane}
      <button onClick={() => setDrawerOpen(true)} style={{
        position: 'fixed', right: 24, bottom: 24, zIndex: 30,
        background: 'var(--accent)', color: 'var(--accent-ink)', border: 'none',
        borderRadius: 999, padding: '14px 22px', cursor: 'pointer',
        display: 'inline-flex', alignItems: 'center', gap: 10, fontWeight: 600,
        boxShadow: '0 8px 24px rgba(255,92,61,0.35)',
      }}>
        <I.Chat size={16} /> Ask about this article
      </button>
      {drawerOpen && (
        <>
          <div onClick={() => setDrawerOpen(false)} style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 40,
          }} />
          <div className="fadein" style={{
            position: 'fixed', top: 0, right: 0, bottom: 0, width: 460, zIndex: 41,
            background: 'var(--bg)', borderLeft: '1px solid var(--line)',
            display: 'flex', flexDirection: 'column',
          }}>
            <div style={{ flex: 1, minHeight: 0 }}>{chatNode}</div>
            <button onClick={() => setDrawerOpen(false)} style={{
              position: 'absolute', top: 14, right: 14, background: 'var(--bg-3)', border: '1px solid var(--line)',
              color: 'var(--text-2)', borderRadius: 999, width: 32, height: 32, cursor: 'pointer',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            }}><I.Close size={14} /></button>
          </div>
        </>
      )}
    </div>
  );
};

window.ArticleDetail = ArticleDetail;
