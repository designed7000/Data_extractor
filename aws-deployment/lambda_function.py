"""
AWS Lambda Price Tracker Function
Compatible with Python 3.13 - Uses BeautifulSoup instead of lxml
"""

import json
import boto3
import requests
from bs4 import BeautifulSoup
import re
import time
import logging
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import urlparse
import os

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')
ssm = boto3.client('ssm')
cloudwatch = boto3.client('cloudwatch')

# DynamoDB tables
products_table = dynamodb.Table('PriceTrackerProducts')
history_table = dynamodb.Table('PriceTrackerHistory')
alerts_table = dynamodb.Table('PriceTrackerAlerts')

class PriceExtractor:
    """Extract prices from various e-commerce sites using BeautifulSoup"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.get_parameter('/price-tracker/scraping/user-agent', 
                                           'Mozilla/5.0 (compatible; PriceTracker/1.0)'),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
        
    def get_parameter(self, name, default=None):
        """Get parameter from Parameter Store with fallback"""
        try:
            response = ssm.get_parameter(Name=name)
            return response['Parameter']['Value']
        except Exception as e:
            logger.warning(f"Failed to get parameter {name}: {e}")
            return default
    
    def extract_price(self, url):
        """Extract price from URL using site-specific logic"""
        try:
            domain = urlparse(url).netloc.lower()
            
            # Add delay to be respectful to servers
            delay = float(self.get_parameter('/price-tracker/scraping/delay-seconds', '2'))
            time.sleep(delay)
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')
            
            if 'amazon' in domain:
                return self._extract_amazon_price(soup)
            elif 'ebay' in domain:
                return self._extract_ebay_price(soup)
            else:
                return self._extract_generic_price(soup)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Price extraction failed for {url}: {e}")
            raise
    
    def _extract_amazon_price(self, soup):
        """Extract price from Amazon product page"""
        # Amazon price selectors (multiple fallbacks)
        price_selectors = [
            '.a-price .a-offscreen',
            '.a-price-whole',
            '#price_inside_buybox',
            '.a-price-range .a-offscreen',
            '#apex_desktop .a-price .a-offscreen',
            '.a-price-symbol + .a-price-whole'
        ]
        
        for selector in price_selectors:
            elements = soup.select(selector)
            for element in elements:
                price_text = element.get_text(strip=True)
                price = self._parse_price(price_text)
                if price:
                    logger.info(f"Amazon price found: {price}")
                    return price
        
        raise ValueError("No price found on Amazon page")
    
    def _extract_ebay_price(self, soup):
        """Extract price from eBay product page"""
        price_selectors = [
            '.mainPrice .price',
            '.u-flL .price',
            '.notranslate',
            '.display-price'
        ]
        
        for selector in price_selectors:
            elements = soup.select(selector)
            for element in elements:
                price_text = element.get_text(strip=True)
                price = self._parse_price(price_text)
                if price:
                    logger.info(f"eBay price found: {price}")
                    return price
        
        raise ValueError("No price found on eBay page")
    
    def _extract_generic_price(self, soup):
        """Extract price from generic website using common patterns"""
        # Common price class names and patterns
        price_patterns = [
            r'price',
            r'cost',
            r'amount',
            r'value',
            r'total'
        ]
        
        # Look for elements with price-related classes
        for pattern in price_patterns:
            elements = soup.find_all(class_=re.compile(pattern, re.I))
            for element in elements:
                price_text = element.get_text(strip=True)
                price = self._parse_price(price_text)
                if price:
                    logger.info(f"Generic price found: {price}")
                    return price
        
        # Look for currency symbols in text
        price_regex = r'[£$€¥₹]\s*[\d,]+\.?\d*'
        all_text = soup.get_text()
        matches = re.findall(price_regex, all_text)
        for match in matches:
            price = self._parse_price(match)
            if price and price > 1:  # Filter out small values that might not be prices
                logger.info(f"Regex price found: {price}")
                return price
        
        raise ValueError("No price found on generic page")
    
    def _parse_price(self, price_text):
        """Parse price from text string"""
        if not price_text:
            return None
            
        # Remove common non-numeric characters but keep decimal points
        price_clean = re.sub(r'[^\d.,]', '', price_text)
        
        if not price_clean:
            return None
        
        # Handle different decimal separators
        if ',' in price_clean and '.' in price_clean:
            # Assume comma is thousands separator if both present
            price_clean = price_clean.replace(',', '')
        elif ',' in price_clean:
            # Check if comma is decimal separator (European format)
            parts = price_clean.split(',')
            if len(parts) == 2 and len(parts[1]) <= 2:
                price_clean = price_clean.replace(',', '.')
            else:
                price_clean = price_clean.replace(',', '')
        
        try:
            return float(price_clean)
        except ValueError:
            return None

def get_products_to_track():
    """Get all active products from DynamoDB"""
    try:
        response = products_table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('active').eq(True)
        )
        return response.get('Items', [])
    except Exception as e:
        logger.error(f"Failed to get products: {e}")
        return []

def save_price_history(product_id, url, price, previous_price=None):
    """Save price data to history table"""
    try:
        item = {
            'product_id': product_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'price': Decimal(str(price)),
            'url': url,
            'ttl': int(time.time()) + (365 * 24 * 60 * 60)  # 1 year TTL
        }
        
        if previous_price:
            item['previous_price'] = Decimal(str(previous_price))
            item['price_change'] = Decimal(str(price - previous_price))
            item['price_change_percent'] = Decimal(str((price - previous_price) / previous_price * 100))
        
        history_table.put_item(Item=item)
        logger.info(f"Saved price history for product {product_id}: {price}")
        
    except Exception as e:
        logger.error(f"Failed to save price history: {e}")

def check_price_alerts(product_id, current_price, previous_price, threshold=0.05):
    """Check if price change exceeds threshold and send alert"""
    if not previous_price:
        return
    
    price_change_percent = abs(current_price - previous_price) / previous_price
    
    if price_change_percent >= threshold:
        try:
            # Save alert to DynamoDB
            alert_item = {
                'alert_id': f"{product_id}_{int(time.time())}",
                'product_id': product_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'previous_price': Decimal(str(previous_price)),
                'current_price': Decimal(str(current_price)),
                'price_change_percent': Decimal(str(price_change_percent * 100)),
                'alert_type': 'decrease' if current_price < previous_price else 'increase',
                'ttl': int(time.time()) + (90 * 24 * 60 * 60)  # 90 days TTL
            }
            alerts_table.put_item(Item=alert_item)
            
            # Send SNS notification
            subject = f"Price Alert: {alert_item['alert_type'].title()} for Product {product_id}"
            message = f"""
