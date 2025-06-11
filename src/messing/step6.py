# Step 6: Web Scraping + AI Extraction Pipeline
# Scrape real company websites, save locally, then extract with AI

import re
import json
import os
import requests
from datetime import datetime
from urllib.parse import urlparse

# You'll need: uv add requests beautifulsoup4
try:
    from bs4 import BeautifulSoup
    SOUP_AVAILABLE = True
except ImportError:
    SOUP_AVAILABLE = False
    print("⚠️  BeautifulSoup not installed. Run: uv add beautifulsoup4")

# Load environment variables if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Gemini AI (optional)
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

def scrape_website(url, save_filename=None):
    """Scrape text content from a website and save locally"""
    
    if not SOUP_AVAILABLE:
        return {"error": "beautifulsoup4 not installed"}
    
    try:
        print(f"🌐 Scraping: {url}")
        
        # Add headers to look like a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        # Fetch the webpage
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header']):
            element.decompose()
        
        # Extract text
        text = soup.get_text()
        
        # Clean up the text
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        clean_text = '\n'.join(chunk for chunk in chunks if chunk)
        
        # Generate filename if not provided
        if not save_filename:
            domain = urlparse(url).netloc.replace('www.', '')
            save_filename = f"scraped_{domain.replace('.', '_')}.txt"
        
        # Save to file
        with open(save_filename, 'w', encoding='utf-8') as f:
            f.write(f"SOURCE: {url}\n")
            f.write(f"SCRAPED: {datetime.now().isoformat()}\n")
            f.write("="*50 + "\n\n")
            f.write(clean_text)
        
        print(f"💾 Saved to: {save_filename}")
        print(f"📊 Text length: {len(clean_text)} characters")
        
        return {
            "success": True,
            "filename": save_filename,
            "url": url,
            "text_length": len(clean_text),
            "preview": clean_text[:200] + "..." if len(clean_text) > 200 else clean_text
        }
        
    except Exception as e:
        return {"error": f"Failed to scrape {url}: {str(e)}"}

def extract_with_patterns(text):
    """Pattern-based extraction"""
    emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
    years = re.findall(r'\b(19\d{2}|20\d{2})\b', text)
    employee_matches = re.findall(r'(\d+)\s+employees?', text, re.IGNORECASE)
    
    # More flexible company name patterns for real websites
    company_patterns = [
        r'Welcome to ([A-Z][A-Za-z\s&]+)!?',
        r'([A-Z][A-Za-z\s&]+) is a',
        r'About ([A-Z][A-Za-z\s&]+)',
        r'([A-Z][A-Za-z\s&]+) - ',  # Common in page titles
    ]
    company_names = []
    for pattern in company_patterns:
        matches = re.findall(pattern, text)
        company_names.extend(matches)
    
    # Remove common false positives
    company_names = [name.strip() for name in company_names 
                    if name.strip() not in ['Privacy', 'Terms', 'Contact', 'Home']]
    
    # Location patterns
    locations = re.findall(r'([A-Z][a-z]+),\s*([A-Z][a-z]+)', text)
    formatted_locations = [f"{city}, {state}" for city, state in locations]
    
    return {
        'company_name': company_names[0] if company_names else None,
        'emails': emails[:3],  # Limit to first 3 emails
        'founded_years': list(set(years)),  # Remove duplicates
        'employee_count': int(employee_matches[0]) if employee_matches else None,
        'locations': formatted_locations[:2],  # Limit locations
    }

