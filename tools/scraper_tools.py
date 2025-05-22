# tools/scraper_tools.py

# --- Standard Library Imports ---
import logging
import re
import time
from urllib.parse import urljoin, urlparse

# --- Third-party Imports ---
import requests
from bs4 import BeautifulSoup, Tag # Import Tag

# --- CrewAI Imports ---
from crewai.tools import BaseTool

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ==================================
# === Tool 1: Blog Post Scraper ===
# ==================================
class BlogPostScraperTool(BaseTool):
    name: str = "Blog Post Company Scraper"
    description: str = ("Scrapes a given blog post URL...") # Shortened
    def _run(self, url: str) -> str:
        logger.info(f"[Tool: {self.name}] Executing for URL: {url}")
        if not isinstance(url, str) or not url.startswith(('http://', 'https://')): logger.error(f"[T: {self.name}] Invalid URL: {url}"); return "Error: Invalid URL provided."
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        companies_found = []
        try:
            response = requests.get(url, headers=headers, timeout=20); response.raise_for_status(); soup = BeautifulSoup(response.text, 'lxml')
            content_area = soup.find('div', class_='blog-post_content-wrapper') or soup.find('div', class_=re.compile(r'content-wrapper', re.IGNORECASE)) or soup.find('article') or soup.find('main') or soup.body or soup
            if not content_area: logger.error(f"[T: {self.name}] No content area: {url}"); return "Error: Could not identify main content area."
            headings = content_area.find_all('h3'); logger.info(f"[T: {self.name}] Found {len(headings)} H3s.")
            for i, heading in enumerate(headings):
                company_name = heading.get_text(strip=True); company_name = re.sub(r'^\d+\.?\s*', '', company_name).strip().replace('®', '').replace('*', '')
                ignore_list = ["conclusion", "introduction", "key takeaways", "faq", "faqs"];
                if len(company_name) < 3 or any(ignore_term in company_name.lower() for ignore_term in ignore_list): logger.debug(f"[T: {self.name}] Ignoring H3: '{company_name}'"); continue
                link_url = "Link not found"; current_element = heading
                while True:
                    next_sibling = current_element.find_next_sibling();
                    if next_sibling is None: break
                    if isinstance(next_sibling, Tag):
                        if next_sibling == headings[i+1] if (i + 1) < len(headings) else None: break
                        link_tag = next_sibling.find('a', href=True)
                        if link_tag: href = link_tag.get('href');
                        if href and urlparse(href).scheme in ['http', 'https', '']:
                            if '#' not in href.split('/')[-1] and not href.startswith(('mailto:', 'tel:', 'javascript:')):
                                absolute_link = urljoin(url, href); link_url = absolute_link; logger.debug(f"[T: {self.name}] Found link '{link_url}' for '{company_name}'"); break
                    current_element = next_sibling
                companies_found.append({"name": company_name, "link": link_url}); logger.debug(f"[T: {self.name}] Potential match: {company_name} ({link_url})")
            if not companies_found: logger.warning(f"[T: {self.name}] No companies in H3s: {url}"); return f"No potential companies identified in H3 headings on {url}."
            output_lines = ["Found Companies:"];
            for company in companies_found: output_lines.append(f"- {company['name']} ({company['link']})")
            logger.info(f"[Tool: {self.name}] Finished scraping. Found {len(companies_found)} entries.")
            return "\n".join(output_lines)
        except requests.exceptions.RequestException as e: logger.error(f"[T: {self.name}] Request Fail: {url}: {e}"); return f"Error: Request failed for {url}."
        except Exception as e: logger.error(f"[T: {self.name}] Unexpected Error: {url}: {e}", exc_info=True); return "Error: An unexpected error occurred during blog scraping."

# --- Instantiate Tool 1 ---
scrape_blog_tool = BlogPostScraperTool()


