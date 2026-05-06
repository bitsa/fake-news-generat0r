-- ============================================================================
-- Fakeline seed data
-- ----------------------------------------------------------------------------
-- 18 mock articles across NYT, NPR, The Guardian — each with a real-looking
-- "original" and a satirical "fake" version pre-baked. Use this to bring up
-- a local dev DB without hitting OpenAI.
--
-- Apply AFTER running migrations. Idempotent on re-run thanks to ON CONFLICT.
--
-- Usage:
--   docker compose exec db psql -U fakeline -d fakeline -f /seed/seed.sql
-- or, from a local psql:
--   psql "$DATABASE_URL" -f api/alembic/seed.sql
-- ============================================================================

BEGIN;

-- ---- sources ---------------------------------------------------------------
INSERT INTO sources (id, name, short_name, feed_url) VALUES
  ('nyt', 'The New York Times', 'NYT', 'https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml'),
  ('npr', 'NPR News',           'NPR', 'https://feeds.npr.org/1001/rss.xml'),
  ('grd', 'The Guardian',       'GRD', 'https://www.theguardian.com/world/rss')
ON CONFLICT (id) DO UPDATE SET
  name       = EXCLUDED.name,
  short_name = EXCLUDED.short_name,
  feed_url   = EXCLUDED.feed_url;

-- ---- articles + transformations -------------------------------------------
-- Articles use deterministic UUIDv5-style IDs derived from external_url so
-- re-running the seed is idempotent. Timestamps are anchored to NOW() so the
-- feed always looks fresh in dev.

