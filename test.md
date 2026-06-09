# 單元 3：Playwright

## 1. 前言

前兩個單元處理的是比較單純的資料來源：

```
單元 1：公開 API，使用 requests 取得 JSON
單元 2：HTML 頁面，使用 requests + BeautifulSoup 解析
```

實務上還有另一種很常見的情境：資料在登入後台裡，而且網站前面有 Cloudflare、驗證碼、SSO、2FA 或其他安全驗證。這時如果直接讓 Playwright 開一個新的自動化瀏覽器，很可能會卡在安全驗證頁。

本章使用真實可測的公開後台：

```
網站：nopCommerce Admin Demo
登入頁：https://admin-demo.nopcommerce.com/login
帳號：admin@yourstore.com
密碼：admin
```

nopCommerce 是開源電商系統。它的 demo 後台有商品、訂單、客戶、報表等頁面。本章使用商品列表作為案例，目標是爬取商品名稱、SKU、價格、庫存與上架狀態。

如果直接用 Playwright 開啟 nopCommerce，可能會卡在 Cloudflare 驗證頁，甚至手動點選也過不去。這不是程式寫錯，也不是 Playwright 語法錯，而是網站的安全服務偵測到自動化瀏覽器。

這是爬蟲實務中很常遇到的情境。真實網站不一定讓自動化瀏覽器順利進入，特別是登入後台、會員中心、報表系統或電商管理台。遇到這種情況，更符合實務的方式是：

```
真人先處理安全驗證與登入
自動化程式再接手登入後的資料擷取
```

本章的流程是：

```
用一般 Chrome 開啟登入頁
→ 使用者手動通過 Cloudflare
→ 使用者手動登入 nopCommerce 後台
→ Playwright 連到這個已登入的 Chrome
→ 前往 Products 頁
→ 等待商品表格載入
→ 擷取資料
→ 輸出 products.csv
```

這不是繞過 Cloudflare。正確觀念是：人負責處理安全驗證與登入，程式負責登入後重複、結構化的資料擷取。

---

## 2. 背景知識

### 2.1 為什麼不能只用 requests

登入後台通常需要 session。使用者登入成功後，瀏覽器會保存 cookie 或其他瀏覽器狀態，後續請求才會被伺服器視為已登入。

如果只用 `requests` 直接打商品頁：

```
https://admin-demo.nopcommerce.com/Admin/Product/List
```

通常會遇到兩種結果：

```
結果 1：被導回登入頁
結果 2：被 Cloudflare 或安全驗證擋住
```

這不是 `requests` 壞掉，而是工具沒有帶著真實瀏覽器的登入狀態。

### 2.2 為什麼直接讓 Playwright 開瀏覽器也可能失敗

Playwright 可以開瀏覽器，但網站可能看得出這是自動化控制的瀏覽器。當網站使用 Cloudflare 這類安全服務時，新的自動化瀏覽器可能被要求驗證；有時即使手動勾選，也不一定放行。

本章實測出的狀況是：

```
一般 Chrome 可以通過 Cloudflare 並登入
Playwright 自己啟動的 Chrome 可能卡在 Cloudflare
```

遇到這種情況，比較可靠的做法是：

```
先用正常 Chrome 完成人類驗證與登入
再讓 Playwright 連到那個 Chrome 接手
```

### 2.3 什麼是 Chrome Remote Debugging

Chrome Remote Debugging 是 Chrome 內建的除錯介面。只要啟動 Chrome 時加上：

```bash
--remote-debugging-port=9222
```

Playwright 就可以透過 CDP（Chrome DevTools Protocol）連到這個 Chrome，並控制它的分頁。

本章提供啟動腳本，不需要每次手動輸入一長串參數。

### 2.4 什麼是 CDP

CDP 是 Chrome DevTools Protocol。Chrome DevTools 能檢查元素、看 Network、控制頁面，底層就是透過類似的協定跟瀏覽器溝通。

Playwright 的這行程式：

```python
browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
```

意思是：不要另外開新的 Playwright 瀏覽器，而是連到已經開好的 Chrome。

這是本章的核心。

---

## 3. 工具教學

### 3.1 Playwright 是什麼