# ============================================================
# === Tool 2: Contact/About Page URL Finder (Requests Based) ===
# ============================================================
class ContactPageUrlFinderTool(BaseTool):
    name: str = "Contact/About Page URL Finder"
    description: str = ("Given a company's website URL, attempts to find the absolute URL of their 'Contact Us', 'About Us', or 'Support' page...") # Shortened
    def _search_links(self, soup_section, effective_url) -> dict:
        keywords_priority = ['contact us', 'contact-us', 'contact', 'kontakt', 'contacto', 'get in touch', 'reach us', 'support', 'hilfe', 'soporte', 'customer service', 'about us', 'about-us', 'about', 'über uns', 'sobre nosotros', 'company', 'locations', 'standorte', 'imprint', 'impressum', 'legal notice', 'legal', 'privacy', 'terms']; found_links = {}
        for link in soup_section.find_all('a', href=True):
            link_text = link.get_text(strip=True).lower(); href = link['href']
            if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')): continue
            absolute_url = urljoin(effective_url, href)
            if absolute_url.rstrip('/') == effective_url.rstrip('/'): continue
            if absolute_url in found_links: continue
            for i, keyword in enumerate(keywords_priority):
                href_path = urlparse(absolute_url).path.lower(); href_parts = [p for p in href_path.split('/') if p]; keyword_simple = keyword.replace(' ', '').replace('-', '')
                is_in_href = False
                if href_parts:
                    if keyword in href_parts or keyword_simple in href_parts: is_in_href = True
                    elif keyword in href_parts[-1] or keyword_simple in href_parts[-1]: is_in_href = True
                is_in_text = keyword in link_text
                if is_in_href or is_in_text:
                    if absolute_url not in found_links or i < found_links[absolute_url]: found_links[absolute_url] = i; logger.debug(f"[T: {self.name}] Found link {absolute_url} (K: '{keyword}', P: {i})")
                    break
        return found_links
    def _run(self, company_url: str) -> str:
        logger.info(f"[Tool: {self.name}] Executing for URL: {company_url}")
        if not isinstance(company_url, str) or not urlparse(company_url).scheme in ['http', 'https']: logger.error(f"[T: {self.name}] Invalid URL: {company_url}"); return "Error: Invalid company URL"
        headers = { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.5', 'Referer': 'https://www.google.com/', 'DNT': '1', 'Connection': 'keep-alive', 'Upgrade-Insecure-Requests': '1', 'Sec-Fetch-Dest': 'document', 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Site': 'cross-site', 'Sec-Fetch-User': '?1', 'TE': 'trailers'}
        result = "Relevant page not found"
        try:
            logger.debug(f"[Tool: {self.name}] Fetching homepage: {company_url}")
            response = requests.get(company_url, headers=headers, timeout=20, allow_redirects=True); response.raise_for_status(); effective_url = response.url
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' not in content_type: logger.warning(f"[T: {self.name}] Homepage Non-HTML: {effective_url} ({content_type})"); return f"Error: Homepage Non-HTML ({content_type})"
            soup = BeautifulSoup(response.text, 'lxml'); page_body = soup.body if soup.body else soup
            logger.info(f"[Tool: {self.name}] Searching for contact/about page links...")
            found_links = {}; footer = soup.find('footer'); nav_or_header = soup.find('nav') or soup.find('header')
            if footer: logger.debug(f"[T: {self.name}] Searching links in footer..."); found_links.update(self._search_links(footer, effective_url))
            if not any(p <= 16 for p in found_links.values()):
                 if nav_or_header: logger.debug(f"[T: {self.name}] Searching links in nav/header..."); header_links = self._search_links(nav_or_header, effective_url); found_links.update(header_links)
            if not any(p <= 16 for p in found_links.values()): logger.debug(f"[T: {self.name}] Searching links in entire body..."); body_links = self._search_links(page_body, effective_url); found_links.update(body_links)
            if found_links:
                sorted_links = sorted(found_links.items(), key=lambda item: (item[1], len(item[0])))
                if sorted_links[0][1] < 19: result = sorted_links[0][0]; logger.info(f"[T: {self.name}] Selected relevant page URL: {result}")
                else: logger.warning(f"[T: {self.name}] Best link found ({sorted_links[0][0]}) was low priority.")
            else: logger.warning(f"[T: {self.name}] No relevant page links found on {effective_url}")
        except requests.exceptions.Timeout: logger.error(f"[T: {self.name}] Timeout: {company_url}"); return "Error: Timeout accessing homepage"
        except requests.exceptions.HTTPError as e: logger.error(f"[T: {self.name}] HTTP {e.response.status_code}: {company_url}"); return f"Error: HTTP {e.response.status_code} on homepage"
        except requests.exceptions.RequestException as e: logger.error(f"[T: {self.name}] Request Fail: {company_url}: {e}"); return "Error: Cannot access homepage"
        except Exception as e: logger.error(f"[T: {self.name}] Unexpected Error: {company_url}: {e}", exc_info=False); return "Error: Processing homepage failed"
        return result

# --- Instantiate Tool 2 ---
find_page_url_tool = ContactPageUrlFinderTool()


# ==============================================
# === Tool 3: Generic Web Content Scraper ===
# ==============================================
class GenericWebScraperTool(BaseTool):
    name: str = "Generic Web Content Scraper"; description: str = ("Fetches main text content...") # Shortened
    def _run(self, url: str) -> str:
        logger.info(f"[Tool: {self.name}] Executing for URL: {url}")
        if not isinstance(url, str) or not urlparse(url).scheme in ['http', 'https']: logger.error(f"[T: {self.name}] Invalid URL: {url}"); return "Error: Invalid URL provided."
        headers = { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.5', 'Referer': 'https://www.google.com/', 'DNT': '1', 'Connection': 'keep-alive', 'Upgrade-Insecure-Requests': '1', 'Sec-Fetch-Dest': 'document', 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Site': 'cross-site', 'Sec-Fetch-User': '?1', 'TE': 'trailers'}
        try:
            response = requests.get(url, headers=headers, timeout=25, allow_redirects=True); response.raise_for_status(); effective_url = response.url
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' not in content_type: logger.warning(f"[T: {self.name}] Non-HTML: {effective_url} ({content_type})"); return f"Error: Non-HTML content ({content_type})"
            soup = BeautifulSoup(response.text, 'lxml');
            for script_or_style in soup(["script", "style"]): script_or_style.decompose()
            main_content = soup.find('main') or soup.find('article') or soup.find('div', role='main')
            if main_content: text = main_content.get_text(separator=' ', strip=True); logger.info(f"[T: {self.name}] Extracted main text for {url}.")
            else: text = soup.body.get_text(separator=' ', strip=True) if soup.body else ""; logger.info(f"[T: {self.name}] Extracted body text (fallback) for {url}.")
            text = re.sub(r'\s{2,}', ' ', text).strip(); max_chars = 10000
            if len(text) > max_chars: logger.warning(f"[T: {self.name}] Truncating text from {url}."); text = text[:max_chars] + "..."
            if not text: logger.warning(f"[T: {self.name}] No text extracted from {url}"); return "Error: No text content found"
            return text
        except requests.exceptions.Timeout: logger.error(f"[T: {self.name}] Timeout: {url}"); return "Error: Timeout accessing URL"
        except requests.exceptions.HTTPError as e: logger.error(f"[T: {self.name}] HTTP {e.response.status_code}: {url}"); return f"Error: HTTP {e.response.status_code}"
        except requests.exceptions.RequestException as e: logger.error(f"[T: {self.name}] Request Fail: {url}: {e}"); return "Error: Cannot access URL"
        except Exception as e: logger.error(f"[T: {self.name}] Unexpected Error: {url}: {e}", exc_info=True); return "Error: Processing failed"

# --- Instantiate Tool 3 ---
generic_scraper_tool = GenericWebScraperTool()
