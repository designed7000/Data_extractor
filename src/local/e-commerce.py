# E-commerce Price Tracker with GenAI Analysis - CLEAN VERSION
# Perfect CV project: Multi-site price monitoring + AI insights + Business value

import requests
from bs4 import BeautifulSoup
import json
import pandas as pd
from datetime import datetime
import time
import random
import re
from urllib.parse import urlparse, urljoin
import hashlib
import os
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

class EcommercePriceTracker:
    def __init__(self):
        self.session = requests.Session()
        self.setup_session()
        self.products = []
        self.price_history = []
    
    def setup_session(self):
        """Setup realistic browser headers to avoid blocking"""
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'DNT': '1',
            'Pragma': 'no-cache',
            'Sec-Ch-Ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # Set additional session attributes for better browser imitation
        self.session.cookies.set_policy({
            'strict_ns_domain': False,
            'strict_ns_set_initial_dollar': False,
            'strict_ns_set_path': False,
        })
        
        # Enable cookie persistence
        self.session.cookies.clear_session_cookies()
        
        # Set reasonable timeouts
        self.session.timeout = (10, 30)  # (connection timeout, read timeout)
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
    def detect_ecommerce_platform(self, url):
        """Detect which e-commerce platform we're scraping"""
        
        domain = urlparse(url).netloc.lower()
        
        if 'amazon' in domain:
            return 'amazon'
        elif 'ebay' in domain:
            return 'ebay'
        elif 'etsy' in domain:
            return 'etsy'
        elif 'shopify' in domain or 'myshopify' in domain:
            return 'shopify'
        elif 'walmart' in domain:
            return 'walmart'
        elif 'target' in domain:
            return 'target'
        elif 'bestbuy' in domain:
            return 'bestbuy'
        else:
            return 'generic'
    
    def clean_price_text(self, price_text):
        """Clean and deduplicate price text"""
        if not price_text:
            return None
        
        # Remove extra whitespace
        price_text = price_text.strip()
        
        # Handle duplicated prices like "$69.99$69.99" for different currencies as well   
        for currency in ['$','£', '€', '¥']:
            if currency in price_text:
                price_parts = [part for part in price_text.split(currency) if part.strip()]
                if price_parts:
                    first_price = re.sub(r'[^\d.,]', '', price_parts[0].strip())
                    if first_price:
                        return f"{currency}{first_price}"
        
        # If no currency symbol, just clean and return
        cleaned = re.sub(r'[^\d.,\$£€¥]', '', price_text)
        return cleaned if cleaned else None
    
    def scrape_category_products(self, category_url, max_products=50):
        """Scrape products from a category page"""
        
        print(f"🛒 Scraping category: {category_url}")
        platform = self.detect_ecommerce_platform(category_url)
        print(f"   Platform detected: {platform}")
        
        products = []
        
        try:
            time.sleep(random.uniform(2, 5))
            response = self.session.get(category_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Platform-specific product extraction
            if platform == 'amazon':
                products = self.extract_amazon_products(soup, category_url)
            elif platform == 'ebay':
                products = self.extract_ebay_products(soup, category_url)
            elif platform == 'shopify':
                products = self.extract_shopify_products(soup, category_url)
            else:
                products = self.extract_generic_products(soup, category_url)
            
            # Limit results
            products = products[:max_products]
            
            print(f"   ✅ Found {len(products)} products")
            
            # Get detailed product information
            detailed_products = []
            for i, product in enumerate(products[:20], 1):  # Limit for demo
                print(f"   Analyzing product {i}/20...")
                detailed_info = self.get_product_details(product)
                if detailed_info:
                    detailed_products.append(detailed_info)
                
                # Be respectful with delays
                time.sleep(random.uniform(1, 3))
            
            return detailed_products
            
        except Exception as e:
            print(f"   ❌ Error scraping category: {e}")
            return []
    
    def extract_amazon_products(self, soup, base_url):
        """Extract products from Amazon search/category page"""
        
        products = []
        
        # Amazon product selectors
        product_containers = soup.find_all(['div'], {
            'data-component-type': 's-search-result'
        }) or soup.find_all(['div'], class_=lambda x: x and 's-result-item' in x)
        
        for container in product_containers:
            try:
                # Product title
                title_elem = container.find(['h2', 'a'], class_=lambda x: x and 's-link' in x)
                title = title_elem.get_text(strip=True) if title_elem else None
                
                # Product URL
                link_elem = container.find('a', class_=lambda x: x and 's-link' in x)
                product_url = urljoin(base_url, link_elem['href']) if link_elem and link_elem.get('href') else None
                
                # Price - improved extraction
                price = None
                price_selectors = [
                    'span.a-price-whole',
                    'span.a-price.a-text-price.a-size-medium.a-color-base',
                    'span.a-price-range',
                    '.a-price .a-offscreen',
                    '.a-price-whole',
                    '[data-a-size="xl"] .a-offscreen',
                    '.a-price .a-price-whole'
                ]
                
                for selector in price_selectors:
                    price_elem = container.select_one(selector)
                    if price_elem:
                        price_text = price_elem.get_text(strip=True)
                        # Clean up duplicated prices
                        price = self.clean_price_text(price_text)
                        break
                
                # If no price found with specific selectors, try general approach
                if not price:
                    price_elem = container.find(['span'], string=re.compile(r'\$[\d,]+(?:\.\d{2})?'))
                    if price_elem:
                        price = self.clean_price_text(price_elem.get_text(strip=True))
                
                # Rating
                rating_elem = container.find(['span'], class_=lambda x: x and 'rating' in x.lower())
                rating = rating_elem.get_text(strip=True) if rating_elem else None
                
                # Image
                img_elem = container.find('img')
                image_url = img_elem.get('src') if img_elem else None
                
                if title and product_url:
                    products.append({
                        'title': title,
                        'url': product_url,
                        'price_text': price,
                        'rating': rating,
                        'image_url': image_url,
                        'platform': 'amazon'
                    })
                    
            except Exception as e:
                continue
        
        return products
    
    def extract_ebay_products(self, soup, base_url):
        """Extract products from eBay search/category page"""
        
        products = []
        
        # eBay product selectors
        product_containers = soup.find_all(['div'], class_=lambda x: x and 's-item' in x)
        
        for container in product_containers:
            try:
                # Title
                title_elem = container.find(['h3', 'a'], class_=lambda x: x and 's-item__title' in x)
                title = title_elem.get_text(strip=True) if title_elem else None
                
                # URL
                link_elem = container.find('a', class_=lambda x: x and 's-item__link' in x)
                product_url = link_elem['href'] if link_elem and link_elem.get('href') else None
                
                # Price
                price_elem = container.find(['span'], class_=lambda x: x and 's-item__price' in x)
                price_text = price_elem.get_text(strip=True) if price_elem else None
                price = self.clean_price_text(price_text) if price_text else None
                
                # Image
                img_elem = container.find('img')
                image_url = img_elem.get('src') if img_elem else None
                
                if title and product_url:
                    products.append({
                        'title': title,
                        'url': product_url,
                        'price_text': price,
                        'rating': None,
                        'image_url': image_url,
                        'platform': 'ebay'
                    })
                    
            except Exception as e:
                continue
        
        return products
    
    def extract_generic_products(self, soup, base_url):
        """Generic product extraction for unknown e-commerce sites"""
        
        products = []
        
        # Common product container patterns
        container_selectors = [
            {'class': lambda x: x and any(word in x.lower() for word in ['product', 'item', 'card'])},
            {'class': lambda x: x and 'grid' in x.lower()},
            {'data-testid': lambda x: x and 'product' in x.lower()}
        ]
        
        product_containers = []
        for selector in container_selectors:
            containers = soup.find_all(['div', 'article', 'li'], selector)
            if containers:
                product_containers = containers
                break
        
        for container in product_containers[:30]:  # Limit to avoid noise
            try:
                # Find title
                title_elem = (
                    container.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']) or
                    container.find('a', class_=lambda x: x and any(word in x.lower() for word in ['title', 'name', 'product'])) or
                    container.find(['span', 'div'], class_=lambda x: x and any(word in x.lower() for word in ['title', 'name']))
                )
                title = title_elem.get_text(strip=True) if title_elem else None
                
                # Find URL
                link_elem = container.find('a', href=True)
                product_url = urljoin(base_url, link_elem['href']) if link_elem else None
                
                # Find price - improved approach
                price = None
                
                # Try price-specific selectors first
                price_selectors = [
                    {'class': lambda x: x and 'price' in x.lower()},
                    {'class': lambda x: x and 'cost' in x.lower()},
                    {'class': lambda x: x and 'amount' in x.lower()}
                ]
                
                for selector in price_selectors:
                    price_elem = container.find(['span', 'div', 'p'], selector)
                    if price_elem:
                        price_text = price_elem.get_text(strip=True)
                        price = self.clean_price_text(price_text)
                        if price:
                            break
                
                # If no price found, look for currency patterns in text
                if not price:
                    # Look for elements containing currency symbols
                    currency_patterns = [
                        re.compile(r'[\$£€¥]\s*[\d,]+(?:\.\d{2})?'),
                        re.compile(r'[\d,]+(?:\.\d{2})?\s*[\$£€¥]'),
                        re.compile(r'\b\d+\.\d{2}\b')  # Decimal prices without currency
                    ]
                    
                    container_text = container.get_text()
                    for pattern in currency_patterns:
                        match = pattern.search(container_text)
                        if match:
                            price = self.clean_price_text(match.group())
                            break
                
                # Find image
                img_elem = container.find('img')
                image_url = img_elem.get('src') if img_elem else None
                
                if title and len(title) > 3:  # Basic validation
                    products.append({
                        'title': title,
                        'url': product_url,
                        'price_text': price,
                        'rating': None,
                        'image_url': image_url,
                        'platform': 'generic'
                    })
                    
            except Exception as e:
                continue
        
        return products
    
    def extract_shopify_products(self, soup, base_url):
        """Extract products from Shopify stores"""
        
        products = []
        
        # Shopify common selectors
        product_containers = soup.find_all(['div'], class_=lambda x: x and any(word in x.lower() for word in ['product-item', 'product-card', 'grid-item']))
        
        for container in product_containers:
            try:
                # Title
                title_elem = container.find(['h2', 'h3', 'a'], class_=lambda x: x and any(word in x.lower() for word in ['title', 'name']))
                title = title_elem.get_text(strip=True) if title_elem else None
                
                # URL
                link_elem = container.find('a', href=True)
                product_url = urljoin(base_url, link_elem['href']) if link_elem else None
                
                # Price
                price_elem = container.find(['span', 'div'], class_=lambda x: x and 'price' in x.lower())
                price_text = price_elem.get_text(strip=True) if price_elem else None
                price = self.clean_price_text(price_text) if price_text else None
                
                # Image
                img_elem = container.find('img')
                image_url = img_elem.get('src') if img_elem else None
                
                if title and product_url:
                    products.append({
                        'title': title,
                        'url': product_url,
                        'price_text': price,
                        'rating': None,
                        'image_url': image_url,
                        'platform': 'shopify'
                    })
                    
            except Exception as e:
                continue
        
        return products
    
    def get_product_details(self, product):
        """Get detailed information for a single product"""
        
        if not product.get('url'):
            return product
        
        try:
            time.sleep(random.uniform(1, 3))
            response = self.session.get(product['url'], timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract additional details
            details = {
                **product,  # Keep original data
                'scraped_at': datetime.now().isoformat(),
                'product_id': hashlib.md5(product['url'].encode()).hexdigest()[:12]
            }
            
            # Get description
            desc_selectors = [
                {'id': lambda x: x and 'description' in x.lower()},
                {'class': lambda x: x and 'description' in x.lower()},
                {'class': lambda x: x and 'detail' in x.lower()}
            ]
            
            for selector in desc_selectors:
                desc_elem = soup.find(['div', 'p', 'section'], selector)
                if desc_elem:
                    details['description'] = desc_elem.get_text(strip=True)[:500]  # Limit length
                    break
            
            # Parse price to numeric value
            if product.get('price_text'):
                details['price_numeric'] = self.parse_price(product['price_text'])
            
            # Get availability
            availability_indicators = ['in stock', 'available', 'add to cart', 'buy now', 'out of stock', 'sold out']
            page_text = soup.get_text().lower()
            
            for indicator in availability_indicators:
                if indicator in page_text:
                    details['availability'] = indicator
                    break
            
            return details
            
        except Exception as e:
            return {**product, 'error': str(e), 'scraped_at': datetime.now().isoformat()}
    
    def parse_price(self, price_text):
        """Extract numeric price from price text - improved version"""
        
        if not price_text:
            return None
        
        # First clean the price text
        cleaned_price = self.clean_price_text(price_text)
        if not cleaned_price:
            return None
        
        # Remove currency symbols and extract numbers
        price_clean = re.sub(r'[\$£€¥]', '', cleaned_price)
        price_clean = re.sub(r'[^\d.,]', '', price_clean)
        
        if not price_clean:
            return None
        
        # Handle different decimal separators
        if ',' in price_clean and '.' in price_clean:
            # Format like 1,234.56
            price_clean = price_clean.replace(',', '')
        elif ',' in price_clean:
            # Could be 1,56 (European) or 1,234 (US thousands separator)
            if len(price_clean.split(',')[-1]) == 2:
                # European decimal: 1,56 -> 1.56
                price_clean = price_clean.replace(',', '.')
            else:
                # US thousands: 1,234 -> 1234
                price_clean = price_clean.replace(',', '')
        
        try:
            return float(price_clean)
        except (ValueError, TypeError):
            return None
    
    def analyze_with_ai(self, products):
        """Analyze products with AI for insights"""
        
        if not GEMINI_AVAILABLE:
            return self.analyze_without_ai(products)
        
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            return self.analyze_without_ai(products)
        
        print(f"🤖 Analyzing {len(products)} products with Gemini AI...")
        
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-pro')
            
            # Prepare product data for AI analysis
            product_summary = []
            for product in products[:20]:  # Limit for token constraints
                summary = {
                    'title': product.get('title', '')[:100],
                    'price': product.get('price_numeric', 0),
                    'platform': product.get('platform', ''),
                    'availability': product.get('availability', '')
                }
                product_summary.append(summary)
            
            prompt = f"""
            Analyze this e-commerce product data and provide business insights.
            Return ONLY valid JSON:
            
            {{
                "price_analysis": {{
                    "average_price": 0.0,
                    "price_range": "min - max",
                    "price_distribution": "analysis of price spread",
                    "value_opportunities": ["product1", "product2"]
                }},
                "market_insights": {{
                    "category_trends": "analysis of product category",
                    "platform_comparison": "which platforms have better prices",
                    "availability_status": "overall stock situation",
                    "seasonal_indicators": "any seasonal pricing patterns"
                }},
                "recommendations": {{
                    "best_deals": [
                        {{
                            "product": "product name",
                            "reason": "why it's a good deal",
                            "confidence": 0.9
                        }}
                    ],
                    "price_alerts": ["products to watch for price drops"],
                    "buying_timing": "best time to buy analysis",
                    "market_position": "how these prices compare to market"
                }},
                "competitive_analysis": {{
                    "price_leaders": "platforms with best prices",
                    "premium_vs_budget": "analysis of price segments",
                    "market_gaps": "opportunities in the market"
                }}
            }}
            
            Product data: {json.dumps(product_summary, indent=2)}
            """
            
            response = model.generate_content(prompt)
            ai_result = response.text.strip()
            
            if ai_result.startswith('```json'):
                ai_result = ai_result.replace('```json', '').replace('```', '').strip()
            
            try:
                ai_analysis = json.loads(ai_result)
                
                # Add non-AI analysis
                basic_analysis = self.analyze_without_ai(products)
                
                return {
                    **ai_analysis,
                    'basic_statistics': basic_analysis,
                    'ai_powered': True,
                    'analysis_date': datetime.now().isoformat()
                }
                
            except json.JSONDecodeError:
                print("   ⚠️  AI returned invalid JSON, falling back to basic analysis")
                return self.analyze_without_ai(products)
                
        except Exception as e:
            print(f"   ⚠️  AI analysis failed: {e}, using basic analysis")
            return self.analyze_without_ai(products)
    
    def analyze_without_ai(self, products):
        """Basic analysis without AI"""
        
        print(f"📊 Analyzing {len(products)} products with basic statistics...")
        
        # Price analysis
        prices = [p.get('price_numeric') for p in products if p.get('price_numeric')]
        
        price_stats = {}
        if prices:
            price_stats = {
                'average_price': sum(prices) / len(prices),
                'min_price': min(prices),
                'max_price': max(prices),
                'price_count': len(prices)
            }
        
        # Platform analysis
        platforms = [p.get('platform') for p in products if p.get('platform')]
        platform_counts = {}
        for platform in platforms:
            platform_counts[platform] = platform_counts.get(platform, 0) + 1
        
        # Availability analysis
        availability = [p.get('availability') for p in products if p.get('availability')]
        availability_counts = {}
        for avail in availability:
            availability_counts[avail] = availability_counts.get(avail, 0) + 1
        
        return {
            'total_products_analyzed': len(products),
            'price_statistics': price_stats,
            'platform_distribution': platform_counts,
            'availability_status': availability_counts,
            'top_products_by_price': sorted(
                [p for p in products if p.get('price_numeric')], 
                key=lambda x: x['price_numeric']
            )[:10],
            'ai_powered': False,
            'analysis_date': datetime.now().isoformat()
        }
    
    def save_results(self, products, analysis, category_name="category"):
        """Save all results to files in the data folder outside src"""
        
        # Get the parent directory of src (go up one level from current script location)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        data_dir = os.path.join(parent_dir, 'data')
        
        # Ensure data directory exists
        os.makedirs(data_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_category = re.sub(r'[^\w\-_]', '_', category_name)
        
        # Save product data
        products_filename = os.path.join(data_dir, f"products_{safe_category}_{timestamp}.json")
        with open(products_filename, 'w', encoding='utf-8') as f:
            json.dump(products, f, indent=2, ensure_ascii=False)
        
        # Save analysis
        analysis_filename = os.path.join(data_dir, f"analysis_{safe_category}_{timestamp}.json")
        with open(analysis_filename, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        
        # Save as CSV
        csv_filename = None
        if products:
            df = pd.DataFrame(products)
            csv_filename = os.path.join(data_dir, f"products_{safe_category}_{timestamp}.csv")
            df.to_csv(csv_filename, index=False)
            print(f"💾 Saved: {csv_filename}")
        
        print(f"💾 Saved: {products_filename}")
        print(f"💾 Saved: {analysis_filename}")
        
        return {
            'products_file': products_filename,
            'analysis_file': analysis_filename,
            'csv_file': csv_filename
        }
    
    def generate_price_alerts(self, products, threshold_percentage=20):
        """Generate price alert recommendations"""
        
        alerts = []
        
        if not products:
            return alerts
        
        prices = [p.get('price_numeric') for p in products if p.get('price_numeric')]
        if not prices:
            return alerts
        
        avg_price = sum(prices) / len(prices)
        
        for product in products:
            price = product.get('price_numeric')
            if price and price < avg_price * (1 - threshold_percentage/100):
                alerts.append({
                    'product': product.get('title', ''),
                    'current_price': price,
                    'average_price': avg_price,
                    'discount_percentage': ((avg_price - price) / avg_price) * 100,
                    'url': product.get('url', ''),
                    'platform': product.get('platform', ''),
                    'alert_type': 'good_deal'
                })
        
        return sorted(alerts, key=lambda x: x['discount_percentage'], reverse=True)

def run_price_tracking_analysis():
    """Main function to run price tracking analysis"""
    
    print("🛒 E-commerce Price Tracker with AI Analysis")
    print("="*60)
    
    tracker = EcommercePriceTracker()
    
    # Get category URL from user
    category_url = input("Enter e-commerce category URL: ").strip()
    
    if not category_url:
        # Default example URLs for testing
        examples = [
            "https://www.amazon.com/s?k=laptops",
            "https://www.ebay.com/sch/i.html?_nkw=smartphones",
            "https://www.etsy.com/search?q=handmade+jewelry"
        ]
        print(f"Using example: {examples[0]}")
        category_url = examples[0]
    
    # Extract category name for file naming
    category_name = input("Enter category name (for file naming): ").strip() or "products"
    
    print(f"\n🎯 Target: {category_url}")
    print(f"📂 Category: {category_name}")
    
    # Scrape products
    products = tracker.scrape_category_products(category_url, max_products=30)
    
    if products:
        print(f"\n📊 Successfully scraped {len(products)} products")
        
        # Analyze with AI
        analysis = tracker.analyze_with_ai(products)
        
        # Generate price alerts
        alerts = tracker.generate_price_alerts(products)
        analysis['price_alerts'] = alerts
        
        # Save results
        files = tracker.save_results(products, analysis, category_name)
        
        # Display key insights
        print("\n" + "="*60)
        print("💰 PRICE TRACKING INSIGHTS")
        print("="*60)
        
        if analysis.get('price_statistics'):
            stats = analysis['price_statistics']
            print(f"💵 Price Analysis:")
        if analysis.get('price_statistics'):
            stats = analysis['price_statistics']
            print(f"💵 Price Analysis:")
            print(f"   Average: ${stats.get('average_price', 0):.2f}")
            print(f"   Range: ${stats.get('min_price', 0):.2f} - ${stats.get('max_price', 0):.2f}")
            print(f"   Products with prices: {stats.get('price_count', 0)}")
        
        if analysis.get('platform_distribution'):
            print(f"\n🏪 Platform Distribution:")
            for platform, count in analysis['platform_distribution'].items():
                print(f"   {platform}: {count} products")
        
        if alerts:
            print(f"\n🚨 Price Alerts ({len(alerts)} deals found):")
            for alert in alerts[:5]:
                discount = alert['discount_percentage']
                print(f"   📉 {alert['product'][:50]}...")
                print(f"       {discount:.1f}% below average (${alert['current_price']:.2f})")
        
        if analysis.get('recommendations'):
            recs = analysis['recommendations']
            if recs.get('best_deals'):
                print(f"\n🎯 AI Recommendations:")
                for deal in recs['best_deals'][:3]:
                    print(f"   ⭐ {deal.get('product', '')}")
                    print(f"       {deal.get('reason', '')}")
        
        print(f"\n📁 Files created:")
        for file_type, filename in files.items():
            if filename:
                print(f"   {file_type}: {filename}")
        
        return {
            'products': products,
            'analysis': analysis,
            'alerts': alerts,
            'files': files
        }
    
    else:
        print("❌ No products found. Try a different URL or check site accessibility.")
        return None

if __name__ == "__main__":
    # Check dependencies
    print("🔍 Checking dependencies...")
    print(f"   Gemini AI: {'✅' if GEMINI_AVAILABLE else '❌'}")
    
    if not GEMINI_AVAILABLE:
        print("   💡 Install for AI features: uv add google-generativeai")
    elif not os.getenv('GEMINI_API_KEY'):
        print("   🔑 Set GEMINI_API_KEY for AI analysis")
    
    # Run the analysis
    results = run_price_tracking_analysis()
    
    if results:
        print(f"\n🎓 CV Project Benefits:")
        print(f"   ✅ Multi-platform e-commerce scraping")
        print(f"   ✅ Intelligent product detection")
        print(f"   ✅ Price parsing and analysis")
        print(f"   ✅ AI-powered market insights")
        print(f"   ✅ Price alert generation")
        print(f"   ✅ Business intelligence output")
        print(f"   ✅ Cross-platform compatibility")
        
        print(f"\n🚀 Expansion Ideas:")
        print(f"   1. Add price history tracking")
        print(f"   2. Build email/SMS alerts")
        print(f"   3. Create price prediction models")
        print(f"   4. Add competitor analysis")
        print(f"   5. Build web dashboard")
        print(f"   6. API for developers")
        print(f"   7. Mobile app integration")