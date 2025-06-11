# Step 3: Better pattern matching
# Let's fix our patterns and add more sophisticated extraction

import re

def find_email(text):
    """Find email addresses in text"""
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)
    return emails

def find_years(text):
    """Find 4-digit years (1900-2099)"""
    year_pattern = r'\b(19\d{2}|20\d{2})\b'
    years = re.findall(year_pattern, text)
    return years

def find_employee_count(text):
    """Find employee counts (number + 'employees')"""
    employee_pattern = r'(\d+)\s+employees?'
    matches = re.findall(employee_pattern, text, re.IGNORECASE)
    return matches

def find_company_name(text):
    """Try to find company names (very basic)"""
    # Look for "Welcome to [Company]" or "[Company] is a"
    patterns = [
        r'Welcome to ([A-Z][A-Za-z]+)!?',
        r'([A-Z][A-Za-z]+) is a',
        r'([A-Z][A-Za-z]+) are a'
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        if matches:
            return matches
    return []

def find_locations(text):
    """Find locations (City, State pattern)"""
    location_pattern = r'([A-Z][a-z]+),\s([A-Z][a-z]+)'
    locations = re.findall(location_pattern, text)
    return [f"{city}, {state}" for city, state in locations]

def extract_company_info(text):
    """Extract company-specific information"""
    info = {
        'company_names': find_company_name(text),
        'emails': find_email(text),
        'founded_years': find_years(text),
        'employee_counts': find_employee_count(text),
        'locations': find_locations(text),
        'word_count': len(text.split())
    }
    return info

# Test it out
if __name__ == "__main__":
    # Read our sample file
    try:
        with open('../sample_data.txt', 'r', encoding='utf-8') as file:
            content = file.read()
        
        print("Original text:")
        print(content)
        print("\n" + "="*60 + "\n")
        
        # Extract information with better patterns
        extracted_info = extract_company_info(content)
        
        print("Extracted company information:")
        for key, value in extracted_info.items():
            if value:  # Only show fields that found something
                print(f"{key}: {value}")
        
        print("\n" + "="*60)
        print("Summary:")
        if extracted_info['company_names']:
            print(f"✅ Found company: {extracted_info['company_names'][0]}")
        if extracted_info['founded_years']:
            print(f"✅ Founded in: {extracted_info['founded_years'][0]}")
        if extracted_info['employee_counts']:
            print(f"✅ Employees: {extracted_info['employee_counts'][0]}")
        if extracted_info['locations']:
            print(f"✅ Location: {extracted_info['locations'][0]}")
            
    except FileNotFoundError:
        print("Run step1.py first to create the sample_data.txt file!")