WITH seed(seq, source_id, ext_url, ext_guid, topic, minutes_ago, orig_title, orig_desc, fake_title, fake_desc) AS (
  VALUES
    (1,  'nyt',   'https://example.com/nyt/1',  'nyt-001', 'Politics',   14,
      'Senate Passes Bipartisan Infrastructure Bill After Marathon Session',
      'The $612 billion package, approved 68-32, funds bridges, broadband, and rail. It now heads to the House, where moderates in both parties signal cautious support.',
      'Senate Passes Bipartisan Bill to Replace All Bridges With Slightly Wider Bridges',
      'After a 19-hour session sustained largely by lukewarm vending-machine soup, lawmakers approved a $612 billion package that pundits described as "broadly the same, but six inches roomier."'),
    (2,  'npr',   'https://example.com/npr/2',  'npr-002', 'Tech',       28,
      'AI Models Now Power Customer Service at 4 of the Top 5 US Banks',
      'A new survey finds large language models handling more than 60% of first-line banking inquiries, raising fresh questions about oversight, error rates, and consumer recourse.',
      'AI Now Handles 60% of Bank Calls; Remaining 40% Are People Yelling at AI',
      'A new survey confirms that the financial sector has finally achieved the long-promised efficiency of having a chatbot apologize to you in 14 different ways before transferring you to a different chatbot.'),
    (3,  'grd',   'https://example.com/grd/3',  'grd-003', 'Climate',    41,
      'European Heatwave Breaks April Records From Lisbon to Warsaw',
      'Temperatures hit 36C in southern Spain as meteorologists warn the early-season heat is consistent with long-running climate trends across the continent.',
      'European Heatwave Breaks Records, Several Calendars',
      'Temperatures climbed so high in Lisbon that the month of April formally requested to be reclassified as "early August," a motion meteorologists called "fair, honestly."'),
    (4,  'nyt',   'https://example.com/nyt/4',  'nyt-004', 'Markets',    55,
      'Tech Stocks Slide as Investors Reassess AI Spending Plans',
      'The Nasdaq fell 1.8% as analysts at three major banks downgraded forward earnings expectations for hyperscalers, citing capex outpacing near-term revenue.',
      'Tech Stocks Plunge After Investors Read One (1) Footnote',
      'The Nasdaq shed 1.8% Monday after a junior analyst at a mid-tier bank scrolled to page 47 of a 10-Q and audibly said "huh."'),
    (5,  'npr',   'https://example.com/npr/5',  'npr-005', 'Health',     72,
      'CDC Reports Sharp Decline in Seasonal Flu Cases This Spring',
      'The agency credits high vaccine uptake and lingering pandemic-era hygiene habits, though officials warn the next strain remains unpredictable.',
      'CDC Reports Flu Down 40%, Says Nation Has "Maybe Finally Learned to Wash Its Hands"',
      'In a press briefing notable for its visible weariness, officials thanked the public for what they described as "a solid C+ effort, which, for us, is a national triumph."'),
    (6,  'grd',   'https://example.com/grd/6',  'grd-006', 'World',      96,
      'UK Government Faces Backlash Over New Housing Targets',
      'Local councils across England warn the proposed 1.5 million-home target is unworkable without significant changes to planning law and funding.',
      'UK Promises 1.5 Million Homes; Local Councils Promise to Hold Meetings About It',
      'A spokesperson for the Local Government Association said councils stand "fully ready" to commission consultations to study the feasibility of forming a steering committee.'),
    (7,  'nyt',   'https://example.com/nyt/7',  'nyt-007', 'Culture',   130,
      'Broadway Box Office Rebounds to Pre-Pandemic Highs',
      'Weekly grosses topped $46 million, led by a wave of new musicals and a surprise revival drawing tourists back to Times Square.',
      'Broadway Hits Pre-Pandemic Highs; Tourists Confirm They Still Don''t Know Where 47th Street Is',
      'Weekly grosses topped $46 million as visitors successfully located their theaters via the time-honored method of standing very still and turning slowly in a circle.'),
    (8,  'npr',   'https://example.com/npr/8',  'npr-008', 'Tech',      165,
      'Open-Source AI Project Reaches 100,000 Contributors',
      'The milestone, announced on the project''s blog, marks a significant shift in how foundation models are developed outside of large corporate labs.',
      'Open-Source AI Project Hits 100,000 Contributors, 99,400 of Whom Just Fixed a Typo',
      'Maintainers celebrated the milestone with a quiet weep into a coffee mug labeled "I REVIEWED THIS PR."'),
    (9,  'grd',   'https://example.com/grd/9',  'grd-009', 'Sports',    210,
      'Premier League Title Race Tightens After Surprise Weekend Results',
      'Two of the top three sides dropped points, leaving the table separated by a single goal difference with five matches to play.',
      'Premier League Race Tightens; Pundits Forced to Use the Phrase "Goal Difference" Out Loud',
      'Broadcasters scrambled to find a graphic capable of displaying a number with a minus sign, eventually settling on "an angry red one."'),
    (10, 'nyt',   'https://example.com/nyt/10', 'nyt-010', 'Business',  250,
      'Major Airline Announces Return of Free Checked Bags on Domestic Routes',
      'The shift, framed as a competitive response, reverses a decade-old policy and is expected to pressure rivals to match within weeks.',
      'Airline Brings Back Free Checked Bags; Charges $40 to Look at Them',
      'A spokesperson clarified that while the bags themselves are free, "visual contact" with one''s luggage will be billed separately as a "Sightline Service Fee."'),
    (11, 'npr',   'https://example.com/npr/11', 'npr-011', 'Education', 305,
      'Universities Roll Out New Policies on AI Use in Coursework',
      'Drafts vary widely across campuses; some require disclosure, others ban use outright. Students and faculty are split on enforcement realism.',
      'Universities Unveil New AI Policies; Students Use AI to Read Them',
      'Faculty senates released 47-page guidance documents on permissible AI use, immediately summarized by every undergraduate into a 200-character TL;DR.'),
    (12, 'grd',   'https://example.com/grd/12', 'grd-012', 'Climate',   360,
      'New Study Links Coastal Erosion to Accelerating Storm Patterns',
      'Researchers tracked 30 sites along the North Atlantic, finding a measurable increase in shoreline retreat over the past decade.',
      'Coast Erodes 12%, Politely Asks if Anyone Has a Plan',
      'The North Atlantic was reached for comment but said it had "honestly given up trying to get anyone''s attention" and just wanted to be left alone.'),
    (13, 'nyt',   'https://example.com/nyt/13', 'nyt-013', 'Tech',      420,
      'Self-Driving Truck Pilot Expands to Three Additional Interstates',
      'The expansion follows a year of supervised runs. Regulators say full autonomous operation remains contingent on weather-handling improvements.',
      'Self-Driving Trucks Expand to More Highways; Honking Now Done by Algorithm',
      'Engineers confirmed that the trucks are fully capable of expressing road rage at a rate equivalent to "1.4 angry cab drivers per mile."'),
    (14, 'npr',   'https://example.com/npr/14', 'npr-014', 'Politics',  510,
      'Mayoral Race in Chicago Heads to Runoff After Tight First Round',
      'No candidate cleared the 50% threshold, setting up a six-week runoff that is expected to focus on public safety and budget priorities.',
      'Chicago Mayoral Race Heads to Runoff; Both Candidates Promise to "Fix the Thing"',
      'Polling indicates voters strongly favor "fixing the thing" over the alternative of "not fixing the thing," with a small but persistent third group preferring "complaining about the thing."'),
    (15, 'grd',   'https://example.com/grd/15', 'grd-015', 'Science',   600,
      'Astronomers Detect Unusual Radio Signal From Nearby Galaxy',
      'The repeating burst, traced to a region 2.5 million light-years away, has prompted a coordinated follow-up by observatories across three continents.',
      'Astronomers Detect Mysterious Radio Signal; It''s Just Their Microwave Again',
      'After 14 hours of careful triangulation, researchers traced the burst to the staff kitchen, where a postdoc was reheating leftover pad thai for the third time.'),
    (16, 'nyt',   'https://example.com/nyt/16', 'nyt-016', 'Food',      720,
      'Restaurant Industry Reports Highest Margins in a Decade',
      'Operators credit menu engineering, leaner staffing models, and a small but persistent shift toward higher-priced tasting formats.',
      'Restaurants Post Record Margins After Discovering You Will Pay $26 for One (1) Egg',
      'Operators credit a breakthrough technique known as "putting it on a small plate and calling it Mediterranean."'),
    (17, 'npr',   'https://example.com/npr/17', 'npr-017', 'Tech',      880,
      'Federal Agency Issues First Guidelines on Synthetic Media Labeling',
      'Platforms will be required to surface provenance metadata on AI-generated content meeting certain thresholds, beginning next year.',
      'Federal Agency Mandates Labels on AI Content; AI Asked to Write the Labels',
      'The agency confirmed that the labels themselves will be drafted by an AI, reviewed by a different AI, and approved by a committee of two AIs and one increasingly nervous person.'),
    (18, 'grd',   'https://example.com/grd/18', 'grd-018', 'Travel',   1100,
      'Tourism Bodies Predict Record Summer for Mediterranean Destinations',
      'Forward bookings are up 18% year-over-year, with operators in Greece and Italy warning of capacity strain in coastal towns.',
      'Mediterranean Predicts Record Summer; Sea Reportedly "Done With This"',
      'Coastal towns warned of strain as the actual sea released a statement saying it would prefer "literally any other body of water" handle a few months this year.')
),
inserted_articles AS (
  INSERT INTO articles (source_id, external_url, external_guid, title, description, topic,
                        published_at, scraped_at, status)
  SELECT
    s.source_id,
    s.ext_url,
    s.ext_guid,
    s.orig_title,
    s.orig_desc,
    s.topic,
    NOW() - (s.minutes_ago || ' minutes')::interval,
    NOW() - ((s.minutes_ago - 5) || ' minutes')::interval,
    'transformed'
  FROM seed s
  ON CONFLICT (source_id, external_url) DO UPDATE SET
    title       = EXCLUDED.title,
    description = EXCLUDED.description,
    topic       = EXCLUDED.topic,
    status      = 'transformed'
  RETURNING id, external_url
)
INSERT INTO transformations (article_id, fake_title, fake_description, model, prompt_version, created_at)
SELECT
  ia.id,
  s.fake_title,
  s.fake_desc,
  'gpt-4o-mini',
  'v1',
  NOW() - ((s.minutes_ago - 7) || ' minutes')::interval
