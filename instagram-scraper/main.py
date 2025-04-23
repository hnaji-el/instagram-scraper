import instaloader
import requests
import pyotp
import os

# Specify the folder for session files
session_folder = "sessions"
os.makedirs(session_folder, exist_ok=True)  # Create the folder if it doesn't exist


proxy_url = "http://ae74129a8d9b7bab7adf:a5fe7ce00ec06c0d@gw.dataimpulse.com:823"
secret_key = "SHQFBBJRBVH6OHMGQ34SHZ2PROJGTI7I"
username = "yecokex184"  # Replace with your Instagram username
password = "xiCYVkb6vp"  # Replace with your Instagram password
session_file = os.path.join(session_folder, f"{username}_session")

def validate_proxy(proxy_url):
    test_url = "https://www.instagram.com"
    proxies = {'http': proxy_url, 'https': proxy_url}
    try:
        response = requests.get(test_url, proxies=proxies, timeout=5)
        if response.status_code == 200:
            print("Proxy is valid and working.")
            return True
        else:
            print(f"Proxy test failed with status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"Proxy test failed: {e}")
        return False

# Function to generate 2FA code
def get_2fa_code(secret_key):
    totp = pyotp.TOTP(secret_key)
    return totp.now()

# Function to scrape posts associated with a hashtag
def scrape_hashtag_posts(L, hashtag_name):
    try:
        hashtag = instaloader.Hashtag.from_name(L.context, hashtag_name)
        print(f"Scraping posts for hashtag: #{hashtag_name}")

        # Iterate through posts associated with the hashtag
        for post in hashtag.get_all_posts():
            user_id = post.owner_id
            username = post.owner_profile.username
            print(f"Username: {username}, User ID: {user_id}")

            # Optionally, you can save this data to a file or database
            # For now, we just print it to the console
    except instaloader.QueryReturnedNotFoundException:
        print(f"there is no hashtag with the this name {hashtag_name}")

# Function to scrape posts associated with a hashtag
def scrape_followers(L, username):
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        print(f"Scraping followers of: #{username}")

        for follower in profile.get_followers():
            user_id = follower.userid
            username = follower.username
            print(f"Username: {username}, User ID: {user_id}")

            # Optionally, you can save this data to a file or database
            # For now, we just print it to the console
    except instaloader.ProfileNotExistsException:
        print(f"there is no profile with the this username {username}")

# Validate proxy before proceeding
if validate_proxy(proxy_url):
    # Get instance
    L = instaloader.Instaloader()

    # Set proxy for Instaloader
    L.context._session.proxies = {'http': proxy_url, 'https': proxy_url}

    try:
        # Attempt to load session
        L.load_session_from_file(username, filename=session_file)
        print("Session loaded successfully!")
    except FileNotFoundError:
        print("Session does not exist. Logging in again.")
        try:
            L.login(username, password)
            print("Login successful!")
            # Save session to file
            L.save_session_to_file(filename=session_file)
            print(f"Session saved to {session_file}")
        except instaloader.exceptions.TwoFactorAuthRequiredException:
            print("Two-factor authentication required.")
            try:
                # Generate the 2FA code using the secret key
                two_factor_code = get_2fa_code(secret_key)
                print(f"Generated 2FA code: {two_factor_code}")
                L.two_factor_login(two_factor_code)
                print("2FA login successful!")
                # Save session to file
                L.save_session_to_file(filename=session_file)
                print(f"Session saved to {session_file}")
            except Exception as e:
                print("Failed to complete 2FA login.")
                print("Error type:", type(e).__name__)
                print("Error message:", str(e))
        except instaloader.exceptions.BadCredentialsException:
            print("Error: Invalid username or password.")
        except instaloader.exceptions.ConnectionException:
            print("Error: Unable to connect. Check your internet or proxy settings.")
        except Exception as e:
            print("An unexpected error occurred.")
            print("Error type:", type(e).__name__)
            print("Error message:", str(e))
else:
    print("Proxy is not valid. Please check your proxy settings.")

# log in
# get all { username: xxx, userid: xxx} associated with a hashtag
# get list of followers of given profile

# instagram_email      |password  |2fa_key                                |profile_link
# yecokex184@venfee.com|xiCYVkb6vp|SHQFBBJRBVH6OHMGQ34SHZ2PROJGTI7I|instagram.com/yecokex184
# royawa3572@venfee.com|ErUbPTsoPM|XTG6LKRKUTDRB2KU42MZ56ZOESFYYVEY|instagram.com/royawa3572

# Optionally, login or load session
#L.login(USER, PASSWORD)        # (login)
#L.interactive_login(USER)      # (ask password on terminal)
#L.load_session_from_file(USER) # (load session created w/
                               #  `instaloader -l USERNAME`)

#
# L = Instaloader()
# for post in L.get_hashtag_posts(HASHTAG):
#     L.download_post(post, target='#'+HASHTAG)
#

# L = Instaloader()
# profile = Profile.from_username(L.context, USERNAME)
# 
# print("{} follows these profiles:".format(profile.username))
# for followee in profile.get_followees():
#     print(followee.username)