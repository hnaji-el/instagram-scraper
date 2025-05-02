import requests
import json
import sys
from typing import List

API_BASE_URL = "http://localhost:3000"

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
