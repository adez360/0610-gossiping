

import csv
from playwright.sync_api import sync_playwright

BOARD_URL   = "https://www.ptt.cc/bbs/Gossiping/index.html"
BASE_URL    = "https://www.ptt.cc"
OUTPUT_FILE = "ptt_gossiping.csv"


def clean_text(string: str) -> str:
    return " ".join(string.split())


def scrape_gossiping() -> list[dict[str, str]]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(BOARD_URL)

        try:
            page.wait_for_selector("button[name='yes']", timeout=3000)
            page.click("button[name='yes']")
        except Exception:
            pass 

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
            nrec   = clean_text(row.locator("div.nrec").inner_text())
            author = clean_text(row.locator("div.meta div.author").inner_text())
            date   = clean_text(row.locator("div.meta div.date").inner_text())

            articles.append(
                {
                    "nrec": nrec,
                    "title": title,
                    "author": author,
                    "date": date,
                    "url": href,
                }
            )

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
