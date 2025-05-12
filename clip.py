import requests
import time
import datetime
import logging
from config import (
    TWITCH_CLIENT_ID,
    TWITCH_CLIENT_SECRET,
    TWITCH_CHANNEL_NAME,
    DISCORD_WEBHOOK_URL,
    CHECK_INTERVAL_SECONDS,
    CLIP_LOOKBACK_MINUTES
)

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Global Variables ---
TWITCH_API_BASE_URL = "https://api.twitch.tv/helix"
TWITCH_AUTH_URL = "https://id.twitch.tv/oauth2/token"
broadcaster_id_cache = None
access_token_cache = None
sent_clip_ids = set() # To keep track of clips already sent

# --- Twitch API Functions ---
def get_twitch_access_token():
    """Obtains a Twitch API access token."""
    global access_token_cache
    if access_token_cache: # Basic caching, real app might check expiry
        return access_token_cache

    params = {
        "client_id": TWITCH_CLIENT_ID,
        "client_secret": TWITCH_CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    try:
        response = requests.post(TWITCH_AUTH_URL, params=params)
        response.raise_for_status()
        access_token_cache = response.json()["access_token"]
        logging.info("Successfully obtained Twitch access token.")
        return access_token_cache
    except requests.exceptions.RequestException as e:
        logging.error(f"Error getting Twitch access token: {e}")
        if response:
            logging.error(f"Response content: {response.text}")
        return None
    except KeyError:
        logging.error(f"Error parsing access token response: {response.text}")
        return None

def get_broadcaster_id(channel_name, access_token):
    """Gets the Twitch User ID for a given channel name."""
    global broadcaster_id_cache
    if broadcaster_id_cache:
        return broadcaster_id_cache

    if not access_token:
        logging.error("Cannot get broadcaster ID without access token.")
        return None

    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {access_token}"
    }
    params = {"login": channel_name}
    try:
        response = requests.get(f"{TWITCH_API_BASE_URL}/users", headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        if data["data"]:
            broadcaster_id_cache = data["data"][0]["id"]
            logging.info(f"Found broadcaster ID for {channel_name}: {broadcaster_id_cache}")
            return broadcaster_id_cache
        else:
            logging.error(f"Could not find broadcaster ID for channel: {channel_name}")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error getting broadcaster ID for {channel_name}: {e}")
        if response:
            logging.error(f"Response content: {response.text}")
        return None
    except (KeyError, IndexError):
        logging.error(f"Error parsing broadcaster ID response: {response.text}")
        return None


def get_recent_clips(broadcaster_id, access_token, lookback_minutes=10):
    """Fetches recent clips for a broadcaster."""
    if not access_token or not broadcaster_id:
        logging.error("Cannot get clips without access token or broadcaster ID.")
        return []

    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {access_token}"
    }
    # Calculate time window for fetching clips
    end_time = datetime.datetime.utcnow()
    start_time = end_time - datetime.timedelta(minutes=lookback_minutes)
    
    # Format times to RFC3339, which Twitch API expects
    # Example: 2023-10-27T10:00:00Z
    started_at_str = start_time.isoformat("T") + "Z"
    # ended_at_str = end_time.isoformat("T") + "Z" # ended_at is optional, using only started_at is fine

    params = {
        "broadcaster_id": broadcaster_id,
        "started_at": started_at_str,
        # "ended_at": ended_at_str, # Optional
        "first": 20  # Get up to 20 clips, adjust if needed
    }
    try:
        response = requests.get(f"{TWITCH_API_BASE_URL}/clips", headers=headers, params=params)
        if response.status_code == 401: # Unauthorized, token might be expired
            logging.warning("Twitch API returned 401, attempting to refresh token.")
            global access_token_cache
            access_token_cache = None # Clear cache to force re-fetch
            new_token = get_twitch_access_token()
            if new_token:
                headers["Authorization"] = f"Bearer {new_token}"
                response = requests.get(f"{TWITCH_API_BASE_URL}/clips", headers=headers, params=params)
            else:
                logging.error("Failed to refresh token, cannot fetch clips.")
                return []

        response.raise_for_status()
        data = response.json()
        return data.get("data", [])
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching clips: {e}")
        if response:
            logging.error(f"Response content: {response.text}")
        return []
    except KeyError:
        logging.error(f"Error parsing clips response: {response.text}")
        return []

