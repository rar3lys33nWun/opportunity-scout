import os, re, time, json, io
from urllib.parse import urlparse, urljoin
from datetime import datetime, timezone
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from ddgs import DDGS

APP_TITLE = "Opportunity Scout"
USER_AGENT = "OpportunityScout/1.0 (public business research; contact: admin@example.com)"
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
HEADERS = {"User-Agent": USER_AGENT}
OPPORTUNITY_TERMS = {
    "Seeking investors/funding": ["seeking investors", "raising capital", "seeking funding", "fundraising", "investment opportunity", "seed funding", "series a"],
    "Seeking business partners": ["seeking partners", "strategic partner", "partnership opportunity", "joint venture", "channel partner"],
    "Seeking suppliers/distributors": ["seeking suppliers", "supplier application", "looking for distributors", "become a supplier", "vendor registration"],
    "Acquisition / M&A": ["seeking acquisitions", "acquisition opportunities", "looking to acquire", "business for sale", "merger and acquisition"],
    "Tenders / RFPs": ["request for proposal", "request for proposals", "request for quotation", "open tender", "invitation to bid", "rfp"],
    "Seeking customers / contractors": ["request for bids", "seeking contractors", "vendor opportunity", "service provider needed"],
    "Investor seeking companies": ["investment criteria", "portfolio companies", "we invest in", "looking to invest", "investment thesis"],
}

st.set_page_config(page_title=APP_TITLE, page_icon="🔎", layout="wide")
st.title("🔎 Opportunity Scout")
st.caption("On-demand company discovery, opportunity research, and public business-contact collection.")

with st.sidebar:
    st.header("Search instructions")
    query = st.text_input("What are you looking for?", value="companies seeking logistics partners")
    country = st.selectbox("Country / market", ["Worldwide", "United States", "United Kingdom", "Canada", "Australia", "Nigeria", "Germany", "India", "Other"])
    other_country = st.text_input("Other country (if selected)", "") if country == "Other" else ""
    categories = st.multiselect("Opportunity types", list(OPPORTUNITY_TERMS.keys()), default=["Seeking investors/funding", "Seeking business partners", "Tenders / RFPs"])
    max_results = st.slider("Search results to inspect", 5, 50, 15, 5)
    pages_per_site = st.slider("Pages to inspect per site", 1, 5, 3)
    st.caption("Country is changeable on every run. Search results and contact availability depend on public sources.")

def detect_categories(text):
    low = text.lower()
    found = []
    for category, terms in OPPORTUNITY_TERMS.items():
        if any(term in low for term in terms):
            found.append(category)
    return found

def safe_fetch(url, timeout=10):
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https") or not p.hostname:
            return None
        # Avoid localhost/private network targets.
        host = p.hostname.lower()
        if host in ("localhost", "127.0.0.1", "::1") or host.endswith(".local"):
            return None
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if r.status_code >= 400 or "text/html" not in r.headers.get("content-type", "").lower():
            return None
        if len(r.content) > 2_000_000:
            return None
        return r.text, r.url
    except requests.RequestException:
        return None

