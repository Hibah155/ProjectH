from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
from transformers import pipeline
from webdriver_manager.chrome import ChromeDriverManager
# from bs4 import BeautifulSoup
# import random
import sqlite3
import time
import re
# import torch
import hashlib
from tqdm import tqdm
from dotenv import load_dotenv
import os
import json
from openai import OpenAI
import concurrent.futures
import threading

# MOVIE_URL = "https://www.rottentomatoes.com/m/knives_out/reviews?type=user"
CHROMEDRIVER_PATH = "./chromedriver"
DB_NAME = "reviewsaireviewidonly.db"
SCROLL_PAUSE_TIME = 2
MAX_CLICKS = 50
TARGET_REVIEWS = 100
BASE_URL = "https://www.rottentomatoes.com/m/"

load_dotenv()
deepseek_client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

def get_thread_safe_connection():
    # Each thread needs its own connection
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def generate_review_hash(review_text, username, date, movie_id):
    unique_string = f"{review_text[:100]}_{username}_{date}_{movie_id}"
    return hashlib.md5(unique_string.encode()).hexdigest()

def setup_ai_analysis_table():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_analysis (
            review_id INTEGER PRIMARY KEY,
            movie_id INTEGER,
            is_authentic BOOLEAN,
            quality_score REAL,
            reasoning TEXT,
            analysis_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (review_id) REFERENCES reviews (id),
            FOREIGN KEY (movie_id) REFERENCES movies (id)
        )
    ''')
    conn.commit()
    conn.close()
    print("AI analysis table ready!")

def setup_database():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS movies
                 (id INTEGER PRIMARY KEY,
                  title TEXT UNIQUE,
                  rt_url TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS reviews
                 (id INTEGER PRIMARY KEY,
                  movie_id INTEGER,
                  review_text TEXT NOT NULL,
                  original_rating REAL,
                  review_type TEXT,
                  username TEXT,
                  date TEXT,
                  review_hash TEXT UNIQUE,  -- Add this column for deduplication
                  FOREIGN KEY (movie_id) REFERENCES movies (id))''')
    
    # c.execute("INSERT OR IGNORE INTO movies (title, rt_url) VALUES (?, ?)",
    #           ("Star Wars: The Last Jedi", "https://www.rottentomatoes.com/m/star_wars_the_last_jedi"))
    
    conn.commit()
    conn.close()

    setup_ai_analysis_table()
    print("Database setup complete.")

def get_movie_url():
    movie_title = input("Enter the movie title: ").strip()
    url = movie_title.lower().replace(' ', '_')
    url = re.sub(r'[^a-z0-9_]', '', url)

    movie_url = f"{BASE_URL}{url}/reviews?type=user"
    return movie_title, movie_url

def scrape_reviews(movie_url):
    print("Launching browser...")

    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service)

    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    try:
        driver.get(movie_url)
        print("Page loaded. Clicking 'Load More' to load additional reviews...")

        time.sleep(3)
        
        clicks = 0

        pbar = tqdm(total=TARGET_REVIEWS, desc="Loading reviews", unit="review")
        while clicks < MAX_CLICKS:
            try:
                load_more_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'div.load-more-container rt-button'))
                )

                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", load_more_button)
                time.sleep(1)

                driver.execute_script("arguments[0].click();", load_more_button)

                clicks += 1
                # print(f"Clicked 'Load More' button {clicks} times.")

                time.sleep(3)

                current_reviews = driver.find_elements(By.CSS_SELECTOR, 'div.audience-review-row')
                # print(f"Current number of reviews loaded: {len(current_reviews)}")
                pbar.update(len(current_reviews) - pbar.n)
                pbar.set_postfix(current=len(current_reviews))

                if len(current_reviews) >= TARGET_REVIEWS:
                    print(f"Target of {TARGET_REVIEWS} reviews reached. Stopping clicks.")
                    break

            except TimeoutException:
                print("No more 'Load More' button found or reached the end.")
                break
            except ElementClickInterceptedException:
                print("Click intercepted, retrying...")
                try:
                    driver.execute_script("arguments[0].click();", load_more_button)
                except:
                    print("Failed to click 'Load More' button after interception.")
                    break
            except Exception as e:
                print(f"Error clicking 'Load More': {e}")
                break

        pbar.close()
        print("Finished loading reviews. Browser closing soon.")
        return driver

        # last_height = driver.execute_script("return document.body.scrollHeight")
        # scrolls = 0
        # while scrolls < MAX_SCROLLS:
        #     driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        #     time.sleep(SCROLL_PAUSE_TIME)
        #     new_height = driver.execute_script("return document.body.scrollHeight")
        #     if new_height == last_height:
        #         print("Reached the bottom of the page.")
        #         break
        #     last_height = new_height
        #     scrolls += 1
        #     if scrolls % 10 == 0:
        #         print(f"Scrolled {scrolls} times...")

        # time.sleep(3)

        # print("Finished loading. Browser closing.")
        # return driver
    
    except Exception as e:
        driver.quit()
        raise e

