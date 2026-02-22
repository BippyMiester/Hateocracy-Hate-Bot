import discord
from discord.ext import commands
import os
import json
import asyncio
import time
import re
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import chromadb
from chromadb.config import Settings
from helpers.Logger import Logger

# Load settings.json configuration.
SETTINGS_PATH = Path("./settings.json")
with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
    settings = json.load(f)

# Extract wiki settings.
wiki_settings = settings["wiki"]
BASE_URL = wiki_settings["base_url"]
WIKI_ALL_PAGES_URL = wiki_settings["all_pages_url"]
MAX_RETRIES = wiki_settings.get("number_of_retries", 5)
PAGE_EXPIRATION_DAYS = wiki_settings.get("page_expiration", 7)
DATA_DIR = Path(wiki_settings["data_directory"])
CHROMA_PERSIST_DIR = Path(wiki_settings["chroma_persist_directory"])
PURGE_SPECIAL_CHARS = wiki_settings.get("purge_special_chars", False)
PURGE_LINES = wiki_settings.get("purge_lines", [])
IGNORED_PAGES = wiki_settings.get("ignored_pages", [])

# Extract FlareSolverr settings.
flaresolverr_settings = settings["apps"]["flaresolverr"]
FLARESOLVERR_URL = flaresolverr_settings["base_url"]
FLARESOLVERR_TIMEOUT = flaresolverr_settings["max_timeout"]
FLARESOLVERR_HEADERS = flaresolverr_settings["headers"]

# Define the file that stores last download timestamps.
LAST_DOWNLOADED_FILE = Path("./data/wiki_last_downloaded.json")

# Ensure the wiki data directory exists.
DATA_DIR.mkdir(parents=True, exist_ok=True)

def sanitize_title(title: str) -> str:
    """
    Sanitize a title so that it contains only A-Z, a-z, 0-9, and underscores.
    Every character not matching these is replaced with an underscore.
    """
    return re.sub(r'[^A-Za-z0-9]', '_', title)

def load_last_downloaded():
    """Load the wiki_last_downloaded.json file, or return an empty dict if it doesn't exist."""
    if LAST_DOWNLOADED_FILE.exists():
        try:
            with open(LAST_DOWNLOADED_FILE, "r", encoding="utf-8") as f:
                last_downloaded = json.load(f)
            Logger.debug("Loaded last downloaded timestamps.")
            return last_downloaded
        except Exception as e:
            Logger.error(f"Error loading {LAST_DOWNLOADED_FILE}: {e}")
            return {}
    else:
        Logger.info(f"{LAST_DOWNLOADED_FILE} does not exist. Creating a new one.")
        return {}

def save_last_downloaded(last_downloaded: dict):
    """Save the wiki_last_downloaded.json file."""
    try:
        with open(LAST_DOWNLOADED_FILE, "w", encoding="utf-8") as f:
            json.dump(last_downloaded, f, indent=4)
        Logger.debug("Saved last downloaded timestamps.")
    except Exception as e:
        Logger.error(f"Error saving {LAST_DOWNLOADED_FILE}: {e}")

def get_with_flaresolverr(target_url: str):
    """
    Uses FlareSolverr (via POST) to get the HTML for the given target URL.
    Returns a tuple (content, status_code).
    If the JSON response contains a "solution" key with a "response",
    that HTML portion is used.
    """
    data = {
        "cmd": flaresolverr_settings["cmd"],
        "url": target_url,
        "maxTimeout": FLARESOLVERR_TIMEOUT
    }
    try:
        response = requests.post(FLARESOLVERR_URL, headers=FLARESOLVERR_HEADERS, json=data)
        content = response.text
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict) and "solution" in parsed and "response" in parsed["solution"]:
                content = parsed["solution"]["response"]
        except Exception:
            pass
        if response.status_code != 200:
            snippet = content[:300] + ("..." if len(content) > 300 else "")
            Logger.error(f"Error fetching {target_url}: Status code {response.status_code}. Raw response snippet: {snippet}")
        return content, response.status_code
    except Exception as e:
        Logger.error(f"Error contacting FlareSolverr for URL {target_url}: {e}")
        return None, None

async def async_get_with_flaresolverr(target_url: str):
    """Wrap get_with_flaresolverr in asyncio.to_thread."""
    return await asyncio.to_thread(get_with_flaresolverr, target_url)

