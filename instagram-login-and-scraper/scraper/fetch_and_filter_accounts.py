import requests
import sys
import json

def fetch_and_filter_accounts(api_endpoint):
    logged = []
    not_logged = []

    try:
        print("Fetching accounts...")
        response = requests.get(api_endpoint, timeout=10)
        response.raise_for_status()

        accounts_data = response.json()
        print(f"Successfully fetched {len(accounts_data)} accounts.")

        for account in accounts_data:
            if account.get("status") == "Logged":
                logged.append(account)
            elif account.get("status") == "NotLogged":
                not_logged.append(account)

        print(f"Found {len(logged)} logged accounts.")
        for acc in logged:
            print(f"  - Logged: {acc.get('username')}")

        print(f"Found {len(not_logged)} accounts needing login.")
        for acc in not_logged:
            print(f"  - Needs Login: {acc.get('username')}")

        return logged, not_logged

    except requests.exceptions.RequestException as e:
        print(f"Error fetching accounts from API: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error decoding JSON response from API.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred during account fetching: {e}", file=sys.stderr)
        sys.exit(1)