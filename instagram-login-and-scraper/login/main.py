import sys
import requests
from requests.auth import HTTPBasicAuth
import json
import os
import instaloader
import pyotp

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
                new_port = int(port_part)
                print(f"Successfully fetched and parsed new proxy: URL={url_part}, Port={new_port}")
                return url_part, new_port
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
    print(f"Fetching max proxy details from {API_BASE_URL}/proxies/max-port...")
    try:
        response = requests.get(f"{API_BASE_URL}/proxies/max-port", timeout=10)
        response.raise_for_status()
        data = response.json()

        max_proxy_port = data.get('maxProxyPort')
        proxy_url = data.get('proxyUrl')

        if max_proxy_port is not None and proxy_url is not None:
            print(f"Successfully fetched existing max proxy details: Port={max_proxy_port}, URL={proxy_url}")
            return True, max_proxy_port + 1, proxy_url
        elif max_proxy_port is None and proxy_url is None:
            print("No proxies found locally. Attempting to fetch from DataImpulse...")
            new_url, new_port = fetch_new_dataimpulse_proxy()
            if new_url is not None and new_port is not None:
                return True, new_port, new_url
            else:
                print("Failed to obtain a new proxy from DataImpulse.", file=sys.stderr)
                return False, None, None
        else:
             return False, None, None # Treat inconsistent data as failure
    except requests.exceptions.RequestException as e:
        print(f"Local API Error: Failed to fetch max proxy details: {e}", file=sys.stderr)
        return False, None, None
    except json.JSONDecodeError:
        print("Local API Error: Failed to decode JSON response for max proxy details.", file=sys.stderr)
        return False, None, None
    except KeyError as e:
        print(f"Local API Error: Key '{e}' not found in the response.", file=sys.stderr)
        return False, None, None

# Main execution part
if __name__ == "__main__":
    print("Starting Login Script...")

    # Get accounts needing login
    not_logged_accounts = get_not_logged_accounts()
    if not_logged_accounts is None:
        sys.exit(1)

    if not not_logged_accounts:
        print("No accounts found with status 'NotLogged'. Nothing to do.")
        sys.exit(0)

    # Get max proxy details
    success, new_proxy_port, proxy_url = get_proxy_details()
    if not success:
        sys.exit(1)

    print("\n--- Data Fetched ---")
    print(f"Accounts to process: {len(not_logged_accounts)}")
    print(f"Maximum proxy port found in DB: {new_proxy_port}")
    print(f"URL for max proxy port: {proxy_url}")

    # --- Placeholder for next steps ---
    print("\n--- Starting Login Process (Placeholder) ---")
    # TODO: Iterate through not_logged_accounts and attempt login using instaloader
    # You would use the login_instagram_account function developed earlier,
    # passing each account dictionary from the not_logged_accounts list.
    # You might also use the max_proxy_port if your logic involves assigning ports.

    # Example loop structure:
    # successful_logins = 0
    # for account in not_logged_accounts:
    #     print(f"\nProcessing login for: {account.get('username')}")
    #     # instance = login_instagram_account(account) # Assuming this function exists and uses API updates
    #     # if instance:
    #     #     successful_logins += 1
    #     #     print(f"Login successful for {account.get('username')}")
    #     # else:
    #     #     print(f"Login failed for {account.get('username')}")
    #     pass # Replace with actual login call

    # print(f"\n--- Login Process Finished ---")
    # print(f"Successfully logged in {successful_logins} out of {len(not_logged_accounts)} accounts.")


# --- Keep existing commented-out code or functions below if needed ---
# ... (rest of your existing code like validate_proxy, get_2fa_code, etc.) ...




# login step: NotLogged
# verification step: Blocked | VerificationRequired
# ... (rest of your existing code) ...

# login step: NotLogged
# verification step: Blocked | VerificationRequired

