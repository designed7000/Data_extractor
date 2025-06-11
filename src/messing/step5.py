# Step 5: Free Gemini AI Integration
# Using Google's Gemini API (free tier: 15 requests/minute, 1500/day)

import re
import json
import os
from datetime import datetime

# You'll need to install: uv add google-generativeai
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️  Gemini not installed. Run: uv add google-generativeai")

def extract_with_patterns(text):
    """Our reliable pattern-based extraction"""
    emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
    years = re.findall(r'\b(19\d{2}|20\d{2})\b', text)
    employee_matches = re.findall(r'(\d+)\s+employees?', text, re.IGNORECASE)
    
    company_patterns = [
        r'Welcome to ([A-Z][A-Za-z]+)!?',
        r'([A-Z][A-Za-z]+) is a',
    ]
    company_names = []
    for pattern in company_patterns:
        matches = re.findall(pattern, text)
        company_names.extend(matches)
    
    locations = re.findall(r'([A-Z][a-z]+),\s([A-Z][a-z]+)', text)
    formatted_locations = [f"{city}, {state}" for city, state in locations]
    
    return {
        'company_name': company_names[0] if company_names else None,
        'email': emails[0] if emails else None,
        'founded_year': years[0] if years else None,
        'employee_count': int(employee_matches[0]) if employee_matches else None,
        'location': formatted_locations[0] if formatted_locations else None,
    }

def extract_with_gemini_ai(text):
    """Use free Gemini API to extract information"""
    
    if not GEMINI_AVAILABLE:
        return {"error": "google-generativeai not installed"}
    
    # Check for API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return {"error": "GEMINI_API_KEY environment variable not set"}
    
    try:
        # Configure Gemini
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        # Create a prompt for data extraction
        prompt = f"""
        Extract company information from this text and return ONLY valid JSON with this exact structure:
        
        {{
            "company_name": "name of the company",
            "industry": "what industry/sector they operate in",
            "description": "brief description of what they do",
            "services": ["list", "of", "main services or products"],
            "company_size": "startup/small/medium/large based on context",
            "business_type": "startup/established/enterprise based on context",
            "specialties": ["key", "areas", "of expertise"]
        }}
        
        Rules:
        - Return ONLY the JSON, no other text
        - If information is not available, use null for that field
        - Be concise but accurate
        
        Text to analyze:
        {text}
        """
        
        response = model.generate_content(prompt)
        ai_result = response.text.strip()
        
        # Clean up the response (sometimes has markdown formatting)
        if ai_result.startswith('```json'):
            ai_result = ai_result.replace('```json', '').replace('```', '').strip()
        
        # Try to parse the JSON response
        try:
            return json.loads(ai_result)
        except json.JSONDecodeError:
            return {"error": "AI returned invalid JSON", "raw_response": ai_result}
            
    except Exception as e:
        return {"error": f"Gemini extraction failed: {str(e)}"}

def fallback_smart_rules(text):
    """Enhanced fallback AI using smart rules"""
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    text_lower = text.lower()
    
    extracted = {}
    
    # Industry detection
    industry_keywords = {
        'software': ['software', 'web development', 'mobile apps'],
        'technology': ['technology', 'tech', 'digital'],
        'consulting': ['consulting', 'advisory']
    }
    
    for industry, keywords in industry_keywords.items():
        if any(keyword in text_lower for keyword in keywords):
            extracted['industry'] = industry
            break
    
    # Services extraction
    services = []
    if 'web development' in text_lower:
        services.append('web development')
    if 'mobile app' in text_lower:
        services.append('mobile apps')
    if services:
        extracted['services'] = services
    
    # Company size from employee count
    pattern_data = extract_with_patterns(text)
    if pattern_data.get('employee_count'):
        count = pattern_data['employee_count']
        if count < 10:
            extracted['company_size'] = 'startup'
        elif count < 50:
            extracted['company_size'] = 'small'
        else:
            extracted['company_size'] = 'medium'
    
    # Description from key lines
    description_parts = []
    for line in lines:
        if any(phrase in line.lower() for phrase in ['we are', 'we specialize', 'our team']):
            description_parts.append(line)
    
    if description_parts:
        extracted['description'] = '. '.join(description_parts)
    
    return extracted

def extract_complete_analysis(text):
    """Extract using patterns, Gemini AI, and combine results"""
    
    print("🔍 Step 1: Pattern-based extraction...")
    pattern_data = extract_with_patterns(text)
    
    print("🤖 Step 2: Gemini AI extraction...")
    ai_data = extract_with_gemini_ai(text)
    
    # If Gemini AI failed, use fallback
    if "error" in ai_data:
        print(f"   ⚠️  Gemini AI failed: {ai_data['error']}")
        print("🔄 Step 3: Using smart rules fallback...")
        ai_data = fallback_smart_rules(text)
        ai_method = "smart_rules"
    else:
        print("   ✅ Gemini AI successful!")
        ai_method = "gemini_pro"
    
    # Combine all data intelligently
    final_result = {}
    
    # Start with pattern data (most reliable)
    for key, value in pattern_data.items():
        if value is not None:
            final_result[key] = value
    
    # Add AI insights (new fields or enhanced data)
    for key, value in ai_data.items():
        if value is not None and key not in final_result:
            final_result[key] = value
    
    # Package everything
    complete_results = {
        'extraction_methods': {
            'patterns': pattern_data,
            'ai': ai_data
        },
        'final_result': final_result,
        'metadata': {
            'ai_method_used': ai_method,
            'total_fields_extracted': len([v for v in final_result.values() if v is not None]),
            'extraction_timestamp': datetime.now().isoformat()
        }
    }
    
    return complete_results

# Test it out
if __name__ == "__main__":
    try:
        # Read the sample file
        with open('../sample_data.txt', 'r', encoding='utf-8') as file:
            content = file.read()
        
        print("📄 Text to analyze:")
        print(content)
        print("\n" + "="*70 + "\n")
        
        # Extract using complete pipeline
        results = extract_complete_analysis(content)
        
        print("="*70)
        print("🎯 FINAL EXTRACTED DATA:")
        print("="*70)
        
        for key, value in results['final_result'].items():
            print(f"  📊 {key}: {value}")
        
        # Save complete results
        with open('step5_gemini_results.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Complete results saved to step5_gemini_results.json")
        
        # Show analytics
        metadata = results['metadata']
        print(f"\n📈 Extraction Analytics:")
        print(f"  🔧 AI Method: {metadata['ai_method_used']}")
        print(f"  📊 Fields Found: {metadata['total_fields_extracted']}")
        print(f"  🕐 Timestamp: {metadata['extraction_timestamp']}")
        
        # Method comparison
        pattern_fields = len([v for v in results['extraction_methods']['patterns'].values() if v])
        ai_fields = len([v for v in results['extraction_methods']['ai'].values() if v and 'error' not in str(v)])
        
        print(f"\n🔍 Method Comparison:")
        print(f"  📋 Patterns found: {pattern_fields} fields")
        print(f"  🤖 AI found: {ai_fields} additional insights")
        
    except FileNotFoundError:
        print("❌ Run step1.py first to create the sample_data.txt file!")
    
    print(f"\n💡 To use Gemini AI (FREE):")
    print(f"   1. Go to https://makersuite.google.com/app/apikey")
    print(f"   2. Create a free API key")
    print(f"   3. Set: export GEMINI_API_KEY='your-key-here'")
    print(f"   4. Run: uv add google-generativeai")
    print(f"   5. Run again to see real AI extraction!")
    print(f"\n   📊 Free tier: 15 requests/minute, 1500/day")