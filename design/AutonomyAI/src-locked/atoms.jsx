// Atoms used across the prototype: logo, badges, buttons, source pill.

const Logo = ({ size = 20 }) => (
  <div style={{ display: 'inline-flex', alignItems: 'baseline', gap: 0, fontFamily: 'var(--display)', fontSize: size, lineHeight: 1, letterSpacing: '0.005em' }}>
    <span style={{ color: 'var(--text)' }}>FAKE</span>
    <span style={{ color: 'var(--accent)', marginLeft: 2 }}>LINE</span>
  </div>
);

// "Fake" treatment is driven by a tweak. This component renders a badge whose
// loudness scales with the tweak. `level` ∈ 'subtle' | 'medium' | 'loud'
const SatireBadge = ({ level = 'medium', size = 'sm' }) => {
  if (level === 'subtle') {
    return (
      <span style={{
        fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '0.12em',
        color: 'var(--text-3)', textTransform: 'uppercase',
      }}>satire</span>
    );
  }
  if (level === 'medium') {
    return (
      <span style={{
        fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '0.14em',
        color: 'var(--accent)', textTransform: 'uppercase',
        border: '1px solid rgba(255,92,61,0.4)', borderRadius: 999,
        padding: '2px 7px',
      }}>satire</span>
    );
  }
  // loud
  return (
    <span style={{
      fontFamily: 'var(--display)', fontSize: size === 'lg' ? 13 : 11, letterSpacing: '0.18em',
      color: 'var(--accent-ink)', background: 'var(--accent)',
      padding: size === 'lg' ? '4px 10px' : '3px 8px', borderRadius: 4,
      textTransform: 'uppercase',
    }}>FAKE NEWS</span>
  );
};

const SourcePill = ({ source, branding = 'dot', size = 'sm' }) => {
  const pad = size === 'lg' ? '5px 10px' : '3px 8px';
  const fs = size === 'lg' ? 11 : 10;
  if (branding === 'monogram') {
    return (
      <span style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        fontFamily: 'var(--mono)', fontSize: fs, color: 'var(--text-2)',
        textTransform: 'uppercase', letterSpacing: '0.1em',
      }}>
        <span style={{
          width: 18, height: 18, borderRadius: 4, background: source.color,
          color: '#0E0E0E', display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 9, fontWeight: 700, fontFamily: 'var(--display)', letterSpacing: '0.04em',
        }}>{source.short}</span>
        <span>{source.name}</span>
      </span>
    );
  }
  if (branding === 'text') {
    return (
      <span style={{ fontFamily: 'var(--mono)', fontSize: fs, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>
        {source.name}
      </span>
    );
  }
  // dot (default)
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontFamily: 'var(--mono)', fontSize: fs, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>
      <span style={{ width: 7, height: 7, borderRadius: 999, background: source.color, display: 'inline-block' }} />
      {source.name}
    </span>
  );
};

const Btn = ({ kind = 'ghost', size = 'md', icon, children, onClick, disabled, style, ...rest }) => {
  const base = {
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
    fontFamily: 'var(--sans)', fontWeight: 500,
    border: '1px solid transparent', borderRadius: 999, cursor: disabled ? 'not-allowed' : 'pointer',
    transition: 'background .15s, border-color .15s, color .15s, transform .05s',
    opacity: disabled ? 0.55 : 1,
    whiteSpace: 'nowrap',
  };
  const sizes = {
    sm: { fontSize: 12, padding: '6px 12px', height: 28 },
    md: { fontSize: 13, padding: '8px 14px', height: 34 },
    lg: { fontSize: 14, padding: '10px 18px', height: 40 },
  };
  const kinds = {
    primary: { background: 'var(--accent)', color: 'var(--accent-ink)', borderColor: 'var(--accent)' },
    secondary: { background: 'var(--bg-3)', color: 'var(--text)', borderColor: 'var(--line)' },
    ghost: { background: 'transparent', color: 'var(--text-2)', borderColor: 'transparent' },
    outline: { background: 'transparent', color: 'var(--text)', borderColor: 'var(--line-2)' },
    danger: { background: 'transparent', color: 'var(--bad)', borderColor: 'var(--line)' },
  };
  return (
    <button onClick={onClick} disabled={disabled} style={{ ...base, ...sizes[size], ...kinds[kind], ...style }} {...rest}>
      {icon && <span style={{ display: 'inline-flex' }}>{icon}</span>}
      {children}
    </button>
  );
};

const Chip = ({ active, onClick, children, count, color }) => (
  <button onClick={onClick} style={{
    display: 'inline-flex', alignItems: 'center', gap: 8,
    background: active ? 'var(--bg-4)' : 'transparent',
    color: active ? 'var(--text)' : 'var(--text-2)',
    border: '1px solid ' + (active ? 'var(--line-2)' : 'var(--line)'),
    borderRadius: 999, padding: '6px 12px', cursor: 'pointer',
    fontFamily: 'var(--sans)', fontSize: 12, fontWeight: 500,
    transition: 'all .15s',
  }}>
    {color && <span style={{ width: 7, height: 7, borderRadius: 999, background: color }} />}
    <span>{children}</span>
    {typeof count === 'number' && (
      <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-3)' }}>{count}</span>
    )}
  </button>
);

const Tag = ({ children, color = 'var(--text-3)' }) => (
  <span style={{
    fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '0.12em',
    color, textTransform: 'uppercase',
  }}>{children}</span>
);

const Divider = ({ vertical, style }) => (
  <div style={{
    background: 'var(--line)',
    width: vertical ? 1 : '100%', height: vertical ? '100%' : 1,
    ...style,
  }} />
);

// Skeleton block for loading rows.
const Skeleton = ({ w = '100%', h = 12, style }) => (
  <div className="pulse" style={{
    width: w, height: h, background: 'var(--bg-3)', borderRadius: 4, ...style,
  }} />
);

// Mini ribbon shown over images / hero areas in 'loud' mode.
const FakeRibbon = () => (
  <div style={{
    position: 'absolute', top: 14, left: -36, transform: 'rotate(-22deg)',
    background: 'var(--accent)', color: 'var(--accent-ink)',
    fontFamily: 'var(--display)', fontSize: 12, letterSpacing: '0.18em',
    padding: '5px 40px', boxShadow: '0 2px 8px rgba(0,0,0,0.4)',
  }}>SATIRE — NOT REAL</div>
);

Object.assign(window, { Logo, SatireBadge, SourcePill, Btn, Chip, Tag, Divider, Skeleton, FakeRibbon });
