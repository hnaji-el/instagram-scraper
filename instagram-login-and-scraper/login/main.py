import sys
import requests
from requests.auth import HTTPBasicAuth
import json
import instaloader
import pyotp
from concurrent.futures import ThreadPoolExecutor
import time

API_BASE_URL = "http://localhost:3000"
# --- DataImpulse Configuration ---
DATAIMPULSE_API_URL = "https://gw.dataimpulse.com:777/api/list"
DATAIMPULSE_USERNAME = "ae74129a8d9b7bab7adf"
DATAIMPULSE_PASSWORD = "a5fe7ce00ec06c0d"

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

def fetch_new_dataimpulse_proxy():
    print("Attempting to fetch a new proxy from DataImpulse...")
    params = {
        'countries': 'de',
        'type': 'sticky',
        'protocol': 'socks5',
        'format': 'socks5://login:password@hostname:port',
        'quantity': 1
    }
    try:
        response = requests.get(
            DATAIMPULSE_API_URL,
            params=params,
            auth=HTTPBasicAuth(DATAIMPULSE_USERNAME, DATAIMPULSE_PASSWORD),
            timeout=15
        )
        response.raise_for_status()

        if response.status_code == 200 and 'text/plain' in response.headers.get('Content-Type', ''):
            proxy_string = response.text.strip()
            if not proxy_string:
                 print("DataImpulse API Error: Received empty response.", file=sys.stderr)
                 return None, None

            # Split the string: "socks5://user:pass@host:port" -> ["socks5://user:pass@host", "port"]
            try:
                url_part, port_part = proxy_string.rsplit(':', 1)
                port = int(port_part)
                print(f"Successfully fetched and parsed new proxy: PROXY_URL={url_part}, PROXY_PORT={port}")
                return port, url_part
            except (ValueError, IndexError) as parse_error:
                print(f"DataImpulse API Error: Failed to parse proxy string '{proxy_string}': {parse_error}", file=sys.stderr)
                return None, None
        else:
            print(f"DataImpulse API Error: Unexpected status code {response.status_code} or content type {response.headers.get('Content-Type')}", file=sys.stderr)
            return None, None

    except requests.exceptions.RequestException as e:
        print(f"DataImpulse API Error: Failed to fetch new proxy: {e}", file=sys.stderr)
        return None, None

def get_proxy_details():
    print(f"Fetching proxy with the max port from {API_BASE_URL}/proxies/max-port...")
    try:
        response = requests.get(f"{API_BASE_URL}/proxies/max-port", timeout=10)
        response.raise_for_status()
        data = response.json()

        max_proxy_port = data.get('maxProxyPort')
        proxy_url_raw = data.get('proxyUrl')

        proxy_url = None
        if proxy_url_raw:
            proxy_url = proxy_url_raw.rsplit(':', 1)[0]

        if max_proxy_port is not None and proxy_url is not None:
            print(f"Successfully fetched existing max proxy details: Port={max_proxy_port}, URL={proxy_url}")
            return True, max_proxy_port + 1, proxy_url
        elif max_proxy_port is None and proxy_url is None:
            print("No proxies found locally. Attempting to fetch from DataImpulse...")
            proxy_port_, proxy_url_ = fetch_new_dataimpulse_proxy()
            if proxy_port_ is not None and proxy_url_ is not None:
                return True, proxy_port_, proxy_url_
            else:
                print("Failed to obtain a new proxy from DataImpulse.", file=sys.stderr)
                return False, None, None
        else:
            print(f"Warning: Inconsistent proxy details received from local API. PORT={max_proxy_port}, PROXY_URL={proxy_url_raw}", file=sys.stderr)
            return False, None, None
    except requests.exceptions.RequestException as e:
        print(f"API Error: Failed to fetch max proxy details: {e}", file=sys.stderr)
        return False, None, None
    except json.JSONDecodeError:
        print("API Error: Failed to decode JSON response for max proxy details.", file=sys.stderr)
        return False, None, None
    except KeyError as e:
        print(f"API Error: Key '{e}' not found in the response.", file=sys.stderr)
        return False, None, None

def create_proxy_record(proxy_url, proxy_port):
    payload = {"proxyUrl": proxy_url, "proxyPort": proxy_port}

    try:
        response = requests.post(f"{API_BASE_URL}/proxy", json=payload, timeout=10)
        if response.status_code == 409:
             print(f"Proxy {proxy_url} already exists (Conflict 409).")
             return None
        response.raise_for_status()
        proxy_data = response.json()

        proxy_id = proxy_data.get('id')
        print(f"Successfully created proxy record with ID: {proxy_id}")
        return proxy_id
    except requests.exceptions.RequestException as e:
        print(f"API Error creating proxy record: {e}", file=sys.stderr)
        return None
    except json.JSONDecodeError:
        print("API Error: Failed to decode JSON response when creating proxy.", file=sys.stderr)
        return None