def extract_emails(text):
    found = {e.strip(".,;:()[]{}<>").lower() for e in EMAIL_RE.findall(text or "")}
    return sorted(e for e in found if not e.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg")))

def search_web(q, market, limit):
    market_hint = "" if market == "Worldwide" else f' "{market}"'
    full_q = f"{q}{market_hint}"
    rows = []
    with DDGS() as ddgs:
        for r in ddgs.text(full_q, max_results=limit):
            rows.append({
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
                "query": full_q,
            })
    return rows

def find_contact_pages(html, base_url, limit=3):
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    for a in soup.find_all("a", href=True):
        label = (a.get_text(" ", strip=True) + " " + a["href"]).lower()
        if any(k in label for k in ["contact", "about", "invest", "partner", "supplier", "vendor", "procurement", "opportunit", "team"]):
            u = urljoin(base_url, a["href"])
            if urlparse(u).netloc == urlparse(base_url).netloc and u not in candidates:
                candidates.append(u)
    return candidates[:limit]

def inspect_result(result, pages_limit):
    source_url = result["url"]
    fetched = safe_fetch(source_url)
    page_text = ""
    emails = []
    pages_checked = []
    final_url = source_url
    if fetched:
        html, final_url = fetched
        soup = BeautifulSoup(html, "html.parser")
        page_text = soup.get_text(" ", strip=True)[:12000]
        emails.extend(extract_emails(html))
        pages_checked.append(final_url)
        for contact_url in find_contact_pages(html, final_url, pages_limit - 1):
            time.sleep(0.6)
            got = safe_fetch(contact_url)
            if got:
                contact_html, resolved = got
                emails.extend(extract_emails(contact_html))
                pages_checked.append(resolved)
                contact_soup = BeautifulSoup(contact_html, "html.parser")
                page_text += " " + contact_soup.get_text(" ", strip=True)[:5000]
    combined = " ".join([result.get("title",""), result.get("snippet",""), page_text])
    categories = detect_categories(combined)
    if not categories:
        categories = ["Needs review"]
    domain = urlparse(final_url).netloc.replace("www.", "")
    return {
        "Company / result": result.get("title", ""),
        "Website": final_url,
        "Domain": domain,
        "Opportunity type": "; ".join(categories),
        "Evidence / search snippet": result.get("snippet", "")[:700],
        "Evidence excerpt": page_text[:900],
        "Emails found": "; ".join(sorted(set(emails))),
        "Source pages checked": "; ".join(pages_checked),
        "Source date checked (UTC)": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "Review status": "Needs human review",
        "Contact permission / lawful basis": "",
        "Suppressed / unsubscribed": "No",
    }

tab1, tab2, tab3 = st.tabs(["Find opportunities", "Results & export", "Email campaign"])

if "results_df" not in st.session_state:
    st.session_state.results_df = pd.DataFrame()

with tab1:
    st.markdown("### Run a live search")
    market = other_country.strip() if country == "Other" and other_country.strip() else country
    if st.button("▶ START AGENT", type="primary", use_container_width=True):
        if not query.strip():
            st.error("Enter a search instruction first.")
        else:
            search_query = query.strip()
            if categories:
                search_query += " " + " OR ".join({
                    "Seeking investors/funding": '"seeking investors" OR "seeking funding" OR fundraising',
                    "Seeking business partners": '"seeking partners" OR "partnership opportunity"',
                    "Seeking suppliers/distributors": '"seeking suppliers" OR "supplier application"',
                    "Acquisition / M&A": '"looking to acquire" OR "acquisition opportunities"',
                    "Tenders / RFPs": '"request for proposal" OR tender OR RFP',
                    "Seeking customers / contractors": '"seeking contractors" OR "request for bids"',
                    "Investor seeking companies": '"we invest in" OR "investment criteria"',
                }.get(c, c) for c in categories)
            st.info(f"Searching for: {search_query} | Market: {market}")
            progress = st.progress(0)
            status = st.empty()
            try:
                hits = search_web(search_query, market, max_results)
                if not hits:
                    st.warning("The search provider returned no results. Try a broader query.")
                rows = []
                seen = set()
                for i, hit in enumerate(hits):
                    if hit["url"] in seen:
                        continue
                    seen.add(hit["url"])
                    status.write(f"Inspecting {i+1}/{len(hits)}: {hit.get('title','')[:100]}")
                    try:
                        rows.append(inspect_result(hit, pages_per_site))
                    except Exception as ex:
                        rows.append({
                            "Company / result": hit.get("title",""), "Website": hit.get("url",""),
                            "Domain": urlparse(hit.get("url","")).netloc, "Opportunity type": "Needs review",
                            "Evidence / search snippet": hit.get("snippet",""), "Evidence excerpt": "",
                            "Emails found": "", "Source pages checked": hit.get("url",""),
                            "Source date checked (UTC)": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                            "Review status": "Needs human review", "Contact permission / lawful basis": "",
                            "Suppressed / unsubscribed": "No"
                        })
                    progress.progress(min(1.0, (i+1)/max(1,len(hits))))
                df = pd.DataFrame(rows)
                if not df.empty:
                    df = df.drop_duplicates(subset=["Website"], keep="first")
                st.session_state.results_df = df
                status.success(f"Finished. Inspected {len(df)} results.")
            except Exception as ex:
                st.error(f"Search failed: {ex}")
                st.caption("Check your internet connection, or try again later if the search provider is rate-limiting requests.")
    st.warning("This is a research assistant, not proof of active intent. Review each source and opportunity date before acting. It respects ordinary public-web access and does not bypass logins, CAPTCHAs, or access controls.")

with tab2:
    st.markdown("### Collected results")
    df = st.session_state.results_df
    if df.empty:
        st.info("Run a search to populate results, or import an existing CSV.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Results", len(df))
        c2.metric("Results with emails", int(df["Emails found"].fillna("").str.len().gt(0).sum()))
        c3.metric("Needs review", int(df["Review status"].eq("Needs human review").sum()))
        edited = st.data_editor(df, use_container_width=True, num_rows="dynamic", key="results_editor")
        st.session_state.results_df = edited
        st.download_button("Download CSV", edited.to_csv(index=False).encode("utf-8-sig"), "opportunity_scout_results.csv", "text/csv")
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            edited.to_excel(writer, index=False, sheet_name="Opportunities")
        st.download_button("Download Excel", out.getvalue(), "opportunity_scout_results.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    uploaded = st.file_uploader("Or import an existing contacts CSV", type=["csv"])
    if uploaded:
        try:
            imported = pd.read_csv(uploaded)
            st.session_state.results_df = pd.concat([st.session_state.results_df, imported], ignore_index=True).drop_duplicates()
            st.success(f"Imported {len(imported)} rows.")
        except Exception as ex:
            st.error(f"Could not read CSV: {ex}")

with tab3:
    st.markdown("### Bulk email (provider setup required)")
    st.write("Campaign sending is intentionally separate from discovery. Use only contacts eligible for your message, and keep proof of consent or another valid legal basis where required.")
    api_key = st.text_input("Resend API key (used only for this session)", type="password")
    from_email = st.text_input("Verified sender address", placeholder="you@your-verified-domain.com")
    from_name = st.text_input("Sender name", value="Business Development")
    subject = st.text_input("Email subject")
    body = st.text_area("Email body", height=180, placeholder="Hello {{company}}, ...")
    st.caption("The sender domain must be verified with your email provider. This starter does not automatically send to every scraped address.")
    df = st.session_state.results_df
    if not df.empty and "Emails found" in df.columns:
        eligible = []
        for _, row in df.iterrows():
            permission = str(row.get("Contact permission / lawful basis", "")).strip()
            suppressed = str(row.get("Suppressed / unsubscribed", "No")).strip().lower() in ("yes", "true", "1")
            emails = [x.strip() for x in str(row.get("Emails found", "")).split(";") if "@" in x]
            if permission and not suppressed:
                for email in emails:
                    eligible.append((email, str(row.get("Company / result", ""))))
        st.write(f"Contacts with a recorded permission/legal-basis note and not marked suppressed: **{len(eligible)}**")
        confirm = st.checkbox("I reviewed the recipient list, sender domain, and legal eligibility for this campaign.")
        if st.button("Send eligible campaign", type="primary"):
            if not (api_key and from_email and subject and body):
                st.error("Fill in the API key, verified sender, subject, and body.")
            elif not confirm:
                st.error("Confirm campaign review before sending.")
            elif not eligible:
                st.error("No eligible recipients. Add a permission/legal-basis note to reviewed records and ensure they are not suppressed.")
            else:
                sent, failed = 0, []
                for email, company in eligible:
                    personalized = body.replace("{{company}}", company)
                    try:
                        resp = requests.post(
                            "https://api.resend.com/emails",
                            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                            json={"from": f"{from_name} <{from_email}>", "to": [email], "subject": subject, "text": personalized},
                            timeout=20
                        )
                        if resp.ok:
                            sent += 1
                        else:
                            failed.append(f"{email}: HTTP {resp.status_code}")
                    except requests.RequestException as ex:
                        failed.append(f"{email}: {ex}")
                    time.sleep(0.25)
                st.success(f"Send requests accepted: {sent}. Failed: {len(failed)}.")
                if failed:
                    st.code("\n".join(failed[:30]))
    else:
        st.info("Run a search first to see contact records here.")

st.divider()
st.caption("Privacy: search results are held in this app session unless you export them. Avoid entering secrets into search instructions. For production use, add authentication, persistent storage, audit logs, unsubscribe processing, and a proper campaign queue.")
