import instaloader
import requests
import threading
import sys
import json
from typing import Dict, Any, List
from check_arguments import check_arguments
import traceback

API_BASE_URL = "http://localhost:3000"

campaign_name, targets, scrape_type = check_arguments()

def update_accounts_activity(account_ids: List[str], is_active: bool):
    api_url = f"{API_BASE_URL}/accounts/activity"
    payload = {
        "accountIds": account_ids,
        "isActive": is_active
    }

    print(f"Attempting to update activity for {len(account_ids)} accounts to isNotActive={is_active} via {api_url}...")

    try:
        response = requests.patch(api_url, json=payload, timeout=15)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        result = response.json()
        print(f"Successfully requested activity update. API response: {result}")
        return True
    except requests.exceptions.Timeout:
        print(f"Error: Timeout during bulk activity update ({api_url})", file=sys.stderr)
        return False
    except requests.exceptions.RequestException as e:
        print(f"Error during bulk activity update ({api_url}): {e}", file=sys.stderr)
        return False
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON response from bulk update API. Status: {response.status_code}, Text: {response.text}", file=sys.stderr)
        return False
    except Exception as e:
         print(f"Unexpected error during bulk activity update ({api_url}): {e}", file=sys.stderr)
         return False

def fetch_logged_accounts(count: int):
    if count <= 0:
        print("Error: Number of accounts to fetch must be positive.", file=sys.stderr)
        return []
    try:
        api_url = f"{API_BASE_URL}/accounts/logged?count={count}"
        print(f"Fetching {count} logged accounts from {api_url}...")

        response = requests.get(api_url, timeout=15)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        accounts = response.json()

        if not isinstance(accounts, list):
             print(f"Error: API did not return a list of accounts. Response: {accounts}", file=sys.stderr)
             return []
        if len(accounts) < count:
            print(f"Warning: Requested {count} accounts, but API returned only {len(accounts)}.", file=sys.stderr)
        print(f"Successfully fetched {len(accounts)} accounts.")
        return accounts
    except requests.exceptions.Timeout:
        print(f"Error: Request to API timed out ({api_url})", file=sys.stderr)
        return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching accounts from API: {e}", file=sys.stderr)
        return []
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON response from API. Response text: {response.text}")
        return []
    except Exception as e:
        print(f"Error: Unexpected error in fetch_logged_accounts: {str(e)}")
        return []

def send_data_to_api(campaign, scraped_accounts, thread_name):
    try:
        api_url = f"{API_BASE_URL}/campaigns/{campaign}/data"
        response = requests.post(api_url, json=scraped_accounts, timeout=10)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        return True
    except requests.exceptions.Timeout:
        print(f"Thread-{thread_name}: Error - Timeout sending data to API ({api_url})", file=sys.stderr)
        return False
    except requests.exceptions.RequestException as e:
        print(f"Thread-{thread_name}: Error sending data to API ({api_url})", file=sys.stderr)
        return False
    except Exception as e:
         print(f"Thread-{thread_name}: Unexpected error in sending data to API ({api_url})", file=sys.stderr)
         return False

def scrape_hashtag_posts(L: instaloader.Instaloader, hashtag_name: str, thread_name: str, campaign: str, counter: List[int], lock: threading.Lock):
    """Scrapes posts for a hashtag, sends data to API, and increments counter."""
    items_sent_count = 0
    try:
        hashtag = instaloader.Hashtag.from_name(L.context, hashtag_name)
        print(f"Thread-{thread_name}: Scraping posts for hashtag: #{hashtag_name}")

        scraped_accounts = []
        for post in hashtag.get_posts_resumable():
            scraped_accounts.append({"username": post.owner_username, "id": post.owner_id})
            if len(scraped_accounts) >= 50:  # Send data in batches of 50
                send_data_to_api(campaign, scraped_accounts, thread_name)
                with lock:
                    counter[0] += len(scraped_accounts)
                items_sent_count += len(scraped_accounts)
                scraped_accounts = []

        if scraped_accounts:  # Send remaining data
            send_data_to_api(campaign, scraped_accounts, thread_name)
            with lock:
                counter[0] += len(scraped_accounts)
            items_sent_count += len(scraped_accounts)

        print(f"Thread-{thread_name}: Finished scraping posts for #{hashtag_name}. Successfully sent {items_sent_count} items to API.")
    except instaloader.QueryReturnedNotFoundException:
        print(f"Thread-{thread_name}: Hashtag #{hashtag_name} not found.")
    except (instaloader.QueryReturnedBadRequestException, instaloader.QueryReturnedForbiddenException, instaloader.LoginRequiredException, instaloader.LoginException, instaloader.InvalidArgumentException, instaloader.PostChangedException, instaloader.TooManyRequestsException) as e:
        print("Error type:", type(e).__name__, file=sys.stderr)
        print("Error message:", str(e), file=sys.stderr)
    except Exception as e:
        print(f"Thread-{thread_name}: Error during scraping/sending for hashtag #{hashtag_name}: {type(e).__name__}", file=sys.stderr)
        print("Error type:", type(e).__name__, file=sys.stderr)
        print("Error message:", str(e), file=sys.stderr)
        traceback.print_exc(file=sys.stderr) # Print the full traceback