Playwright 是瀏覽器自動化工具，由 Microsoft 開發，可以用 Python 控制 Chromium、Firefox、WebKit。它可以開網頁、點擊元素、填寫表單、等待資料載入、讀取文字、截圖與下載檔案。

Playwright 與 requests 的根本差異在於：requests 只發送 HTTP 請求，拿到原始 HTML；Playwright 控制一個真實的瀏覽器，頁面上的 JavaScript 會執行，動態渲染的內容也看得到。

安裝：

```bash
pip install playwright
playwright install chromium
```

第一行安裝 Python 套件，第二行下載 Playwright 管理的 Chromium 瀏覽器。

### 3.2 為什麼使用 Playwright

| 情境 | 工具 | 原因 |
| --- | --- | --- |
| 公開 JSON API | `requests` | 直接、快速 |
| HTML 原始碼已有資料 | `requests` + `BeautifulSoup` | 不需要瀏覽器 |
| 登入後台、JS 動態介面 | `Playwright` | 需要瀏覽器狀態與完整 DOM |
| Cloudflare 擋自動化瀏覽器 | Chrome + CDP + Playwright | 讓人先通過驗證，再由程式接手 |

### 3.3 Browser / Context / Page 三層架構

Playwright 操作的物件分三層，理解這個架構是使用 Playwright 的基礎：

```
Browser（瀏覽器）
  └── Context（瀏覽器分組，類似不同的使用者設定檔）
        └── Page（分頁，操作的主要對象）
```

**Browser**：整個瀏覽器程序。可以是 Playwright 自己啟動的（`launch()`），或是連到外部已開啟的瀏覽器（`connect_over_cdp()`）。

**Context**：隔離的瀏覽環境，擁有各自的 Cookie、LocalStorage 與快取。相當於「無痕視窗」。同一個 Browser 可以有多個 Context，互不影響。

**Page**：一個分頁。所有操作（前往網址、點擊、讀取文字）都是在 Page 上執行。

程式碼對應：

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    # Browser：啟動新的 Chromium 瀏覽器（headless 模式，不顯示視窗）
    browser = p.chromium.launch()

    # Context：建立一個隔離的瀏覽環境
    context = browser.new_context()

    # Page：開一個新分頁
    page = context.new_page()

    page.goto("https://example.com")
    print(page.title())

    browser.close()
```

本章使用的是 `connect_over_cdp()`（連到已開啟的 Chrome），而不是 `launch()`（開新瀏覽器），原因與差異詳見 3.8 節。

### 3.4 sync_playwright() 的用法

Playwright 使用 `with sync_playwright() as p:` 的 context manager 語法。

`with` 的作用是確保程式結束（包含出錯時）都會自動關閉瀏覽器，不會留下殭屍程序。

```python
from playwright.sync_api import sync_playwright

# 正確寫法：使用 with，確保瀏覽器一定會被關閉
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("https://example.com")
    # ... 操作頁面
# 離開 with 區塊後，瀏覽器自動關閉
```

`p.chromium` 是 Chromium 瀏覽器的啟動器，`p.firefox` 與 `p.webkit` 分別對應 Firefox 與 Safari 引擎。

### 3.5 Locator：找到頁面上的元素

Playwright 用 **Locator** 定位頁面元素。Locator 不是立刻去找元素，而是描述「要找什麼」，在真正執行操作時才定位。

```python
# 建立 Locator（此時還沒有真正找元素）
button = page.locator("button.submit")

# 執行操作時才定位元素
button.click()
```

**常用 Selector 語法：**

| Selector | 說明 | 範例 |
| --- | --- | --- |
| `tag` | HTML 標籤 | `"table"` |
| `.class` | CSS class | `".product-name"` |
| `#id` | HTML id | `"#products-grid"` |
| `tag.class` | 標籤 + class | `"tr.product-row"` |
| `parent child` | 後代選擇器 | `"#products-grid tbody tr"` |
| `[attr=value]` | 屬性值 | `"input[name='email']"` |
| `:nth-child(n)` | 第 n 個子元素 | `"tr:nth-child(2)"` |

**Locator 常用方法：**

