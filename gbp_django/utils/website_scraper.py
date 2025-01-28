import requests
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

def extract_key_content(soup):
    """Extract important content from the webpage."""
    # Try to get meta description first
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if meta_desc and meta_desc.get('content'):
        return meta_desc['content']
    
    # Get main content areas
    main_content = []
    priority_tags = ['h1', 'h2', 'h3', 'p']
    
    for tag in priority_tags:
        elements = soup.find_all(tag)
        for element in elements[:3]:  # Limit to first 3 of each tag
            if element.text.strip():
                main_content.append(element.text.strip())
    
    return ' '.join(main_content)

def basic_summarize(text, max_length=150):
    """Basic text summarization by extracting key sentences."""
    # Split into sentences
    sentences = [s.strip() for s in text.split('.') if s.strip()]
    
    # If text is already short enough, return it
    if len(text) <= max_length:
        return text
    
    # Otherwise, take first 2-3 sentences that fit within max_length
    summary = []
    current_length = 0
    
    for sentence in sentences:
        if current_length + len(sentence) + 2 <= max_length:  # +2 for period and space
            summary.append(sentence)
            current_length += len(sentence) + 2
        else:
            break
    
    return '. '.join(summary) + '.'

def scrape_and_summarize_website(url):
    """Scrape a website and create a basic summary of its content."""
    try:
        # Fetch the webpage
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract key content
        content = extract_key_content(soup)
        
        # Create summary
        summary = basic_summarize(content)
        
        return summary

    except requests.exceptions.RequestException as e:
        logger.error(f"Error during website scraping: {e}")
        return "Error scraping website"
    except Exception as e:
        logger.error(f"Error processing website content: {e}")
        return "Error processing website content"
