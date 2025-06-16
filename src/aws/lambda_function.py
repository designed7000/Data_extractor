# lambda_function.py - AWS Lambda Price Tracker
# Cloud-optimized version for serverless deployment

import json
import boto3
import requests
from bs4 import BeautifulSoup
import hashlib
import re
import os
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import urlparse, urljoin
import time
import random

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')
ssm = boto3.client('ssm')
cloudwatch = boto3.client('cloudwatch')

class CloudPriceTracker:
    """AWS Lambda-optimized price tracker"""
    
    def __init__(self):
        self.session = requests.Session()
        self.setup_session()
        self.config = self.load_config()
        
        # DynamoDB tables
        self.products_table = dynamodb.Table('PriceTracker-Products')
        self.history_table = dynamodb.Table('PriceTracker-History')
        self.alerts_table = dynamodb.Table('PriceTracker-Alerts')
    
    def setup_session(self):
        """Setup HTTP session with realistic headers"""
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive'
        })
    
    def load_config(self):
        """Load configuration from AWS Parameter Store"""
        try:
            # Get all parameters for price tracker
            response = ssm.get_parameters_by_path(
                Path='/price-tracker/',
                Recursive=True
            )
            
            config = {}
            for param in response['Parameters']:
                key = param['Name'].split('/')[-1]
                value = param['Value']
                
                # Parse JSON values
                if key in ['product-urls', 'alert-emails']:
                    config[key.replace('-', '_')] = json.loads(value)
                elif key in ['price-change-threshold']:
                    config[key.replace('-', '_')] = float(value)
                else:
                    config[key.replace('-', '_')] = value
            
            return config
            
        except Exception as e:
            print(f"Error loading config: {e}")
            # Return default config
            return {
                'product_urls': [],
                'price_change_threshold': 5.0,
                'alert_emails': []
            }
    
    def save_product(self, product_data):
        """Save product to DynamoDB"""
        product_id = hashlib.md5(product_data['url'].encode()).hexdigest()[:12]
        
        try:
            # Check if product exists
            response = self.products_table.get_item(Key={'product_id': product_id})
            
            if 'Item' in response:
                # Update existing product
                self.products_table.update_item(
                    Key={'product_id': product_id},
                    UpdateExpression='SET title = :title, last_updated = :timestamp, is_active = :active',
                    ExpressionAttributeValues={
                        ':title': product_data.get('title', ''),
                        ':timestamp': datetime.now().isoformat(),
                        ':active': True
                    }
                )
            else:
                # Create new product
                self.products_table.put_item(
                    Item={
                        'product_id': product_id,
                        'url': product_data['url'],
                        'title': product_data.get('title', ''),
                        'platform': product_data.get('platform', ''),
                        'category': product_data.get('category', 'tracked'),
                        'first_seen': datetime.now().isoformat(),
                        'last_updated': datetime.now().isoformat(),
                        'is_active': True
                    }
                )
            
            return product_id
            
        except Exception as e:
            print(f"Error saving product: {e}")
            return None
    
    def save_price_record(self, product_id, price_data):
        """Save price record to DynamoDB"""
        try:
            # Convert float to Decimal for DynamoDB
            price_numeric = None
            if price_data.get('price_numeric'):
                price_numeric = Decimal(str(price_data['price_numeric']))
            
            self.history_table.put_item(
                Item={
                    'product_id': product_id,
                    'timestamp': datetime.now().isoformat(),
                    'price': price_numeric,
                    'price_text': price_data.get('price_text', ''),
                    'availability': price_data.get('availability', ''),
                    'rating': price_data.get('rating', ''),
                    'platform': price_data.get('platform', ''),
                    'session_id': price_data.get('session_id', ''),
                    'ttl': int((datetime.now() + timedelta(days=365)).timestamp())  # Auto-delete after 1 year
                }
            )
            
        except Exception as e:
            print(f"Error saving price record: {e}")
    
    def get_latest_price(self, product_id):
        """Get the most recent price for a product"""
        try:
            response = self.history_table.query(
                KeyConditionExpression='product_id = :pid',
                ExpressionAttributeValues={':pid': product_id},
                ScanIndexForward=False,  # Descending order
                Limit=1
            )
            
            if response['Items']:
                item = response['Items'][0]
                return {
                    'price': float(item['price']) if item.get('price') else None,
                    'timestamp': item['timestamp'],
                    'availability': item.get('availability', '')
                }
            return None
            
        except Exception as e:
            print(f"Error getting latest price: {e}")
            return None
    
    def detect_price_changes(self, product_id, new_price, threshold=5.0):
        """Detect significant price changes"""
        latest_price = self.get_latest_price(product_id)
        
        if not latest_price or not latest_price['price'] or not new_price:
            return None
        
        old_price = latest_price['price']
        percentage_change = ((new_price - old_price) / old_price) * 100
        
        if abs(percentage_change) >= threshold:
            alert_type = 'price_drop' if percentage_change < 0 else 'price_increase'
            
            # Save alert to DynamoDB
            try:
                self.alerts_table.put_item(
                    Item={
                        'alert_id': f"{product_id}_{int(datetime.now().timestamp())}",
                        'product_id': product_id,
                        'alert_type': alert_type,
                        'old_price': Decimal(str(old_price)),
                        'new_price': Decimal(str(new_price)),
                        'percentage_change': Decimal(str(percentage_change)),
                        'created_at': datetime.now().isoformat(),
                        'is_notified': False
                    }
                )
            except Exception as e:
                print(f"Error saving alert: {e}")
            
            return {
                'alert_type': alert_type,
                'old_price': old_price,
                'new_price': new_price,
                'percentage_change': percentage_change,
                'is_significant': True
            }
        
        return {'is_significant': False}
    
    def scrape_single_product(self, url):
        """Scrape a single product page"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            platform = self.detect_platform(url)
            
            product_data = {
                'url': url,
                'platform': platform,
                'scraped_at': datetime.now().isoformat()
            }
            
            # Platform-specific extraction
            if platform == 'amazon':
                product_data.update(self.extract_amazon_details(soup))
            elif platform == 'ebay':
                product_data.update(self.extract_ebay_details(soup))
            else:
                product_data.update(self.extract_generic_details(soup))
            
            # Clean and parse price
            if product_data.get('price_text'):
                product_data['price_text'] = self.clean_price_text(product_data['price_text'])
                product_data['price_numeric'] = self.parse_price(product_data['price_text'])
            
            return product_data
            
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None
    
    def detect_platform(self, url):
        """Detect e-commerce platform"""
        domain = urlparse(url).netloc.lower()
        
        if 'amazon' in domain:
            return 'amazon'
        elif 'ebay' in domain:
            return 'ebay'
        elif 'etsy' in domain:
            return 'etsy'
        else:
            return 'generic'
    
    def extract_amazon_details(self, soup):
        """Extract Amazon product details"""
        details = {}
        
        # Title
        title_selectors = ['#productTitle', 'h1.a-size-large']
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
            '#priceblock_ourprice'
        ]
        
        for selector in price_selectors:
            price_elem = soup.select_one(selector)
            if price_elem:
                details['price_text'] = price_elem.get_text(strip=True)
                break
        
        # Availability
        availability_elem = soup.select_one('#availability span')
        if availability_elem:
            details['availability'] = availability_elem.get_text(strip=True)
        
        return details
    
    def extract_ebay_details(self, soup):
        """Extract eBay product details"""
        details = {}
        
        # Title
        title_elem = soup.select_one('#x-title-label-lbl')
        if title_elem:
            details['title'] = title_elem.get_text(strip=True)
        
        # Price
        price_selectors = ['.notranslate', '.display-price']
        for selector in price_selectors:
            price_elem = soup.select_one(selector)
            if price_elem and '$' in price_elem.get_text():
                details['price_text'] = price_elem.get_text(strip=True)
                break
        
        return details
    
    def extract_generic_details(self, soup):
        """Generic product extraction"""
        details = {}
        
        # Title
        title_elem = soup.select_one('h1')
        if title_elem:
            details['title'] = title_elem.get_text(strip=True)
        
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
    
    def clean_price_text(self, price_text):
        """Clean price text"""
        if not price_text:
            return None
        
        price_text = price_text.strip()
        
        # Handle duplicated prices like "$69.99$69.99"
        if '$' in price_text:
            price_parts = [part for part in price_text.split('$') if part.strip()]
            if price_parts:
                first_price = re.sub(r'[^\d.,]', '', price_parts[0].strip())
                if first_price:
                    return f"${first_price}"
        
        return price_text
    
    def parse_price(self, price_text):
        """Parse price to float"""
        if not price_text:
            return None
        
        # Remove currency symbols and extract numbers
        price_clean = re.sub(r'[\$£€¥]', '', price_text)
        price_clean = re.sub(r'[^\d.,]', '', price_clean)
        
        if not price_clean:
            return None
        
        # Handle comma separators
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
    
    def track_products_cloud(self, product_urls):
        """Main tracking function for Lambda"""
        session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        tracked_products = []
        price_changes = []
        
        for url in product_urls:
            try:
                # Scrape product
                product_data = self.scrape_single_product(url)
                
                if product_data:
                    product_data['session_id'] = session_id
                    
                    # Save product and get ID
                    product_id = self.save_product(product_data)
                    
                    if product_id:
                        # Save price record
                        self.save_price_record(product_id, product_data)
                        
                        # Check for price changes
                        if product_data.get('price_numeric'):
                            change = self.detect_price_changes(
                                product_id,
                                product_data['price_numeric'],
                                self.config.get('price_change_threshold', 5.0)
                            )
                            
                            if change and change.get('is_significant'):
                                price_changes.append({
                                    **product_data,
                                    **change,
                                    'product_id': product_id
                                })
                        
                        tracked_products.append(product_data)
                
                # Be respectful with delays
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                print(f"Error tracking {url}: {e}")
                continue
        
        return {
            'tracked_products': tracked_products,
            'price_changes': price_changes,
            'session_id': session_id,
            'summary': {
                'total_tracked': len(tracked_products),
                'changes_detected': len(price_changes),
                'timestamp': datetime.now().isoformat()
            }
        }
    
    def send_notifications(self, price_changes):
        """Send SNS notifications for price changes"""
        if not price_changes:
            return
        
        sns_topic_arn = os.environ.get('SNS_TOPIC_ARN')
        if not sns_topic_arn:
            print("No SNS topic configured")
            return
        
        try:
            for change in price_changes:
                message = {
                    'product': change.get('title', 'Unknown Product'),
                    'url': change.get('url', ''),
                    'old_price': float(change.get('old_price', 0)),
                    'new_price': float(change.get('new_price', 0)),
                    'percentage_change': float(change.get('percentage_change', 0)),
                    'alert_type': change.get('alert_type', 'change'),
                    'timestamp': datetime.now().isoformat()
                }
                
                direction = "📉" if change.get('percentage_change', 0) < 0 else "📈"
                subject = f"Price Alert {direction}: {change.get('alert_type', 'Change').title()} Detected"
                
                sns.publish(
                    TopicArn=sns_topic_arn,
                    Subject=subject,
                    Message=json.dumps(message, indent=2)
                )
                
            print(f"Sent {len(price_changes)} notifications")
            
        except Exception as e:
            print(f"Error sending notifications: {e}")
    
    def send_metrics(self, results):
        """Send custom metrics to CloudWatch"""
        try:
            cloudwatch.put_metric_data(
                Namespace='PriceTracker',
                MetricData=[
                    {
                        'MetricName': 'ProductsTracked',
                        'Value': len(results['tracked_products']),
                        'Unit': 'Count'
                    },
                    {
                        'MetricName': 'PriceChangesDetected',
                        'Value': len(results['price_changes']),
                        'Unit': 'Count'
                    },
                    {
                        'MetricName': 'SuccessfulRuns',
                        'Value': 1,
                        'Unit': 'Count'
                    }
                ]
            )
        except Exception as e:
            print(f"Error sending metrics: {e}")

def lambda_handler(event, context):
    """
    AWS Lambda entry point
    
    This function is called by AWS when the Lambda is triggered
    """
    
    print(f"Price tracker started at {datetime.now()}")
    print(f"Event: {json.dumps(event)}")
    
    try:
        # Initialize tracker
        tracker = CloudPriceTracker()
        
        # Get product URLs from config or event
        product_urls = event.get('product_urls', tracker.config.get('product_urls', []))
        
        if not product_urls:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'No product URLs configured',
                    'message': 'Add URLs to Parameter Store at /price-tracker/product-urls'
                })
            }
        
        # Run tracking
        results = tracker.track_products_cloud(product_urls)
        
        # Send notifications for significant changes
        if results['price_changes']:
            tracker.send_notifications(results['price_changes'])
        
        # Send metrics to CloudWatch
        tracker.send_metrics(results)
        
        # Return success response
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Price tracking completed successfully',
                'summary': results['summary'],
                'significant_changes': len(results['price_changes'])
            })
        }
        
    except Exception as e:
        print(f"Lambda execution failed: {str(e)}")
        
        # Send error metric
        try:
            cloudwatch.put_metric_data(
                Namespace='PriceTracker',
                MetricData=[{
                    'MetricName': 'Errors',
                    'Value': 1,
                    'Unit': 'Count'
                }]
            )
        except:
            pass
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
        }

# For testing locally
if __name__ == "__main__":
    # Test event
    test_event = {
        'source': 'test',
        'product_urls': [
            'https://www.amazon.com/dp/B08N5WRWNW'
        ]
    }
    
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))