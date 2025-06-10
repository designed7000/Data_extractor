# Step 1: Read a text file with UV virtual environment
# This is our starting point - just reading and displaying text

"""
Setup Instructions:
1. Install UV: curl -LsSf https://astral.sh/uv/install.sh | sh
2. Create project: uv init data-extractor
3. cd data-extractor
4. Copy this code into src/step1.py
5. Run: uv run src/step1.py
"""

def read_text_file(filename):
    """Read a text file and return its contents"""
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            content = file.read()
        return content
    except FileNotFoundError:
        return f"File '{filename}' not found!"
    except Exception as e:
        return f"Error reading file: {e}"

# Test it out
if __name__ == "__main__":
    # Create a sample text file first
    sample_text = """
    Welcome to TechCorp!
    
    We are a software company founded in 2020.
    Our headquarters is in San Francisco, California.
    We specialize in web development and mobile apps.
    Our team has 25 employees.
    
    Contact us at info@techcorp.com
    """
    
    # Write the sample file
    with open('sample_data.txt', 'w', encoding='utf-8') as f:
        f.write(sample_text)
    
    # Now read it back
    content = read_text_file('sample_data.txt')
    print("File contents:")
    print(content)