```python
# 取得元素的文字內容
text = page.locator("#title").inner_text()

# 取得元素的 HTML 屬性值
href = page.locator("a.edit").get_attribute("href")

# 計算符合 selector 的元素數量
count = page.locator("tbody tr").count()

# 取得第 n 個符合的元素（從 0 開始）
first_row = page.locator("tbody tr").nth(0)

# 對多個元素逐一處理
rows = page.locator("tbody tr")
for i in range(rows.count()):
    row = rows.nth(i)
    print(row.inner_text())
```

**Locator 可以鏈式查詢（在元素內繼續找子元素）：**

```python
# 先找到 tr，再在 tr 內找所有 td
row = page.locator("tbody tr").nth(0)
cells = row.locator("td")
first_cell_text = cells.nth(0).inner_text()
```

### 3.6 常用頁面操作

**前往網址：**

```python
page.goto("https://example.com")
# goto() 會等到頁面的 load 事件觸發才繼續
```

**點擊元素：**

```python
page.click("#submit-button")
# 或使用 Locator
page.locator("#submit-button").click()
```

**填寫輸入欄位：**

```python
page.fill("#email", "admin@example.com")
page.fill("#password", "secret")
# fill() 會先清空欄位，再輸入文字
```

**截圖（除錯很好用）：**

```python
page.screenshot(path="debug.png")
# 截取目前整個頁面的截圖，儲存成圖檔
```

**取得頁面標題：**

```python
title = page.title()
print(title)
```

**取得目前 URL：**

```python
url = page.url
```

### 3.7 等待機制

這是 Playwright 最重要的概念之一。頁面資料通常是 JavaScript 非同步載入的。`page.goto()` 只代表頁面的初始 HTML 載入完成，不代表動態資料（例如表格資料）已經出現。

若不等待直接操作，常見錯誤是：

```
頁面剛載入完成
→ 程式立刻去找表格
→ 表格還在 loading，找不到元素
→ TimeoutError 或抓到空資料
```

**等待特定元素出現：**

```python
# 等到 selector 對應的元素出現在 DOM 中，才繼續執行
# timeout 單位是毫秒，預設 30000（30 秒）
page.wait_for_selector("#products-grid tbody tr", timeout=30000)
```

**等待頁面載入狀態：**

```python
page.wait_for_load_state("networkidle")
# networkidle：等到網路請求停止 500ms 以上
# domcontentloaded：等到 DOM 建立完成
# load：等到所有資源（圖片、CSS）載入完成
```

**應該用哪種等待方式？**

- 有明確的目標元素（例如表格列）→ 用 `wait_for_selector()`，最精準
- 頁面有複雜的非同步載入，沒有明確元素可等 → 用 `wait_for_load_state("networkidle")`

### 3.8 launch() vs connect_over_cdp()

本章同時用到兩種啟動方式，差異如下：

| 方式 | 說明 | 適用情境 |
| --- | --- | --- |
| `p.chromium.launch()` | Playwright 自己開新瀏覽器 | 網站不擋自動化瀏覽器，或只需爬公開頁面 |
| `p.chromium.connect_over_cdp(url)` | 連到外部已開啟的 Chrome | 需要人工登入、通過 Cloudflare、使用已存在的登入狀態 |

`connect_over_cdp()` 的前提是目標 Chrome 必須用 `--remote-debugging-port` 啟動，開啟 CDP 連接埠。

```python
# 啟動新瀏覽器
browser = p.chromium.launch(headless=False)  # headless=False 讓視窗顯示出來

# 連到已開啟的 Chrome
browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
```

### 3.9 最小可執行範例：連到已開啟的 Chrome

先用 remote debugging 啟動 Chrome。

**macOS：**

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/test-chrome
```

**Windows（命令提示字元 cmd）：**

```bash
"C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --remote-debugging-port=9222 ^
  --user-data-dir=C:\temp\test-chrome
```

**Windows（PowerShell）：**

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-port=9222 `
  --user-data-dir=C:\temp\test-chrome
