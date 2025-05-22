# tools/unified_email_finder.py
import re
import logging
import time
import random
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from crewai.tools import BaseTool
from utils.error_handler import retry, handle_api_error

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class UnifiedEmailFinderTool(BaseTool):
    name: str = "Unified Company Email Finder"
    description: str = (
        "Given a company's website URL, finds contact email addresses using multiple methods. "
        "Input must be the company website URL string. Returns the most relevant email found."
    )
    
    # Request headers
    _headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://www.google.com/',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    # Common contact page paths
    _contact_paths = [
        '/contact', '/contact-us', '/about/contact', '/about-us/contact',
        '/support', '/help', '/team', '/about/team', '/about-us/team',
        '/company/team', '/company/contact', '/company', '/imprint'
    ]
    
    def extract_domain(self, url: str) -> str:
        """Extract the domain from a URL."""
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        # Remove www. if present
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    
    def is_valid_email(self, email: str) -> bool:
        """Validate an email address format and filter out common false positives."""
        # Email regex pattern
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        
        if not re.match(email_pattern, email):
            return False
            
        # Filter out common false positives
        invalid_patterns = [
            r'example\.com$', r'yourname@', r'your@email\.com$',
            r'user@', r'name@', r'domain\.com$', r'email@example',
            r'test@', r'@example\.', r'sample@', r'wixpress\.com$',
            r'wordpress\.com$', r'sentry\.io$', r'localhost', r'mysite\.com$'
        ]
        
        for pattern in invalid_patterns:
            if re.search(pattern, email.lower()):
                return False
        
        # Check email parts
        local_part, domain_part = email.split('@', 1)
        if not local_part or not domain_part or '.' not in domain_part:
            return False
        if len(email) > 64 or len(email) < 6 or email.count('@') != 1:
            return False
        if email.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg')):
            return False
        
        return True
    
    def find_emails(self, soup, page_url=None):
        """Extract emails from a BeautifulSoup object using multiple methods."""
        emails = set()
        
        # Method 1: Extract from mailto links
        mailto_links = soup.select('a[href^="mailto:"]')
        for link in mailto_links:
            href = link.get('href', '')
            match = re.search(r'mailto:([^?]+)', href)
            if match:
                email = match.group(1).strip().lower()
                if self.is_valid_email(email):
                    emails.add(email)
        
        # Method 2: Extract from text content
        if soup.body:
            text_content = soup.body.get_text(' ', strip=True)
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            found_emails = re.findall(email_pattern, text_content)
            for email in found_emails:
                if self.is_valid_email(email.lower()):
                    emails.add(email.lower())
        
        # Method 3: Look for obfuscated emails
        if soup.body:
            text_content = soup.body.get_text(' ', strip=True)
            patterns = [
                r'([a-zA-Z0-9._%+-]+)\s*[\[\(\{]at[\]\)\}]\s*([a-zA-Z0-9.-]+)\s*[\[\(\{]dot[\]\)\}]\s*([a-zA-Z]{2,})',
                r'([a-zA-Z0-9._%+-]+)\s*@\s*([a-zA-Z0-9.-]+)\s*\.\s*([a-zA-Z]{2,})'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, text_content)
                for match in matches:
                    if isinstance(match, tuple) and len(match) == 3:
                        email = f"{match[0].strip()}@{match[1].strip()}.{match[2].strip()}"
                        if self.is_valid_email(email.lower()):
                            emails.add(email.lower())
        
        return list(emails)
    
    def get_best_email(self, emails):
        """Select the best email from a list based on common business prefixes."""
        if not emails:
            return None
            
        # Priority prefixes for business emails
        prefixes = [
            'contact@', 'info@', 'hello@', 'sales@', 'support@', 
            'team@', 'hr@', 'careers@', 'jobs@', 'inquiries@'
        ]
        
        # First try to find emails with priority prefixes
        for prefix in prefixes:
            for email in emails:
                if email.startswith(prefix):
                    return email
        
        # If no priority email found, return the first one
        return emails[0]
    
    def find_contact_pages(self, base_url, soup):
        """Find contact page URLs from links on the current page."""
        contact_urls = []
        domain = self.extract_domain(base_url)
        
        # Keywords that might indicate contact pages
        keywords = ['contact', 'team', 'about us', 'about', 'support', 'help']
        
        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href')
            link_text = a_tag.text.lower().strip()
            
            # Skip empty or javascript links
            if not href or href.startswith(('javascript:', 'mailto:', 'tel:')) or href == '#':
                continue
                
            # Create absolute URL
            absolute_url = urljoin(base_url, href)
            parsed_url = urlparse(absolute_url)
            
            # Only consider links to the same domain
            if parsed_url.netloc and self.extract_domain(absolute_url) != domain:
                continue
                
            # Check URL path and link text
            path = parsed_url.path.lower()
            if any(contact_path in path for contact_path in self._contact_paths):
                contact_urls.append(absolute_url)
                continue
                
            if any(keyword in link_text for keyword in keywords):
                contact_urls.append(absolute_url)
        
        return list(set(contact_urls))  # Remove duplicates
    
    @retry(max_attempts=3, delay=2, backoff=2, exceptions=(requests.RequestException,))
    def fetch_url(self, url, headers=None):
        """Fetch URL with retry mechanism."""
        return requests.get(url, headers=headers or self._headers, timeout=15, allow_redirects=True)
    
    @handle_api_error
    def _run(self, company_url: str) -> str:
        """Main method to find a company's contact email."""
        logger.info(f"[Tool: {self.name}] Executing for URL: {company_url}")
        
        if not isinstance(company_url, str):
            return ""
            
        # Ensure URL has protocol
        if not company_url.startswith(('http://', 'https://')):
            company_url = 'https://' + company_url
        
        # Track visited URLs to avoid loops
        visited_urls = set()
        all_emails = []
        
        try:
            # Start with the homepage
            logger.debug(f"Fetching homepage: {company_url}")
            
            response = self.fetch_url(company_url)
            response.raise_for_status()
            visited_urls.add(company_url)
            
            homepage_soup = BeautifulSoup(response.text, 'lxml')
            
            # Find emails on homepage
            homepage_emails = self.find_emails(homepage_soup, company_url)
            all_emails.extend(homepage_emails)
            
            # If we already found a good email, return it
            if homepage_emails:
                best_email = self.get_best_email(homepage_emails)
                if best_email and any(best_email.startswith(prefix) for prefix in ['contact@', 'info@', 'hello@']):
                    return best_email
            
            # Find contact pages
            contact_pages = self.find_contact_pages(company_url, homepage_soup)
            
            # Visit up to 3 contact pages
            for url in contact_pages[:3]:
                if url in visited_urls:
                    continue
                    
                try:
                    logger.debug(f"Fetching contact page: {url}")
                    time.sleep(random.uniform(1, 2))  # Be polite with delays
                    
                    response = self.fetch_url(url)
                    response.raise_for_status()
                    visited_urls.add(url)
                    
                    contact_soup = BeautifulSoup(response.text, 'lxml')
                    contact_emails = self.find_emails(contact_soup, url)
                    
                    all_emails.extend(contact_emails)
                except Exception as e:
                    logger.warning(f"Error fetching contact page {url}: {e}")
            
            # Return the best email found
            if all_emails:
                return self.get_best_email(all_emails)
            
            return ""
            
        except Exception as e:
            logger.error(f"Error finding email for {company_url}: {str(e)}")
            return ""

# Instantiate the tool
unified_email_finder_tool = UnifiedEmailFinderTool()