# Specify the folder for session files
# session_folder = "sessions"
# os.makedirs(session_folder, exist_ok=True)  # Create the folder if it doesn't exist
# 
# 
# proxy_url = "http://ae74129a8d9b7bab7adf:a5fe7ce00ec06c0d@gw.dataimpulse.com:823"
# secret_key = "SHQFBBJRBVH6OHMGQ34SHZ2PROJGTI7I"
# username = "yecokex184"  # Replace with your Instagram username
# password = "xiCYVkb6vp"  # Replace with your Instagram password
# session_file = os.path.join(session_folder, f"{username}_session")
# 
# def validate_proxy(proxy_url):
#     test_url = "https://www.instagram.com"
#     proxies = {'http': proxy_url, 'https': proxy_url}
#     try:
#         response = requests.get(test_url, proxies=proxies, timeout=5)
#         if response.status_code == 200:
#             print("Proxy is valid and working.")
#             return True
#         else:
#             print(f"Proxy test failed with status code: {response.status_code}")
#             return False
#     except requests.exceptions.RequestException as e:
#         print(f"Proxy test failed: {e}")
#         return False
# 
# # Function to generate 2FA code
# def get_2fa_code(secret_key):
#     totp = pyotp.TOTP(secret_key)
#     return totp.now()
# 
# # Function to scrape posts associated with a hashtag
# def scrape_hashtag_posts(L, hashtag_name):
#     try:
#         hashtag = instaloader.Hashtag.from_name(L.context, hashtag_name)
#         print(f"Scraping posts for hashtag: #{hashtag_name}")
# 
#         # Iterate through posts associated with the hashtag
#         for post in hashtag.get_all_posts():
#             user_id = post.owner_id
#             username = post.owner_profile.username
#             print(f"Username: {username}, User ID: {user_id}")
# 
#             # Optionally, you can save this data to a file or database
#             # For now, we just print it to the console
#     except instaloader.QueryReturnedNotFoundException:
#         print(f"there is no hashtag with the this name {hashtag_name}")
# 
# # Function to scrape posts associated with a hashtag
# def scrape_followers(L, username):
#     try:
#         profile = instaloader.Profile.from_username(L.context, username)
#         print(f"Scraping followers of: #{username}")
# 
#         for follower in profile.get_followers():
#             user_id = follower.userid
#             username = follower.username
#             print(f"Username: {username}, User ID: {user_id}")
# 
#             # Optionally, you can save this data to a file or database
#             # For now, we just print it to the console
#     except instaloader.ProfileNotExistsException:
#         print(f"there is no profile with the this username {username}")
# 
# # Validate proxy before proceeding
# if validate_proxy(proxy_url):
#     # Get instance
#     L = instaloader.Instaloader()
# 
#     # Set proxy for Instaloader
#     L.context._session.proxies = {'http': proxy_url, 'https': proxy_url}
# 
#     try:
#         # Attempt to load session
#         L.load_session_from_file(username, filename=session_file)
#         print("Session loaded successfully!")
#     except FileNotFoundError:
#         print("Session does not exist. Logging in again.")
#         try:
#             L.login(username, password)
#             print("Login successful!")
#             # Save session to file
#             L.save_session_to_file(filename=session_file)
#             print(f"Session saved to {session_file}")
#         except instaloader.exceptions.TwoFactorAuthRequiredException:
#             print("Two-factor authentication required.")
#             try:
#                 # Generate the 2FA code using the secret key
#                 two_factor_code = get_2fa_code(secret_key)
#                 print(f"Generated 2FA code: {two_factor_code}")
#                 L.two_factor_login(two_factor_code)
#                 print("2FA login successful!")
#                 # Save session to file
#                 L.save_session_to_file(filename=session_file)
#                 print(f"Session saved to {session_file}")
#             except Exception as e:
#                 print("Failed to complete 2FA login.")
#                 print("Error type:", type(e).__name__)
#                 print("Error message:", str(e))
#         except instaloader.exceptions.BadCredentialsException:
#             print("Error: Invalid username or password.")
#         except instaloader.exceptions.ConnectionException:
#             print("Error: Unable to connect. Check your internet or proxy settings.")
#         except Exception as e:
#             print("An unexpected error occurred.")
#             print("Error type:", type(e).__name__)
#             print("Error message:", str(e))
# else:
#     print("Proxy is not valid. Please check your proxy settings.")