```

Chrome 路徑若不存在，請確認安裝位置。Chrome 也可能裝在 `C:\Program Files (x86)\Google\Chrome\Application\chrome.exe`。

再用 Playwright 連進去，前往頁面並印出標題：

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    # 連到外部 Chrome，不是自己開新瀏覽器
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")

    # 取得該 Chrome 目前的 context（使用者設定檔）
    context = browser.contexts[0]

    # 開新分頁
    page = context.new_page()

    page.goto("https://example.com")
    print(page.title())  # 印出頁面標題

    # connect_over_cdp 的情況下，不 close browser
    # 因為這個 Chrome 是使用者手動開的，不應該由程式關掉
```

預期結果：

```
終端機印出 "Example Domain"
Chrome 視窗顯示 example.com 頁面
```

| 程式 | 說明 |
| --- | --- |
| `connect_over_cdp("http://127.0.0.1:9222")` | 連到已用 remote debugging 開啟的 Chrome |
| `browser.contexts[0]` | 取得 Chrome 目前的瀏覽器 context（使用者的登入狀態在這裡） |
| `context.new_page()` | 在該 Chrome 中開新分頁 |
| `page.goto(url)` | 控制分頁前往指定網址 |

### 3.10 完整範例：在 python.org 搜尋新聞

學完前面的基礎後，用一個完整的例子把所有操作串起來：前往 python.org、填寫搜尋欄、等待結果、擷取標題與連結。

這個範例使用 `launch()` 開新瀏覽器，適合不需要登入的公開頁面。

```python
# search_python_news.py

from playwright.sync_api import sync_playwright

SEARCH_URL = "https://www.python.org/search/"
KEYWORD    = "release"

def search_python_news(keyword):
    with sync_playwright() as p:
        # headless=False 讓瀏覽器視窗顯示出來，方便觀察每一步的執行過程
        # 確認流程正確後可改成 headless=True，讓程式在背景安靜執行
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        # 1. 前往搜尋頁
        page.goto(SEARCH_URL)

        # 2. 填入關鍵字
        # fill() 會先清空欄位再輸入，比 type() 更可靠
        page.fill("input[name='q']", keyword)

        # 3. 按 Enter 送出搜尋
        page.press("input[name='q']", "Enter")

        # 4. 等待結果列表出現
        # 搜尋送出後頁面會重新載入，直接讀取會抓到空資料
        # wait_for_selector 確保結果出現後再繼續
        page.wait_for_selector("ul.list-recent-events li", timeout=15000)

        # 5. 取得所有結果列
        result_items = page.locator("ul.list-recent-events li")
        count = result_items.count()
        print(f"找到{count} 筆結果")

        # 6. 逐一擷取標題與連結
        results = []
        for i in range(min(count, 10)):  # 最多取前 10 筆
            item = result_items.nth(i)
            link  = item.locator("a").first
            title = link.inner_text().strip()
            href  = link.get_attribute("href")

            # href 可能是相對路徑，補上 domain 變成完整 URL
            if href and href.startswith("/"):
                href = "https://www.python.org" + href

            results.append({"title": title, "url": href})

        browser.close()
        return results

if __name__ == "__main__":
    results = search_python_news(KEYWORD)
    for i, r in enumerate(results, start=1):
        print(f"{i:2}.{r['title']}")
        print(f"{r['url']}")
```

**執行：**

```bash
python search_python_news.py
```

**預期輸出：**

```
找到 10 筆結果
 1. Python 3.13.3, 3.12.10, 3.11.12, 3.10.17, and 3.9.22 are now available
    https://www.python.org/blogs/PSF/...
 2. Python 3.14.0 alpha 7 is now available
    https://www.python.org/blogs/PSF/...
...
```

**這個範例涵蓋的操作：**

| 程式 | 說明 |
| --- | --- |
| `launch(headless=False)` | 開啟顯示視窗的瀏覽器，方便除錯 |
| `page.goto(url)` | 前往指定網址 |
| `page.fill(selector, text)` | 清空欄位並填入文字 |
| `page.press(selector, key)` | 在元素上按下指定按鍵 |
| `page.wait_for_selector(selector)` | 等到元素出現才繼續 |
| `locator.count()` | 取得符合 selector 的元素數量 |
| `locator.nth(i)` | 取得第 i 個符合的元素 |
| `locator.inner_text()` | 取得元素的文字內容 |
| `locator.get_attribute("href")` | 取得元素的屬性值 |

---

## 4. 專案結構

