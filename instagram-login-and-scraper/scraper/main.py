import instaloader
import requests
import threading
import sys
import json
from typing import Dict, Any, List
from check_arguments import check_arguments
import time
import random
import traceback

API_BASE_URL = "http://localhost:3000"

campaign_name, targets, scrape_type = check_arguments()

def update_account_record(account_id, status, session_data=None):
    payload = {"status": status}

    if session_data:
        payload["sessionData"] = session_data

    try:
        response = requests.patch(f"{API_BASE_URL}/accounts/{account_id}", json=payload, timeout=15)
        response.raise_for_status()
        print(f"Successfully updated account {account_id}.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"API Error updating account {account_id}: {e}", file=sys.stderr)
        return False
    except json.JSONDecodeError:
        print(f"API Error: Failed to decode JSON response when updating account {account_id}.", file=sys.stderr)
        return False


def update_accounts_activity(account_ids: List[str], is_active: bool):
    api_url = f"{API_BASE_URL}/accounts/activity"
    payload = {
        "accountIds": account_ids,
        "isActive": is_active
    }

    print(f"Attempting to update activity for {len(account_ids)} accounts to isNotActive={is_active}...")

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
        print(f"Fetching {count} logged accounts...")

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
        api_url = f"{API_BASE_URL}/campaigns/{campaign}"
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

def scrape_hashtag_posts(L: instaloader.Instaloader, account_info: Dict[str, Any], hashtag_name: str, thread_name: str, campaign: str, counter: List[int], lock: threading.Lock):
    """Scrapes posts for a hashtag, sends data to API, and increments counter."""
    items_sent_count = 0
    total_posts_scraped_for_hashtag = 0
    MAX_POSTS_PER_HASHTAG = 1000

    try:
        hashtag = instaloader.Hashtag.from_name(L.context, hashtag_name)
        print(f"Thread-{thread_name}: Scraping posts for hashtag: #{hashtag_name}")

        scraped_accounts = []
        for post in hashtag.get_posts_resumable():
            scraped_accounts.append({"username": post.owner_username, "id": post.owner_id})
            total_posts_scraped_for_hashtag += 1

            # if total_posts_scraped_for_hashtag >= MAX_POSTS_PER_HASHTAG:
            #     print(f"Thread-{thread_name}: Reached post limit ({MAX_POSTS_PER_HASHTAG}) for #{hashtag_name}.")
            #     break # Stop scraping this hashtag

            if len(scraped_accounts) >= 50:  # Send data in batches of 50
                if send_data_to_api(campaign, scraped_accounts, thread_name):
                    with lock:
                        counter[0] += len(scraped_accounts)
                    items_sent_count += len(scraped_accounts)
                else:
                    print(f"Thread-{thread_name}: Failed to send batch for #{hashtag_name}. Stopping scrape for this hashtag.")

                scraped_accounts = []
            #     time.sleep(random.uniform(15, 30))
            # time.sleep(random.uniform(0.5, 2.0))

        if scraped_accounts:  # Send remaining data
            if send_data_to_api(campaign, scraped_accounts, thread_name):
                with lock:
                    counter[0] += len(scraped_accounts)
                items_sent_count += len(scraped_accounts)

        print(f"Thread-{thread_name}: Finished scraping posts for #{hashtag_name}. Processed {total_posts_scraped_for_hashtag} posts. Successfully sent {items_sent_count} items to API.")

    except instaloader.QueryReturnedNotFoundException:
        print(f"Thread-{thread_name}: Hashtag #{hashtag_name} not found.", file=sys.stderr)
    except instaloader.TooManyRequestsException as e:
        print(f"Thread-{thread_name}: Hit rate limit (TooManyRequestsException) for #{hashtag_name}. Stopping scrape for this hashtag.", file=sys.stderr)
        print("Error type:", type(e).__name__, file=sys.stderr)
        print("Error message:", str(e), file=sys.stderr)
        traceback.print_exc(file=sys.stderr) # Print the full traceback
    except (instaloader.QueryReturnedBadRequestException, instaloader.QueryReturnedForbiddenException) as e:
        error_message = str(e)
        if "checkpoint_required" in error_message:
            print(f"Error: Checkpoint required for {account_info.get("username")}. Manual intervention needed.", file=sys.stderr)
            update_account_record(account_info.get("id"), "CheckpointRequired")
        else:
            print(f"Error: Challenge required for {account_info.get("username")}. Manual intervention needed.", file=sys.stderr)
            update_account_record(account_info.get("id"), "ChallengeRequired")
        print("Error type:", type(e).__name__, file=sys.stderr)
        print("Error message:", str(e), file=sys.stderr)
        traceback.print_exc(file=sys.stderr) # Print the full traceback
    except instaloader.exceptions.ConnectionException as e:
        error_message = str(e)
        if "401 Unauthorized" in error_message or "login_required" in error_message:
            print(f"Error: Login required for {account_info.get("username")}.", file=sys.stderr)
            update_account_record(account_info.get("id"), "NotLogged")
        print("Error type:", type(e).__name__, file=sys.stderr)
        print("Error message:", str(e), file=sys.stderr)
        traceback.print_exc(file=sys.stderr) # Print the full traceback
    except instaloader.LoginRequiredException as e:
        update_account_record(account_info.get("id"), "NotLogged")
        print("Error type:", type(e).__name__, file=sys.stderr)
        print("Error message:", str(e), file=sys.stderr)
        traceback.print_exc(file=sys.stderr) # Print the full traceback
    except Exception as e:
        print(f"Thread-{thread_name}: Error during scraping/sending for hashtag #{hashtag_name}: {type(e).__name__}", file=sys.stderr)
        print("Error type:", type(e).__name__, file=sys.stderr)
        print("Error message:", str(e), file=sys.stderr)
        traceback.print_exc(file=sys.stderr) # Print the full traceback

def scrape_followers(L: instaloader.Instaloader,  account_info: Dict[str, Any],  username_target: str, thread_name: str, campaign: str, counter: List[int], lock: threading.Lock):
    """Scrapes followers for a user, sends data to API, and increments counter."""
    items_sent_count = 0
    total_followers_scraped_for_username = 0
    MAX_FOLLOWERS_PER_USERNAME = 1000

    try:
        profile = instaloader.Profile.from_username(L.context, username_target)
        print(f"Thread-{thread_name}: Scraping followers of: {username_target}")

        scraped_accounts = []
        for follower in profile.get_followers():
            scraped_accounts.append({"username": follower.username, "id": follower.userid})
            total_followers_scraped_for_username += 1

            # if total_followers_scraped_for_username >= MAX_FOLLOWERS_PER_USERNAME:
            #     print(f"Thread-{thread_name}: Reached followers limit ({MAX_FOLLOWERS_PER_USERNAME}) for {username_target}.")
            #     break # Stop scraping this username

            if len(scraped_accounts) >= 50:  # Send data in batches of 50
                if send_data_to_api(campaign, scraped_accounts, thread_name):
                    with lock:
                        counter[0] += len(scraped_accounts)
                    items_sent_count += len(scraped_accounts)
                else:
                    print(f"Thread-{thread_name}: Failed to send batch for {username_target}. Stopping scrape for this username.")

                scraped_accounts = []
            #     time.sleep(random.uniform(15, 30))
            # time.sleep(random.uniform(0.5, 2.0))

        
        if scraped_accounts:  # Send remaining data
            if send_data_to_api(campaign, scraped_accounts, thread_name):
                with lock:
                    counter[0] += len(scraped_accounts)
                items_sent_count += len(scraped_accounts)

        print(f"Thread-{thread_name}: Finished scraping followers for {username_target}. Processed {total_followers_scraped_for_username} followers. Successfully sent {items_sent_count} items to API.")
    except instaloader.ProfileNotExistsException:
        print(f"Thread-{thread_name}: Profile {username_target} not found.")
    except instaloader.TooManyRequestsException as e:
        print(f"Thread-{thread_name}: Hit rate limit (TooManyRequestsException) for {username_target}. Stopping scrape for this username.", file=sys.stderr)
        print("Error type:", type(e).__name__, file=sys.stderr)
        print("Error message:", str(e), file=sys.stderr)
        traceback.print_exc(file=sys.stderr) # Print the full traceback
    except (instaloader.QueryReturnedBadRequestException, instaloader.QueryReturnedForbiddenException) as e:
        error_message = str(e)
        if "checkpoint_required" in error_message:
            print(f"Error: Checkpoint required for {account_info.get("username")}. Manual intervention needed.", file=sys.stderr)
            update_account_record(account_info.get("id"), "CheckpointRequired")
        else:
            print(f"Error: Challenge required for {account_info.get("username")}. Manual intervention needed.", file=sys.stderr)
            update_account_record(account_info.get("id"), "ChallengeRequired")
        print("Error type:", type(e).__name__, file=sys.stderr)
        print("Error message:", str(e), file=sys.stderr)
        traceback.print_exc(file=sys.stderr) # Print the full traceback
    except instaloader.exceptions.ConnectionException as e:
        error_message = str(e)
        if "401 Unauthorized" in error_message or "login_required" in error_message:
            print(f"Error: Login required for {account_info.get("username")}.", file=sys.stderr)
            update_account_record(account_info.get("id"), "NotLogged")
        print("Error type:", type(e).__name__, file=sys.stderr)
        print("Error message:", str(e), file=sys.stderr)
        traceback.print_exc(file=sys.stderr) # Print the full traceback
    except instaloader.LoginRequiredException as e:
        update_account_record(account_info.get("id"), "NotLogged")
        print("Error type:", type(e).__name__, file=sys.stderr)
        print("Error message:", str(e), file=sys.stderr)
        traceback.print_exc(file=sys.stderr) # Print the full traceback
    except Exception as e:
        print(f"Thread-{thread_name}: Error during scraping/sending for username {username_target}: {type(e).__name__}", file=sys.stderr)
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
            scrape_hashtag_posts(L, account_info, target, thread_name, campaign, counter, lock)
        elif scrape_type == "Followers":
            scrape_followers(L, account_info, target, thread_name, campaign, counter, lock)
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