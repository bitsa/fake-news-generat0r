# **Home Assignment: Fake News Generator**

## **Overview**

Build a full-stack application that scrapes real news articles from multiple sources, transforms them into satirical/fake versions using an LLM, displays them in a news website UI, and provides a chat interface to ask structured questions about each article.

## **Time Estimation**

**4 hours.** You are expected (and encouraged) to use AI tools. What matters is your ability to make good decisions, ship working software, and explain your tradeoffs.

## **The Task**

### **1\. News Scraper (Backend)**

Build a scraper that collects articles from these public RSS feeds:  
• <https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml> (New York Times)  
• <https://feeds.npr.org/1001/rss.xml> (NPR News)  
• <https://www.theguardian.com/world/rss> (The Guardian)  
For each article, extract: title, description/snippet, source name, publish date, and original URL. Store raw articles in the database. Scraping should run on demand via an API trigger.

### **2\. Fake News Transformer (Backend)**

For each scraped article, generate a satirical/fake version using the OpenAI API:  
• Transform the title and description into a humorous or absurd version while keeping it recognizable  
• Store both original and fake versions, linked together in the database  
• The transformation should be asynchronous \- don't block the scraping pipeline  
**Important:** The OpenAI API key will be provided as an environment variable. Do NOT commit it to the repository.

### **3\. News Website UI (Frontend)**

Build a news feed interface that displays the fake articles:  
• **News feed** \- list of fake articles with title, snippet, source, and date  
• **Article detail view** \- full fake article with a toggle to show the original  
• **Filtering** \- by source  
• All data is persisted in the database \- refreshing the page or restarting the app shows the same articles

### **4\. Chat Interface (Frontend \+ Backend)**

For each article, provide a chat panel where the user can ask structured questions such as:  
• "Summarize this article"  
• "What are the key entities mentioned?" (people, companies, locations)  
• "How was the original article changed?"  
Chat history is persisted per article in the database. Queries are handled by the backend.

## **Technical Requirements**

**Frontend:** TypeScript. Style it enough to be usable.  
**Backend:** Node.js or Python. Your choice \- justify it.  
**Database:** Relational database. Must have a proper schema with migrations.  
**LLM Integration:** We will provide an OpenAI API key. You may use any model available through the OpenAI API.  
**Docker:** docker-compose to spin up the full stack with one command.

## **What We Evaluate**

1\. **Database schema design** \- How do you model articles, sources, transformations, and chat history?  
2\. **API design** \- Endpoint structure for scraping, articles, and chat  
3\. **Async pipeline** \- How do you orchestrate the scrape-to-display flow?  
4\. **LLM integration** \- How do you interact with external LLM APIs?  
5\. **Frontend component structure** \- News feed, article detail, chat panel, state management  
6\. **Error handling** \- What happens when things go wrong?  
7\. **Code organization** \- Separation of concerns, project structure, readability  
8\. **AI-assisted development** \- What tools did you use? What was your workflow? Which parts were AI-generated vs hand-written? How did you validate and review AI output?

## **Submission**

1\. **GitHub repo** \- public, with a README containing setup instructions  
2\. **15-minute Loom video** explaining:  
• A quick demo of the working app  
• Your DB schema design and the scrape-to-display pipeline  
• How you handle LLM integration  
• Key architectural decisions and tradeoffs  
• What would you improve with more time  
• Where and how you used AI tools, and what you wrote/reviewed yourself

## **Bonus (only if time allows)**

• Scheduled scraping (cron or background job)  
• Article similarity detection (avoid scraping near-duplicates from different sources)  
• Streaming LLM responses in the chat interface

## **Important Notes**

• **Data persistence is a core requirement.** All articles, transformations, and chat messages must survive app restarts.  
• **Do not commit the OpenAI API key** to your repository. Use environment variables and document the setup in your README.  
• **The app must run with a single** docker-compose up **command.** We will test this first.  
• **Focus on working software over polish.** A functional app with rough edges beats a beautiful UI that doesn't work end-to-end.  
• **Be prepared to defend your decisions.** In the follow-up interview, we will ask about your architecture, tradeoffs, and what you would change.  
