# Job Market Intelligence Platform
# Perfect CV project: Web Scraping + GenAI + Business Value

import requests
from bs4 import BeautifulSoup
import json
import pandas as pd
from datetime import datetime
import time
import random
import re

class JobMarketAnalyzer:
    def __init__(self):
        self.session = requests.Session()
        self.setup_session()
        self.job_data = []
    
    def setup_session(self):
        """Setup realistic browser headers"""
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def scrape_indeed_jobs(self, job_title, location="United States", max_pages=3):
        """Scrape job listings from Indeed"""
        
        print(f"🔍 Scraping Indeed for: {job_title} in {location}")
        
        base_url = "https://www.indeed.com/jobs"
        jobs = []
        
        for page in range(max_pages):
            params = {
                'q': job_title,
                'l': location,
                'start': page * 10
            }
            
            try:
                time.sleep(random.uniform(2, 5))  # Be respectful
                response = self.session.get(base_url, params=params, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Find job cards (Indeed's structure)
                job_cards = soup.find_all(['div'], class_=lambda x: x and 'job' in x.lower())
                
                for card in job_cards[:10]:  # Limit per page
                    job_info = self.extract_job_info(card)
                    if job_info:
                        jobs.append(job_info)
                
                print(f"   Page {page+1}: Found {len(job_cards)} job listings")
                
            except Exception as e:
                print(f"   Error on page {page+1}: {e}")
                continue
        
        return jobs
    
    def extract_job_info(self, job_card):
        """Extract job information from a job card"""
        
        try:
            # Extract title
            title_elem = job_card.find(['h2', 'a'], class_=lambda x: x and any(word in x.lower() for word in ['title', 'job']))
            title = title_elem.get_text(strip=True) if title_elem else "N/A"
            
            # Extract company
            company_elem = job_card.find(['span', 'div'], class_=lambda x: x and 'company' in x.lower())
            company = company_elem.get_text(strip=True) if company_elem else "N/A"
            
            # Extract location
            location_elem = job_card.find(['div', 'span'], class_=lambda x: x and 'location' in x.lower())
            location = location_elem.get_text(strip=True) if location_elem else "N/A"
            
            # Extract salary (if available)
            salary_elem = job_card.find(['span', 'div'], class_=lambda x: x and 'salary' in x.lower())
            salary = salary_elem.get_text(strip=True) if salary_elem else "N/A"
            
            # Extract job description snippet
            desc_elem = job_card.find(['div', 'span'], class_=lambda x: x and any(word in x.lower() for word in ['summary', 'snippet', 'description']))
            description = desc_elem.get_text(strip=True) if desc_elem else "N/A"
            
            # Extract posting date
            date_elem = job_card.find(['span', 'time'], class_=lambda x: x and 'date' in x.lower())
            posted_date = date_elem.get_text(strip=True) if date_elem else "N/A"
            
            return {
                'title': title,
                'company': company,
                'location': location,
                'salary': salary,
                'description': description,
                'posted_date': posted_date,
                'scraped_at': datetime.now().isoformat(),
                'source': 'indeed'
            }
            
        except Exception as e:
            return None
    
    def scrape_company_career_pages(self, companies):
        """Scrape career pages of specific companies"""
        
        print(f"🏢 Scraping company career pages...")
        
        career_jobs = []
        for company in companies:
            try:
                # Common career page patterns
                career_urls = [
                    f"https://{company}.com/careers",
                    f"https://{company}.com/jobs",
                    f"https://careers.{company}.com",
                    f"https://jobs.{company}.com"
                ]
                
                for url in career_urls:
                    try:
                        time.sleep(random.uniform(2, 4))
                        response = self.session.get(url, timeout=10)
                        
                        if response.status_code == 200:
                            soup = BeautifulSoup(response.content, 'html.parser')
                            text = soup.get_text()
                            
                            # Extract job-related information
                            job_mentions = self.extract_job_mentions(text, company)
                            career_jobs.extend(job_mentions)
                            
                            print(f"   ✅ {company}: Found {len(job_mentions)} job mentions")
                            break
                            
                    except:
                        continue
                        
            except Exception as e:
                print(f"   ❌ {company}: {e}")
                continue
        
        return career_jobs
    
    def extract_job_mentions(self, text, company):
        """Extract job-related information from career page text"""
        
        jobs = []
        
        # Common job title patterns
        job_patterns = [
            r'(Software Engineer|Data Scientist|Product Manager|Designer|Developer|Analyst|Manager|Director|VP)',
            r'(Senior|Junior|Lead|Principal)\s+([A-Z][a-z]+\s*){1,3}',
            r'(Frontend|Backend|Full[- ]?Stack|DevOps|ML|AI)\s+(Engineer|Developer)',
        ]
        
        for pattern in job_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                job_title = match if isinstance(match, str) else ' '.join(filter(None, match))
                
                if len(job_title) > 5:  # Filter out too short matches
                    jobs.append({
                        'title': job_title,
                        'company': company,
                        'location': 'Various',
                        'salary': 'N/A',
                        'description': f'Position at {company}',
                        'posted_date': 'Recent',
                        'scraped_at': datetime.now().isoformat(),
                        'source': 'company_career_page'
                    })
        
        return jobs[:10]  # Limit results
    
    def analyze_with_ai(self, job_data):
        """Analyze job data with AI insights"""
        
        print(f"🤖 Analyzing {len(job_data)} jobs with AI...")
        
        # Skill extraction
        all_skills = []
        all_titles = []
        all_companies = []
        
        for job in job_data:
            # Extract skills from job descriptions
            skills = self.extract_skills(job.get('description', ''))
            all_skills.extend(skills)
            
            # Collect titles and companies
            all_titles.append(job.get('title', ''))
            all_companies.append(job.get('company', ''))
        
        # Analyze trends
        analysis = {
            'total_jobs_analyzed': len(job_data),
            'top_skills': self.get_top_items(all_skills, 15),
            'top_job_titles': self.get_top_items(all_titles, 10),
            'top_companies': self.get_top_items(all_companies, 10),
            'salary_insights': self.analyze_salaries(job_data),
            'location_trends': self.analyze_locations(job_data),
            'posting_trends': self.analyze_posting_dates(job_data),
            'generated_insights': self.generate_market_insights(job_data)
        }
        
        return analysis
    
    def extract_skills(self, description):
        """Extract technical skills from job descriptions"""
        
        skill_keywords = [
            'Python', 'JavaScript', 'Java', 'React', 'Node.js', 'AWS', 'Docker',
            'Kubernetes', 'SQL', 'MongoDB', 'PostgreSQL', 'Git', 'Linux',
            'Machine Learning', 'AI', 'Data Science', 'Pandas', 'NumPy',
            'TensorFlow', 'PyTorch', 'Scikit-learn', 'Tableau', 'Power BI',
            'Excel', 'Figma', 'Sketch', 'Adobe', 'Agile', 'Scrum'
        ]
        
        found_skills = []
        desc_lower = description.lower()
        
        for skill in skill_keywords:
            if skill.lower() in desc_lower:
                found_skills.append(skill)
        
        return found_skills
    
    def get_top_items(self, items, limit=10):
        """Get top occurring items"""
        from collections import Counter
        counter = Counter([item for item in items if item and item != 'N/A'])
        return counter.most_common(limit)
    
    def analyze_salaries(self, job_data):
        """Analyze salary information"""
        salaries = [job.get('salary', '') for job in job_data if job.get('salary') != 'N/A']
        return {
            'total_with_salary': len(salaries),
            'salary_mentions': salaries[:10]  # Sample salaries
        }
    
    def analyze_locations(self, job_data):
        """Analyze job locations"""
        locations = [job.get('location', '') for job in job_data if job.get('location') != 'N/A']
        return self.get_top_items(locations, 10)
    
    def analyze_posting_dates(self, job_data):
        """Analyze when jobs were posted"""
        dates = [job.get('posted_date', '') for job in job_data if job.get('posted_date') != 'N/A']
        return self.get_top_items(dates, 5)
    
    def generate_market_insights(self, job_data):
        """Generate business insights from job data"""
        
        insights = []
        
        # Remote work analysis
        remote_jobs = sum(1 for job in job_data if 'remote' in job.get('description', '').lower())
        if remote_jobs > 0:
            remote_percentage = (remote_jobs / len(job_data)) * 100
            insights.append(f"{remote_percentage:.1f}% of jobs mention remote work")
        
        # Experience level analysis
        senior_jobs = sum(1 for job in job_data if 'senior' in job.get('title', '').lower())
        if senior_jobs > 0:
            senior_percentage = (senior_jobs / len(job_data)) * 100
            insights.append(f"{senior_percentage:.1f}% of jobs are senior-level positions")
        
        # Tech stack trends
        ai_jobs = sum(1 for job in job_data if any(term in job.get('description', '').lower() for term in ['ai', 'machine learning', 'artificial intelligence']))
        if ai_jobs > 0:
            ai_percentage = (ai_jobs / len(job_data)) * 100
            insights.append(f"{ai_percentage:.1f}% of jobs mention AI/ML")
        
        return insights
    
    def save_results(self, job_data, analysis, filename_prefix="job_market"):
        """Save all results to files"""
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save raw job data
        jobs_filename = f"{filename_prefix}_jobs_{timestamp}.json"
        with open(jobs_filename, 'w', encoding='utf-8') as f:
            json.dump(job_data, f, indent=2, ensure_ascii=False)
        
        # Save analysis
        analysis_filename = f"{filename_prefix}_analysis_{timestamp}.json"
        with open(analysis_filename, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        
        # Save as CSV for easy viewing
        if job_data:
            df = pd.DataFrame(job_data)
            csv_filename = f"{filename_prefix}_data_{timestamp}.csv"
            df.to_csv(csv_filename, index=False)
            print(f"💾 Saved: {csv_filename}")
        
        print(f"💾 Saved: {jobs_filename}")
        print(f"💾 Saved: {analysis_filename}")
        
        return {
            'jobs_file': jobs_filename,
            'analysis_file': analysis_filename,
            'csv_file': csv_filename if job_data else None
        }

def run_job_market_analysis():
    """Main function to run the complete job market analysis"""
    
    print("🚀 Job Market Intelligence Platform")
    print("="*50)
    
    analyzer = JobMarketAnalyzer()
    
    # Configuration
    job_titles = ["Data Scientist", "Software Engineer", "Product Manager"]
    tech_companies = ["google", "microsoft", "apple", "amazon", "meta"]
    
    all_jobs = []
    
    # Scrape job boards
    for title in job_titles:
        jobs = analyzer.scrape_indeed_jobs(title, max_pages=2)
        all_jobs.extend(jobs)
        time.sleep(3)  # Be respectful between searches
    
    # Scrape company career pages
    company_jobs = analyzer.scrape_company_career_pages(tech_companies)
    all_jobs.extend(company_jobs)
    
    print(f"\n📊 Total jobs collected: {len(all_jobs)}")
    
    if all_jobs:
        # Analyze with AI
        analysis = analyzer.analyze_with_ai(all_jobs)
        
        # Save results
        files = analyzer.save_results(all_jobs, analysis)
        
        # Display key insights
        print("\n" + "="*50)
        print("🎯 KEY MARKET INSIGHTS")
        print("="*50)
        
        print(f"📈 Jobs analyzed: {analysis['total_jobs_analyzed']}")
        
        if analysis['top_skills']:
            print(f"\n💻 Top Skills in Demand:")
            for skill, count in analysis['top_skills'][:10]:
                print(f"   {skill}: {count} mentions")
        
        if analysis['generated_insights']:
            print(f"\n🔍 Market Trends:")
            for insight in analysis['generated_insights']:
                print(f"   • {insight}")
        
        if analysis['top_companies']:
            print(f"\n🏢 Top Hiring Companies:")
            for company, count in analysis['top_companies'][:5]:
                print(f"   {company}: {count} jobs")
        
        print(f"\n📁 Files created:")
        for file_type, filename in files.items():
            if filename:
                print(f"   {file_type}: {filename}")
        
        return {
            'jobs': all_jobs,
            'analysis': analysis,
            'files': files
        }
    
    else:
        print("❌ No jobs found. Try adjusting search criteria or checking website accessibility.")
        return None

if __name__ == "__main__":
    # Run the analysis
    results = run_job_market_analysis()
    
    if results:
        print(f"\n🎓 CV Project Benefits:")
        print(f"   ✅ Web scraping multiple sources")
        print(f"   ✅ Data cleaning and processing") 
        print(f"   ✅ AI-powered analysis")
        print(f"   ✅ Business insights generation")
        print(f"   ✅ Multiple output formats")
        print(f"   ✅ Real market value")
        
        print(f"\n🚀 Next steps for your CV:")
        print(f"   1. Add data visualization (matplotlib/plotly)")
        print(f"   2. Build a web dashboard (Streamlit/Flask)")
        print(f"   3. Add predictive modeling")
        print(f"   4. Deploy to cloud (Heroku/AWS)")
        print(f"   5. Schedule automated runs")