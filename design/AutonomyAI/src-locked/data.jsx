// Mock data for the prototype. Shape mirrors the DB schema in CLAUDE.md.
const SOURCES = [
  { id: 'nyt', name: 'The New York Times', short: 'NYT', color: 'var(--nyt)', feed: 'rss.nytimes.com/services/xml/rss/nyt/HomePage.xml' },
  { id: 'npr', name: 'NPR News', short: 'NPR', color: 'var(--npr)', feed: 'feeds.npr.org/1001/rss.xml' },
  { id: 'grd', name: 'The Guardian', short: 'GRD', color: 'var(--grd)', feed: 'theguardian.com/world/rss' },
];

// 18 articles. Each has an "original" (plausible-looking real) and a "fake" satirical version.
const ARTICLES_RAW = [
  {
    sourceId: 'nyt', minutesAgo: 14, topic: 'Politics',
    origTitle: 'Senate Passes Bipartisan Infrastructure Bill After Marathon Session',
    origDesc: 'The $612 billion package, approved 68-32, funds bridges, broadband, and rail. It now heads to the House, where moderates in both parties signal cautious support.',
    fakeTitle: 'Senate Passes Bipartisan Bill to Replace All Bridges With Slightly Wider Bridges',
    fakeDesc: 'After a 19-hour session sustained largely by lukewarm vending-machine soup, lawmakers approved a $612 billion package that pundits described as "broadly the same, but six inches roomier."',
  },
  {
    sourceId: 'npr', minutesAgo: 28, topic: 'Tech',
    origTitle: 'AI Models Now Power Customer Service at 4 of the Top 5 US Banks',
    origDesc: 'A new survey finds large language models handling more than 60% of first-line banking inquiries, raising fresh questions about oversight, error rates, and consumer recourse.',
    fakeTitle: 'AI Now Handles 60% of Bank Calls; Remaining 40% Are People Yelling at AI',
    fakeDesc: 'A new survey confirms that the financial sector has finally achieved the long-promised efficiency of having a chatbot apologize to you in 14 different ways before transferring you to a different chatbot.',
  },
  {
    sourceId: 'grd', minutesAgo: 41, topic: 'Climate',
    origTitle: 'European Heatwave Breaks April Records From Lisbon to Warsaw',
    origDesc: 'Temperatures hit 36C in southern Spain as meteorologists warn the early-season heat is consistent with long-running climate trends across the continent.',
    fakeTitle: 'European Heatwave Breaks Records, Several Calendars',
    fakeDesc: 'Temperatures climbed so high in Lisbon that the month of April formally requested to be reclassified as "early August," a motion meteorologists called "fair, honestly."',
  },
  {
    sourceId: 'nyt', minutesAgo: 55, topic: 'Markets',
    origTitle: 'Tech Stocks Slide as Investors Reassess AI Spending Plans',
    origDesc: 'The Nasdaq fell 1.8% as analysts at three major banks downgraded forward earnings expectations for hyperscalers, citing capex outpacing near-term revenue.',
    fakeTitle: 'Tech Stocks Plunge After Investors Read One (1) Footnote',
    fakeDesc: 'The Nasdaq shed 1.8% Monday after a junior analyst at a mid-tier bank scrolled to page 47 of a 10-Q and audibly said "huh."',
  },
  {
    sourceId: 'npr', minutesAgo: 72, topic: 'Health',
    origTitle: 'CDC Reports Sharp Decline in Seasonal Flu Cases This Spring',
    origDesc: 'The agency credits high vaccine uptake and lingering pandemic-era hygiene habits, though officials warn the next strain remains unpredictable.',
    fakeTitle: 'CDC Reports Flu Down 40%, Says Nation Has "Maybe Finally Learned to Wash Its Hands"',
    fakeDesc: 'In a press briefing notable for its visible weariness, officials thanked the public for what they described as "a solid C+ effort, which, for us, is a national triumph."',
  },
  {
    sourceId: 'grd', minutesAgo: 96, topic: 'World',
    origTitle: 'UK Government Faces Backlash Over New Housing Targets',
    origDesc: 'Local councils across England warn the proposed 1.5 million-home target is unworkable without significant changes to planning law and funding.',
    fakeTitle: 'UK Promises 1.5 Million Homes; Local Councils Promise to Hold Meetings About It',
    fakeDesc: 'A spokesperson for the Local Government Association said councils stand "fully ready" to commission consultations to study the feasibility of forming a steering committee.',
  },
  {
    sourceId: 'nyt', minutesAgo: 130, topic: 'Culture',
    origTitle: 'Broadway Box Office Rebounds to Pre-Pandemic Highs',
    origDesc: 'Weekly grosses topped $46 million, led by a wave of new musicals and a surprise revival drawing tourists back to Times Square.',
    fakeTitle: 'Broadway Hits Pre-Pandemic Highs; Tourists Confirm They Still Don\'t Know Where 47th Street Is',
    fakeDesc: 'Weekly grosses topped $46 million as visitors successfully located their theaters via the time-honored method of standing very still and turning slowly in a circle.',
  },
  {
    sourceId: 'npr', minutesAgo: 165, topic: 'Tech',
    origTitle: 'Open-Source AI Project Reaches 100,000 Contributors',
    origDesc: 'The milestone, announced on the project\'s blog, marks a significant shift in how foundation models are developed outside of large corporate labs.',
    fakeTitle: 'Open-Source AI Project Hits 100,000 Contributors, 99,400 of Whom Just Fixed a Typo',
    fakeDesc: 'Maintainers celebrated the milestone with a quiet weep into a coffee mug labeled "I REVIEWED THIS PR."',
  },
  {
    sourceId: 'grd', minutesAgo: 210, topic: 'Sports',
    origTitle: 'Premier League Title Race Tightens After Surprise Weekend Results',
    origDesc: 'Two of the top three sides dropped points, leaving the table separated by a single goal difference with five matches to play.',
    fakeTitle: 'Premier League Race Tightens; Pundits Forced to Use the Phrase "Goal Difference" Out Loud',
    fakeDesc: 'Broadcasters scrambled to find a graphic capable of displaying a number with a minus sign, eventually settling on "an angry red one."',
  },
  {
    sourceId: 'nyt', minutesAgo: 250, topic: 'Business',
    origTitle: 'Major Airline Announces Return of Free Checked Bags on Domestic Routes',
    origDesc: 'The shift, framed as a competitive response, reverses a decade-old policy and is expected to pressure rivals to match within weeks.',
    fakeTitle: 'Airline Brings Back Free Checked Bags; Charges $40 to Look at Them',
    fakeDesc: 'A spokesperson clarified that while the bags themselves are free, "visual contact" with one\'s luggage will be billed separately as a "Sightline Service Fee."',
  },
  {
    sourceId: 'npr', minutesAgo: 305, topic: 'Education',
    origTitle: 'Universities Roll Out New Policies on AI Use in Coursework',
    origDesc: 'Drafts vary widely across campuses; some require disclosure, others ban use outright. Students and faculty are split on enforcement realism.',
    fakeTitle: 'Universities Unveil New AI Policies; Students Use AI to Read Them',
    fakeDesc: 'Faculty senates released 47-page guidance documents on permissible AI use, immediately summarized by every undergraduate into a 200-character TL;DR.',
  },
  {
    sourceId: 'grd', minutesAgo: 360, topic: 'Climate',
    origTitle: 'New Study Links Coastal Erosion to Accelerating Storm Patterns',
    origDesc: 'Researchers tracked 30 sites along the North Atlantic, finding a measurable increase in shoreline retreat over the past decade.',
    fakeTitle: 'Coast Erodes 12%, Politely Asks if Anyone Has a Plan',
    fakeDesc: 'The North Atlantic was reached for comment but said it had "honestly given up trying to get anyone\'s attention" and just wanted to be left alone.',
  },
  {
    sourceId: 'nyt', minutesAgo: 420, topic: 'Tech',
    origTitle: 'Self-Driving Truck Pilot Expands to Three Additional Interstates',
    origDesc: 'The expansion follows a year of supervised runs. Regulators say full autonomous operation remains contingent on weather-handling improvements.',
    fakeTitle: 'Self-Driving Trucks Expand to More Highways; Honking Now Done by Algorithm',
    fakeDesc: 'Engineers confirmed that the trucks are fully capable of expressing road rage at a rate equivalent to "1.4 angry cab drivers per mile."',
  },
  {
    sourceId: 'npr', minutesAgo: 510, topic: 'Politics',
    origTitle: 'Mayoral Race in Chicago Heads to Runoff After Tight First Round',
    origDesc: 'No candidate cleared the 50% threshold, setting up a six-week runoff that is expected to focus on public safety and budget priorities.',
    fakeTitle: 'Chicago Mayoral Race Heads to Runoff; Both Candidates Promise to "Fix the Thing"',
    fakeDesc: 'Polling indicates voters strongly favor "fixing the thing" over the alternative of "not fixing the thing," with a small but persistent third group preferring "complaining about the thing."',
  },
  {
    sourceId: 'grd', minutesAgo: 600, topic: 'Science',
    origTitle: 'Astronomers Detect Unusual Radio Signal From Nearby Galaxy',
    origDesc: 'The repeating burst, traced to a region 2.5 million light-years away, has prompted a coordinated follow-up by observatories across three continents.',
    fakeTitle: 'Astronomers Detect Mysterious Radio Signal; It\'s Just Their Microwave Again',
    fakeDesc: 'After 14 hours of careful triangulation, researchers traced the burst to the staff kitchen, where a postdoc was reheating leftover pad thai for the third time.',
  },
  {
    sourceId: 'nyt', minutesAgo: 720, topic: 'Food',
    origTitle: 'Restaurant Industry Reports Highest Margins in a Decade',
    origDesc: 'Operators credit menu engineering, leaner staffing models, and a small but persistent shift toward higher-priced tasting formats.',
    fakeTitle: 'Restaurants Post Record Margins After Discovering You Will Pay $26 for One (1) Egg',
    fakeDesc: 'Operators credit a breakthrough technique known as "putting it on a small plate and calling it Mediterranean."',
  },
  {
    sourceId: 'npr', minutesAgo: 880, topic: 'Tech',
    origTitle: 'Federal Agency Issues First Guidelines on Synthetic Media Labeling',
    origDesc: 'Platforms will be required to surface provenance metadata on AI-generated content meeting certain thresholds, beginning next year.',
    fakeTitle: 'Federal Agency Mandates Labels on AI Content; AI Asked to Write the Labels',
    fakeDesc: 'The agency confirmed that the labels themselves will be drafted by an AI, reviewed by a different AI, and approved by a committee of two AIs and one increasingly nervous person.',
  },
  {
    sourceId: 'grd', minutesAgo: 1100, topic: 'Travel',
    origTitle: 'Tourism Bodies Predict Record Summer for Mediterranean Destinations',
    origDesc: 'Forward bookings are up 18% year-over-year, with operators in Greece and Italy warning of capacity strain in coastal towns.',
    fakeTitle: 'Mediterranean Predicts Record Summer; Sea Reportedly "Done With This"',
    fakeDesc: 'Coastal towns warned of strain as the actual sea released a statement saying it would prefer "literally any other body of water" handle a few months this year.',
  },
];