本章會建立以下檔案：

```
unit-03-solution/
├── start_chrome_debug.sh               # 啟動腳本（macOS / Linux）
├── start_chrome_debug.bat              # 啟動腳本（Windows）
├── scrape_products_from_chrome.py      # 連到已登入 Chrome 並爬商品列表
├── products.csv                        # 爬取後產生的商品 CSV
└── chrome-debug-profile/               # Chrome 使用者資料（含登入狀態，不提交版控）
```

---

## 5. 操作流程：先用 Chrome 完成登入

### 5.1 啟動可被 Playwright 連線的 Chrome

進入範例資料夾，依作業系統執行對應的啟動腳本。

---

**macOS / Linux：**

```bash
cd unit-03-solution
./start_chrome_debug.sh
```

`start_chrome_debug.sh` 內容如下：

```bash
#!/usr/bin/env bash
set -euo pipefail

PROFILE_DIR="${PWD}/chrome-debug-profile"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

"${CHROME}" \
  --remote-debugging-port=9222 \
  --user-data-dir="${PROFILE_DIR}" \
  --no-first-run \
  --no-default-browser-check \
  "https://admin-demo.nopcommerce.com/login" \
  2> chrome-debug.log
```

---

**Windows：**

```bash
cd unit-03-solution
start_chrome_debug.bat
```

`start_chrome_debug.bat` 內容如下：

```
@echo off
set PROFILE_DIR=%~dp0chrome-debug-profile
set CHROME="C:\Program Files\Google\Chrome\Application\chrome.exe"

%CHROME% ^
  --remote-debugging-port=9222 ^
  --user-data-dir="%PROFILE_DIR%" ^
  --no-first-run ^
  --no-default-browser-check ^
  "https://admin-demo.nopcommerce.com/login"
```

若 Chrome 安裝路徑不同（例如 `Program Files (x86)`），請修改 `set CHROME=` 那一行。

---

**重要參數說明：**

| 參數 | 用途 |
| --- | --- |
| `--remote-debugging-port=9222` | 開啟 CDP 連線入口，讓 Playwright 可以連進來 |
| `--user-data-dir=chrome-debug-profile` | 使用固定 profile，保留登入與驗證狀態 |
| `--no-first-run` | 避免 Chrome 第一次啟動提示干擾 |
| `2> chrome-debug.log`（Mac） | 把 Chrome log 收到檔案，避免終端機被訊息洗版 |

### 5.2 手動通過 Cloudflare 與登入

Chrome 開啟後，在瀏覽器中操作：

步驟 1：如果看到 Cloudflare「驗證您是人類」，手動勾選。

步驟 2：進入 nopCommerce 登入頁。

步驟 3：輸入帳密：

```
Email: admin@yourstore.com
Password: admin
```

步驟 4：登入後確認看到後台 Dashboard。

步驟 5：不要關閉 Chrome。

這一步必須由人完成，因為 Cloudflare 與登入驗證是安全流程。本章不教繞過安全驗證。

---

## 6. 手動偵察商品列表

寫爬蟲前先確認資料位置。

步驟 1：在已登入的 Chrome 中打開：

```
https://admin-demo.nopcommerce.com/Admin/Product/List
```

步驟 2：確認頁面出現商品搜尋區與商品表格。

步驟 3：按 `F12` 或 `Cmd + Option + I` 開啟 DevTools。

步驟 4：使用 Elements 工具點選商品表格中的資料列。

步驟 5：確認商品表格的 selector：

```
#products-grid tbody tr
```

selector 拆解：

| 片段 | 意義 |
| --- | --- |
| `#products-grid` | id 為 `products-grid` 的商品表格 |
| `tbody` | 表格資料列所在區域 |
| `tr` | 每一筆商品資料列 |

本章要擷取的欄位：

| 欄位 | 來源 |
| --- | --- |
| `name` | 商品名稱 |
| `sku` | SKU |
| `price` | 價格 |
| `stock_quantity` | 庫存數量 |
| `published` | 是否上架 |

---

## 7. 程式實作：連到 Chrome 並爬商品

### 7.1 連到 Chrome

`scrape_products_from_chrome.py` 的第一個重點是連到剛剛開好的 Chrome。

