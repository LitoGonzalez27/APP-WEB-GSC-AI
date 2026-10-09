# -*- coding: utf-8 -*-
"""Base de conocimiento CMO-friendly.

Para cada check: qué falla (sin jerga), por qué le importa al negocio,
cómo se arregla (instrucción lista para el equipo técnico) y esfuerzo × impacto.
El dashboard usa estos textos cuando un check puntúa 0 o 0.5.
"""

KB = {
    "1.1": {
        "titulo": "The robots instruction file isn't working",
        "por_que": "It's the front door: if robots.txt fails or returns an error page, AI systems don't know what they can read and many simply leave. You're invisible because of a 5-minute fix.",
        "como": "Serve /robots.txt as plain text with HTTP 200. If the site is a SPA, exclude /robots.txt from the framework's routing.",
        "esfuerzo": "Low", "impacto": "High",
    },
    "1.2": {
        "titulo": "There's no deliberate decision about which AIs can read the site",
        "por_que": "Without explicit rules, either you allow everything with no control or —worse— someone blocked 'AI' altogether and took you out of ChatGPT and Perplexity answers, where your customers are already searching. Each bot has a different job: blocking the training bot doesn't take you out of answers; blocking the search bot does.",
        "como": "Define per-bot rules in robots.txt: allow OAI-SearchBot, ChatGPT-User and PerplexityBot (visibility); decide on GPTBot/ClaudeBot/Google-Extended (training) according to your strategy.",
        "esfuerzo": "Low", "impacto": "High",
    },
    "1.3": {
        "titulo": "What you say you allow and what your firewall does don't match",
        "por_que": "Your robots.txt says 'come in' but the firewall/CDN slams the door on AI bots. You think you're open and you're not: zero AI visibility without anyone having decided it.",
        "como": "Review the WAF/CDN rules (Cloudflare, Akamai…) and align the list of allowed bots with robots.txt. Then verify with test requests using each bot's user-agent.",
        "esfuerzo": "Medium", "impacto": "High",
    },
    "1.4": {
        "titulo": "The sitemap is missing or out of date",
        "por_que": "The sitemap is the official list of content you offer to AI systems. Without it (or with a stale one), they discover your pages late, badly or never — especially the new ones, which are the ones you want them to cite.",
        "como": "Generate sitemap.xml automatically with real lastmod dates, reference it in robots.txt and regenerate it with every publication.",
        "esfuerzo": "Low", "impacto": "Medium",
    },
    "1.5": {
        "titulo": "Discovery signals are missing from the headers",
        "por_que": "It's a minor technical signal that the most advanced systems use to find their way. Not urgent: it's one of the cheap things that set you apart once the basics are in place.",
        "como": "Add Link headers (RFC 8288) with canonical/alternate/api relations to the server responses.",
        "esfuerzo": "Low", "impacto": "Low",
    },
    "1.6": {
        "titulo": "Some key content is hidden behind a login or walls",
        "por_que": "An AI agent arrives as an anonymous visitor: if the content you want it to cite (products, prices, services) requires registration or is covered by notices, it doesn't exist for the AI, and it will cite the competitor that does show it.",
        "como": "Make sure business pages render their full content without a session or interaction. Notices (cookies, popups) must not block the content's HTML.",
        "esfuerzo": "Medium", "impacto": "High",
    },
    "1.7": {
        "titulo": "The domain doesn't announce its AI capabilities at DNS level",
        "por_que": "DNS-AID is the experimental standard for agents to discover what a domain offers before even visiting it. To be honest: almost nobody has it and no mainstream agent queries it yet. It's an early-mover positioning check, not a results one.",
        "como": "Publish a discovery TXT record (_aid) in DNS pointing to the site's capabilities. 15 minutes of work once the standard matures.",
        "esfuerzo": "Low", "impacto": "Low (today)",
    },
    "2.1": {
        "titulo": "You don't declare what AI can do with your content",
        "por_que": "Content Signals are the emerging way to say 'you can use this to answer, not to train'. Only 4% of sites do it: declaring it puts you in the leading group and protects your interests without giving up visibility.",
        "como": "Add Content Signals to robots.txt declaring the purpose of each use: search=yes (visible in AI search engines), ai-input=yes (eligible to be cited in answers — the GEO lever), ai-train according to your intellectual property strategy.",
        "esfuerzo": "Low", "impacto": "Medium",
    },
    "2.2": {
        "titulo": "Nobody monitors which AI bots come in or what they cost you",
        "por_que": "Without a control panel, you don't know who reads you, how often or at what server cost. You can't manage (or monetize) what you don't measure.",
        "como": "Turn on AI crawler management in the CDN (in Cloudflare: AI Crawl Control, included in paid plans) and review the report monthly.",
        "esfuerzo": "Low", "impacto": "Medium",
    },
    "2.3": {
        "titulo": "You don't verify agents' real identity",
        "por_que": "Anyone can pose as an 'OpenAI bot'. The emerging standard (Web Bot Auth) lets you cryptographically verify who is who. Today it's getting ahead; in 1-2 years it will be the norm.",
        "como": "Enable verification of signed bots in the CDN (Cloudflare Verified Bots). Note it on the roadmap, not as an urgent item.",
        "esfuerzo": "Medium", "impacto": "Low (today)",
    },
    "2.4": {
        "titulo": "Traffic control kicks out the good bots",
        "por_que": "An overly aggressive limit bans legitimate AI bots after a few pages: they read 5% of your site and leave. Result: you appear rarely and poorly in answers.",
        "como": "Configure gentle rate limiting for verified bots (HTTP 429 with Retry-After instead of a permanent 403 ban).",
        "esfuerzo": "Medium", "impacto": "Medium",
    },
    "3.1": {
        "titulo": "The content has no structured data (or it's broken)",
        "por_que": "Structured data is the spec sheet AI reads without guessing: what you sell, at what price, who you are. Without it, AI interprets by eye — and when it guesses, it gets YOUR price and YOUR brand wrong.",
        "como": "Implement valid JSON-LD on every template (Organization, Product, Article, FAQPage as appropriate) and validate it with the Rich Results Test in CI.",
        "esfuerzo": "Medium", "impacto": "High",
    },
    "3.2": {
        "titulo": "Your brand identity isn't declared for machines",
        "por_que": "If you don't declare who you are (brand, logo, official profiles), AI may confuse you with someone else, describe you wrongly or fail to link you to your own mentions. The entity is the foundation of all AI visibility.",
        "como": "Add a complete Organization schema on the home page: name, url, logo, sameAs (social profiles, Wikipedia if it exists) and contactPoint.",
        "esfuerzo": "Low", "impacto": "High",
    },
    "3.3": {
        "titulo": "Product pages don't provide the minimum purchase data",
        "por_que": "Without structured price, currency and availability, a shopping assistant can't recommend your products with confidence — and it will recommend the competitor's that do. It's the entry requirement for conversational commerce.",
        "como": "Complete the Product/Offer schema on every product page: price, priceCurrency, availability, plus name, image, brand and GTIN/SKU.",
        "esfuerzo": "Medium", "impacto": "High",
    },
    "3.4": {
        "titulo": "Products/content are 'bare' of attributes",
        "por_que": "The more structured attributes (brand, material, dimensions, ratings), the more customer questions AI can answer with your data: 'is it cotton?', 'what do people think?'. Every missing attribute is an answer you don't feature in.",
        "como": "Enrich the markup with GTIN, SKU, brand, material, color, size, aggregateRating and review where they exist. For content: author, datePublished, dateModified.",
        "esfuerzo": "Medium", "impacto": "Medium",
    },
    "3.5": {
        "titulo": "The page structure doesn't communicate hierarchy",
        "por_que": "Agents understand the page through its skeleton (headings, sections, real buttons). A 'div soup' works for the human eye but is unreadable for a machine: it doesn't know what's a heading, what's navigation or what's a button.",
        "como": "Use semantic HTML: a single h1, a coherent h2/h3 hierarchy, landmarks (main, nav, header, footer), real <button> elements and labels on forms.",
        "esfuerzo": "Medium", "impacto": "Medium",
    },
    "3.6": {
        "titulo": "There are controls an agent sees but doesn't know what they do",
        "por_que": "The browser turns your site into an accessibility tree, and that's what AI agents consume: they get a list of controls with their role and their NAME. A button with no name, or called 'link' or 'see more', reaches the agent as a blank box: it can press it, but it can't decide whether it should. That's where an agent gets lost or presses the wrong thing — and where the purchase someone asked it to make on your site falls through.",
        "como": "Give every actionable control its own name: visible text inside the <button>/<a>, or aria-label if it's an icon ('Add to cart', not 'Add'). Image-only links need descriptive alt text. Replace generic texts ('see more', 'here', 'link') with what they actually do. Check it yourself: in Chrome, Inspect → Elements → Accessibility → Show Accessibility Tree.",
        "esfuerzo": "Medium", "impacto": "High",
    },
    "4.1": {
        "titulo": "The content only exists if JavaScript runs",
        "por_que": "AI crawlers (those of ChatGPT, Claude or Perplexity) do NOT run JavaScript. If your site is built in the browser, to them it's EMPTY: it's the most serious failure possible — the equivalent of having no website in the AI channel.",
        "como": "Implement server-side rendering (SSR) or pre-rendering (SSG) so the HTML arrives complete: content, prices and CTAs present without running JS.",
        "esfuerzo": "High", "impacto": "Critical",
    },
    "4.2": {
        "titulo": "The price or the buy button isn't in the base HTML",
        "por_que": "If the price is painted with JavaScript, AI systems don't see it or cite an old one. An assistant that doesn't see the price doesn't recommend the product.",
        "como": "Render price, availability and CTA in the server HTML, consistent with the Product/Offer schema.",
        "esfuerzo": "Medium", "impacto": "High",
    },
    "4.3": {
        "titulo": "The site responds too slowly for AI systems",
        "por_que": "When ChatGPT queries your site live to answer a user, it has a budget of seconds. If you don't make it, it answers with your competitor's source. Slowness here doesn't lower your rankings: it erases you from the answer.",
        "como": "Optimize TTFB to below 0.8s: full-page cache, CDN, and review the origin server's response time.",
        "esfuerzo": "Medium", "impacto": "High",
    },
    "4.4": {
        "titulo": "Not every piece of content can be reached with a direct link",
        "por_que": "Agents navigate by URLs, not clicks. If a product or state can only be reached by interacting (filters, sessions), the agent can't return to it or recommend it with a link.",
        "como": "Give every relevant product, variant and state a unique, stable URL; verify they open in incognito without a session.",
        "esfuerzo": "Medium", "impacto": "Medium",
    },
    "4.5": {
        "titulo": "There's no documented programmatic access",
        "por_que": "The next level: an agent doesn't have to 'read' your site but can query it as a service. Without a documented API, every interaction is fragile scraping.",
        "como": "Publish an OpenAPI spec of the public endpoints (catalog, availability, search) at /openapi.json.",
        "esfuerzo": "High", "impacto": "Medium (growing)",
    },
    "4.6": {
        "titulo": "The page 'jumps' while loading (unstable layout)",
        "por_que": "Agents that operate your site take screenshots between actions. If the layout reshuffles while loading (banners pushing content, images without reserved height), the agent clicks where the button NO LONGER is — just as happens to your users. A high CLS breaks agent tasks and human conversions at the same time.",
        "como": "Reserve dimensions for images/embeds (width/height or aspect-ratio), load banners and notices without shifting content, and keep CLS ≤ 0.1 on key templates.",
        "esfuerzo": "Medium", "impacto": "Medium",
    },
    "4.7": {
        "titulo": "Some buttons and links are too small for an agent to hit",
        "por_que": "An agent operating your site clicks by coordinates on a screenshot; it doesn't 'understand' the button the way you do. If a control is under 24 pixels, the click misses or hits the one next to it, and the task breaks right at the final step. It's exactly the same problem a user has with a finger on a phone: what you fix for the agent you fix for your customers.",
        "como": "Ensure a minimum clickable area of 24×24 px (WCAG 2.2 'Target Size') on every control, enlarging with padding rather than making the icon bigger. And make sure every clickable element has cursor:pointer and is a real <button>/<a>, not a div with onclick.",
        "esfuerzo": "Low", "impacto": "Medium",
    },
    "4.8": {
        "titulo": "Pages that don't exist return 'all good'",
        "por_que": "It's the most dangerous silent failure for an agent. A person sees the 'page not found' message and turns back; the agent only looks at the response code, reads 200 = 'success' and keeps working on an empty page. The error spreads without anyone noticing and ends up as made-up data or a task abandoned halfway.",
        "como": "Return a real HTTP 404 (or 410) on non-existent URLs, never 200 or a redirect to the home page. And make the error page include navigation or a search box so the agent can recover instead of hitting a dead end.",
        "esfuerzo": "Low", "impacto": "High",
    },
    "5.1": {
        "titulo": "The pages don't answer: they beat around the bush",
        "por_que": "LLMs cite the fragment that best answers. If your first lines are 'welcome to the leading website…', the citable answer is somewhere else — usually on the competitor's site that gets straight to the point.",
        "como": "Rewrite key pages with the answer in the first block after the H1 (30-100 direct words), and the detail afterwards.",
        "esfuerzo": "Medium", "impacto": "High",
    },
    "5.2": {
        "titulo": "The content isn't split into self-explanatory sections",
        "por_que": "AI doesn't read your whole page: it extracts chunks. If each section doesn't make sense on its own (descriptive heading + self-contained content), the extracted chunk loses its meaning and doesn't get cited.",
        "como": "Structure with descriptive question- or statement-style H2/H3s ('How much X costs', 'X vs Y') and 40-300-word sections that work out of context.",
        "esfuerzo": "Medium", "impacto": "High",
    },
    "5.3": {
        "titulo": "The content doesn't show who wrote it or when",
        "por_que": "AI systems weigh source reliability when choosing whom to cite. Without an identifiable author, date or sources, your content competes at a disadvantage against content that does demonstrate authority.",
        "como": "Add an author with a linked bio, visible dates also in the schema (datePublished/dateModified), and cited sources in expert content.",
        "esfuerzo": "Low", "impacto": "Medium",
    },
    "5.5": {
        "titulo": "The guide file for LLMs (llms.txt) is missing",
        "por_que": "To be honest: today almost no LLM reads it (97% never get a visit). But it takes an hour, Google already measures it in Lighthouse, and having it leaves you ready if it takes off. Hygiene, not a lever.",
        "como": "Publish /llms.txt in Markdown with the site structure and links to the key pages.",
        "esfuerzo": "Low", "impacto": "Low",
    },
    "5.6": {
        "titulo": "The site doesn't offer a lightweight version for machines (Markdown)",
        "por_que": "An agent that asks for your page 'in Markdown' (content negotiation) gets heavy HTML it has to clean up, spending tokens and losing accuracy. Serving Markdown directly makes your content cheaper and more reliable to consume — only 3.9% of sites do it, and it's one of the 4 dimensions Cloudflare's scanner scores.",
        "como": "Configure content negotiation on the server/CDN: when a request arrives with Accept: text/markdown, serve the Markdown version of the page (Cloudflare offers it as a feature; it can also be generated at build time).",
        "esfuerzo": "Medium", "impacto": "Medium (growing)",
    },
    "1.8": {
        "titulo": "Basic citation metadata is missing from the pages",
        "por_que": "Canonical, language and Open Graph are the minimum a system uses to identify and cite a page. Without canonical, citations get split across variants of the same URL; without lang, the language is guessed; without og:image/og:type, the preview comes out broken when someone shares your content.",
        "como": "Add to every template: <link rel=canonical>, lang on <html>, and the og:image and og:type metas. It's template configuration, not content: once per page type.",
        "esfuerzo": "Low", "impacto": "Medium",
    },
    "3.7": {
        "titulo": "The brand doesn't exist as an entity on Wikipedia/Wikidata",
        "por_que": "Wikipedia is the single largest source of citations in AI answers, and Wikidata is the graph systems use to disambiguate who you are. Without an item with your domain as the official website (P856), AI can't verify your identity or tell you apart from namesakes: you're competing without an entry in the registry they consult most.",
        "como": "Create (or claim) the brand's Wikidata item with the P856 property pointing to the domain, notability permitting. If there's enough press coverage, consider a Wikipedia article — keeping the conflict-of-interest rules in mind: better proposed with sources than self-published.",
        "esfuerzo": "Medium", "impacto": "High",
    },
    "4.9": {
        "titulo": "Some redirects leave an agent without JS stranded",
        "por_que": "A meta-refresh or location.href stub only works by running JavaScript or waiting: an agent reading the HTML stays on the intermediate page, and a hop to another domain breaks the citation's attribution. Every stub is one of your pages that agents read as empty.",
        "como": "Replace meta-refresh and JavaScript redirects with server-side HTTP 301/308 redirects, and avoid your own URLs ending up serving content from another domain.",
        "esfuerzo": "Low", "impacto": "Medium",
    },
    "5.7": {
        "titulo": "Verifiable trust pages (who's behind the site) are missing",
        "por_que": "Before recommending, an agent checks the same things a careful person would: who's behind it (About), how to get in touch and the legal basis. If it can't find them or they're empty, your content competes with less trust — it's E-E-A-T at site level, not article level.",
        "como": "Publish, and link from the footer, About us/About me, Contact and Privacy/Legal notice pages with real content (not empty templates), and make sure they're in the sitemap.",
        "esfuerzo": "Low", "impacto": "Medium",
    },
    "5.8": {
        "titulo": "Some pages don't fit in an agent's context",
        "por_que": "A page whose text exceeds ~25K tokens isn't read in full: the agent truncates it, and what's truncated gets cited badly or ignored. It usually gives away auto-generated endless pages or entire archives dumped into one URL.",
        "como": "Split endless pages into per-topic URLs (better for classic SEO too), and move long dumps (changelogs, full listings) to their own linked pages.",
        "esfuerzo": "Medium", "impacto": "Low",
    },
    "6.1": {
        "titulo": "The site doesn't offer any 'service window' for agents",
        "por_que": "Agents prefer querying a structured service (MCP) to interpreting HTML. Fewer than 15 of the 200,000 most visited sites offer one: whoever has it first in their sector will be the 'easy' site agents use by default.",
        "como": "Consider exposing an MCP server (or NLWeb, which reuses the existing schema) with the key capabilities: browse the catalog, check availability, book/buy.",
        "esfuerzo": "High", "impacto": "High (future bet)",
    },
    "6.2": {
        "titulo": "The forms are hard for an agent to operate",
        "por_que": "An agent trying to request a quote or sign up needs labelled fields and real buttons. Forms without labels or with a CAPTCHA at every step mean abandoned tasks — and the agent takes the conversion elsewhere.",
        "como": "Bind every field to its label with <label for='id'> (it's not enough for the label to sit next to it), add standard autocomplete so the agent knows what each field asks for, and reserve CAPTCHA for risk signals instead of for everyone.",
        "esfuerzo": "Medium", "impacto": "Medium",
    },
    "6.3": {
        "titulo": "Real agent test pending",
        "por_que": "The definitive test: give an agent (Operator, Claude) a real task on the site and see where it gets stuck. The video of it getting stuck is worth more than any report for understanding the problem.",
        "como": "Guided session: define a typical customer task and document the agent's execution step by step.",
        "esfuerzo": "Low", "impacto": "Diagnostic",
    },
    "6.4": {
        "titulo": "An agent can't sign in to the private area",
        "por_que": "Everything behind the login (orders, quotes, invoices, history) is invisible and inoperable for an assistant acting on your customer's behalf. If there's also a CAPTCHA, the block is total: you're shutting the door on the user's own legitimate agent, not on an attacker. The right pattern isn't giving the agent the password, but offering delegated permission.",
        "como": "Ideal: expose discoverable OAuth 2.0 (/.well-known/oauth-authorization-server) so the agent gets a scoped permission without handling the password. Minimum: a login form with autocomplete='username' and 'current-password', with no CAPTCHA in the normal flow (reserve it for suspicious attempts).",
        "esfuerzo": "High", "impacto": "High",
    },
    "7.5": {
        "titulo": "Shipping times and costs can't be read automatically",
        "por_que": "When an assistant compares your store with two others, shipping decides the purchase as much as price does. If your terms are in prose or on a separate page, the agent can't find them: either it discards you for lack of data or —worse— it makes up a delivery time and creates a support issue when the order doesn't arrive when promised.",
        "como": "Add shippingDetails (OfferShippingDetails) inside each product's Offer, with shippingRate, deliveryTime and shippingDestination. It's the same markup Google Merchant Center already requires, so it can usually be reused.",
        "esfuerzo": "Medium", "impacto": "High",
    },
    "7.6": {
        "titulo": "The returns policy isn't in a format AI understands",
        "por_que": "Returns are the safety net that makes an agent dare to buy on its own. Without that structured data, a cautious assistant picks the competitor that does declare '30 days, free'. Having a good policy and not publishing it in a readable way is losing the sale while holding the winning argument.",
        "como": "Declare hasMerchantReturnPolicy (MerchantReturnPolicy) with merchantReturnDays, returnPolicyCategory and returnMethod in the product's Offer, and keep it in sync with the actual policy.",
        "esfuerzo": "Medium", "impacto": "High",
    },
    "7.1": {
        "titulo": "The catalog isn't ready for shopping assistants",
        "por_que": "ChatGPT already lets people buy inside the chat (with Etsy and over a million Shopify stores). To appear there, your catalog must be ingestible in a structured way. Without a feed, you don't exist in the conversational shop window.",
        "como": "Generate a complete product feed (Google Merchant style) and keep it in sync; if the store runs on Shopify/WooCommerce, turn on the native integrations.",
        "esfuerzo": "Medium", "impacto": "High",
    },
    "7.2": {
        "titulo": "The marked-up price and the visible price don't match",
        "por_que": "If your own data contradicts itself, the shopping assistant will serve the wrong price: complaints, broken carts and distrust. It's the most dangerous error in the AI channel because it involves money.",
        "como": "Sync the JSON-LD with the real price/stock on every render (same data source) and audit consistency weekly.",
        "esfuerzo": "Medium", "impacto": "Critical",
    },
    "7.3": {
        "titulo": "The checkout isn't ready for agent purchases",
        "por_que": "The agentic commerce standard (ACP, from OpenAI and Stripe) is already running in production. The good news: the merchant remains the official seller and keeps the customer. Whoever integrates first shows up first in 'buy in ChatGPT'.",
        "como": "Verify that the PSP supports the Delegated Payment Spec (Stripe already does); apply for access to OpenAI's commerce program; prepare the catalog for ACP ingestion.",
        "esfuerzo": "High", "impacto": "High (window of opportunity)",
    },
}


def advice_for(check_id):
    return KB.get(check_id)
