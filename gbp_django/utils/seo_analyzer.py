import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

def analyze_website(url):
    """
    Analyzes a website for SEO health, including meta tags, content quality,
    mobile-friendliness, page speed, and backlinks.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        soup = BeautifulSoup(response.content, 'html.parser')

        # Meta Tags Analysis
        meta_tags_score = analyze_meta_tags(soup)

        # Content Quality Analysis
        content_quality_score = analyze_content_quality(soup)

        # Mobile Friendliness Analysis
        mobile_friendly_score = analyze_mobile_friendliness(soup)

        # Page Speed Analysis (basic)
        page_speed_score = analyze_page_speed(response)

        # Backlink Analysis (basic)
        backlinks_score = analyze_backlinks(soup, url)

        # Calculate overall score
        overall_score = calculate_overall_score(
            meta_tags_score,
            content_quality_score,
            mobile_friendly_score,
            page_speed_score,
            backlinks_score
        )

        return {
            'meta_tags_score': meta_tags_score,
            'content_quality_score': content_quality_score,
            'mobile_friendly_score': mobile_friendly_score,
            'page_speed_score': page_speed_score,
            'backlinks_score': backlinks_score,
            'overall_score': overall_score
        }

    except requests.exceptions.RequestException as e:
        print(f"Error during website analysis: {e}")
        return {
            'meta_tags_score': 0,
            'content_quality_score': 0,
            'mobile_friendly_score': 0,
            'page_speed_score': 0,
            'backlinks_score': 0,
            'overall_score': 0
        }

def analyze_meta_tags(soup):
    """Analyzes meta tags for SEO optimization."""
    title = soup.find('title')
    description = soup.find('meta', attrs={'name': 'description'})
    keywords = soup.find('meta', attrs={'name': 'keywords'})

    score = 0
    if title and len(title.text) > 10:
        score += 30
    if description and len(description.get('content', '')) > 50:
        score += 40
    if keywords and len(keywords.get('content', '')) > 10:
        score += 30
    return min(score, 100)

def analyze_content_quality(soup):
    """Analyzes content quality based on text length and heading usage."""
    text_content = soup.get_text(separator=' ', strip=True)
    text_length = len(text_content)
    h1_count = len(soup.find_all('h1'))
    h2_count = len(soup.find_all('h2'))

    score = 0
    if text_length > 500:
        score += 50
    if h1_count > 0:
        score += 25
    if h2_count > 2:
        score += 25
    return min(score, 100)

def analyze_mobile_friendliness(soup):
    """Analyzes mobile-friendliness based on viewport meta tag."""
    viewport_tag = soup.find('meta', attrs={'name': 'viewport'})
    if viewport_tag and 'width=device-width' in viewport_tag.get('content', ''):
        return 100
    return 0

def analyze_page_speed(response):
    """Analyzes page speed based on response time."""
    response_time = response.elapsed.total_seconds()
    if response_time < 1:
        return 100
    elif response_time < 3:
        return 70
    elif response_time < 5:
        return 40
    else:
        return 20

def analyze_backlinks(soup, url):
    """Analyzes backlinks by counting external links."""
    external_links = 0
    for link in soup.find_all('a', href=True):
        href = link['href']
        if is_external_link(href, url):
            external_links += 1
    return min(external_links * 10, 100)

def is_external_link(url, base_url):
    """Checks if a URL is external to the base URL."""
    if not url or url.startswith('#') or url.startswith('mailto:') or url.startswith('tel:'):
        return False
    
    parsed_url = urlparse(url)
    parsed_base = urlparse(base_url)
    
    if not parsed_url.netloc:
        return False
    
    return parsed_url.netloc != parsed_base.netloc

def calculate_overall_score(meta_tags_score, content_quality_score, mobile_friendly_score, page_speed_score, backlinks_score):
    """Calculates the overall SEO score."""
    return int((
        meta_tags_score +
        content_quality_score +
        mobile_friendly_score +
        page_speed_score +
        backlinks_score
    ) / 5)
