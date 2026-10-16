# Source: BAMA.ir
import csv
import os
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

TARGET_COUNT = 500
MAX_UNCHANGED_ROUNDS = 15
CUTOFF_DATE = (1405, 7, 1)

# Define the output CSV path.
CSV_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "cars.csv"
)

# Define the CSV columns.
FIELDNAMES = [
    "brand",
    "model",
    "trim",
    "year",
    "mileage_km",
    "city",
    "price_toman",
    "published_date",
    "body_condition",
    "ad_url",
]

# Map filter codes to Persian body conditions.
FILTERS = [
    ("scratches", "دارای خط و خش"),
    ("one_paint", "یک لکه رنگ"),
    ("no_paint", "بدون رنگ"),
    ("multi_paint", "چند لکه رنگ"),
    ("around_paint", "دوررنگ"),
    ("refinement", "ترمیم"),
    ("two_paint", "دو لکه رنگ"),
    ("hood_replace", "تعویض کاپوت"),
    ("fender_replace", "تعویض گلگیر"),
    ("fender_paint", "رنگ گلگیر"),
    ("one_door", "یک درب رنگ"),
    ("door_replace", "تعویض درب"),
    ("full_paint", "تمام‌رنگ"),
    ("crashed", "تصادفی"),
    ("two_door", "دو درب رنگ"),
    ("hood_paint", "رنگ کاپوت"),
    ("burned", "سوخته"),
    ("room_replace", "تعویض اتاق"),
]


def extract_article(article, body_condition):
    # Extract the brand and model.
    brand = ""
    model = ""

    name_elements = article.select(
        "span.inline-block.text-right.w-full."
        "text-base.leading-6.font-semibold.truncate.text-neutral-10"
    )

    for element in name_elements:
        text = element.get_text(" ", strip=True)

        if "،" in text:
            brand, model = [
                part.strip()
                for part in text.split("،", 1)
            ]
            break

    # Skip articles with missing brand or model.
    if not brand or not model:
        return None

    # Extract the vehicle trim.
    trim = ""

    trim_elements = article.select(
        "span.inline-block.text-right.w-full."
        "text-sm.leading-6.font-normal.truncate.text-neutral-10"
    )

    for element in trim_elements:
        text = element.get_text(" ", strip=True)

        if (
            text
            and not re.fullmatch(r"\d{4}", text)
            and "کیلومتر" not in text
            and "صفر کیلومتر" not in text
        ):
            trim = text
            break

    # Extract the production year.
    year = ""

    for element in article.select("span"):
        text = element.get_text(strip=True)

        if re.fullmatch(r"\d{4}", text):
            number = int(text)

            if 1300 <= number <= 1405 or 1900 <= number <= 2100:
                year = number
                break

    article_text = article.get_text(" ", strip=True)

    # Extract mileage, using zero for new cars.
    if "صفر کیلومتر" in article_text:
        mileage_km = 0
    else:
        mileage_match = re.search(
            r"([\d,]+)\s*کیلومتر",
            article_text
        )

        mileage_km = (
            int(mileage_match.group(1).replace(",", ""))
            if mileage_match
            else ""
        )

    # Extract the city name.
    city = ""

    for element in article.select(
        "p.inline-block.text-right.w-full.text-sm.leading-6.font-normal"
    ):
        text = element.get_text(" ", strip=True)

        if text:
            city = text.split("،", 1)[0].strip()
            break

    # Extract the publication date.
    published_date = ""

    for element in article.select("span"):
        text = element.get_text(" ", strip=True)

        if re.fullmatch(r"14\d{2}/\d{1,2}/\d{1,2}", text):
            published_date = text
            break

    # Extract the price in toman.
    price_toman = ""

    for element in article.select("span"):
        text = element.get_text(strip=True).replace(",", "").strip()

        if re.fullmatch(r"\d{7,}", text):
            price_toman = int(text)
            break

    # Skip articles without a valid price.
    if not price_toman:
        return None

    # Extract and normalize the advertisement URL.
    ad_url = ""

    for link in article.select("a[href]"):
        href = link.get("href", "").strip()

        if href.startswith("/"):
            ad_url = "https://bama.ir" + href
            break

        if href.startswith("https://bama.ir/") or href.startswith(
            "http://bama.ir/"
        ):
            ad_url = href
            break

    # Return the extracted vehicle data.
    return {
        "brand": brand,
        "model": model,
        "trim": trim,
        "year": year,
        "mileage_km": mileage_km,
        "city": city,
        "price_toman": price_toman,
        "published_date": published_date,
        "body_condition": body_condition,
        "ad_url": ad_url,
    }