# Load local embedding model using SentenceTransformer.
try:
    from sentence_transformers import SentenceTransformer
    Logger.info("Loading local embedding model using SentenceTransformer...")
    embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    Logger.info("Local embedding model loaded.")
except ModuleNotFoundError as e:
    Logger.error("Module 'sentence_transformers' not found. Please install it with 'pip install sentence-transformers'.")
    raise e

async def index_wiki_pages():
    Logger.info("Starting Wiki task: Updating wiki pages and indexing with ChromaDB...")
    
    last_downloaded = load_last_downloaded()
    current_time = int(time.time())
    expiration_seconds = PAGE_EXPIRATION_DAYS * 86400  # days to seconds

    pages = []
    next_page_url = WIKI_ALL_PAGES_URL

    try:
        # Loop through all pages from the All Pages listing.
        while next_page_url:
            Logger.info(f"Fetching wiki pages list from {next_page_url}")
            content, status_code = await async_get_with_flaresolverr(next_page_url)
            if content:
                snippet = content[:300] + ("..." if len(content) > 300 else "")
                Logger.debug(f"Raw HTML snippet from {next_page_url}: {snippet}")
            if status_code != 200:
                raise Exception(f"Error fetching wiki pages list. Status code: {status_code}")
            soup = BeautifulSoup(content, "html.parser")
            
            # Extract page links.
            page_links = soup.select("ul.mw-allpages-chunk li a")
            if not page_links:
                page_links = soup.select("div.mw-allpages-body ul li a")
            for a in page_links:
                title = a.get_text(strip=True)
                # Skip ignored pages.
                if title in IGNORED_PAGES:
                    Logger.info(f"Ignoring page '{title}' as it is in the ignored_pages list.")
                    continue
                href = a.get("href")
                if href and title:
                    if not href.startswith("http"):
                        href = BASE_URL + href
                    pages.append({"title": title, "url": href})
            
            Logger.info(f"Found {len(page_links)} pages on current listing. Total pages so far: {len(pages)}")
            
            # Follow Next page link.
            next_link = soup.select_one("div.mw-allpages-nav a[title='Special:AllPages']")
            if next_link and "Next page" in next_link.get_text():
                href = next_link.get("href")
                if href:
                    next_page_url = BASE_URL + href
                    Logger.info(f"Next page found. Moving to {next_page_url}")
                else:
                    next_page_url = None
            else:
                next_page_url = None
    except Exception as e:
        Logger.error(f"Error fetching wiki pages list: {e}")
        return

    Logger.info(f"Total pages discovered: {len(pages)}")

    # Assign unique sanitized titles.
    used_ids = {}
    unique_pages = []
    for page in pages:
        title = page["title"]
        sanitized = sanitize_title(title)
        if sanitized in used_ids:
            used_ids[sanitized] += 1
            unique_title = f"{sanitized}_{used_ids[sanitized]}"
        else:
            used_ids[sanitized] = 0
            unique_title = sanitized
        page["unique_title"] = unique_title
        unique_pages.append(page)
    pages = unique_pages

    # Log discovered pages.
    for page in pages:
        Logger.debug(f"Discovered URL: {page['url']} (Original: {page['title']}, Unique: {page['unique_title']})")
    
    # Step 2: Download each page and save plain text from <div id="mw-content-text"> to DATA_DIR.
    for page in pages:
        title = page["title"]
        unique_title = page["unique_title"]
        last_time = last_downloaded.get(title, 0)
        if current_time - last_time < expiration_seconds:
            Logger.info(f"Skipping {title}: downloaded {current_time - last_time} sec ago (< {expiration_seconds} sec expiration).")
            continue
        
        retry_count = 0
        content = None
        status_code = None
        while retry_count < MAX_RETRIES:
            Logger.debug(f"Attempt {retry_count+1} for downloading {title}")
            content, status_code = await async_get_with_flaresolverr(page["url"])
            if status_code == 500 and content and "Error solving the challenge" in content:
                retry_count += 1
                Logger.warning(f"Retry {retry_count} for downloading {title} due to challenge error.")
                await asyncio.sleep(1)
            else:
                break
        if retry_count == MAX_RETRIES:
            Logger.error(f"Failed to download {title} after {MAX_RETRIES} retries. Setting its timestamp to 0.")
            last_downloaded[title] = 0
            save_last_downloaded(last_downloaded)
            continue
        if status_code != 200:
            Logger.error(f"Error downloading {title}: Status code {status_code}.")
            continue
        try:
            soup = BeautifulSoup(content, "html.parser")
            # Extract text only within the div with id "mw-content-text".
            content_div = soup.find("div", id="mw-content-text")
            if content_div:
                text_content = content_div.get_text(separator="\n", strip=True)
            else:
                Logger.warning(f"Div id 'mw-content-text' not found for {title}; extracting all text.")
                text_content = soup.get_text(separator="\n", strip=True)
            filename = DATA_DIR / f"{unique_title}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(text_content)
            Logger.info(f"Downloaded and saved text for page: {title} as {unique_title}.txt")
            last_downloaded[title] = int(time.time())
            save_last_downloaded(last_downloaded)
        except Exception as e:
            Logger.error(f"Error processing page {title}: {e}")
            continue

    # Step 3: Clean up files prior to indexing.
    try:
        txt_files = list(DATA_DIR.glob("*.txt"))
        Logger.info(f"Found {len(txt_files)} text files in {DATA_DIR} for cleanup.")
        for file in txt_files:
            try:
                with open(file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                cleaned_lines = []
                for line in lines:
                    stripped_line = line.strip()
                    # If purge_special_chars is true and line consists of a single non-alphanumeric character.
                    if PURGE_SPECIAL_CHARS and len(stripped_line) == 1 and not stripped_line.isalnum():
                        continue
                    # Remove line if it exactly matches any string in PURGE_LINES.
                    if stripped_line in PURGE_LINES:
                        continue
                    # Remove line if it starts with "Honest Trailers Commentary".
                    if stripped_line.startswith("Honest Trailers Commentary"):
                        continue
                    cleaned_lines.append(line.rstrip())
                new_content = "\n".join(cleaned_lines)
                with open(file, "w", encoding="utf-8") as f:
                    f.write(new_content)
                Logger.debug(f"Cleaned file: {file.name} (original {len(lines)} lines, cleaned {len(cleaned_lines)} lines)")
            except Exception as e:
                Logger.error(f"Error cleaning file {file.name}: {e}")
                continue
    except Exception as e:
        Logger.error(f"Error during file cleanup: {e}")
        return

    # Step 4: Index pages with local embeddings using ChromaDB.
    try:
        txt_files = list(DATA_DIR.glob("*.txt"))
        Logger.info(f"Found {len(txt_files)} text files in {DATA_DIR} for indexing.")
        client = chromadb.Client(
            settings=Settings(
                persist_directory=str(CHROMA_PERSIST_DIR),
                anonymized_telemetry=False
            )
        )
        try:
            collection = client.get_collection("wiki")
            Logger.info("Loaded existing 'wiki' collection from ChromaDB.")
        except Exception:
            collection = client.create_collection("wiki")
            Logger.info("Created new 'wiki' collection in ChromaDB.")
        
        doc_ids = []
        documents = []
        metadatas = []
        for file in txt_files:
            try:
                with open(file, "r", encoding="utf-8") as f:
                    text_content = f.read()
                Logger.debug(f"Generating embedding for file: {file.name}")
                embedding_vector = await asyncio.to_thread(lambda: embedding_model.encode(text_content).tolist())
                doc_id = sanitize_title(file.stem)
                doc_ids.append(doc_id)
                documents.append(text_content)
                metadatas.append({"filename": str(file)})
                Logger.info(f"Indexed file: {file.name} (token count approx: {len(text_content.split())})")
            except Exception as e:
                Logger.error(f"Error processing file {file.name}: {e}")
                continue

        if doc_ids:
            await asyncio.to_thread(lambda: collection.upsert(ids=doc_ids, documents=documents, metadatas=metadatas))
            Logger.info(f"Successfully upserted {len(doc_ids)} documents into the wiki collection.")
        else:
            Logger.warning("No documents to upsert into the wiki collection.")
    except Exception as e:
        Logger.error(f"Error during indexing with ChromaDB: {e}")
        return

    Logger.info("Wiki task completed successfully.")

async def setup(bot: commands.Bot):
    Logger.info("Setting up Wiki task...")
    asyncio.create_task(index_wiki_pages())
    Logger.info("Wiki task scheduled successfully.")