// chat seed messages keyed by article index — gives us realistic threads
const CHAT_SEEDS = {
  0: [
    { role: 'user', text: 'Summarize this article', t: -22 },
    { role: 'assistant', text: 'The Senate passed a $612B infrastructure package 68–32 after a long session. The bill funds bridges, broadband, and rail, and now goes to the House where bipartisan support looks cautious but real.', t: -22 },
    { role: 'user', text: 'How was the original article changed?', t: -18 },
    { role: 'assistant', kind: 'diff', text: 'The fake version retains the procedural framing (vote count, dollar figure, House handoff) but pivots the substance into absurdity — replacing infrastructure outcomes with the comically narrow improvement of "slightly wider bridges."', t: -18 },
  ],
  1: [
    { role: 'user', text: 'What are the key entities mentioned?', t: -8 },
    { role: 'assistant', kind: 'entities', text: 'Extracted from the original.', t: -8 },
  ],
};

// build final article objects with stable ids and timestamps
const NOW = Date.now();
const ARTICLES = ARTICLES_RAW.map((a, i) => ({
  id: 'art_' + String(i + 1).padStart(3, '0'),
  source: SOURCES.find(s => s.id === a.sourceId),
  topic: a.topic,
  publishedAt: NOW - a.minutesAgo * 60 * 1000,
  scrapedAt: NOW - (a.minutesAgo - 5) * 60 * 1000,
  transformedAt: NOW - (a.minutesAgo - 7) * 60 * 1000,
  url: 'https://example.com/' + a.sourceId + '/' + (i + 1),
  original: { title: a.origTitle, description: a.origDesc },
  fake: { title: a.fakeTitle, description: a.fakeDesc },
  status: 'transformed', // 'scraped' | 'transforming' | 'transformed' | 'failed'
}));

function relTime(ts) {
  const m = Math.floor((Date.now() - ts) / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return m + 'm ago';
  const h = Math.floor(m / 60);
  if (h < 24) return h + 'h ago';
  const d = Math.floor(h / 24);
  return d + 'd ago';
}
function fmtTime(ts) {
  const d = new Date(ts);
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}
function fmtClock(ts) {
  return new Date(ts).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}

Object.assign(window, { SOURCES, ARTICLES, CHAT_SEEDS, relTime, fmtTime, fmtClock });
