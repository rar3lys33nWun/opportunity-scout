# Opportunity Scout — starter application

An on-demand web research dashboard for finding public business opportunities and publicly published business contact emails.

## Features
- Change target country/market on every search, including Worldwide.
- Search for investors, fundraising, partnerships, suppliers, acquisitions, tenders/RFPs, and contractors.
- Inspect public result pages and a small number of relevant same-site pages.
- Extract visible email addresses, deduplicate results, preserve source URLs and evidence excerpts.
- Export results to CSV and Excel.
- Optional one-recipient-at-a-time email sending through Resend after a human reviews contacts and records a permission/legal-basis note.

## Run locally
Requires Python 3.10+.

```bash
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL Streamlit prints (typically http://localhost:8501).

## Email sending setup
1. Create an account with Resend.
2. Verify a domain you own and configure its DNS records.
3. In the app, provide the API key and verified sender address at campaign time.
4. Review contacts and fill in the “Contact permission / lawful basis” column only after assessing eligibility.
5. Mark opt-outs in “Suppressed / unsubscribed”; suppressed contacts are excluded.

Do not use this app for unsolicited high-volume spam. Comply with CAN-SPAM, GDPR/UK GDPR, CASL, privacy rules, provider acceptable-use policies, and the laws that apply to your recipients. A public email address is not, by itself, proof of consent or permission to send marketing.

## Limitations
- Search availability depends on the DDGS search provider and may be rate-limited or change over time.
- Search snippets and keyword matches are clues, not proof that a company currently has an active need. Review evidence and dates manually.
- Email validation is basic; the app does not claim that an address is deliverable.
- This is a prototype, not a hardened multi-user SaaS. It has no login, durable database, background worker, or unsubscribe landing page. Add these before production deployment.
- Website crawling is deliberately shallow and does not bypass authentication, CAPTCHAs, robots restrictions, or access controls.