```python
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9222"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP_URL)
    context = browser.contexts[0]
```

如果這裡失敗，通常代表 `start_chrome_debug.sh` 沒有執行，或 Chrome 已經被關掉。

### 7.2 取得 nopCommerce 分頁

Chrome 裡可能已經有 nopCommerce 分頁，也可能沒有。以下函式會先找既有分頁，找不到才開新分頁。

```python
def get_page(context):
    for page in context.pages:
        if "admin-demo.nopcommerce.com" in page.url:
            return page
    return context.new_page()
```

這樣寫的理由是：使用者可能已經在 Chrome 裡登入並停在 Dashboard。程式應該接手現有頁面，而不是假設一定要開新頁。

### 7.3 等待使用者確認已登入

```python
print("請先確認這個 Chrome 已經通過 Cloudflare 並登入 nopCommerce 後台。")
input("確認登入完成後，回到終端機按 Enter 開始爬商品...")
```

這個 `input()` 是人機協作的接口。程式不負責登入，只在使用者確認登入完成後接手資料擷取。

### 7.4 前往商品頁並等待表格

```python
PRODUCTS_URL = "https://admin-demo.nopcommerce.com/Admin/Product/List"

def scrape_products(page):
    page.goto(PRODUCTS_URL)
    page.wait_for_selector("#products-grid tbody tr", timeout=30000)
```

`page.goto()` 只代表瀏覽器開始前往頁面，不代表商品資料已經渲染完成。因此要用 `wait_for_selector()` 等到表格列出現。

若沒有等待，常見錯誤是：

```
頁面還在載入
→ 程式立刻讀取表格
→ 找不到資料或只抓到空表格
```

### 7.5 擷取表格欄位

```python
rows = page.locator("#products-grid tbody tr")
products = []

for index in range(rows.count()):
    row = rows.nth(index)
    cells = row.locator("td")

    products.append(
        {
            "name": clean_text(cells.nth(2).inner_text()),
            "sku": clean_text(cells.nth(3).inner_text()),
            "price": clean_text(cells.nth(4).inner_text()),
            "stock_quantity": clean_text(cells.nth(5).inner_text()),
            "published": clean_text(cells.nth(6).inner_text()),
        }
    )
```

欄位從 `cells.nth(2)` 開始，是因為表格前面有 checkbox、圖片或其他操作欄。這種欄位位置不是猜出來的，而是從 DevTools 偵察得到的。

### 7.6 清理文字

```python
def clean_text(value):
    return " ".join(value.split())
```

後台表格中的文字常有換行、Tab 或多餘空白。`split()` 會用所有空白切開字串，再用單一空白接回去，可以得到乾淨欄位。

### 7.7 輸出 CSV

```python
def write_csv(products):
    fieldnames = ["name", "sku", "price", "stock_quantity", "published"]

    with OUTPUT_FILE.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(products)
```

使用 `DictWriter` 的理由是資料已經整理成 dictionary。`fieldnames` 可以固定欄位順序，方便後續分析。

---

## 8. 完整執行

### 8.1 第一個終端機：啟動 Chrome

**macOS / Linux：**

```bash
cd unit-03-solution
./start_chrome_debug.sh
```

**Windows：**

```bash
cd unit-03-solution
start_chrome_debug.bat
```

在開出的 Chrome 裡：

```
通過 Cloudflare
→ 登入 admin@yourstore.com / admin
→ 確認看到 Dashboard
→ 不要關 Chrome
```

### 8.2 第二個終端機：執行爬蟲

```bash
cd unit-03-solution
python scrape_products_from_chrome.py
```

終端機會出現：

```
請先確認這個 Chrome 已經通過 Cloudflare 並登入 nopCommerce 後台。
確認登入完成後，回到終端機按 Enter 開始爬商品...
```

確認 Chrome 已登入後，按 Enter。

成功時會看到：

```
取得 15 筆商品資料
已輸出到 products.csv
```

檢查輸出：

```bash
head products.csv
```

預期格式：

```
name,sku,price,stock_quantity,published
Apple MacBook Pro 13-inch,AP_MBP_13,$1,800.00,100,True
...
```

