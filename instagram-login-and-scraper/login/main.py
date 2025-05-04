import sys
import requests
import json
import instaloader
import pyotp
from concurrent.futures import ThreadPoolExecutor
import time

API_BASE_URL = "http://localhost:3000"

def get_not_logged_accounts():
    print(f"Fetching not logged accounts...")
    try:
        response = requests.get(f"{API_BASE_URL}/accounts/not-logged", timeout=10)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        accounts = response.json()
        print(f"Successfully fetched {len(accounts)} accounts needing login.")
        return accounts
    except requests.exceptions.RequestException as e:
        print(f"API Error: Failed to fetch not logged accounts: {e}", file=sys.stderr)
        return None
    except json.JSONDecodeError:
        print("API Error: Failed to decode JSON response for not logged accounts.", file=sys.stderr)
        return None

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

def get_2fa_code(secret_key):
    if not secret_key:
        print("Error: 2FA secret key is missing.", file=sys.stderr)
        return None
    try:
        totp = pyotp.TOTP(secret_key)
        return totp.now()
    except Exception as e:
        print(f"Error generating 2FA code: {e}", file=sys.stderr)
        return None

def login_instagram_account(account, proxy):
    username = account.get('username')
    password = account.get('password')
    two_factor_secret = account.get('twoFactorAuthSecret')

    print(f"Processing login for: {username}")
    print(f"Using proxy: {proxy}")

    # Get instance
    L = instaloader.Instaloader()

    # Set proxy for Instaloader
    L.context._session.proxies = {'http': proxy, 'https': proxy}

    try:
        L.login(username, password)
        session_data = L.save_session()
        print(f"Login successful for {username}!")
        return True, session_data, "Logged"
    except instaloader.TwoFactorAuthRequiredException:
        print(f"Thread-{username}: Two-factor authentication required.")

        two_factor_secret = account.get('twoFactorAuthSecret')
        if not two_factor_secret:
            print(f"Thread-{username}: Missing 2FA secret key.", file=sys.stderr)
            return False, None, "TwoFactorAuthFailed"
        
        # Try up to 3 times for 2FA code itself
        for attempt in range(3):
            try:
                two_factor_code = get_2fa_code(two_factor_secret)
                if two_factor_code:
                    print(f"Thread-{username}: Attempting 2FA login (Attempt {attempt + 1}/3)...")
                    L.two_factor_login(two_factor_code)
                    session_data = L.save_session()
                    print(f"Thread-{username}: 2FA login successful!")
                    return True, session_data, "Logged"
                else:
                    # Should not happen if secret exists, but handle defensively
                    print(f"Thread-{username}: Could not generate 2FA code.", file=sys.stderr)
                    return False, None, "TwoFactorAuthFailed"
            except Exception as e:
                print(f"Thread-{username}: Failed 2FA login attempt {attempt + 1}/3.", file=sys.stderr)
                print(f"Thread-{username}: Error type: {type(e).__name__}", file=sys.stderr)
                print(f"Thread-{username}: Error message: {str(e)}", file=sys.stderr)
                if attempt >= 2:
                    print(f"Thread-{username}: All 3 2FA login attempts failed.", file=sys.stderr)
                    return False, None, "TwoFactorAuthFailed"
        return False, None, "TwoFactorAuthFailed"
    except instaloader.BadCredentialsException:
        print("Error: Invalid password.", file=sys.stderr)
        return False, None, "WrongPassword"
    except instaloader.LoginException as e:
        error_message = str(e)
        print(f"LoginException encountered: {error_message}", file=sys.stderr)
        if "Login: Checkpoint required" in error_message:
            print(f"Error: Checkpoint required for {username}. Manual intervention needed.", file=sys.stderr)
            return False, None, "CheckpointRequired"
        else:
             print(f"Error: Username doesn't exist: {username}", file=sys.stderr)
             return False, None, "NotExist"
    except Exception as e:
        print("An unexpected error occurred.", file=sys.stderr)
        print("Error type:", type(e).__name__, file=sys.stderr)
        print("Error message:", str(e), file=sys.stderr)
        return False, None, None 

def process_account_login(account_data):
    account_id = account_data.get('id')
    proxy = account_data.get('proxy').get("proxyUrl")

    # Attempt login
    login_success, session_data, status = login_instagram_account(account_data, proxy)

    # Update database based on login result
    if login_success:
        # Update account status and save session
        if update_account_record(account_id, status, session_data):
            return True # Indicate success
        else:
            return False # Indicate failure during update
    else:
        # Login failed, update only the status
        update_account_record(account_id, status)
        return False

if __name__ == "__main__":
    print("Starting Login Process...")

    # Get accounts needing login
    not_logged_accounts = get_not_logged_accounts()
    if not_logged_accounts is None:
        sys.exit(1)

    if not not_logged_accounts:
        print("No accounts found with status 'NotLogged'. Nothing to do.")
        sys.exit(0)

    num_accounts = len(not_logged_accounts)
    print(f"Starting processing for {num_accounts} accounts using up to {num_accounts} workers...")

    start_time = time.time()
    results = []

    # Use ThreadPoolExecutor for managing threads
    with ThreadPoolExecutor(max_workers=num_accounts) as executor:
        results = list(executor.map(process_account_login, not_logged_accounts))

    end_time = time.time()
    duration = end_time - start_time

    # Calculate final counts based on the boolean results from the workers
    number_of_successful_logins = sum(1 for r in results if r is True)
    number_of_failed_logins = num_accounts - number_of_successful_logins

    print("\n--- Login Process Finished ---")
    print(f"Total accounts processed: {num_accounts}")
    print(f"Successful logins: {number_of_successful_logins}")
    print(f"Failed logins: {number_of_failed_logins}")
    print(f"Total execution time: {duration:.2f} seconds")