def parse_reviews(driver):
    print("Parsing reviews...")
    # soup = BeautifulSoup(html_content, 'html.parser')
    reviews = []

    review_cards = driver.find_elements(By.CSS_SELECTOR, 'div.audience-review-row')
    print(f"Found {len(review_cards)} review cards on the page.")

    for card in tqdm(review_cards, desc="Parsing reviews", unit="review"):
        try:
            text_element = card.find_element(By.CSS_SELECTOR, 'p.audience-reviews__review')
            review_text = text_element.text.strip()

            try:
                user_element = card.find_element(By.CSS_SELECTOR, 'a.audience-reviews__name')
                username = user_element.text.strip()
            except:
                username = "Anonymous"

            date_element = card.find_element(By.CSS_SELECTOR, 'span.audience-reviews__duration')
            date = date_element.text.strip()

            try:
                rating_stars_group = card.find_element(By.CSS_SELECTOR, 'rating-stars-group')
                rating = rating_stars_group.get_attribute('score')
                if rating:
                    rating = float(rating)
                else:
                    rating = None
            except Exception as e:
                print(f"Error getting rating: {e}")
                rating = None

            # star_element = card.find_element(By.CSS_SELECTOR, 'div.audience-review-meta')
            # rating = star_element.get_attribute('aria-label')

            # try:
            #     star_element = card.find_element(By.CSS_SELECTOR, '[aria-label*="star"]')
            #     aria_label = star_element.get_attribute('aria-label')
            #     if aria_label:
            #         rating = float(aria_label.split(' ')[0])
            #     else:
            #         rating = None
            # except:
            #     rating = None
            #     print("Could not find star rating for this review.")

            reviews.append({
                'text': review_text,
                'rating': rating,
                'username': username,
                'date': date
            })
        except Exception as e:
            print(f"Error parsing review card: {e}")
            continue
    
    print(f"Successfully parsed {len(reviews)} reviews.")
    return reviews

def save_reviews_to_db(reviews_list, movie_title, movie_url):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("INSERT OR IGNORE INTO movies (title, rt_url) VALUES (?, ?)", (movie_title, movie_url))
    c.execute("SELECT id FROM movies WHERE title = ?", (movie_title,))
    movie_id = c.fetchone()[0]

    inserted_count = 0
    duplicate_count = 0

    for review in reviews_list:
        try:
            review_hash = generate_review_hash(
                review['text'],
                review['username'],
                review['date'],
                movie_id
            )

            # Check if review already exists
            c.execute("SELECT id FROM reviews WHERE review_hash = ?", (review_hash,))
            existing_review = c.fetchone()
            
            if existing_review:
                duplicate_count += 1
                continue

            # Insert the new review
            c.execute('''INSERT INTO reviews
                         (movie_id, review_text, original_rating, review_type, username, date, review_hash)
                         VALUES (?, ?, ?, ?, ?, ?, ?)''',
                         (movie_id, review['text'], review['rating'], 'audience', 
                          review['username'], review['date'], review_hash))
            inserted_count += 1

        except sqlite3.Error as e:
            print(f"Error inserting review: {e}")

    conn.commit()
    conn.close()
    print(f"Successfully saved {inserted_count} new reviews to the database.")
    print(f"Skipped {duplicate_count} duplicate reviews.")

    return movie_id

