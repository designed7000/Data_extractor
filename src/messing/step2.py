# Step 2: Extract specific information from text
# Now we'll find specific pieces of information in our text

import re

def find_email(text):
    """Find email addresses in text"""
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)
    return emails

def find_year(text):
    """Find 4-digit years in text"""
    year_pattern = r'\b(19|20)\d{2}\b'
    years = re.findall(year_pattern, text)
    return years

def find_numbers(text):
    """Find all numbers in text"""
    number_pattern = r'\b\d+\b'
    numbers = re.findall(number_pattern, text)
    return numbers

def extract_basic_info(text):
    """Extract basic information from text"""
    info = {
        'emails': find_email(text),
        'years': find_year(text),
        'numbers': find_numbers(text),
        'word_count': len(text.split())
    }
    return info

# Test it out
if __name__ == "__main__":
    # Read our sample file from step 1
    try:
        with open('../sample_data.txt', 'r', encoding='utf-8') as file:
            content = file.read()
        
        print("Original text:")
        print(content)
        print("\n" + "="*50 + "\n")
        
        # Extract information
        extracted_info = extract_basic_info(content)
        
        print("Extracted information:")
        for key, value in extracted_info.items():
            print(f"{key}: {value}")
            
    except FileNotFoundError:
        print("Run step1.py first to create the sample_data.txt file!")