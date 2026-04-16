from flask import Flask, render_template, jsonify, request
from crawler import load_data, start_crawl_thread, get_status, CATEGORIES, heal_stale_progress

# Heal any stale in_progress flag left by a previous crash or page refresh
heal_stale_progress()

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html", categories=CATEGORIES)


@app.route("/api/books")
def api_books():
    data  = load_data()
    books = data.get("books", [])

    q             = request.args.get("q", "").strip().lower()
    category      = request.args.get("category", "").strip()
    price_min     = request.args.get("price_min", "")
    price_max     = request.args.get("price_max", "")
    discount_only = request.args.get("discount_only", "") == "1"
    sort          = request.args.get("sort", "default")

    if q:
        books = [b for b in books if q in b["title"].lower()]
    if category:
        books = [b for b in books if b["category"] == category]
    if price_min:
        try: books = [b for b in books if b["price"] >= float(price_min)]
        except ValueError: pass
    if price_max:
        try: books = [b for b in books if b["price"] <= float(price_max)]
        except ValueError: pass
    if discount_only:
        books = [b for b in books if b["discount_pct"] > 0]

    if sort == "price_asc":
        books.sort(key=lambda b: b["price"])
    elif sort == "price_desc":
        books.sort(key=lambda b: b["price"], reverse=True)
    elif sort == "discount":
        books.sort(key=lambda b: b["discount_pct"], reverse=True)
    elif sort == "name_asc":
        books.sort(key=lambda b: b["title"].lower())

    total    = len(books)
    # per_page=9999 used by table view to get all rows at once
    per_page = int(request.args.get("per_page", 24))
    per_page = min(per_page, 9999)
    page     = max(1, int(request.args.get("page", 1)))
    paged    = books[(page-1)*per_page : page*per_page]

    return jsonify({
        "books":       paged,
        "total":       total,
        "page":        page,
        "per_page":    per_page,
        "pages":       max(1, (total + per_page - 1) // per_page),
        "crawled_at":  data.get("crawled_at"),
        "in_progress": data.get("in_progress", False),
    })


@app.route("/api/crawl/start", methods=["POST"])
def start_crawl():
    body          = request.get_json(silent=True) or {}
    mode          = body.get("mode", "count")
    count         = int(body.get("count", 120))
    category_slug = body.get("category_slug", None)
    ok = start_crawl_thread(mode=mode, count=count, category_slug=category_slug)
    return jsonify({"started": ok})


@app.route("/api/crawl/status")
def crawl_status():
    return jsonify(get_status())


if __name__ == "__main__":
    print("\n  📚  CacheP Bookstore Crawler")
    print("  ➜  http://localhost:5000\n")
    app.run(debug=False, port=5000, use_reloader=False, threaded=True)