def analyze_single_review(review_text):
    system_prompt = """
    You are an expert film criticism analyst. Your task is to judge the quality and authenticity of user movie reviews to help filter out review bombing, spam, and low-effort content.

    Analyze the given review text and respond STRICTLY with a valid JSON object containing only these three fields:
    1. "is_authentic": A boolean. false if the review seems like spam, trolling, review bombing, is completely off-topic, or is a very low-effort rant (e.g., "This movie sucks!").
    2. "quality_score": A float between 0.1 (lowest quality) and 1.0 (highest quality). Base this on thoughtfulness, use of detail, coherence, and originality. A one-word rant scores 0.1. A well-reasoned paragraph scores 0.9-1.0.
    3. "reasoning": A very brief one-sentence explanation for your judgments.

    Be strict. The goal is to create a more accurate aggregate score by downweighting unhelpful reviews.
    """
    
    try:
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",  # Use the latest deepseek-chat model
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"REVIEW TEXT: {review_text}"}
            ],
            response_format={"type": "json_object"}, # Force it to return JSON
            temperature=0.1 # Low temperature for more deterministic, consistent outputs
        )
        
        # Parse the JSON response from the AI
        analysis_result = json.loads(response.choices[0].message.content)
        return analysis_result
        
    except Exception as e:
        print(f"\nDeepSeek API error for review: {e}")
        # Return a default "low quality" result if the API call fails
        return {"is_authentic": False, "quality_score": 0.1, "reasoning": "API analysis failed."}

