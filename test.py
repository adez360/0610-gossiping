import csv
from playwright.sync_api import sync_playwright

BOARD_URL = "https://www.ptt.cc/bbs/Gossiping/index.html"
BASE_URL = "https://www.ptt.cc"
OUTPUT_FILE = "ptt_gossiping.csv"

def clean_text(string: str) -> str:
    return " ".join(string.split())


def gossiping() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto("https://example.com")
        print(page.title())



if __name__ == "__main__":
    gossiping()