FROM seed s
JOIN inserted_articles ia ON ia.external_url = s.ext_url
ON CONFLICT (article_id) DO UPDATE SET
  fake_title       = EXCLUDED.fake_title,
  fake_description = EXCLUDED.fake_description,
  model            = EXCLUDED.model,
  prompt_version   = EXCLUDED.prompt_version;

-- ---- chat seeds (one realistic thread for article #1) ---------------------
-- Lets you verify the chat UI without hitting the LLM. Persistence test:
-- reload the article page and these should still be there.

DO $$
DECLARE
  art_id UUID;
BEGIN
  SELECT id INTO art_id
  FROM articles
  WHERE source_id = 'nyt' AND external_url = 'https://example.com/nyt/1';

  IF art_id IS NULL THEN RETURN; END IF;

  -- only seed if this article has no chat history yet
  IF NOT EXISTS (SELECT 1 FROM chat_messages WHERE article_id = art_id) THEN
    INSERT INTO chat_messages (article_id, role, content, kind, payload, created_at) VALUES
      (art_id, 'user',
       'Summarize this article',
       NULL, NULL,
       NOW() - interval '22 minutes'),
      (art_id, 'assistant',
       'The Senate passed a $612B infrastructure package 68–32 after a long session. The bill funds bridges, broadband, and rail, and now goes to the House where bipartisan support looks cautious but real.',
       NULL, NULL,
       NOW() - interval '22 minutes'),
      (art_id, 'user',
       'How was the original article changed?',
       NULL, NULL,
       NOW() - interval '18 minutes'),
      (art_id, 'assistant',
       'The fake version retains the procedural framing (vote count, dollar figure, House handoff) but pivots the substance into absurdity — replacing infrastructure outcomes with the comically narrow improvement of "slightly wider bridges."',
       'diff',
       jsonb_build_object(
         'tokens', jsonb_build_array(
           jsonb_build_object('t', 'eq',  'v', 'Senate Passes Bipartisan '),
           jsonb_build_object('t', 'del', 'v', 'Infrastructure Bill After Marathon Session'),
           jsonb_build_object('t', 'add', 'v', 'Bill to Replace All Bridges With Slightly Wider Bridges')
         )
       ),
       NOW() - interval '18 minutes');
  END IF;
END $$;

COMMIT;

-- ============================================================================
-- Sanity checks (run manually):
--   SELECT count(*) FROM articles;           -- 18
--   SELECT count(*) FROM transformations;    -- 18
--   SELECT count(*) FROM chat_messages;      -- 4 (seeded thread)
-- ============================================================================