def analyze_reviews_with_ai_ordered(movie_id):
    print("Starting parallel AI analysis of reviews (ordered)...")
    setup_ai_analysis_table()

    # Get reviews to analyze
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT r.id, r.review_text 
        FROM reviews r 
        LEFT JOIN ai_analysis a ON r.id = a.review_id 
        WHERE r.movie_id = ? AND a.review_id IS NULL
        ORDER BY r.id  -- Ensure we process in order
    ''', (movie_id,))
    reviews_to_analyze = cursor.fetchall()
    conn.close()
    
    print(f"Found {len(reviews_to_analyze)} reviews to analyze...")
    
    # Pre-insert placeholder records to preserve order
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    for review_id, _ in reviews_to_analyze:
        cursor.execute('''
            INSERT OR IGNORE INTO ai_analysis 
            (review_id, movie_id, is_authentic, quality_score, reasoning)
            VALUES (?, ?, NULL, NULL, 'Analysis in progress')
        ''', (review_id, movie_id))
    conn.commit()
    conn.close()
    
    # Process reviews in parallel but update existing records
    def process_review(review_data):
        review_id, review_text = review_data
        analysis = analyze_single_review(review_text)
        
        if analysis:
            thread_conn = get_thread_safe_connection()
            thread_cursor = thread_conn.cursor()
            thread_cursor.execute('''
                UPDATE ai_analysis 
                SET is_authentic = ?, quality_score = ?, reasoning = ?
                WHERE review_id = ?
            ''', (
                analysis['is_authentic'],
                analysis['quality_score'],
                analysis['reasoning'],
                review_id
            ))
            thread_conn.commit()
            thread_conn.close()
        return review_id  # Return the ID to track completion order

    # Use ThreadPoolExecutor for parallel processing
    max_workers = 5
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Process in order but complete asynchronously
        results = list(tqdm(executor.map(process_review, reviews_to_analyze), 
                          total=len(reviews_to_analyze), desc="Analyzing reviews"))
    
    print(f"AI analysis complete! Analyzed {len(reviews_to_analyze)} reviews")
    print(f"Processed in this order: {results}")  # This shows completion order

def analyze_reviews_with_ai_parallel(movie_id):
    print("Starting parallel AI analysis of reviews...")
    setup_ai_analysis_table()

    # Get reviews to analyze
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT r.id, r.review_text 
        FROM reviews r 
        LEFT JOIN ai_analysis a ON r.id = a.review_id 
        WHERE r.movie_id = ? AND a.review_id IS NULL
    ''', (movie_id,))
    reviews_to_analyze = cursor.fetchall()
    conn.close()
    
    print(f"Found {len(reviews_to_analyze)} reviews to analyze...")
    
    # Process reviews in parallel
    def process_review(review_data):
        review_id, review_text = review_data
        analysis = analyze_single_review(review_text)
        
        if analysis:
            thread_conn = get_thread_safe_connection()
            thread_cursor = thread_conn.cursor()
            thread_cursor.execute('''
                INSERT INTO ai_analysis 
                (review_id, movie_id, is_authentic, quality_score, reasoning)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                review_id,
                movie_id,
                analysis['is_authentic'],
                analysis['quality_score'],
                analysis['reasoning'],
            ))
            thread_conn.commit()
            thread_conn.close()
        return True

    # Use ThreadPoolExecutor for parallel processing
    max_workers = 5  # Adjust based on your API rate limits
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        list(tqdm(executor.map(process_review, reviews_to_analyze), 
                 total=len(reviews_to_analyze), desc="Analyzing reviews"))
    
    print(f"AI analysis complete! Analyzed {len(reviews_to_analyze)} reviews")

def analyze_reviews_with_ai(movie_id):
    print("Starting AI analysis of reviews...")

    setup_ai_analysis_table()

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT r.id, r.review_text 
        FROM reviews r 
        LEFT JOIN ai_analysis a ON r.id = a.review_id 
        WHERE r.movie_id = ? AND a.review_id IS NULL
    ''', (movie_id,))

    reviews_to_analyze = cursor.fetchall()
    print(f"Found {len(reviews_to_analyze)} reviews to analyze...")
    
    analyzed_count = 0
    for review_id, review_text in tqdm(reviews_to_analyze, desc="Analyzing with DeepSeek"):
        analysis = analyze_single_review(review_text)
        if analysis:
            cursor.execute('''
                INSERT INTO ai_analysis 
                (review_id, movie_id, is_authentic, quality_score, reasoning)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                review_id,
                movie_id, # <- Now passing the movie_id to the query
                analysis['is_authentic'],
                analysis['quality_score'],
                analysis['reasoning'],
            ))
            analyzed_count += 1
        time.sleep(0.2)

    conn.commit()
    conn.close()
    print(f"AI analysis complete! Analyzed {analyzed_count} reviews")

def calculate_sanitized_score(movie_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Get the USER'S rating and the AI's quality score & authenticity flag
    cursor.execute('''
        SELECT r.original_rating, a.quality_score, a.is_authentic
        FROM reviews r
        JOIN ai_analysis a ON r.id = a.review_id
        WHERE r.movie_id = ? AND r.original_rating IS NOT NULL
    ''', (movie_id,))

    reviews = cursor.fetchall()
    conn.close()

    if not reviews:
        return None

    total_weight = 0
    weighted_sum = 0

    for original_rating, quality_score, is_authentic in reviews:
        # Define the weight logic. This is the crucial part!
        # Example: Weight = quality_score, but set to 0 if not authentic.
        weight = quality_score if is_authentic else 0.0

        # Use the USER'S original rating, weighted by the AI's judgment
        weighted_sum += original_rating * weight
        total_weight += weight

    if total_weight > 0:
        sanitized_score = (weighted_sum / total_weight) * 20  # Convert from 0-5 star to 0-100
    else:
        sanitized_score = 0

    return round(sanitized_score, 2)

def calculate_rt_audience_score(movie_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            COUNT(*) as total_reviews,
            SUM(CASE WHEN original_rating >= 3.5 THEN 1 ELSE 0 END) as fresh_reviews
        FROM reviews
        WHERE movie_id = ? AND original_rating IS NOT NULL
    ''', (movie_id,))

    total, fresh = cursor.fetchone()
    conn.close()

    print(f"{fresh}")
    if total > 0:
        audience_score = (fresh / total) * 100
        return round(audience_score, 2)
    else:
        return None

