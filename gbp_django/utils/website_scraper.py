import requests
from bs4 import BeautifulSoup
from transformers import pipeline

def scrape_and_summarize_website(url):
    """Scrape a website and summarize its content using a transformer model."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes
        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract all text from the body
        text_content = ' '.join(soup.body.stripped_strings)

        # Initialize the summarization pipeline
        summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

        # Generate summary
        summary_text = summarizer(text_content, max_length=150, min_length=30, do_sample=False)[0]['summary_text']

        return summary_text

    except requests.exceptions.RequestException as e:
        print(f"Error during website scraping: {e}")
        return "Error scraping website"
    except Exception as e:
        print(f"Error during summarization: {e}")
        return "Error summarizing website"
