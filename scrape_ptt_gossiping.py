import csv
from playwright.sync_api import sync_playwright, Page


BOARD_URL = "https://www.ptt.cc/bbs/Gossiping/index.html"
BASE_URL = "https://www.ptt.cc"
OUTPUT_FILE = "ptt_gossiping.csv"
NUM_PAGES = 3


def clean_text(string: str) -> str:
    return " ".join(string.split())


def parse_page(page: Page) -> list[dict[str, str]]:
    page.wait_for_selector("div.r-ent", timeout=15000)
    rows = page.locator("div.r-ent")
    articles: list[dict[str, str]] = []

    for i in range(rows.count()):
        row = rows.nth(i)
        link = row.locator("div.title a")

        if link.count() == 0:
            continue

        title = clean_text(link.inner_text())
        href = link.get_attribute("href")

        if href is None:
            continue

        if href.startswith("/"):
            href = BASE_URL + href
        nrec = clean_text(row.locator("div.nrec").inner_text())
        author = clean_text(row.locator("div.meta div.author").inner_text())
        date = clean_text(row.locator("div.meta div.date").inner_text())

        articles.append(
            {
                "nrec": nrec,
                "title": title,
                "author": author,
                "date": date,
                "url": href,
            }
        )

    return articles


def get_prev_page_url(page: Page) -> str | None:
    prev_link = page.locator("a.btn.wide", has_text="上頁")
    if prev_link.count() == 0:
        return None
    href = prev_link.first.get_attribute("href")
    if href is None:
        return None
    if href.startswith("/"):
        href = BASE_URL + href
    return href


def scrape_gossiping(num_pages: int = NUM_PAGES) -> list[dict[str, str]]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BOARD_URL)

        try:
            page.wait_for_selector("button[name='yes']", timeout=3000)
            page.click("button[name='yes']")
        except Exception:
            pass

        articles: list[dict[str, str]] = []

        for _ in range(num_pages):
            articles.extend(parse_page(page))

            prev_url = get_prev_page_url(page)
            if prev_url is None:
                break
            page.goto(prev_url)

        browser.close()
        return articles


def write_csv(articles: list[dict[str, str]]) -> None:
    fieldnames = ["nrec", "title", "author", "date", "url"]

    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(articles)


if __name__ == "__main__":
    articles = scrape_gossiping()
    write_csv(articles)
    print(f"Done: {len(articles)} articles from {NUM_PAGES} pages")