def display_analysis_results(movie_title):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM movies WHERE title = ?", (movie_title,))
    movie_row = cursor.fetchone()

    if not movie_row:
        print(f"Movie '{movie_title}' not found in database.")
        conn.close()
        return
    
    movie_id = movie_row[0]

    rt_score = calculate_rt_audience_score(movie_id)
    sanitized_score = calculate_sanitized_score(movie_id)

    cursor.execute('''
        SELECT 
            COUNT(*) as total_reviews,
            AVG(r.original_rating) as avg_original_rating,
            AVG(r.original_rating) * 20 as avg_original_score, -- Convert 0-5 to 0-100
            AVG(a.quality_score) as avg_quality_score,
            SUM(CASE WHEN a.is_authentic THEN 1 ELSE 0 END) as authentic_count,
            SUM(CASE WHEN NOT a.is_authentic THEN 1 ELSE 0 END) as inauthentic_count
        FROM reviews r
        JOIN ai_analysis a ON r.id = a.review_id
        WHERE r.movie_id = ?
    ''', (movie_id,))

    stats = cursor.fetchone()
    
    # Get sentiment distribution
    cursor.execute('''
        SELECT 
            -- Create buckets for quality scores
            CASE 
                WHEN quality_score >= 0.9 THEN 'Excellent (0.9-1.0)'
                WHEN quality_score >= 0.7 THEN 'Good (0.7-0.89)'
                WHEN quality_score >= 0.5 THEN 'Fair (0.5-0.69)'
                WHEN quality_score >= 0.3 THEN 'Poor (0.3-0.49)'
                ELSE 'Very Poor (0.1-0.29)'
            END as quality_bucket,
            COUNT(*) as count,
            AVG(quality_score) as avg_quality_in_bucket
        FROM ai_analysis a
        JOIN reviews r ON a.review_id = r.id
        WHERE r.movie_id = ?
        GROUP BY quality_bucket
        ORDER BY avg_quality_in_bucket DESC
    ''', (movie_id,))

    distribution = cursor.fetchall()
    
    print(f"\n=== AI ANALYSIS RESULTS for '{movie_title}' ===")
    if stats:
        total_reviews, avg_original, avg_original_score, avg_quality, authentic_count, inauthentic_count = stats
        
        print(f"Total Reviews Analyzed: {total_reviews}")
        print(f"Official RT Audience Score: {rt_score:.2f}%")
        print(f"Raw Average Star Rating: {avg_original:.2f}/5 ({avg_original_score:.2f}/100)")
        print(f"Sanitized Score (AI-Weighted): {sanitized_score:.2f}/100") 
        print(f"Average AI Quality Score: {avg_quality:.2f}/1.0")
        print(f"Authentic Reviews: {authentic_count} ({authentic_count/total_reviews*100:.1f}%)")
        print(f"Potential Review Bombs/Spam: {inauthentic_count} ({inauthentic_count/total_reviews*100:.1f}%)")
        
        print("\n--- Quality Distribution ---")
        for bucket, count, avg_qual in distribution:
            print(f"  - {bucket}: {count} reviews (Avg: {avg_qual:.2f})")
    
    conn.close()

if __name__ == "__main__":
    print("Starting RT reviews scraper...")
    setup_database()

    movie_title, movie_url = get_movie_url()
    print(f"Scraping reviews for: {movie_title}")
    print(f"URL: {movie_url}")

    # driver = scrape_reviews(movie_url)
    # all_reviews = parse_reviews(driver)

    driver = scrape_reviews(movie_url)
    all_reviews = parse_reviews(driver)
    driver.quit()

    movie_id = save_reviews_to_db(all_reviews, movie_title, movie_url)
    print("Scraping complete!")

    analyze_reviews_with_ai_ordered(movie_id)
    display_analysis_results(movie_title)

    print("\nProcess completed successfully :)")