def is_older_than_cutoff(date_text):
    """Check whether an absolute publication date precedes the cutoff."""

    # Ignore relative or invalid date formats.
    match = re.fullmatch(
        r"(14\d{2})/(\d{1,2})/(\d{1,2})",
        date_text.strip()
    )

    if not match:
        return False

    # Compare dates as tuples of year, month, and day.
    ad_date = tuple(map(int, match.groups()))

    return ad_date < CUTOFF_DATE


def save_csv(cars):
    # Overwrite the CSV with all collected advertisements.
    with open(
        CSV_FILE,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=FIELDNAMES
        )

        writer.writeheader()
        writer.writerows(cars)


def main():
    collected_cars = []

    # Track advertisements to prevent duplicates.
    seen_ads = set()

    with sync_playwright() as p:
        # Launch Microsoft Edge using Chromium.
        browser = p.chromium.launch(
            headless=False,
            channel="msedge"
        )

        # Configure the browser page.
        page = browser.new_page(
            viewport={"width": 1366, "height": 900},
            locale="fa-IR",
        )

        # Scrape advertisements for each body condition.
        for filter_code, body_condition in FILTERS:
            url = (
                "https://bama.ir/car?"
                "price=0,90000000000"
                f"&status={filter_code}"
                "&sort=2"
            )

            print("\n" + "=" * 60)
            print(f"body condition : {body_condition}")
            print(f"URL: {url}")

            # Open the filtered results page.
            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            page.wait_for_timeout(5000)

            collected_in_filter = 0
            unchanged_rounds = 0
            stop_filter = False

            # Continue until the target or stopping condition is reached.
            while (
                collected_in_filter < TARGET_COUNT
                and unchanged_rounds < MAX_UNCHANGED_ROUNDS
                and not stop_filter
            ):
                # Retrieve the current article HTML from the DOM.
                html_list = page.locator("article").evaluate_all(
                    "(elements) => elements.map(el => el.outerHTML)"
                )

                print(
                    f"Articles in DOM: {len(html_list)} | "
                    f"Collected in filter: "
                    f"{collected_in_filter}/{TARGET_COUNT}"
                )

                previous_count = len(collected_cars)

                # Parse and process each visible advertisement.
                for article_html in html_list:
                    if collected_in_filter >= TARGET_COUNT:
                        break

                    article = BeautifulSoup(
                        article_html,
                        "html.parser"
                    )

                    car = extract_article(
                        article,
                        body_condition
                    )

                    # Skip invalid advertisements.
                    if car is None:
                        continue

                    # Stop this filter when an old advertisement is found.
                    if is_older_than_cutoff(car["published_date"]):
                        print(
                            f" cutoff date: {car['published_date']} "
                            f"in filter {filter_code}"
                        )
                        stop_filter = True
                        break

                    # Use the URL, or HTML as a fallback, to identify duplicates.
                    unique_key = car["ad_url"] or article_html.strip()

                    if unique_key in seen_ads:
                        continue

                    # Store the unique advertisement.
                    seen_ads.add(unique_key)
                    collected_cars.append(car)
                    collected_in_filter += 1

                    print(
                        f"Total: {len(collected_cars)} | "
                        f"Filter: {collected_in_filter} | "
                        f"{car['brand']} {car['model']} | "
                        f"Date: {car['published_date']}"
                    )

                if stop_filter:
                    break

                # Track rounds that produce no new advertisements.
                if len(collected_cars) == previous_count:
                    unchanged_rounds += 1
                else:
                    unchanged_rounds = 0

                if collected_in_filter >= TARGET_COUNT:
                    break

                # Move to the next filter if results stop changing.
                if unchanged_rounds >= MAX_UNCHANGED_ROUNDS:
                    print("No new ads, moving to the next filter.")
                    break

                # Scroll down to load more advertisements.
                page.evaluate(
                    "window.scrollTo(0, document.body.scrollHeight)"
                )

                page.wait_for_timeout(2000)

                # Click the load-more button when available.
                more_button = page.get_by_role(
                    "button",
                    name="more",
                    exact=True
                )

                if (
                    more_button.count() > 0
                    and more_button.first.is_visible()
                    and more_button.first.is_enabled()
                ):
                    print("Clicking 'بیشتر'...")
                    more_button.first.click()
                    page.wait_for_timeout(5000)
                else:
                    page.wait_for_timeout(2000)

            print(
                f" filter end  {filter_code}. "
                f"receive ads : {collected_in_filter}"
            )

            # Save progress after each filter.
            if collected_cars:
                save_csv(collected_cars)

        # Close the browser after scraping.
        browser.close()

    # Print the final collection summary.
    print("\n" + "=" * 60)
    print(f"sum of distinct ads : {len(collected_cars)}")
    print(f"output file : {CSV_FILE}")


if __name__ == "__main__":
    main()
```