實際筆數與商品名稱可能因 demo 站資料更新而不同。判斷成功與否，應看是否成功輸出欄位正確的 CSV，而不是硬背固定資料。

---

## 9. 人機協作的爬蟲思維

本章的流程體現了一個在實務中很常見的判斷：**不是所有事情都適合自動化**。

### 9.1 自動化的邊界

Playwright 可以自動開瀏覽器、填表單、點按鈕，但並非所有操作都值得自動化。以登入流程為例：

| 登入類型 | 自動化難度 | 建議做法 |
| --- | --- | --- |
| 帳號密碼，沒有額外驗證 | 低 | 可以讓 Playwright 自動登入 |
| 帳號密碼 + 驗證碼 | 高 | 考慮人工登入後由程式接手 |
| SSO / Google 登入 | 高 | 人工登入後儲存 session，程式接手 |
| 2FA / OTP | 極高 | 人工登入，程式接手資料擷取 |
| Cloudflare 安全驗證 | 不可預測 | 人工通過驗證，程式接手 |

當自動化登入的成本（開發時間、維護難度、失敗風險）高於人工登入的成本時，讓人完成登入、程式接手資料擷取，是合理的工程取捨。

### 9.2 這個流程適用的真實情境

以下情境都可以用本章的 Chrome + CDP + Playwright 流程處理：

- 公司內部後台（ERP、CRM、報表系統）
- 需要 2FA 的服務（Google Workspace、企業 SSO）
- Cloudflare 或 Bot 防護擋住自動化瀏覽器的網站
- 需要人工審核才能進入的頁面

共同點是：**身份驗證由人完成，重複性的資料擷取由程式完成**。

---

## 10. 補充：storage_state 與 persistent profile

### 10.1 storage_state 適合什麼情境

Playwright 也可以用 `storage_state()` 保存登入狀態：

```python
context.storage_state(path="auth.json")
```

下次載入：

```python
context = browser.new_context(storage_state="auth.json")
```

這適合沒有 Cloudflare 或安全驗證比較單純的網站。

### 10.2 auth.json 的限制

`storage_state` 的做法有一個前提：**Playwright 自己啟動的瀏覽器必須能完成登入**。

若網站有 Cloudflare 保護，Playwright 新開的瀏覽器在第一步就可能被擋住，根本無法取得 auth.json。遇到這種情況，`connect_over_cdp` 是更可靠的起點——先用一般 Chrome 完成登入，再讓 Playwright 接手。

### 10.3 三種方案比較

| 方案 | 適用情境 | 本章定位 |
| --- | --- | --- |
| `storage_state(auth.json)` | 登入流程單純、沒有 Cloudflare | 補充 |
| `launch_persistent_context()` | 想保存 Playwright 啟動的瀏覽器 profile | 補充 |
| `connect_over_cdp()` | 一般 Chrome 能登入，Playwright 新瀏覽器被擋 | 本章使用 |

---

## 11. 練習題

### 題目：用 Playwright 爬 PTT 八卦版文章列表

PTT 八卦版（Gossiping）在進入前會顯示年齡確認頁。這個頁面是 HTML 表單，需要點擊「已滿 18 歲」按鈕才能進入。這是一個很適合練習 Playwright 的情境——requests 無法點擊按鈕，但 Playwright 可以。

目標頁面：`https://www.ptt.cc/bbs/Gossiping/index.html`

**需求：**

1. 用 Playwright 開啟 PTT 八卦版
2. 若出現年齡確認頁，自動點擊「我已滿 18 歲」按鈕
3. 等待文章列表出現
4. 擷取文章列表的以下欄位：
    - 推文數（`nrec`）
    - 標題（`title`）
    - 作者（`author`）
    - 日期（`date`）
    - 文章連結（`url`）
5. 輸出成 `ptt_gossiping.csv`

**交付項目：**

- `scrape_ptt_gossiping.py`
- `ptt_gossiping.csv`（至少包含一頁的文章資料）

---

**解題步驟提示：**

**步驟 1：先用 DevTools 偵察**

在瀏覽器中開啟 `https://www.ptt.cc/bbs/Gossiping/index.html`，觀察：

- 年齡確認頁的按鈕 selector 是什麼？
- 文章列表每一列的 selector 是什麼？
- 各欄位（推文數、標題、作者、日期）在哪個子元素裡？

