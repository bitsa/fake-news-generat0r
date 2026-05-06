// Admin/scrape modal: lets the user trigger scraping and see per-source progress.

const AdminModal = ({ open, onClose, onRunScrape, onRunTransform, scrapeState }) => {
  if (!open) return null;
  const sources = scrapeState.sources;
  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 60,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      backdropFilter: 'blur(4px)',
    }}>
      <div onClick={e => e.stopPropagation()} className="fadein" style={{
        background: 'var(--bg-2)', border: '1px solid var(--line)',
        borderRadius: 'var(--radius-lg)', width: 640, maxWidth: '92vw',
        boxShadow: '0 30px 80px rgba(0,0,0,0.6)',
      }}>
        <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: 'var(--bg-3)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent)' }}>
            <I.Layers size={16} />
          </div>
          <div style={{ flex: 1 }}>
            <div className="display" style={{ fontSize: 22, letterSpacing: '0.01em' }}>SCRAPE & TRANSFORM</div>
            <div style={{ fontSize: 12, color: 'var(--text-3)' }}>Trigger the pipeline manually. Both stages run async on the server.</div>
          </div>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: 'var(--text-3)', cursor: 'pointer' }}>
            <I.Close size={16} />
          </button>
        </div>

        <div style={{ padding: 24 }}>
          <div style={{ display: 'grid', gap: 10, marginBottom: 18 }}>
            {SOURCES.map(s => {
              const st = sources[s.id] || { phase: 'idle', scraped: 0, transformed: 0 };
              const phaseLabel = {
                idle: 'Idle', scraping: 'Scraping…', scraped: 'Scraped',
                transforming: 'Transforming…', done: 'Done', failed: 'Failed',
              }[st.phase];
              const phaseColor = st.phase === 'failed' ? 'var(--bad)'
                : st.phase === 'done' ? 'var(--good)'
                : (st.phase === 'scraping' || st.phase === 'transforming') ? 'var(--accent)'
                : 'var(--text-3)';
              return (
                <div key={s.id} style={{
                  display: 'grid', gridTemplateColumns: '180px 1fr auto', gap: 16, alignItems: 'center',
                  background: 'var(--bg-3)', border: '1px solid var(--line)',
                  borderRadius: 'var(--radius)', padding: '12px 14px',
                }}>
                  <SourcePill source={s} branding="monogram" />
                  <div>
                    <div style={{ height: 6, background: 'var(--bg-4)', borderRadius: 999, overflow: 'hidden' }}>
                      <div style={{
                        height: '100%',
                        width: ((st.transformed || 0) / Math.max(1, st.scraped || 6)) * 100 + '%',
                        background: 'var(--accent)',
                        transition: 'width .4s ease',
                      }} />
                    </div>
                    <div style={{ marginTop: 6, fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-3)', display: 'flex', justifyContent: 'space-between' }}>
                      <span>{st.scraped} scraped · {st.transformed} transformed</span>
                      <span style={{ color: phaseColor }}>{phaseLabel}</span>
                    </div>
                  </div>
                  <span style={{ width: 8, height: 8, borderRadius: 999, background: phaseColor, boxShadow: phaseColor === 'var(--accent)' ? '0 0 0 4px rgba(255,92,61,0.15)' : 'none' }} />
                </div>
              );
            })}
          </div>

          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            <Btn kind="primary" size="md" icon={<I.Refresh size={14} />} onClick={onRunScrape} disabled={scrapeState.busy}>
              {scrapeState.busy ? 'Pipeline running…' : 'Run full pipeline'}
            </Btn>
            <Btn kind="outline" size="md" icon={<I.Sparkle size={14} />} onClick={onRunTransform} disabled={scrapeState.busy}>
              Re-transform existing
            </Btn>
            <div style={{ flex: 1 }} />
            <span style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--mono)' }}>
              POST /api/scrape · POST /api/transform
            </span>
          </div>

          <div style={{ marginTop: 20, padding: 14, background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: 'var(--radius)', fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-3)', maxHeight: 140, overflow: 'auto' }}>
            {(scrapeState.log || []).map((l, i) => (
              <div key={i} style={{ display: 'flex', gap: 10, padding: '2px 0' }}>
                <span style={{ color: 'var(--text-4)' }}>{l.t}</span>
                <span style={{ color: l.level === 'error' ? 'var(--bad)' : l.level === 'ok' ? 'var(--good)' : 'var(--text-2)' }}>
                  {l.msg}
                </span>
              </div>
            ))}
            {(!scrapeState.log || scrapeState.log.length === 0) && (
              <span style={{ color: 'var(--text-4)' }}>// No runs yet. Click "Run full pipeline".</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

window.AdminModal = AdminModal;
