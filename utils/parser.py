# utils/parser.py
"""
Utility module for parsing data from various sources and formats.
"""

import re
import logging
import ast
import json
from typing import List, Dict, Any, Optional, Union
from utils.logging_utils import get_logger

logger = get_logger(__name__)

def parse_url_list(agent_output: str) -> List[str]:
    """
    Extract URLs from agent output text with improved parsing.
    
    Args:
        agent_output: The text output from an agent
        
    Returns:
        List of extracted URLs
    """
    logger.debug(f"Parsing URL list from agent output")
    urls = []
    
    if not isinstance(agent_output, str): 
        logger.warning(f"URL Parser received non-string input: {type(agent_output)}")
        return urls
        
    # Clean the output - remove prefixes like "FINAL ANSWER:"
    cleaned_output = agent_output
    if cleaned_output.strip().upper().startswith("FINAL ANSWER:"):
        cleaned_output = cleaned_output.split(":", 1)[1].strip()
    
    # Method 1: Try to parse as JSON
    try:
        # Sometimes the output is actually JSON format
        json_data = json.loads(cleaned_output)
        if isinstance(json_data, list):
            urls = [str(item).strip() for item in json_data 
                   if isinstance(item, str) and item.strip().startswith('http')]
            if urls:
                logger.info(f"Extracted {len(urls)} URLs via JSON parsing")
                return urls
    except json.JSONDecodeError:
        pass
    except Exception as e:
        logger.debug(f"JSON parsing failed: {e}")
    
    # Method 2: Try to parse as Python literal
    try:
        potential_list = ast.literal_eval(cleaned_output)
        if isinstance(potential_list, list):
            urls = [str(item).strip() for item in potential_list 
                   if isinstance(item, str) and item.strip().startswith('http')]
            if urls:
                logger.info(f"Extracted {len(urls)} URLs via literal evaluation")
                return urls
    except Exception as e:
        logger.debug(f"Could not parse URL list via literal evaluation: {e}")
    
    # Method 3: Extract URLs using regex
    try:
        # More comprehensive URL pattern
        url_pattern = r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)'
        matches = re.findall(url_pattern, cleaned_output)
        
        # Clean URLs
        urls = [url.strip('.,)("\'') for url in matches]
        
        # Filter out non-webpage URLs
        urls = [url for url in urls if not url.endswith(
            ('.png', '.jpg', '.jpeg', '.gif', '.css', '.js', '.svg', '.webp'))]
        
        # Remove duplicates while preserving order
        unique_urls = []
        for url in urls:
            if url not in unique_urls:
                unique_urls.append(url)
        
        logger.info(f"Extracted {len(unique_urls)} URLs via regex")
        return unique_urls
    except Exception as e:
        logger.error(f"Error during regex URL extraction: {e}")
        return []

def parse_company_data(agent_output: str) -> List[Dict[str, str]]:
    """
    Extract company data (name and website) from agent output with improved parsing.
    
    Args:
        agent_output: The text output from an agent
        
    Returns:
        List of dictionaries with company information
    """
    logger.debug(f"Parsing company data from agent output")
    companies = []
    
    if not isinstance(agent_output, str):
        logger.warning(f"Company parser received non-string input: {type(agent_output)}")
        return companies
    
    # Clean the output
    cleaned_output = agent_output
    if cleaned_output.strip().upper().startswith("FINAL ANSWER:"):
        cleaned_output = cleaned_output.split(":", 1)[1].strip()
    cleaned_output = cleaned_output.strip().strip('```python').strip('```').strip()
    
    # Method 1: Try to parse as JSON
    try:
        json_data = json.loads(cleaned_output)
        if isinstance(json_data, list):
            for item in json_data:
                if isinstance(item, dict):
                    name = item.get('name')
                    website = item.get('website')
                    
                    if (isinstance(name, str) and isinstance(website, str) and 
                        name.strip() and website.strip().startswith('http') and 
                        1 < len(name) < 60):
                        
                        companies.append({
                            'name': name.strip(),
                            'website': website.strip()
                        })
            
            if companies:
                logger.info(f"Extracted {len(companies)} companies via JSON parsing")
                return companies
    except json.JSONDecodeError:
        pass
    except Exception as e:
        logger.debug(f"JSON parsing failed: {e}")
    
    # Method 2: Try to parse as Python literal
    try:
        potential_list = ast.literal_eval(cleaned_output)
        if isinstance(potential_list, list):
            for item in potential_list:
                if isinstance(item, dict):
                    name = item.get('name')
                    website = item.get('website')
                    
                    if (isinstance(name, str) and isinstance(website, str) and 
                        name.strip() and website.strip().startswith('http') and 
                        1 < len(name) < 60):
                        
                        companies.append({
                            'name': name.strip(),
                            'website': website.strip()
                        })
            
            if companies:
                logger.info(f"Extracted {len(companies)} companies via literal evaluation")
                return companies
    except Exception as e:
        logger.debug(f"Could not parse company data via literal evaluation: {e}")
    
    # Method 3: Try to extract using enhanced regex
    try:
        # Look for patterns like "Company Name: url" or "Name: Company, URL: website"
        company_patterns = [
            r'(?:company|name)?\s*:\s*"?([^",\n]{2,60})"?\s*(?:,|;)?\s*(?:website|url)?\s*:\s*"?(https?://[^\s",\n]+)"?',
            r'"?([^",\n]{2,60})"?\s*(?:-|:|\|)\s*"?(https?://[^\s",\n]+)"?',
            r'"?name"?\s*(?::|=)\s*"?([^",\n]{2,60})"?.*?"?(?:website|url)"?\s*(?::|=)\s*"?(https?://[^\s",\n]+)"?',
        ]
        
        for pattern in company_patterns:
            matches = re.findall(pattern, cleaned_output, re.IGNORECASE | re.MULTILINE)
            
            for match in matches:
                if len(match) >= 2:
                    name = match[0].strip()
                    website = match[1].strip()
                    
                    # Basic validation
                    if name and website.startswith('http') and 1 < len(name) < 60:
                        # Avoid duplicates
                        if not any(c['name'].lower() == name.lower() for c in companies):
                            companies.append({
                                'name': name,
                                'website': website
                            })
        
        if companies:
            logger.info(f"Extracted {len(companies)} companies via regex")
            return companies
    except Exception as e:
        logger.error(f"Error during regex company extraction: {e}")
        
    # If all methods fail
    logger.warning("All parsing methods failed to extract company data")
    return []

