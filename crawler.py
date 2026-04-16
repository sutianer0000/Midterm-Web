import requests
import time
import json
import os
import threading
import hashlib
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "vi-VN,vi;q=0.9",
    "Referer": "https://cachep.vn/",
}
IMG_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://cachep.vn/",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "sec-fetch-dest": "image",
    "sec-fetch-mode": "no-cors",
    "sec-fetch-site": "cross-site",
}

IMAGES_DIR = os.path.join(os.path.dirname(__file__), "static", "images")
os.makedirs(IMAGES_DIR, exist_ok=True)

CATEGORIES = [
    {"label": "Văn Học",             "slug": "sach-van-hoc"},
    {"label": "Thiếu Nhi",           "slug": "sach-thieu-nhi"},
    {"label": "Kinh Tế",             "slug": "kinh-te"},
    {"label": "Tâm Lý - Kỹ Năng",   "slug": "tam-ly-ky-nang-song"},
    {"label": "Nuôi Dạy Con",        "slug": "sach-nuoi-day-con"},
    {"label": "Tiểu Sử - Hồi Ký",   "slug": "tieu-su-hoi-ky"},
    {"label": "Lịch Sử - Địa Lý",   "slug": "lich-su-dia-ly"},
    {"label": "Khoa Học Kỹ Thuật",  "slug": "khoa-hoc-ky-thuat"},
    {"label": "Sách Ngoại Văn",     "slug": "sach-ngoai-van-1"},
    {"label": "Manga - Comic",       "slug": "truyen-tranh"},
    {"label": "Tiểu Thuyết",         "slug": "tieu-thuyet"},
    {"label": "Kỹ Năng Sống",        "slug": "ky-nang-song"},
    {"label": "Marketing",           "slug": "marketing-ban-hang"},
    {"label": "Khởi Nghiệp",        "slug": "khoi-nghiep-lam-giau"},
    {"label": "Tiếng Anh",          "slug": "sach-hoc-tieng-anh"},
    {"label": "Tác Phẩm Kinh Điển", "slug": "tac-pham-kinh-dien"},
]

DATA_FILE    = os.path.join(os.path.dirname(__file__), "books_data.json")
_file_lock   = threading.Lock()
_status_lock = threading.Lock()

# Single source of truth — one dict, one lock
_status = {
    "running":         False,
    "mode":            None,
    "progress":        0,
    "total":           len(CATEGORIES),
    "current_cat":     "",
    "books_found":     0,
    "newly_added":     0,
    "imgs_downloaded": 0,
    "last_crawled":    None,
    "error":           None,
}


def get_status():
    with _status_lock:
        return dict(_status)


def _set(**kw):
    with _status_lock:
        _status.update(kw)


# ── image helpers ─────────────────────────────────────────────────────────────

def _img_local_path(url):
    ext = url.split("?")[0].rsplit(".", 1)[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "webp", "gif"):
        ext = "jpg"
    h = hashlib.md5(url.encode()).hexdigest()[:16]
    return f"{h}.{ext}", os.path.join(IMAGES_DIR, f"{h}.{ext}")


def download_image(url):
    if not url:
        return ""
    fname, fpath = _img_local_path(url)
    if os.path.exists(fpath) and os.path.getsize(fpath) > 500:
        return f"/static/images/{fname}"
    try:
        r = requests.get(url, headers=IMG_HEADERS, timeout=10, stream=True)
        if r.status_code == 200 and "image" in r.headers.get("Content-Type", ""):
            with open(fpath, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            with _status_lock:
                _status["imgs_downloaded"] += 1
            return f"/static/images/{fname}"
    except Exception:
        pass
    return ""


# ── atomic save + status finish ───────────────────────────────────────────────

def _save_progress(all_books):
    """Save mid-crawl snapshot — in_progress=True."""
    _write_file(all_books, in_progress=True)


def _finish(all_books, newly_added):
    """
    Atomically: write final file (in_progress=False) AND set running=False.
    Both happen under the file lock so there is no window where the file
    says finished but status still says running (or vice versa).
    """
    _write_file(all_books, in_progress=False)
    _set(
        running=False,
        current_cat="Xong!",
        last_crawled=datetime.now().isoformat(),
        books_found=len(all_books),
        newly_added=newly_added,
    )


def _write_file(all_books, in_progress):
    result = {
        "crawled_at": datetime.now().isoformat(),
        "total":      len(all_books),
        "in_progress": in_progress,
        "books":      list(all_books.values()),
    }
    with _file_lock:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)


# ── parse one product ─────────────────────────────────────────────────────────

