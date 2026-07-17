import os, time, re, hashlib, random
from urllib.parse import urljoin
from dataclasses import dataclass
from bs4 import BeautifulSoup
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# ---------- CONFIG ----------
BASE = "https://buktex.com"

ROOT_CATEGORIES = [
    "https://buktex.com/k-p-b",
    "https://buktex.com/prostini",
    "https://buktex.com/pledi",
    "https://buktex.com/skatertini"
]

KNOWN_GROUPS = {
    "https://buktex.com/simeyka": {"id": 1001, "name": "Сімейка"},
    "https://buktex.com/polikoton-odnospalniy": {"id": 1002, "name": "Полікотон односпальний"},
    "https://buktex.com/polikoton-dvospalniy": {"id": 1003, "name": "Полікотон двоспальний"},
    "https://buktex.com/polikoton-ievro-rozmir": {"id": 1004, "name": "Полікотон євро розмір"},
    "https://buktex.com/gold-pivtorachka-dityacha": {"id": 1005, "name": "Gold півторачка дитяча"},
    "https://buktex.com/koton-odnospalniy": {"id": 1006, "name": "Котон односпальний"},
    "https://buktex.com/koton-dvospalniy": {"id": 1007, "name": "Котон двоспальний"},
    "https://buktex.com/koton-ievro-rozmir": {"id": 1008, "name": "Котон євро розмір"},
    "https://buktex.com/polisatin-flanel": {"id": 1009, "name": "Полісатин фланель"},
    "https://buktex.com/polisatin-pivtorachka": {"id": 1010, "name": "Полісатин півторачка"},
    "https://buktex.com/polisatin-flanel-ievro": {"id": 1011, "name": "Полісатин фланель євро"},
}

OUTPUT_DIR  = os.path.dirname(os.path.abspath(__file__))
OUTPUT_NAME = "feed.xml"

@dataclass
class Product:
    url: str
    name: str | None
    description: str | None
    sku: str | None
    availability_pm: str | None
    price_uah: str | None
    images: list[str]

# ---------- Selenium Setup ----------
def make_driver():
    print("[INFO] Инициализация скрытого браузера с защитой от бана...")
    opts = Options()
    opts.add_argument("--headless=new") 
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    opts.add_argument('--disable-gpu')
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--log-level=3")
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return driver

# ---------- Parsing Logic ----------
def discover_categories(driver):
    print("[INFO] Поиск всех категорий на сайте...")
    discovered = {}
    discovered.update(KNOWN_GROUPS)
    
    subcat_links = set()
    for root in ROOT_CATEGORIES:
        driver.get(root)
        time.sleep(random.uniform(2.0, 3.0))
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)
        
        soup = BeautifulSoup(driver.page_source, "lxml")
        for a in soup.select("a"):
            href = a.get("href")
            if not href: continue
            
            if href.startswith("/"):
                href = urljoin(BASE, href)
                
            if href.startswith(BASE):
                if any(x in href for x in ["/shop/", "/cart", "/wishlist", "/compare", "/account", "/optova-spivpracya", "tel:", "mailto:", "viber:"]):
                    continue
                href = href.split('#')[0].split('?')[0]
                
                if href != BASE and href != BASE + "/" and href not in ROOT_CATEGORIES:
                    subcat_links.add(href)
                    
    for link in subcat_links:
        if link not in discovered:
            driver.get(link)
            time.sleep(random.uniform(1.5, 2.5))
            title = driver.title if driver.title else ""
            name = title.replace("БУКОВИНСЬКИЙ ТЕКСТИЛЬ", "").strip(" |")
            if not name:
                name = link.strip("/").split("/")[-1]
                
            gid = 100000 + int(hashlib.md5(link.encode()).hexdigest()[:6], 16)
            discovered[link] = {"id": gid, "name": name}
            print(f"      Найдена новая категория: {name} ({link})")
            
    return discovered

def get_product_links(driver, cat_url):
    print(f"[CAT] Категория: {cat_url}")
    driver.get(cat_url)
    time.sleep(random.uniform(2.0, 4.0))
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(random.uniform(1.5, 3.0))

    links = set()
    soup = BeautifulSoup(driver.page_source, "lxml")
    items = soup.select('a[href*="/shop/"]')
    for item in items:
        href = item.get("href")
        if href and not any(x in href for x in ["/cart", "/wishlist", "/compare", "/account"]):
            links.add(urljoin(BASE, href))
    
    print(f"      Найдено ссылок: {len(links)}")
    return list(links)

