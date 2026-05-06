// Chat panel: streaming responses, quick prompts, persisted history,
// special message kinds for entities + diff.

const QUICK_PROMPTS = [
  { k: 'summarize', label: 'Summarize this article', icon: <I.List size={13} /> },
  { k: 'entities',  label: 'Key entities', icon: <I.Tag size={13} /> },
  { k: 'changed',   label: 'How was it changed?', icon: <I.Diff size={13} /> },
];

// Mock entity extraction (deterministic, derived from text).
function extractEntities(article) {
  const text = (article.original.title + ' ' + article.original.description);
  // simple heuristic: capitalized multi-word phrases
  const people = [];
  const orgs = [];
  const places = [];
  // hand-curated per-article extras for realism, fall back to source name otherwise
  const seeds = {
    art_001: { people: ['Senate Majority Leader'], orgs: ['U.S. Senate', 'House of Representatives'], places: ['Washington, D.C.'] },
    art_002: { people: [], orgs: ['OpenAI', 'Top 5 US Banks'], places: ['United States'] },
    art_003: { people: [], orgs: ['European Meteorological Service'], places: ['Lisbon', 'Warsaw', 'Spain', 'Europe'] },
    art_004: { people: [], orgs: ['Nasdaq', 'JPMorgan', 'Goldman Sachs'], places: ['Wall Street'] },
    art_005: { people: [], orgs: ['CDC'], places: ['United States'] },
    art_006: { people: [], orgs: ['UK Government', 'Local Government Association'], places: ['England'] },
  };
  const s = seeds[article.id] || { people: [], orgs: [article.source.name], places: [] };
  return s;
}

// Mock streaming generator: returns chunks for a typed-out effect.
function tokensFor(prompt, article) {
  if (prompt === 'summarize') {
    const orig = article.original.description;
    // Compose a 2-sentence summary
    const t = (article.original.title.replace(/\.$/, '') + '. ') + orig + ' The piece frames it as a developing story with broader implications.';
    return t.split(/(\s+)/);
  }
  if (prompt === 'changed') {
    return ('The fake version preserves the structure of the original headline (subject, action, framing) but swaps the substantive outcome for an absurd or comically narrow one. The body rewrites the lede with concrete-sounding but ridiculous detail, while keeping the same source signals so it reads as a recognizable parody.').split(/(\s+)/);
  }
  if (prompt === 'entities') {
    return ['__entities__'];
  }
  // freeform fallback
  return ('That\'s a great question. Based on this article from ' + article.source.name + ', ' + article.original.description.split('.').slice(0, 2).join('.') + '.').split(/(\s+)/);
}

const TypingDot = () => (
  <span style={{ display: 'inline-flex', gap: 3, alignItems: 'center', padding: '0 4px' }}>
    {[0, 1, 2].map(i => (
      <span key={i} style={{
        width: 5, height: 5, borderRadius: 999, background: 'var(--text-3)',
        animation: 'pulse 1.2s ease-in-out infinite',
        animationDelay: (i * 0.18) + 's',
      }} />
    ))}
  </span>
);

