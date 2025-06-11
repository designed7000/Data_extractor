# E-commerce Price Tracker with Price History Tracking
# Advanced CV project: Multi-site monitoring + Historical analysis + Trend prediction

import requests
from bs4 import BeautifulSoup
import json
import pandas as pd
from datetime import datetime, timedelta
import time
import random
import re
from urllib.parse import urlparse, urljoin
import hashlib
import os
import sqlite3
from typing import List, Dict, Optional

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

class PriceHistoryDatabase:
    """Handles all database operations for price history"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Save database in data folder
            current_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_dir)
            data_dir = os.path.join(parent_dir, 'data')
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, 'price_history.db')
        
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Products table - stores unique product information
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                title TEXT,
                platform TEXT,
                category TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        # Price history table - stores all price records
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT,
                price REAL,
                price_text TEXT,
                availability TEXT,
                rating TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source_session TEXT,
                FOREIGN KEY (product_id) REFERENCES products (product_id)
            )
        ''')
        
        # Price alerts table - stores significant price changes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT,
                alert_type TEXT,  -- 'price_drop', 'price_increase', 'back_in_stock', 'out_of_stock'
                old_price REAL,
                new_price REAL,
                percentage_change REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_notified BOOLEAN DEFAULT 0,
                FOREIGN KEY (product_id) REFERENCES products (product_id)
            )
        ''')
        
        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_price_history_product_id ON price_history(product_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_price_history_date ON price_history(scraped_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_product_id ON price_alerts(product_id)')
        
        conn.commit()
        conn.close()
        
        print(f"📊 Database initialized: {self.db_path}")
    
    def save_product(self, product_data: Dict) -> str:
        """Save or update product information"""
        
        product_id = product_data.get('product_id')
        if not product_id:
            # Generate product ID from URL
            product_id = hashlib.md5(product_data['url'].encode()).hexdigest()[:12]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if product exists
        cursor.execute('SELECT product_id FROM products WHERE product_id = ?', (product_id,))
        exists = cursor.fetchone()
        
        if exists:
            # Update existing product
            cursor.execute('''
                UPDATE products 
                SET title = ?, platform = ?, last_updated = CURRENT_TIMESTAMP, is_active = 1
                WHERE product_id = ?
            ''', (product_data.get('title'), product_data.get('platform'), product_id))
        else:
            # Insert new product
            cursor.execute('''
                INSERT INTO products (product_id, url, title, platform, category)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                product_id,
                product_data.get('url'),
                product_data.get('title'),
                product_data.get('platform'),
                product_data.get('category', 'unknown')
            ))
        
        conn.commit()
        conn.close()
        
        return product_id
    
    def save_price_record(self, product_id: str, price_data: Dict, session_id: str = None):
        """Save a price record to history"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if session_id is None:
            session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        cursor.execute('''
            INSERT INTO price_history (product_id, price, price_text, availability, rating, source_session)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            product_id,
            price_data.get('price_numeric'),
            price_data.get('price_text'),
            price_data.get('availability'),
            price_data.get('rating'),
            session_id
        ))
        
        conn.commit()
        conn.close()
    
    def get_latest_price(self, product_id: str) -> Optional[Dict]:
        """Get the most recent price for a product"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT price, price_text, availability, scraped_at
            FROM price_history
            WHERE product_id = ?
            ORDER BY scraped_at DESC
            LIMIT 1
        ''', (product_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'price': result[0],
                'price_text': result[1],
                'availability': result[2],
                'scraped_at': result[3]
            }
        return None
    
    def get_price_history(self, product_id: str, days: int = 30) -> List[Dict]:
        """Get price history for a product"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        since_date = datetime.now() - timedelta(days=days)
        
        cursor.execute('''
            SELECT price, price_text, availability, scraped_at
            FROM price_history
            WHERE product_id = ? AND scraped_at >= ?
            ORDER BY scraped_at ASC
        ''', (product_id, since_date.isoformat()))
        
        results = cursor.fetchall()
        conn.close()
        
        return [
            {
                'price': row[0],
                'price_text': row[1],
                'availability': row[2],
                'scraped_at': row[3]
            }
            for row in results
        ]
    
    def detect_price_changes(self, product_id: str, new_price: float, threshold: float = 5.0) -> Optional[Dict]:
        """Detect significant price changes and create alerts"""
        
        latest_price = self.get_latest_price(product_id)
        
        if not latest_price or not latest_price['price'] or not new_price:
            return None
        
        old_price = float(latest_price['price'])
        percentage_change = ((new_price - old_price) / old_price) * 100
        
        # Only create alert if change is significant
        if abs(percentage_change) >= threshold:
            alert_type = 'price_drop' if percentage_change < 0 else 'price_increase'
            
            # Save alert to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO price_alerts (product_id, alert_type, old_price, new_price, percentage_change)
                VALUES (?, ?, ?, ?, ?)
            ''', (product_id, alert_type, old_price, new_price, percentage_change))
            
            conn.commit()
            conn.close()
            
            return {
                'alert_type': alert_type,
                'old_price': old_price,
                'new_price': new_price,
                'percentage_change': percentage_change,
                'is_significant': True
            }
        
        return {
            'alert_type': 'minor_change',
            'old_price': old_price,
            'new_price': new_price,
            'percentage_change': percentage_change,
            'is_significant': False
        }
    
    def get_trending_products(self, days: int = 7, limit: int = 10) -> List[Dict]:
        """Get products with the most significant price changes"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        since_date = datetime.now() - timedelta(days=days)
        
        cursor.execute('''
            SELECT 
                p.product_id,
                p.title,
                p.platform,
                pa.alert_type,
                pa.percentage_change,
                pa.old_price,
                pa.new_price,
                pa.created_at
            FROM price_alerts pa
            JOIN products p ON pa.product_id = p.product_id
            WHERE pa.created_at >= ?
            ORDER BY ABS(pa.percentage_change) DESC
            LIMIT ?
        ''', (since_date.isoformat(), limit))
        
        results = cursor.fetchall()
        conn.close()
        
        return [
            {
                'product_id': row[0],
                'title': row[1],
                'platform': row[2],
                'alert_type': row[3],
                'percentage_change': row[4],
                'old_price': row[5],
                'new_price': row[6],
                'created_at': row[7]
            }
            for row in results
        ]

class EcommercePriceHistoryTracker:
    """Enhanced price tracker with historical data"""
    
    def __init__(self):
        self.session = requests.Session()
        self.setup_session()
        self.db = PriceHistoryDatabase()
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
    def setup_session(self):
        """Setup realistic browser headers to avoid blocking"""
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def track_products_from_urls(self, product_urls: List[str], category: str = "tracked") -> Dict:
        """Track specific products by their URLs - perfect for monitoring watchlist"""
        
        print(f"🎯 Tracking {len(product_urls)} specific products...")
        
        tracked_products = []
        price_changes = []
        
        for i, url in enumerate(product_urls, 1):
            print(f"   Processing product {i}/{len(product_urls)}...")
            
            try:
                # Scrape current product data
                product_data = self.scrape_single_product(url, category)
                
                if product_data:
                    # Save product to database
                    product_id = self.db.save_product(product_data)
                    product_data['product_id'] = product_id
                    
                    # Save current price record
                    self.db.save_price_record(product_id, product_data, self.session_id)
                    
                    # Check for price changes
                    if product_data.get('price_numeric'):
                        price_change = self.db.detect_price_changes(
                            product_id, 
                            product_data['price_numeric'],
                            threshold=3.0  # 3% threshold for individual tracking
                        )
                        
                        if price_change and price_change.get('is_significant'):
                            price_changes.append({
                                **product_data,
                                **price_change
                            })
                    
                    tracked_products.append(product_data)
                
                # Be respectful with delays
                time.sleep(random.uniform(2, 4))
                
            except Exception as e:
                print(f"   ❌ Error tracking {url}: {e}")
                continue
        
        return {
            'tracked_products': tracked_products,
            'price_changes': price_changes,
            'session_id': self.session_id,
            'tracking_summary': {
                'total_tracked': len(tracked_products),
                'price_changes_detected': len(price_changes),
                'successful_rate': len(tracked_products) / len(product_urls) * 100
            }
        }
    
    def scrape_single_product(self, url: str, category: str = "tracked") -> Optional[Dict]:
        """Scrape a single product page for current information"""
        
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            platform = self.detect_ecommerce_platform(url)
            
            # Extract basic product info
            product_data = {
                'url': url,
                'platform': platform,
                'category': category,
                'scraped_at': datetime.now().isoformat()
            }
            
            # Platform-specific extraction
            if platform == 'amazon':
                product_data.update(self.extract_amazon_product_details(soup))
            elif platform == 'ebay':
                product_data.update(self.extract_ebay_product_details(soup))
            else:
                product_data.update(self.extract_generic_product_details(soup))
            
            # Clean and parse price
            if product_data.get('price_text'):
                product_data['price_text'] = self.clean_price_text(product_data['price_text'])
                product_data['price_numeric'] = self.parse_price(product_data['price_text'])
            
            return product_data
            
        except Exception as e:
            print(f"   Error scraping {url}: {e}")
            return None
    
    def detect_ecommerce_platform(self, url: str) -> str:
        """Detect e-commerce platform from URL"""
        domain = urlparse(url).netloc.lower()
        
        if 'amazon' in domain:
            return 'amazon'
        elif 'ebay' in domain:
            return 'ebay'
        elif 'etsy' in domain:
            return 'etsy'
        elif 'shopify' in domain:
            return 'shopify'
        else:
            return 'generic'
    
    def extract_amazon_product_details(self, soup) -> Dict:
        """Extract product details from Amazon product page"""
        
        details = {}
        
        # Title
        title_selectors = ['#productTitle', 'h1.a-size-large', '.product-title']
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                details['title'] = title_elem.get_text(strip=True)
                break
        
        # Price
        price_selectors = [
            '.a-price .a-offscreen',
            '.a-price-whole',
            '#priceblock_dealprice',
            '#priceblock_ourprice',
            '.a-price.a-text-price.a-size-medium.a-color-base'
        ]
        
        for selector in price_selectors:
            price_elem = soup.select_one(selector)
            if price_elem:
                details['price_text'] = price_elem.get_text(strip=True)
                break
        
        # Availability
        availability_selectors = ['#availability span', '.a-color-success', '.a-color-state']
        for selector in availability_selectors:
            avail_elem = soup.select_one(selector)
            if avail_elem:
                details['availability'] = avail_elem.get_text(strip=True)
                break
        
        # Rating
        rating_elem = soup.select_one('.a-icon-alt')
        if rating_elem:
            details['rating'] = rating_elem.get_text(strip=True)
        
        return details
    
    def extract_ebay_product_details(self, soup) -> Dict:
        """Extract product details from eBay product page"""
        
        details = {}
        
        # Title
        title_elem = soup.select_one('#x-title-label-lbl')
        if title_elem:
            details['title'] = title_elem.get_text(strip=True)
        
        # Price
        price_selectors = ['.notranslate', '.u-flL.condText', '.display-price']
        for selector in price_selectors:
            price_elem = soup.select_one(selector)
            if price_elem and '$' in price_elem.get_text():
                details['price_text'] = price_elem.get_text(strip=True)
                break
        
        # Availability
        availability_elem = soup.select_one('.u-flL.condText')
        if availability_elem:
            details['availability'] = availability_elem.get_text(strip=True)
        
        return details
    
    def extract_generic_product_details(self, soup) -> Dict:
        """Generic product details extraction"""
        
        details = {}
        
        # Title - try common patterns
        title_selectors = ['h1', '.product-title', '.product-name', '[class*="title"]']
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                title_text = title_elem.get_text(strip=True)
                if len(title_text) > 10:  # Reasonable title length
                    details['title'] = title_text
                    break
        
        # Price - look for currency patterns
        price_patterns = [
            re.compile(r'\$[\d,]+(?:\.\d{2})?'),
            re.compile(r'£[\d,]+(?:\.\d{2})?'),
            re.compile(r'€[\d,]+(?:\.\d{2})?')
        ]
        
        page_text = soup.get_text()
        for pattern in price_patterns:
            match = pattern.search(page_text)
            if match:
                details['price_text'] = match.group()
                break
        
        return details
    
    def clean_price_text(self, price_text: str) -> str:
        """Clean price text (reuse from original implementation)"""
        if not price_text:
            return None
        
        price_text = price_text.strip()
        
        # Handle duplicated prices like "$69.99$69.99"
        if '$' in price_text:
            price_parts = [part for part in price_text.split('$') if part.strip()]
            if price_parts:
                first_price = price_parts[0].strip()
                first_price = re.sub(r'[^\d.,]', '', first_price)
                if first_price:
                    return f"${first_price}"
        
        # Handle other currencies
        for currency in ['£', '€', '¥']:
            if currency in price_text:
                price_parts = [part for part in price_text.split(currency) if part.strip()]
                if price_parts:
                    first_price = re.sub(r'[^\d.,]', '', price_parts[0].strip())
                    if first_price:
                        return f"{currency}{first_price}"
        
        cleaned = re.sub(r'[^\d.,\$£€¥]', '', price_text)
        return cleaned if cleaned else None
    
    def parse_price(self, price_text: str) -> Optional[float]:
        """Parse price text to numeric value (reuse from original)"""
        if not price_text:
            return None
        
        cleaned_price = self.clean_price_text(price_text)
        if not cleaned_price:
            return None
        
        price_clean = re.sub(r'[\$£€¥]', '', cleaned_price)
        price_clean = re.sub(r'[^\d.,]', '', price_clean)
        
        if not price_clean:
            return None
        
        if ',' in price_clean and '.' in price_clean:
            price_clean = price_clean.replace(',', '')
        elif ',' in price_clean:
            if len(price_clean.split(',')[-1]) == 2:
                price_clean = price_clean.replace(',', '.')
            else:
                price_clean = price_clean.replace(',', '')
        
        try:
            return float(price_clean)
        except (ValueError, TypeError):
            return None
    
    def analyze_price_trends(self, product_id: str = None, days: int = 30) -> Dict:
        """Analyze price trends for products"""
        
        analysis = {
            'period_days': days,
            'analysis_date': datetime.now().isoformat(),
            'trending_products': [],
            'summary_stats': {}
        }
        
        if product_id:
            # Analyze specific product
            history = self.db.get_price_history(product_id, days)
            if history:
                prices = [h['price'] for h in history if h['price']]
                if len(prices) >= 2:
                    analysis['product_trend'] = {
                        'product_id': product_id,
                        'price_points': len(prices),
                        'current_price': prices[-1],
                        'starting_price': prices[0],
                        'min_price': min(prices),
                        'max_price': max(prices),
                        'average_price': sum(prices) / len(prices),
                        'total_change': ((prices[-1] - prices[0]) / prices[0]) * 100,
                        'volatility': max(prices) - min(prices)
                    }
        else:
            # Analyze trending products across platform
            trending = self.db.get_trending_products(days, limit=20)
            analysis['trending_products'] = trending
            
            if trending:
                changes = [t['percentage_change'] for t in trending]
                analysis['summary_stats'] = {
                    'total_price_alerts': len(trending),
                    'biggest_drop': min(changes),
                    'biggest_increase': max(changes),
                    'average_change': sum(changes) / len(changes)
                }
        
        return analysis
    
    def generate_watchlist_report(self, product_urls: List[str]) -> Dict:
        """Generate a comprehensive report for a watchlist of products"""
        
        print("📊 Generating watchlist report...")
        
        # Track all products
        tracking_results = self.track_products_from_urls(product_urls, "watchlist")
        
        # Analyze trends for each product
        trend_analysis = []
        for product in tracking_results['tracked_products']:
            if product.get('product_id'):
                trends = self.analyze_price_trends(product['product_id'], days=30)
                if trends.get('product_trend'):
                    trend_analysis.append({
                        'product': product,
                        'trends': trends['product_trend']
                    })
        
        # Get overall market trends
        market_trends = self.analyze_price_trends(days=7)
        
        # Compile comprehensive report
        report = {
            'report_generated': datetime.now().isoformat(),
            'watchlist_summary': {
                'total_products': len(product_urls),
                'successfully_tracked': len(tracking_results['tracked_products']),
                'price_changes_detected': len(tracking_results['price_changes']),
                'success_rate': tracking_results['tracking_summary']['successful_rate']
            },
            'current_session': tracking_results,
            'trend_analysis': trend_analysis,
            'market_overview': market_trends,
            'actionable_insights': self.generate_insights(tracking_results, trend_analysis)
        }
        
        # Save comprehensive report
        self.save_history_report(report)
        
        return report
    
    def generate_insights(self, tracking_results: Dict, trend_analysis: List) -> List[str]:
        """Generate actionable insights from the data"""
        
        insights = []
        
        # Price change insights
        significant_drops = [p for p in tracking_results['price_changes'] if p.get('percentage_change', 0) < -10]
        if significant_drops:
            insights.append(f"🔥 {len(significant_drops)} products have dropped 10%+ in price - potential buying opportunities")
        
        # Trend insights
        if trend_analysis:
            volatile_products = [t for t in trend_analysis if t['trends'].get('volatility', 0) > 50]
            if volatile_products:
                insights.append(f"⚠️ {len(volatile_products)} products showing high price volatility - monitor closely")
        
        # Availability insights
        availability_issues = [p for p in tracking_results['tracked_products'] 
                              if p.get('availability') and 'out of stock' in p['availability'].lower()]
        if availability_issues:
            insights.append(f"📦 {len(availability_issues)} products currently out of stock")
        
        return insights
    
    def save_history_report(self, report: Dict):
        """Save the comprehensive report to files"""
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        data_dir = os.path.join(parent_dir, 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save detailed JSON report
        report_file = os.path.join(data_dir, f"price_history_report_{timestamp}.json")
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # Save CSV summary for easy analysis
        if report['current_session']['tracked_products']:
            df = pd.DataFrame(report['current_session']['tracked_products'])
            csv_file = os.path.join(data_dir, f"tracked_products_{timestamp}.csv")
            df.to_csv(csv_file, index=False)
            print(f"💾 Saved: {csv_file}")
        
        print(f"💾 Saved: {report_file}")

def run_price_history_tracking():
    """Main function to run price history tracking"""
    
    print("📈 E-commerce Price History Tracker")
    print("="*60)
    
    tracker = EcommercePriceHistoryTracker()
    
    print("Choose tracking mode:")
    print("1. Track specific product URLs (watchlist mode)")
    print("2. Analyze existing price history")
    print("3. View trending products")
    
    choice = input("\nEnter choice (1, 2, or 3): ").strip()
    
    if choice == "1":
        # Watchlist mode
        print("\nWatchlist Mode - Track specific products over time")
        print("Enter product URLs (one per line, empty line to finish):")
        
        product_urls = []
        while True:
            url = input("Product URL: ").strip()
            if not url:
                break
            product_urls.append(url)
        
        if not product_urls:
            # Example URLs for demo
            product_urls = [
                "https://www.amazon.com/dp/B08N5WRWNW",  # Example product
                "https://www.amazon.com/dp/B07XTK8YTF"   # Example product
            ]
            print(f"Using example URLs for demo...")
        
        # Generate comprehensive report
        report = tracker.generate_watchlist_report(product_urls)
        
        # Display key insights
        print("\n" + "="*60)
        print("📊 PRICE HISTORY TRACKING RESULTS")
        print("="*60)
        
        summary = report['watchlist_summary']
        print(f"📈 Tracking Summary:")
        print(f"   Products tracked: {summary['successfully_tracked']}/{summary['total_products']}")
        print(f"   Price changes detected: {summary['price_changes_detected']}")
        print(f"   Success rate: {summary['success_rate']:.1f}%")
        
        if report['actionable_insights']:
            print(f"\n💡 Key Insights:")
            for insight in report['actionable_insights']:
                print(f"   {insight}")
        
        if report['current_session']['price_changes']:
            print(f"\n🚨 Price Changes Detected:")
            for change in report['current_session']['price_changes'][:5]:
                direction = "📉" if change['percentage_change'] < 0 else "📈"
                print(f"   {direction} {change.get('title', 'Unknown')[:40]}...")
                print(f"       {change['percentage_change']:.1f}% change (${change['old_price']:.2f} → ${change['new_price']:.2f})")
        
    elif choice == "2":
        # History analysis mode
        print("\nAnalyzing existing price history...")
        trends = tracker.analyze_price_trends(days=30)
        
        print("\n📊 Market Trends (Last 30 days):")
        if trends['trending_products']:
            print(f"   📈 Total price alerts: {len(trends['trending_products'])}")
            
            print(f"\n🔥 Top Price Changes:")
            for trend in trends['trending_products'][:5]:
                direction = "📉" if trend['percentage_change'] < 0 else "📈"
                print(f"   {direction} {trend['title'][:40]}...")
                print(f"       {trend['percentage_change']:.1f}% change on {trend['platform']}")
        else:
            print("   No historical data found. Start tracking products first!")
    
    elif choice == "3":
        # Trending products view
        print("\nFetching trending products...")
        trending = tracker.db.get_trending_products(days=7, limit=15)
        
        if trending:
            print("\n🔥 Trending Products (Last 7 days):")
            for i, product in enumerate(trending, 1):
                direction = "📉" if product['percentage_change'] < 0 else "📈"
                print(f"{i}. {direction} {product['title'][:50]}...")
                print(f"   {product['percentage_change']:.1f}% change on {product['platform']}")
                print(f"   ${product['old_price']:.2f} → ${product['new_price']:.2f}")
                print()
        else:
            print("No trending data available. Start tracking products to see trends!")
    
    else:
        print("Invalid choice. Please run again and select 1, 2, or 3.")

if __name__ == "__main__":
    print("🔍 Checking dependencies...")
    print(f"   SQLite: ✅ (built-in)")
    print(f"   Pandas: ✅")
    print(f"   Requests: ✅")
    
    # Run the price history tracker
    run_price_history_tracking()
    
    print(f"\n🎓 Price History Tracking Benefits:")
    print(f"   ✅ Persistent price monitoring")
    print(f"   ✅ Historical trend analysis")
    print(f"   ✅ Automated price change detection")
    print(f"   ✅ SQLite database for reliability")
    print(f"   ✅ Watchlist functionality")
    print(f"   ✅ Market trend insights")
    print(f"   ✅ Actionable notifications")
    
    print(f"\n🚀 Next Level Features:")
    print(f"   1. Email/SMS price alerts")
    print(f"   2. Price prediction ML models")
    print(f"   3. Web dashboard with charts")
    print(f"   4. Scheduled monitoring (cron jobs)")
    print(f"   5. API endpoints for integration")
    print(f"   6. Mobile app notifications")