def parse_analysis_results(result: str) -> Dict[str, str]:
    """
    Parse analysis results to extract email and pain points with improved parsing.
    
    Args:
        result: The analysis text from an agent
        
    Returns:
        Dictionary with email and pain points
    """
    logger.debug(f"Parsing analysis results")
    
    if not isinstance(result, str):
        logger.warning(f"Analysis parser received non-string input: {type(result)}")
        return {"email": "", "pain_points": "Analysis failed - non-string result"}
    
    # Try JSON parsing first if the result looks like JSON
    if result.strip().startswith('{') and result.strip().endswith('}'):
        try:
            data = json.loads(result)
            if isinstance(data, dict):
                email = data.get('email', '')
                pain_points = data.get('pain_points', '')
                
                if isinstance(email, str) and isinstance(pain_points, str):
                    return {
                        "email": email.strip(),
                        "pain_points": pain_points.strip()
                    }
        except:
            pass
    
    # Remove "FINAL ANSWER:" prefix if present
    cleaned_result = result
    if cleaned_result.strip().upper().startswith("FINAL ANSWER:"):
        cleaned_result = cleaned_result.split(":", 1)[1].strip()
    
    # Initialize default returns
    email = ""
    pain_points = ""
    
    # Extract email addresses - more comprehensive pattern
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    email_matches = re.findall(email_pattern, cleaned_result)
    
    # Filter valid emails
    valid_emails = [
        e for e in email_matches 
        if '@' in e and '.' in e.split('@')[-1] and not any(
            invalid in e.lower() for invalid in 
            ['example.com', 'test', 'error', 'your', 'domain.com', 'email@', 'user@']
        )
    ]
    
    if valid_emails:
        email = valid_emails[0]
    
# utils/parser.py (continued)
    # Extract pain points using several patterns
    
    # Method 1: Look for labeled sections
    pain_patterns = [
        r'(?:pain points?|challenges?|issues?)(?:\s*:|.*?:)(.*?)(?:(?:email|contact|conclusion)|\Z)',
        r'(?:1[\.\)])(.*?)(?:(?:2[\.\)]|email|contact|conclusion)|\Z)',
        r'potential pain points?:(.*?)(?:(?:email|contact|conclusion)|\Z)'
    ]
    
    for pattern in pain_patterns:
        matches = re.findall(pattern, cleaned_result, re.IGNORECASE | re.DOTALL)
        if matches:
            pain_points = matches[0].strip()
            break
    
    # Method 2: If no labeled section found, look for structured content with numbers
    if not pain_points:
        # Look for numbered lists (1. Point, 2. Point, etc.)
        numbered_pattern = r'(?:\d+[\.\)]\s*[^\d\.\)]+)+'
        matches = re.findall(numbered_pattern, cleaned_result)
        if matches:
            pain_points = ' '.join(matches).strip()
    
    # Method 3: If email exists, take everything after it
    if not pain_points and email and email in cleaned_result:
        pain_points = cleaned_result.split(email, 1)[1].strip()
    
    # Method 4: If nothing else works, use everything
    if not pain_points:
        pain_points = cleaned_result.strip()
        
    return {"email": email, "pain_points": pain_points}