const EntitiesCard = ({ entities }) => {
  const groups = [
    { k: 'people', label: 'People', items: entities.people, color: 'var(--grd)' },
    { k: 'orgs', label: 'Organizations', items: entities.orgs, color: 'var(--accent-2)' },
    { k: 'places', label: 'Locations', items: entities.places, color: 'var(--good)' },
  ];
  const allEmpty = groups.every(g => g.items.length === 0);
  if (allEmpty) {
    return <span style={{ color: 'var(--text-3)', fontSize: 13 }}>No named entities extracted.</span>;
  }
  return (
    <div style={{ display: 'grid', gap: 10, marginTop: 4 }}>
      {groups.filter(g => g.items.length).map(g => (
        <div key={g.k}>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-3)', marginBottom: 6 }}>{g.label}</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {g.items.map((it, i) => (
              <span key={i} style={{
                background: 'var(--bg-4)', color: 'var(--text)',
                border: '1px solid var(--line-2)', borderRadius: 999,
                padding: '4px 10px', fontSize: 12,
                display: 'inline-flex', alignItems: 'center', gap: 6,
              }}>
                <span style={{ width: 6, height: 6, borderRadius: 999, background: g.color }} />
                {it}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};

const Message = ({ msg, article }) => {
  const isUser = msg.role === 'user';
  return (
    <div className="fadein" style={{
      display: 'flex', gap: 10, padding: '14px 0',
      flexDirection: isUser ? 'row-reverse' : 'row',
    }}>
      <div style={{
        flex: '0 0 auto', width: 26, height: 26, borderRadius: 999,
        background: isUser ? 'var(--bg-4)' : 'var(--accent)',
        color: isUser ? 'var(--text-2)' : 'var(--accent-ink)',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      }}>
        {isUser ? <I.User size={13} /> : <I.Bot size={14} />}
      </div>
      <div style={{ flex: 1, minWidth: 0, maxWidth: '85%' }}>
        <div style={{
          background: isUser ? 'var(--bg-3)' : 'transparent',
          border: isUser ? '1px solid var(--line)' : 'none',
          borderRadius: 12,
          padding: isUser ? '10px 14px' : '4px 0',
          color: 'var(--text)', fontSize: 14, lineHeight: 1.55,
        }}>
          {msg.kind === 'entities' ? (
            <>
              <div style={{ color: 'var(--text-2)', marginBottom: 4 }}>{msg.text}</div>
              <EntitiesCard entities={extractEntities(article)} />
            </>
          ) : msg.streaming ? (
            <span>{msg.text}<span className="blink" style={{ color: 'var(--accent)', marginLeft: 1 }}>▍</span></span>
          ) : (
            <span style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</span>
          )}
        </div>
        <div style={{ marginTop: 4, fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-4)', textAlign: isUser ? 'right' : 'left' }}>
          {fmtClock(msg.t)}
        </div>
      </div>
    </div>
  );
};

const ChatPanel = ({ article, history, setHistory }) => {
  const [draft, setDraft] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const scrollRef = React.useRef(null);
  React.useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [history]);

  const send = (text, promptKey) => {
    if (busy) return;
    const userMsg = { id: 'm_' + Date.now(), role: 'user', text, t: Date.now() };
    const placeholder = { id: 'm_' + (Date.now() + 1), role: 'assistant', text: '', t: Date.now(), streaming: true };
    setHistory(h => [...h, userMsg, placeholder]);
    setBusy(true);
    setDraft('');

    const tokens = tokensFor(promptKey || 'free', article);

    // Special-cased entities response (no streaming)
    if (tokens[0] === '__entities__') {
      setTimeout(() => {
        setHistory(h => h.map(m => m.id === placeholder.id ? {
          ...m, streaming: false, kind: 'entities', text: 'Here are the entities I pulled from the original article:',
        } : m));
        setBusy(false);
      }, 600);
      return;
    }

    let i = 0;
    const tick = () => {
      if (i >= tokens.length) {
        setHistory(h => h.map(m => m.id === placeholder.id ? { ...m, streaming: false } : m));
        setBusy(false);
        return;
      }
      const chunk = tokens.slice(0, i + 1).join('');
      setHistory(h => h.map(m => m.id === placeholder.id ? { ...m, text: chunk } : m));
      i++;
      setTimeout(tick, 18 + Math.random() * 30);
    };
    setTimeout(tick, 280);
  };

  const onSubmit = (e) => {
    e.preventDefault();
    if (draft.trim()) send(draft.trim());
  };

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%',
      background: 'var(--bg-2)', border: '1px solid var(--line)',
      borderRadius: 'var(--radius-lg)', overflow: 'hidden',
    }}>
      <div style={{ padding: '16px 18px', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ width: 28, height: 28, borderRadius: 8, background: 'var(--accent)', color: 'var(--accent-ink)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
          <I.Sparkle size={15} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: 13 }}>Article assistant</div>
          <div className="truncate" style={{ fontSize: 11, color: 'var(--text-3)' }}>Grounded on: {article.original.title}</div>
        </div>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>gpt-4o</span>
      </div>

      <div ref={scrollRef} style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '4px 18px' }}>
        {history.length === 0 ? (
          <div style={{ padding: '24px 0', color: 'var(--text-3)', fontSize: 13, lineHeight: 1.6 }}>
            <div style={{ marginBottom: 10, color: 'var(--text-2)' }}>Ask anything about this article.</div>
            History is persisted per-article — refresh and your thread is still here.
          </div>
        ) : (
          history.map(m => <Message key={m.id} msg={m} article={article} />)
        )}
        {busy && history[history.length - 1]?.role === 'assistant' && history[history.length - 1].text === '' && (
          <div style={{ padding: '4px 0 18px 36px' }}><TypingDot /></div>
        )}
      </div>

      <div style={{ padding: '10px 14px 6px', borderTop: '1px solid var(--line)', display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {QUICK_PROMPTS.map(p => (
          <button key={p.k} onClick={() => send(p.label, p.k)} disabled={busy} style={{
            background: 'var(--bg-3)', border: '1px solid var(--line)',
            color: 'var(--text-2)', borderRadius: 999, padding: '6px 10px',
            fontSize: 11, cursor: busy ? 'not-allowed' : 'pointer',
            display: 'inline-flex', alignItems: 'center', gap: 6, opacity: busy ? 0.55 : 1,
          }}>
            {p.icon} {p.label}
          </button>
        ))}
      </div>

      <form onSubmit={onSubmit} style={{ padding: '8px 14px 14px', display: 'flex', gap: 8 }}>
        <input value={draft} onChange={e => setDraft(e.target.value)} placeholder="Ask about this article…"
          style={{
            flex: 1, background: 'var(--bg-3)', border: '1px solid var(--line)',
            color: 'var(--text)', borderRadius: 999, padding: '10px 16px',
            fontSize: 13, fontFamily: 'inherit', outline: 'none',
          }}
          onFocus={e => e.target.style.borderColor = 'var(--line-2)'}
          onBlur={e => e.target.style.borderColor = 'var(--line)'}
        />
        <button type="submit" disabled={!draft.trim() || busy} style={{
          background: 'var(--accent)', color: 'var(--accent-ink)', border: 'none',
          borderRadius: 999, width: 38, height: 38, cursor: (!draft.trim() || busy) ? 'not-allowed' : 'pointer',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          opacity: (!draft.trim() || busy) ? 0.5 : 1,
        }}><I.Send size={15} /></button>
      </form>
    </div>
  );
};

window.ChatPanel = ChatPanel;