def parse_product_page(driver, url):
    driver.get(url)
    time.sleep(random.uniform(1.5, 2.5))
    soup = BeautifulSoup(driver.page_source, "lxml")

    name = soup.find("h1").get_text(strip=True) if soup.find("h1") else "Без назви"
    
    sku_el = soup.select_one(".js-sku-text")
    sku = sku_el.get_text(strip=True).replace("Артикул:", "").strip() if sku_el else ""

    price_el = soup.select_one('[data-test="price"]')
    price = "".join(re.findall(r'\d+', price_el.get_text())) if price_el else "0"

    desc_el = soup.select_one('[data-component="product-description-tab-content"]')
    description = str(desc_el) if desc_el else ""

    status = soup.select_one('[role="status"]')
    availability = "+" if status and "наявност" in status.get_text().lower() else "-"

    imgs = []
    main_img = soup.select_one('img[data-product-illustration="true"]')
    if main_img and main_img.get("src"):
        imgs.append(urljoin(BASE, main_img.get("src")))
    
    others = soup.select('[data-product-thumbnail-full]')
    for img in others:
        img_url = urljoin(BASE, img.get("data-product-thumbnail-full"))
        if img_url not in imgs:
            imgs.append(img_url)

    return Product(url=url, name=name, description=description, sku=sku, 
                   availability_pm=availability, price_uah=price, images=imgs)

# ---------- XML Generation ----------
def escape_xml(text):
    if not text: return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")

def generate_xml(categories, products):
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<yml_catalog date="{date_str}">',
        '  <shop>',
        '    <name>Buktex</name>',
        '    <company>Buktex</company>',
        '    <url>https://buktex.com/</url>',
        '    <currencies>',
        '      <currency id="UAH" rate="1"/>',
        '    </currencies>',
        '    <categories>'
    ]
    
    # Categories
    for gid, gname in categories.items():
        xml.append(f'      <category id="{gid}">{escape_xml(gname)}</category>')
    xml.append('    </categories>')
    
    # Offers
    xml.append('    <offers>')
    for p in products:
        available_str = "true" if p['availability'] == "+" else "false"
        xml.append(f'      <offer id="{p["id"]}" available="{available_str}">')
        xml.append(f'        <url>{escape_xml(p["url"])}</url>')
        xml.append(f'        <price>{p["price"]}</price>')
        xml.append('        <currencyId>UAH</currencyId>')
        xml.append(f'        <categoryId>{p["group_id"]}</categoryId>')
        
        for img in p['images']:
            xml.append(f'        <picture>{escape_xml(img)}</picture>')
            
        xml.append(f'        <name>{escape_xml(p["name"])}</name>')
        
        if p["sku"]:
            xml.append(f'        <vendorCode>{escape_xml(p["sku"])}</vendorCode>')
            
        xml.append(f'        <description><![CDATA[{p["description"]}]]></description>')
        xml.append('      </offer>')
        
    xml.append('    </offers>')
    xml.append('  </shop>')
    xml.append('</yml_catalog>')
    
    return "\n".join(xml)

def main():
    driver = make_driver()
    products_data = []
    used_groups = {} 

    try:
        all_categories = discover_categories(driver)
        
        for cat_url, info in all_categories.items():
            links = get_product_links(driver, cat_url)
            gid = info["id"]
            gname = info["name"]
            used_groups[gid] = gname
            
            for link in links:
                try:
                    print(f"      Парсим: {link}")
                    p = parse_product_page(driver, link)
                    
                    product_id = f"{gid}-{p.sku if p.sku else hashlib.md5(link.encode()).hexdigest()[:8]}"
                    
                    products_data.append({
                        "id": product_id,
                        "url": p.url,
                        "name": p.name,
                        "description": p.description,
                        "sku": p.sku,
                        "availability": p.availability_pm,
                        "price": p.price_uah,
                        "images": p.images,
                        "group_id": gid
                    })
                except Exception as e:
                    print(f"      [!] Ошибка при парсинге {link}: {e}")

        # Генерация XML
        xml_content = generate_xml(used_groups, products_data)
        
        save_path = os.path.join(OUTPUT_DIR, OUTPUT_NAME)
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(xml_content)

        print(f"\n[ГОТОВО] XML Файл для Prom.ua успешно сохранен: {save_path}")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