def scrape_followers(L: instaloader.Instaloader, username_target: str, thread_name: str, campaign: str, counter: List[int], lock: threading.Lock):
    """Scrapes followers for a user, sends data to API, and increments counter."""
    items_sent_count = 0
    try:
        profile = instaloader.Profile.from_username(L.context, username_target)
        print(f"Thread-{thread_name}: Scraping followers of: {username_target}")

        scraped_accounts = []
        for follower in profile.get_followers():
            scraped_accounts.append({"username": follower.username, "id": follower.userid})
            if len(scraped_accounts) >= 50:  # Send data in batches of 50
                send_data_to_api(campaign, scraped_accounts, thread_name)
                with lock:
                    counter[0] += len(scraped_accounts)
                items_sent_count += len(scraped_accounts)
                scraped_accounts = []

        if scraped_accounts:  # Send remaining data
            send_data_to_api(campaign, scraped_accounts, thread_name)
            with lock:
                counter[0] += len(scraped_accounts)
            items_sent_count += len(scraped_accounts)

        print(f"Thread-{thread_name}: Finished scraping followers for {username_target}. Successfully sent {items_sent_count} items to API.")
    except instaloader.ProfileNotExistsException:
        print(f"Thread-{thread_name}: Profile {username_target} not found.")
    except Exception as e:
        print(f"Thread-{thread_name}: Error during scraping/sending for profile {username_target}: {e}", file=sys.stderr)
        print("Error type:", type(e).__name__, file=sys.stderr)
        print("Error message:", str(e), file=sys.stderr)
        traceback.print_exc(file=sys.stderr) # Print the full traceback

def worker_scrape(account_info: Dict[str, Any], target: str, scrape_type: str, campaign: str, counter: List[int], lock: threading.Lock):
    """Handles setup, scraping, API calls, and counter increment for one account/target."""
    thread_name = threading.current_thread().name
    print(f"Thread-{thread_name}: Starting worker for account {account_info.get('username')} and target {target}")

    # Get instaloader instance
    L = instaloader.Instaloader(
        compress_json=False, # Easier debugging
        save_metadata=False, # Don't save metadata files
        download_pictures=False, # Don't download media
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        post_metadata_txt_pattern="" # Avoid creating txt files
    )

    # Proxy Setup
    proxy = account_info.get('proxy').get('proxyUrl')
    L.context._session.proxies = {'http': proxy, 'https': proxy}

    # Session Loading
    username = account_info.get('username')
    session_data = account_info.get('sessionData')

    L.load_session(username, session_data)
    print(f"Thread-{thread_name}: Successfully loaded session for {username}")

    try:
        if scrape_type == "Hashtags":
            scrape_hashtag_posts(L, target, thread_name, campaign, counter, lock)
        elif scrape_type == "Followers":
            scrape_followers(L, target, thread_name, campaign, counter, lock)
        else:
            print(f"Thread-{thread_name}: Unknown scrape type '{scrape_type}'.", file=sys.stderr)

        print(f"Thread-{thread_name}: Worker finished processing target '{target}'.")

    except Exception as e:
        print(f"Thread-{thread_name}: An unexpected error occurred in worker for target {target}: {e}", file=sys.stderr)


if __name__ == "__main__":
    # Determine the number of accounts needed based on targets
    num_accounts_needed = len(targets)

    # Fetch the accounts
    logged_accounts = fetch_logged_accounts(num_accounts_needed)

    if not logged_accounts:
        print("Error: No logged accounts fetched or available. Exiting.", file=sys.stderr)
        sys.exit(1)
    
    account_ids_to_update = [acc['id'] for acc in logged_accounts if 'id' in acc]
    update_accounts_activity(account_ids_to_update, True)

    # Ensure we have enough accounts for the targets
    if len(logged_accounts) < len(targets):
        print(f"Warning: Not enough logged accounts ({len(logged_accounts)}) for all targets ({len(targets)}). Some targets will be skipped.", file=sys.stderr)
        # Trim targets list to match available accounts
        targets = targets[:len(logged_accounts)]

    print(f"\nStarting scraping campaign '{campaign_name}' for {len(targets)} targets using {len(logged_accounts)} accounts.")

    threads = []
    total_scraped_count = [0] # Use a list to hold the mutable integer count
    counter_lock = threading.Lock() # Lock for safe access to the counter

    # Assign one account per target and create threads
    for i in range(len(targets)):
        account = logged_accounts[i]
        target = targets[i]
        # Pass campaign_name, total_scraped_count, and counter_lock to the worker
        thread = threading.Thread(target=worker_scrape, args=(account, target, scrape_type, campaign_name, total_scraped_count, counter_lock), name=f"Worker-{i+1}")
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    print("\nWaiting for all scraping threads to complete...")
    for thread in threads:
        thread.join()

    update_accounts_activity(account_ids_to_update, False)

    print("\n--- Scraping Campaign Finished ---")
    print(f"Campaign Name: {campaign_name}")
    print(f"Scrape Type: {scrape_type}")
    print(f"Total items successfully scraped and sent to API: {total_scraped_count[0]}")
    print("Script finished.")