def _parse_product(p, slug):
    variants = p.get("variants", [{}])
    v = variants[0] if variants else {}
    price         = float(v.get("price", 0))
    compare_price = float(v.get("compare_at_price") or 0)
    if compare_price and compare_price > price:
        discount_pct = round((compare_price - price) / compare_price * 100)
    else:
        discount_pct  = 0
        compare_price = 0
    images    = p.get("images", [])
    raw_img   = images[0].get("src", "").split("?")[0] if images else ""
    local_img = download_image(raw_img)
    publisher = p.get("vendor", "").strip()
    return {
        "id":            str(p.get("id", "")),
        "title":         p["title"],
        "publisher":     publisher,
        "handle":        p.get("handle", ""),
        "price":         price,
        "compare_price": compare_price,
        "discount_pct":  discount_pct,
        "image":         local_img,
        "image_src":     raw_img,
        "url":           f"https://cachep.vn/products/{p.get('handle', '')}",
        "tags":          p.get("tags", []),
        "category":      slug,
    }


def fetch_page(slug, page):
    url = f"https://cachep.vn/collections/{slug}/products.json?limit=30&page={page}"
    r = requests.get(url, headers=HEADERS, timeout=12)
    r.raise_for_status()
    return [_parse_product(p, slug) for p in r.json().get("products", []) if p.get("title")]


# ── MODE 1: crawl N more books ────────────────────────────────────────────────

def crawl_by_count(target_count):
    _set(running=True, mode="count", progress=0,
         total=len(CATEGORIES), books_found=0, newly_added=0,
         imgs_downloaded=0, current_cat="", error=None)

    existing    = load_data()
    all_books   = {b["id"]: b for b in existing.get("books", [])}
    seen_before = set(all_books.keys())
    newly_added = 0

    try:
        for i, cat in enumerate(CATEGORIES):
            if newly_added >= target_count:
                break
            _set(current_cat=cat["label"], progress=i)
            page = 1
            while newly_added < target_count:
                try:
                    books = fetch_page(cat["slug"], page)
                    if not books:
                        break
                    for b in books:
                        if b["id"] not in all_books:
                            all_books[b["id"]] = b
                            if b["id"] not in seen_before:
                                newly_added += 1
                        else:
                            all_books[b["id"]].update(b)
                    _set(books_found=len(all_books), newly_added=newly_added)
                    _save_progress(all_books)   # mid-crawl snapshot
                    page += 1
                    time.sleep(0.6)
                except Exception as e:
                    print(f"  Error {cat['slug']} p{page}: {e}")
                    break
    finally:
        # Always runs — even if an exception occurs
        _finish(all_books, newly_added)


# ── MODE 2: crawl all of one category ────────────────────────────────────────

def crawl_by_category(slug):
    cat_label = next((c["label"] for c in CATEGORIES if c["slug"] == slug), slug)
    _set(running=True, mode="category", progress=0, total=999,
         books_found=0, newly_added=0, imgs_downloaded=0,
         current_cat=cat_label, error=None)

    existing    = load_data()
    all_books   = {b["id"]: b for b in existing.get("books", [])}
    seen_before = set(all_books.keys())
    newly_added = 0
    page        = 1

    try:
        while True:
            _set(current_cat=f"{cat_label} (trang {page})", progress=page)
            try:
                books = fetch_page(slug, page)
                if not books:
                    break
                for b in books:
                    is_new = b["id"] not in all_books
                    all_books[b["id"]] = b
                    if is_new and b["id"] not in seen_before:
                        newly_added += 1
                _set(books_found=len(all_books), newly_added=newly_added)
                _save_progress(all_books)
                page += 1
                time.sleep(0.6)
            except Exception as e:
                print(f"  Error {slug} p{page}: {e}")
                break
    finally:
        _finish(all_books, newly_added)


# ── public API ────────────────────────────────────────────────────────────────

def start_crawl_thread(mode="count", count=120, category_slug=None):
    if _status["running"]:
        return False
    if mode == "category" and category_slug:
        t = threading.Thread(target=crawl_by_category, args=(category_slug,), daemon=True)
    else:
        t = threading.Thread(target=crawl_by_count, args=(count,), daemon=True)
    t.start()
    return True


def load_data():
    with _file_lock:
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {"books": [], "total": 0, "crawled_at": None, "in_progress": False}


def heal_stale_progress():
    """On startup: if file says in_progress=True but no crawl running, fix it."""
    with _file_lock:
        if not os.path.exists(DATA_FILE):
            return
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("in_progress"):
                data["in_progress"] = False
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print("[crawler] Healed stale in_progress=True on startup")
        except Exception:
            pass
