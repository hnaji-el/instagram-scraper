import sys
import json

def check_arguments():
    if len(sys.argv) == 4:
        campaign_name = sys.argv[1]
        targets_json = sys.argv[2]
        scrape_type = sys.argv[3]

        try:
            targets = json.loads(targets_json)
            if not isinstance(targets, list): # Check if targets is a list
                raise ValueError("Targets argument must be a JSON list.")
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error: Invalid format for targets argument: {targets_json}", file=sys.stderr)
            print(f"Details: {e}", file=sys.stderr)
            sys.exit(1)

        print(f"Received Campaign Name: {campaign_name}")
        print(f"Received Targets: {targets}")
        print(f"Received Type: {scrape_type}")
        return campaign_name, targets, scrape_type
    else:
        print(f"Error: Incorrect number of arguments provided", file=sys.stderr)
        print(f"Expected 4 arguments, but received {len(sys.argv)}.", file=sys.stderr)
        print("Usage: python3 <script_path> <campaign_name> <targets_json_string> <scrape_type>", file=sys.stderr)
        sys.exit(1)