Price Alert!

Product ID: {product_id}
Previous Price: £{previous_price:.2f}
Current Price: £{current_price:.2f}
Change: {price_change_percent*100:.1f}%
Alert Type: {alert_item['alert_type'].title()}

This is an automated alert from your Price Tracker.
            """
            
            # Get SNS topic ARN (assuming it's set in environment or parameter store)
            topic_arn = os.environ.get('SNS_TOPIC_ARN')
            if topic_arn:
                sns.publish(
                    TopicArn=topic_arn,
                    Message=message,
                    Subject=subject
                )
                logger.info(f"Alert sent for product {product_id}")
            
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")

def send_cloudwatch_metrics(metric_name, value, unit='Count'):
    """Send custom metrics to CloudWatch"""
    try:
        cloudwatch.put_metric_data(
            Namespace='PriceTracker',
            MetricData=[
                {
                    'MetricName': metric_name,
                    'Value': value,
                    'Unit': unit,
                    'Timestamp': datetime.now(timezone.utc)
                }
            ]
        )
    except Exception as e:
        logger.error(f"Failed to send CloudWatch metric: {e}")

def lambda_handler(event, context):
    """Main Lambda handler function"""
    logger.info("Price tracker function started")
    
    try:
        # Initialize price extractor
        extractor = PriceExtractor()
        
        # Get products to track
        products = get_products_to_track()
        logger.info(f"Found {len(products)} products to track")
        
        if not products:
            logger.warning("No products found to track")
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'No products to track'})
            }
        
        # Track prices
        successful_tracks = 0
        failed_tracks = 0
        alerts_sent = 0
        
        for product in products:
            try:
                product_id = product['product_id']
                url = product['url']
                previous_price = float(product.get('last_price', 0)) if product.get('last_price') else None
                
                logger.info(f"Tracking product {product_id}: {url}")
                
                # Extract current price
                current_price = extractor.extract_price(url)
                
                # Update product with latest price
                products_table.update_item(
                    Key={'product_id': product_id},
                    UpdateExpression='SET last_price = :price, last_updated = :timestamp',
                    ExpressionAttributeValues={
                        ':price': Decimal(str(current_price)),
                        ':timestamp': datetime.now(timezone.utc).isoformat()
                    }
                )
                
                # Save to history
                save_price_history(product_id, url, current_price, previous_price)
                
                # Check for alerts
                threshold = float(extractor.get_parameter('/price-tracker/alerts/price-change-threshold', '0.05'))
                if previous_price:
                    price_change_percent = abs(current_price - previous_price) / previous_price
                    if price_change_percent >= threshold:
                        check_price_alerts(product_id, current_price, previous_price, threshold)
                        alerts_sent += 1
                
                successful_tracks += 1
                logger.info(f"Successfully tracked {product_id}: £{current_price:.2f}")
                
            except Exception as e:
                failed_tracks += 1
                logger.error(f"Failed to track product {product.get('product_id', 'unknown')}: {e}")
        
        # Send CloudWatch metrics
        send_cloudwatch_metrics('ProductsTracked', successful_tracks)
        send_cloudwatch_metrics('TrackingErrors', failed_tracks)
        send_cloudwatch_metrics('AlertsSent', alerts_sent)
        
        result = {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Price tracking completed',
                'products_tracked': successful_tracks,
                'tracking_errors': failed_tracks,
                'alerts_sent': alerts_sent,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        }
        
        logger.info(f"Price tracking completed: {successful_tracks} successful, {failed_tracks} failed")
        return result
        
    except Exception as e:
        logger.error(f"Lambda function failed: {e}")
        send_cloudwatch_metrics('LambdaErrors', 1)
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
        }

# For local testing
if __name__ == "__main__":
    # Test the function locally
    test_event = {"test": True}
    test_context = {}
    result = lambda_handler(test_event, test_context)
    print(json.dumps(result, indent=2))