def update_account_record(account_id, status, proxy_id=None, session_data=None):
    payload = {"status": status}

    if proxy_id:
        payload["proxyId"] = proxy_id
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

def login_instagram_account(account, proxy_url):
    username = account.get('username')
    password = account.get('password')
    two_factor_secret = account.get('twoFactorAuthSecret')

    print(f"Processing login for: {username}")
    print(f"Using proxy: {proxy_url}")

    # Get instance
    L = instaloader.Instaloader()

    # Set proxy for Instaloader
    L.context._session.proxies = {'http': proxy_url, 'https': proxy_url}

    try:
        L.login(username, password)
        session_data = L.save_session()
        print(f"Login successful for {username}!")
        return True, session_data, "Logged"
    except instaloader.TwoFactorAuthRequiredException:
        print("Two-factor authentication required.")
        try:
            # Generate the 2FA code using the secret key
            two_factor_code = get_2fa_code(two_factor_secret)
            if two_factor_code:
                L.two_factor_login(two_factor_code)
                session_data = L.save_session()
                print(f"2FA login successful for {username}!")
                return True, session_data, "Logged"
            else:
                print("Could not generate 2FA code (missing secret?).", file=sys.stderr)
                return False, None, "TwoFactorAuthFailed"
        except Exception as e:
            print("Failed to complete 2FA login.", file=sys.stderr)
            print("Error type:", type(e).__name__, file=sys.stderr)
            print("Error message:", str(e), file=sys.stderr)
            return False, None, "TwoFactorAuthFailed"
    except instaloader.BadCredentialsException:
        print("Error: Invalid password.", file=sys.stderr)
        return False, None, "WrongPassword"
    except instaloader.LoginException as e:
        error_message = str(e)
        print(f"LoginException encountered: {error_message}", file=sys.stderr)
        if "Login: Checkpoint required" in error_message:
            print(f"Error: Checkpoint required for {username}. Manual intervention needed.", file=sys.stderr)
            return False, None, "VerificationRequired"
        else:
             print(f"Error: Username doesn't exist: {username}", file=sys.stderr)
             return False, None, "NotExist"
    except Exception as e:
        print("An unexpected error occurred.", file=sys.stderr)
        print("Error type:", type(e).__name__, file=sys.stderr)
        print("Error message:", str(e), file=sys.stderr)
        return False, None, None 

def process_account_login(account_data_tuple):
    account, proxy_port, proxy_url = account_data_tuple

    account_id = account.get('id')
    username = account.get('username')

    full_proxy_string = f"{proxy_url}:{proxy_port}"

    # Attempt login
    login_success, session_data, status = login_instagram_account(account, full_proxy_string)

    # Update database based on login result
    if login_success:
        # Create proxy record for the *successfully used* port
        proxy_id = create_proxy_record(full_proxy_string, proxy_port)
        # Update account status, link proxy (if created), save session
        if update_account_record(account_id, status, proxy_id, session_data):
            return True # Indicate success
        else:
            return False # Indicate failure during update
    else:
        # Login failed, update only the status
        update_account_record(account_id, status)
        return False

if __name__ == "__main__":
    print("Starting Login Script...")

    # Get accounts needing login
    not_logged_accounts = get_not_logged_accounts()
    if not_logged_accounts is None:
        sys.exit(1)

    if not not_logged_accounts:
        print("No accounts found with status 'NotLogged'. Nothing to do.")
        sys.exit(0)

    # Get proxy details
    success, proxy_port, proxy_url = get_proxy_details()
    if not success:
        sys.exit(1)

    print("Starting Login Process...")

    # Prepare data for workers: List of (account, proxy_port, proxy_url) tuples
    accounts_with_proxies = []
    for i, account in enumerate(not_logged_accounts):
        accounts_with_proxies.append((account, proxy_port + i, proxy_url))

    num_accounts = len(not_logged_accounts)
    print(f"Starting processing for {num_accounts} accounts using up to {num_accounts} workers...")

    start_time = time.time()
    results = []

    # Use ThreadPoolExecutor for managing threads
    with ThreadPoolExecutor(max_workers=num_accounts) as executor:
        results = list(executor.map(process_account_login, accounts_with_proxies))

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