# --- Discord Webhook Function ---
def send_discord_notification(webhook_url, clip_url, clip_title, channel_name):
    """Sends a notification to Discord via webhook."""
    message = f"🎬 New clip from **{channel_name}**!\n**{clip_title}**\n{clip_url}"
    payload = {"content": message}
    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        logging.info(f"Successfully sent clip to Discord: {clip_url}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error sending notification to Discord: {e}")
        if response:
            logging.error(f"Response content: {response.text}")

# --- Main Loop ---
def main():
    logging.info("Starting Twitch Clip Monitor...")

    # Initial token and broadcaster ID fetch
    token = get_twitch_access_token()
    if not token:
        logging.critical("Failed to get initial access token. Exiting.")
        return

    broadcaster_id = get_broadcaster_id(TWITCH_CHANNEL_NAME, token)
    if not broadcaster_id:
        logging.critical(f"Failed to get broadcaster ID for {TWITCH_CHANNEL_NAME}. Exiting.")
        return

    # Populate sent_clip_ids with clips from the last `CLIP_LOOKBACK_MINUTES` on first run
    # so we don't spam with old clips if the script restarts.
    logging.info(f"Performing initial clip scan for the last {CLIP_LOOKBACK_MINUTES} minutes to prime known clips...")
    initial_clips = get_recent_clips(broadcaster_id, token, lookback_minutes=CLIP_LOOKBACK_MINUTES)
    for clip in initial_clips:
        sent_clip_ids.add(clip['id'])
    logging.info(f"Primed {len(sent_clip_ids)} clips. Monitoring for new ones.")


    while True:
        try:
            logging.info(f"Checking for new clips for {TWITCH_CHANNEL_NAME}...")
            
            # Refresh token if needed (basic check, or rely on 401 handling in get_recent_clips)
            # For app access tokens, they last long, so explicit refresh here might be overkill
            # unless the script runs for many days/weeks.
            # The 401 handling in get_recent_clips is more robust.
            current_token = get_twitch_access_token() # ensures we have a valid token
            if not current_token:
                logging.error("Failed to get access token. Skipping this check cycle.")
                time.sleep(CHECK_INTERVAL_SECONDS)
                continue

            clips = get_recent_clips(broadcaster_id, current_token, lookback_minutes=CLIP_LOOKBACK_MINUTES)
            
            if not clips:
                logging.info("No clips found in the lookback window.")
            else:
                new_clips_found = 0
                for clip in reversed(clips): # Process older clips first if multiple found
                    if clip['id'] not in sent_clip_ids:
                        clip_url = clip['url']
                        clip_title = clip['title']
                        logging.info(f"New clip found: {clip_title} - {clip_url}")
                        send_discord_notification(DISCORD_WEBHOOK_URL, clip_url, clip_title, TWITCH_CHANNEL_NAME)
                        sent_clip_ids.add(clip['id'])
                        new_clips_found += 1
                        time.sleep(1) # Small delay to avoid Discord rate limits if many clips found at once
                if new_clips_found == 0:
                    logging.info("No *new* clips found (all fetched clips already sent).")
        
        except Exception as e:
            logging.error(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
        
        logging.info(f"Waiting for {CHECK_INTERVAL_SECONDS // 60} minutes before next check...")
        time.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    if not all([TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET, TWITCH_CHANNEL_NAME, DISCORD_WEBHOOK_URL]):
        logging.critical("One or more configuration variables are missing in config.py. Please fill them out.")
    elif "YOUR_" in TWITCH_CLIENT_ID or "YOUR_" in TWITCH_CLIENT_SECRET or "YOUR_" in DISCORD_WEBHOOK_URL or "target_twitch_channel_name" == TWITCH_CHANNEL_NAME:
        logging.critical("Placeholder values detected in config.py. Please replace them with your actual credentials and channel name.")
    else:
        main()