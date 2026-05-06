// Lightweight inline SVG icon set. Stroke-based, 1.5px, currentColor.
const Icon = ({ d, size = 16, fill, stroke = 'currentColor', sw = 1.6, children, ...rest }) => (
  <svg viewBox="0 0 24 24" width={size} height={size} fill={fill || 'none'} stroke={stroke} strokeWidth={sw}
       strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...rest}>
    {children || <path d={d} />}
  </svg>
);

const I = {
  Search: (p) => <Icon {...p}><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></Icon>,
  Filter: (p) => <Icon {...p}><path d="M3 5h18M6 12h12M10 19h4" /></Icon>,
  Refresh: (p) => <Icon {...p}><path d="M21 12a9 9 0 1 1-3.2-6.9M21 4v5h-5" /></Icon>,
  Send: (p) => <Icon {...p}><path d="M22 2 11 13" /><path d="M22 2 15 22l-4-9-9-4Z" /></Icon>,
  Close: (p) => <Icon {...p}><path d="M6 6l12 12M18 6 6 18" /></Icon>,
  Chat: (p) => <Icon {...p}><path d="M21 12a8 8 0 0 1-11.7 7L4 20l1-4.6A8 8 0 1 1 21 12Z" /></Icon>,
  Sparkle: (p) => <Icon {...p}><path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.5 5.5l2.8 2.8M15.7 15.7l2.8 2.8M5.5 18.5l2.8-2.8M15.7 8.3l2.8-2.8" /></Icon>,
  ArrowLeft: (p) => <Icon {...p}><path d="M19 12H5M12 19l-7-7 7-7" /></Icon>,
  ArrowRight: (p) => <Icon {...p}><path d="M5 12h14M12 5l7 7-7 7" /></Icon>,
  External: (p) => <Icon {...p}><path d="M14 4h6v6M10 14 20 4M19 14v6H4V5h6" /></Icon>,
  Toggle: (p) => <Icon {...p}><rect x="2" y="7" width="20" height="10" rx="5" /><circle cx="8" cy="12" r="3" fill="currentColor" stroke="none" /></Icon>,
  Doc: (p) => <Icon {...p}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /></Icon>,
  Bot: (p) => <Icon {...p}><rect x="4" y="8" width="16" height="12" rx="3" /><path d="M12 4v4M9 14h.01M15 14h.01M9 18h6" /></Icon>,
  User: (p) => <Icon {...p}><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></Icon>,
  Check: (p) => <Icon {...p}><path d="M5 12l5 5L20 7" /></Icon>,
  Warn: (p) => <Icon {...p}><path d="M12 3 2 21h20Z" /><path d="M12 10v5M12 18.5v.01" /></Icon>,
  Loader: (p) => <Icon {...p}><path d="M12 3v4M12 17v4M5 12H1M23 12h-4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8" /></Icon>,
  Diff: (p) => <Icon {...p}><path d="M8 3v18M16 3v18M3 8h10M11 16h10" /></Icon>,
  List: (p) => <Icon {...p}><path d="M4 6h16M4 12h16M4 18h10" /></Icon>,
  Tag: (p) => <Icon {...p}><path d="M20.6 13.4 13 21l-9-9V4h8l8.6 8.6a1 1 0 0 1 0 1.4Z"/><circle cx="8" cy="8" r="1.5" fill="currentColor" stroke="none"/></Icon>,
  Pin: (p) => <Icon {...p}><path d="M12 22v-7M5 9l7-7 7 7-3 3-1-1-6 6-1-1Z" /></Icon>,
  Clock: (p) => <Icon {...p}><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></Icon>,
  Layers: (p) => <Icon {...p}><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m3 13 9 5 9-5M3 17l9 5 9-5" /></Icon>,
  Settings: (p) => <Icon {...p}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z"/></Icon>,
};

window.I = I;
