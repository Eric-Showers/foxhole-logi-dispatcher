import time
import asyncio
import os

from playwright.async_api import async_playwright

# Converts a timestamp to a relative time string (eg. "6 hours ago")
def get_relative_time_str(prev_time):
    if prev_time is None:
        return "Never"
    current_time = time.time()
    elapsed_time = current_time - prev_time

    if elapsed_time < 60:
        return f"{int(elapsed_time)} seconds ago"
    elif elapsed_time < 3600:
        return f"{int(elapsed_time / 60)} minutes ago"
    elif elapsed_time < 86400:
        return f"{int(elapsed_time / 3600)} hours ago"
    else:
        return f"{int(elapsed_time / 86400)} days ago"


# Formats a response string into a list of strings, each with a max length of 1990 characters
# Does not split lines
def chunk_response(table_str):
    chunks = []
    current_chunk = ''
    for line in table_str.split('\n'):
        if len(current_chunk) + len(line) + 1 > 1990:
            chunks.append(current_chunk)
            current_chunk = ''
        current_chunk += line + '\n'
    if current_chunk:
        chunks.append(current_chunk)
    return chunks


# Takes a list of item dicts (w/ 'quantity' & 'info') and sorts into categories & descending order
def organizeItemList(item_list):
    # Sort quotas into categories
    categorized = {}
    for item in item_list:
        category = item['info']['category']
        if category not in categorized:
            categorized[category] = []
        categorized[category].append({'display_name': item['info']['display_name'], 'quantity': item['quantity']})
    # Sort each category by quantity, descending order
    for cat, quotas in categorized.items():
        categorized[cat] = sorted(quotas, key=lambda x: x['quantity'], reverse=True)
    return categorized


# TBH I vibe coded this one because it's hopefully a temporary hack :|
async def run_fir_parser(image_path: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()
        await page.goto("http://127.0.0.1:8800/")

        # Upload the screenshot
        file_input = await page.wait_for_selector('input[type="file"]')
        await file_input.set_input_files(image_path)

        # More robust selector
        status_selector = 'li:has-text("Wait for processing") div span'

        for i in range(60):  # Wait up to 30s
            processed_text = await page.eval_on_selector(
                status_selector, "el => el.innerText"
            )
            if processed_text.strip().startswith("1 of"):
                break
            await asyncio.sleep(0.5)
        else:
            raise asyncio.TimeoutError('FIR took too long to process')

        async with page.expect_download() as download_info:
            await page.click("button.tsv")
        download = await download_info.value

        tsv_path = await download.path()

        with open(tsv_path, "r", encoding="utf-8") as f:
            tsv_data = f.read()

        await browser.close()
        os.remove(image_path)
        return tsv_data