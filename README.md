# Rotten Tomatoes Review Sanitizer

An AI-powered system that analyzes Rotten Tomatoes audience reviews to filter out review bombing, spam, and low-quality content, creating a more accurate "sanitized" score.

## Features

- **Web Scraping**: Automatically collects user reviews from Rotten Tomatoes
- **AI Analysis**: Uses DeepSeek AI to evaluate review quality and authenticity
- **Quality Scoring**: Rates reviews from 0.1 (low effort) to 1.0 (high quality)
- **Review Bombing Detection**: Identifies and filters out spam/troll content
- **Smart Aggregation**: Creates weighted scores based on review quality
- **Database Storage**: SQLite database with deduplication and efficient storage
- **Parallel Processing**: Multi-threaded analysis for faster processing

## How It Works

1. **Data Acquisition**: Scrapes reviews from Rotten Tomatoes using Selenium
2. **Data Storage**: Stores reviews in SQLite with metadata and deduplication
3. **AI Analysis**: Uses DeepSeek API to judge review quality and authenticity
4. **Score Calculation**: Creates weighted average scores based on AI assessment
5. **Results Presentation**: Compares original vs. sanitized scores with detailed analytics

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Hibah155/ProjectH.git
   cd ProjectH

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt

3. **Set up environment variables**:
   Create a .env file

4. **Add your DeepSeek API key**:
   DEEPSEEK_API_KEY=your_api_key_here

5. **Download ChromeDriver**:
   Ensure ChromeDriver is in your path or project directory
   Download from: https://chromedriver.chromedriver.org/

## Usage

Run the main script:
python newscrape.py

The program will:
Prompt you for a movie title
Scrape reviews from Rotten Tomatoes
Analyze them using AI
Display comparative results showing:
  -Original Rotten Tomatoes score
  -Sanitized AI-weighted score
  -Quality distribution of reviews
  -Detection of potential review bombing

## Project Structure
ProjectH/
├── newscrape.py          # Main application script
├── .gitignore           # Git ignore rules
├── README.md            # This file
├── requirements.txt     # Python dependencies
└── final.db            # SQLite database (created automatically)

## Technical Details
Web Scraping: Selenium WebDriver with Chrome
AI Integration: DeepSeek Chat API for review analysis
Database: SQLite with proper schema design
Concurrency: ThreadPoolExecutor for parallel processing
Data Validation: MD5 hashing for review deduplication

## Example Output
=== AI ANALYSIS RESULTS for 'barbie' ===
Total Reviews Analyzed: 300
Official RT Audience Score: 51.3%
Raw Average Star Rating: 3.1/5 (61.0%)
Sanitized Score (AI-Weighted): 67.4%
Average AI Quality Score: 49.4%
Authentic Reviews: 242 (80.7%)
Potential Review Bombs/Spam: 58 (19.3%)

--- Review Quality Distribution ---
  - Excellent (90-100%): 15 reviews (5.0% of reviews) - Avg quality of reviews: 90.7%
  - Good (70-89%): 76 reviews (25.3% of reviews) - Avg quality of reviews: 75.9%
  - Fair (50-69%): 79 reviews (26.3% of reviews) - Avg quality of reviews: 56.1%
  - Poor (30-49%): 69 reviews (23.0% of reviews) - Avg quality of reviews: 35.8%
  - Very Poor (10-29%): 61 reviews (20.3% of reviews) - Avg quality of reviews: 12.8%

--- SCORE COMPARISON ---
Official RT Score:            51.3%
Raw Average Score:            61.0%
AI-Sanitized Score:           67.4%
AI Quality Adjustment:         +6.4%
→ Moderate quality adjustment applied

--- INTERPRETATION ---
The AI analysis detected that 19.3% of reviews may be review bombing, spam, or low-quality content.
The sanitized score is 16.1% HIGHER than the official score, suggesting review bombing was occurring.

Overall review quality: 49.4%
→ Mostly brief, emotional, or low-effort reviews

## Use Cases
Film Studios: Get accurate audience sentiment beyond review bombing
Critics: Understand genuine audience reception vs. coordinated campaigns
Researchers: Analyze review quality patterns and audience behavior
Movie Fans: See what actual viewers think without spam interference

## Limitations
Requires Rotten Tomatoes page structure to remain consistent
Dependent on DeepSeek API availability and pricing
ChromeDriver requires a compatible Chrome version
Processing time increases with the number of reviews

## Future Enhancements
Web interface with Flask/Django
Historical trend analysis
Comparative analysis across multiple platforms
Sentiment analysis beyond binary authentic/inauthentic
Export functionality for data analysis

## License
This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing
Contributions, issues, and feature requests are welcome! Feel free to check the issues page.

## Contact
Hibah Sohail Siddiqui - GitHub

**Note: This project is for educational and research purposes. Please respect Rotten Tomatoes' terms of service and use responsibly.**

