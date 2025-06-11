# Step 4: Add simple AI to understand context
# Now we'll use AI to extract information that patterns might miss

import re
import json
from datetime import datetime

# We'll start with a simple approach using OpenAI

def extract_with_patterns(text):
    """Our existing pattern-based extraction from Step 3"""
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

def extract_with_simple_ai(text):
    """Simple AI-like extraction using keyword context"""
    
    # This simulates AI by looking at context around keywords
    # Later we'll replace this with real AI
    
    lines = text.lower().split('\n')
    ai_extracted = {}
    
    # Look for industry information
    industry_keywords = ['software', 'technology', 'web development', 'mobile apps', 'consulting']
    for line in lines:
        for keyword in industry_keywords:
            if keyword in line:
                ai_extracted['industry'] = keyword.title()
                break
        if 'industry' in ai_extracted:
            break
    
    # Look for company description
    description_lines = []
    for line in lines:
        if any(word in line for word in ['we are', 'we specialize', 'our team']):
            description_lines.append(line.strip())
    
    if description_lines:
        ai_extracted['description'] = '. '.join(description_lines)
    
    # Look for contact information context
    for line in lines:
        if 'contact' in line and '@' in line:
            ai_extracted['has_contact_info'] = True
            break
    
    return ai_extracted

def combine_extractions(text):
    """Combine pattern-based and AI-based extraction"""
    
    print("🔍 Extracting with patterns...")
    pattern_data = extract_with_patterns(text)
    
    print("🤖 Extracting with simple AI...")
    ai_data = extract_with_simple_ai(text)
    
    # Combine both approaches
    combined_data = {
        **pattern_data,  # Start with pattern data
        **ai_data,       # Add AI insights
        'extraction_method': 'pattern + simple_ai',
        'extraction_timestamp': datetime.now().isoformat()
    }
    
    return combined_data

# Test it out
if __name__ == "__main__":
    try:
        # Read the sample file
        with open('../sample_data.txt', 'r', encoding='utf-8') as file:
            content = file.read()
        
        print("Original text:")
        print(content)
        print("\n" + "="*60 + "\n")
        
        # Extract using combined approach
        extracted_data = combine_extractions(text=content)
        
        print("Combined extraction results:")
        for key, value in extracted_data.items():
            if key != 'extraction_timestamp':
                print(f"  {key}: {value}")
        
        # Save results
        with open('step4_results.json', 'w', encoding='utf-8') as f:
            json.dump(extracted_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Results saved to step4_results.json")
        
        # Show what AI found that patterns didn't
        print(f"\n🤖 AI discovered:")
        if 'industry' in extracted_data:
            print(f"  - Industry: {extracted_data['industry']}")
        if 'description' in extracted_data:
            print(f"  - Description: {extracted_data['description']}")
        
    except FileNotFoundError:
        print("❌ Run step1.py first to create the sample_data.txt file!")