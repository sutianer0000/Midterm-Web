
### Web Programming & Applications (503073) — Topic 7: Web Crawling
(For better setup instructions, read the README.txt that is included in the outside of this demo's folder)
---

## What it does

Crawls **cachep.vn** (Cá Chép Bookstore) using their Shopify JSON API and displays
all books in a beautiful interactive dashboard with:

- Book title, cover image, original price, discounted price, discount %
- Filter by category (16 categories from the real site)
- Filter by price range (min → max)
- Filter: show only discounted books
- Search by keyword (book title)
- Sort by: price low→high, price high→low, biggest discount, A→Z
- Click any book to see details and link to the real product page

---

## Requirements

- Python 3.9 or higher
- pip
- Internet connection (for crawling)

---

## Setup

### 1. Install dependencies
```bash
pip install flask requests beautifulsoup4 lxml
```

### 2. Run the server
```bash
python app.py
```

### 3. Open in browser
→ http://localhost:5000

---

## How to use

1. Open http://localhost:5000
2. Click **"⚡ Thu thập dữ liệu"** (the gold button in the top right)
3. Wait ~2–3 minutes while the crawler fetches data
4. Browse, filter, and search books!

Data is saved to `books_data.json` — you don't need to re-crawl every time.

---

## Project Structure

```
cachep/
├── app.py           # Flask web server
├── crawler.py       # Crawler engine (Shopify JSON API)
├── books_data.json  # Crawled data (created after first crawl)
├── requirements.txt
├── README.md
└── templates/
    └── index.html   # Full UI dashboard
```

---

## Crawling details

- Source: `https://cachep.vn/collections/{slug}/products.json`
- Politeness delay: 600ms between requests
- Respects robots.txt (Allow: / on cachep.vn)
- User-Agent: `CachepCrawler/1.0 (Educational - Web Programming 503073)`
- Crawls 16 categories × up to 4 pages × 30 items = up to ~1,920 books

---

## API Endpoints

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Dashboard UI |
| `/api/books` | GET | Books list (supports q, category, price_min, price_max, discount_only, sort, page) |
| `/api/crawl/start` | POST | Start a crawl |
| `/api/crawl/status` | GET | Live crawl progress |