def extract_with_smart_ai(text):
    """Enhanced AI extraction with better logic"""
    text_lower = text.lower()
    
    extracted = {}
    
    # Industry detection with more keywords
    industry_keywords = {
        'technology': ['software', 'technology', 'tech', 'AI', 'machine learning', 'cloud'],
        'consulting': ['consulting', 'advisory', 'professional services'],
        'manufacturing': ['manufacturing', 'production', 'factory', 'automotive'],
        'finance': ['finance', 'banking', 'investment', 'financial'],
        'healthcare': ['healthcare', 'medical', 'pharmaceutical', 'biotech'],
        'retail': ['retail', 'ecommerce', 'shopping', 'consumer'],
    }
    
    for industry, keywords in industry_keywords.items():
        if any(keyword in text_lower for keyword in keywords):
            extracted['industry'] = industry
            break
    
    # Services extraction with more patterns
    services = []
    service_patterns = {
        'web development': ['web development', 'website', 'web design'],
        'software development': ['software development', 'custom software', 'application development'],
        'consulting': ['consulting', 'advisory services', 'strategy'],
        'cloud services': ['cloud', 'AWS', 'Azure', 'cloud migration'],
        'data analytics': ['data analytics', 'business intelligence', 'data science'],
        'cybersecurity': ['cybersecurity', 'security', 'penetration testing'],
    }
    
    for service, patterns in service_patterns.items():
        if any(pattern in text_lower for pattern in patterns):
            services.append(service)
    
    if services:
        extracted['services'] = services
    
    # Extract key phrases that might be company descriptions
    description_indicators = ['we are', 'we help', 'we provide', 'our mission', 'we specialize']
    descriptions = []
    
    for line in text.split('\n'):
        line = line.strip()
        if any(indicator in line.lower() for indicator in description_indicators):
            if len(line) > 20 and len(line) < 200:  # Reasonable length
                descriptions.append(line)
    
    if descriptions:
        extracted['description'] = descriptions[0]  # Take the first good one
    
    return extracted

def full_extraction_pipeline(url):
    """Complete pipeline: scrape -> extract -> analyze"""
    
    print("🚀 Starting full extraction pipeline...")
    print("="*60)
    
    # Step 1: Scrape the website
    scrape_result = scrape_website(url)
    if "error" in scrape_result:
        return scrape_result
    
    # Step 2: Read the scraped file
    filename = scrape_result["filename"]
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Step 3: Extract with both methods
    print("\n🔍 Extracting data...")
    pattern_data = extract_with_patterns(content)
    ai_data = extract_with_smart_ai(content)
    
    # Step 4: Combine results
    final_result = {**pattern_data, **ai_data}
    
    # Step 5: Package everything
    complete_results = {
        'source': {
            'url': url,
            'filename': filename,
            'scraped_at': datetime.now().isoformat()
        },
        'extraction_methods': {
            'patterns': pattern_data,
            'smart_ai': ai_data
        },
        'final_result': final_result,
        'metadata': {
            'total_fields': len([v for v in final_result.values() if v]),
            'text_length': len(content)
        }
    }
    
    # Step 6: Save results
    result_filename = f"extraction_results_{urlparse(url).netloc.replace('www.', '').replace('.', '_')}.json"
    with open(result_filename, 'w', encoding='utf-8') as f:
        json.dump(complete_results, f, indent=2, ensure_ascii=False)
    
    return complete_results

# Test with real company websites
if __name__ == "__main__":
    
    # Test URLs - real company about pages
    test_urls = [
        "https://about.gitlab.com",
        "https://about.github.com", 
        "https://www.stripe.com/about",
        # Add more as needed
    ]
    
    print("🌐 Web Scraping + AI Extraction Pipeline")
    print("Choose an option:")
    print("1. Test with a predefined URL")
    print("2. Enter your own URL")
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    if choice == "1":
        url = test_urls[0]  # Default to GitLab
        print(f"Using: {url}")
    elif choice == "2":
        url = input("Enter company website URL: ").strip()
    else:
        print("Invalid choice, using default...")
        url = test_urls[0]
    
    # Run the pipeline
    results = full_extraction_pipeline(url)
    
    if "error" not in results:
        print("\n" + "="*60)
        print("🎯 EXTRACTION COMPLETE!")
        print("="*60)
        
        for key, value in results['final_result'].items():
            if value:
                print(f"  📊 {key}: {value}")
        
        print(f"\n📁 Files created:")
        print(f"  - {results['source']['filename']} (scraped content)")
        print(f"  - extraction_results_*.json (full results)")
        
    else:
        print(f"\n❌ Error: {results['error']}")
        print("\n💡 Tips:")
        print("  - Make sure the URL is accessible")
        print("  - Install dependencies: uv add requests beautifulsoup4")