**步驟 2：處理年齡確認頁**

年齡確認按鈕出現在一個獨立的頁面。處理方式：

```python
# 等一下確認按鈕，若出現就點擊，若沒有就繼續
try:
    page.wait_for_selector("__確認按鈕的selector__", timeout=3000)
    page.click("__確認按鈕的selector__")
except:
    pass  # 已進入文章列表頁，不需要點擊
```

**步驟 3：等待文章列表出現**

```python
page.wait_for_selector("__文章列的selector__")
```

**步驟 4：擷取每一列資料**

```python
rows = page.locator("__文章列的selector__")
for i in range(rows.count()):
    row = rows.nth(i)
    # 在 row 內找各個欄位
    nrec  = row.locator("__推文數selector__").inner_text()
    title = row.locator("__標題selector__").inner_text()
    # ...
```

**步驟 5：輸出 CSV**

```python
import csv

with open("ptt_gossiping.csv", "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["nrec", "title", "author", "date", "url"])
    writer.writeheader()
    writer.writerows(articles)
```

---

**常見問題：**

| 問題 | 原因 | 解法 |
| --- | --- | --- |
| 程式一直停在年齡確認頁 | 沒有點擊確認按鈕 | 確認按鈕的 selector 是否正確 |
| 擷取到空標題 | 部分列是置頂文或分隔列 | 加入判斷，過濾空值或特定 class |
| 文章連結是相對路徑 | `href` 只有 `/bbs/Gossiping/M.xxx.html` | 補上 `https://www.ptt.cc` |
| CSV 出現亂碼 | 編碼問題 | 確認 `open()` 使用 `encoding="utf-8"` |

---

## 12. 常見錯誤與排解

| 問題 | 原因 | 解法 |
| --- | --- | --- |
| `ModuleNotFoundError: No module named 'playwright'` | 尚未安裝 Playwright | 執行 `pip install playwright` |
| `connect ECONNREFUSED 127.0.0.1:9222` | Chrome 沒有用 debug 模式啟動 | macOS 執行 `./start_chrome_debug.sh`，Windows 執行 `start_chrome_debug.bat` |
| Windows 執行 `.bat` 出現「找不到路徑」 | Chrome 安裝路徑與 bat 檔不同 | 確認 Chrome 位置，修改 bat 檔中的 `set CHROME=` |
| 第二個終端機找不到已登入狀態 | 連錯 Chrome 或 debug Chrome 已關閉 | 確認不要關掉第一個終端機開出的 Chrome |
| 一直停在 Cloudflare | 還沒用一般 Chrome 通過驗證 | 在第一個 Chrome 視窗手動完成驗證 |
| 按 Enter 後被導回登入頁 | 尚未登入或登入 session 失效 | 回 Chrome 手動登入後再執行爬蟲 |
| `TimeoutError` 等不到 `#products-grid tbody tr` | 未登入、頁面載入慢、selector 改版 | 確認目前能手動看到 Products 表格，再檢查 selector |
| CSV 只有標題沒有資料 | 表格沒有資料或 rows selector 錯 | 印出 `rows.count()` 並用 DevTools 重新確認 selector |
| 欄位內容錯位 | 表格欄位順序改變 | 重新確認每個 `td` 對應欄位 |
| 第一個終端機出現 Chrome updater log | Chrome 自己的背景訊息 | 腳本已把錯誤輸出寫到 `chrome-debug.log`，可忽略 |

---

## 13. 小結

本章完成的不是玩具登入頁，而是真實後台常見流程：

```
Cloudflare / 安全驗證
→ 人工登入
→ Playwright 連到已登入 Chrome
→ 進入後台商品頁
→ 等待表格
→ 擷取欄位
→ 輸出 CSV
```

最重要的觀念是：

```
不是所有登入都該自動化
不是所有安全驗證都該繞過
人處理身份驗證
程式處理重複資料擷取
```

這個流程很適合延伸到公司內部後台、CRM、ERP、報表系統、電商管理台。下一步可以加入分頁、搜尋條件、商品詳情頁與資料庫儲存，逐步變成完整的後台資料擷取專案。