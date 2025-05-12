# TCM
TCM (Twitch Clip Monitor) is a Python-based utility designed to monitor a specified Twitch channel for new clip uploads. Upon detection, it dispatches a Discord Webhook notification that includes a direct URL to the newly available clip.

## Features

*   Monitors a specific Twitch channel for new clips.
*   Fetches clips created within a configurable recent time window (lookback period).
*   Posts notifications to a Discord channel using a webhook.
*   Includes clip title, creator, and URL in the notification.
*   Avoids sending duplicate notifications for the same clip, even across script restarts (within the lookback window on startup).
*   Handles Twitch API App Access Token acquisition and automatic refresh on expiry (detects 401 errors).
*   Configurable check interval.

## Prerequisites

*   **Python 3.x**
*   **`requests` library:** Install using pip:
    ```bash
    pip install requests
    ```
*   **Twitch Developer Application:** You need a Client ID and Client Secret.
    *   Go to the [Twitch Developer Console](https://dev.twitch.tv/console).
    *   Register a new application (type "Chat Bot" or "Other" is fine).
    *   Note down the **Client ID** and generate/note down a **Client Secret**. *Keep your Client Secret confidential!*
*   **Discord Webhook URL:**
    *   Go to your Discord Server Settings -> Integrations -> Webhooks -> New Webhook.
    *   Configure the webhook (name, channel).
    *   Copy the **Webhook URL**. *Keep this URL secure, as anyone with it can post messages to that channel.*

## Setup & Configuration

1.  **Clone or Download:** Get the `clip.py` and `config.py` files.
2.  **Install Dependencies:**
    ```bash
    pip install requests
    ```
3.  **Configure `config.py`:**
    Open the `config.py` file and replace the placeholder values with your actual credentials and desired settings:

    ```python
    # Twitch API Credentials (Get from https://dev.twitch.tv/console)
    TWITCH_CLIENT_ID = "YOUR_TWITCH_CLIENT_ID_HERE"  # Replace with your Client ID
    TWITCH_CLIENT_SECRET = "YOUR_TWITCH_CLIENT_SECRET_HERE" # Replace with your Client Secret

    # Target Twitch Channel
    TWITCH_CHANNEL_NAME = "TWITCH_CHANNEL_NAME_HERE" # Replace with the channel's Twitch login name (e.g., "twitchdev")

    # Discord Webhook URL (Get from Server Settings -> Integrations -> Webhooks)
    DISCORD_WEBHOOK_URL = "YOUR_DISCORD_WEBHOOK_URL_HERE" # Replace with your webhook URL

    # --- Script Settings ---

    # How often (in seconds) to check for new clips.
    # Be mindful of Twitch API rate limits. Values between 30-300 are reasonable.
    CHECK_INTERVAL_SECONDS = 30 # Default: 30 seconds (check every half minute)

    # How far back (in minutes) to look for clips each check.
    # This helps catch clips created between checks. Should be slightly larger than CHECK_INTERVAL_SECONDS / 60.
    # Also determines the initial scan window on script start to avoid spamming old clips.
    CLIP_LOOKBACK_MINUTES = 2 # Default: 2 minutes
    ```

    *   **`TWITCH_CLIENT_ID`**: Your application's Client ID from the Twitch Dev Console.
    *   **`TWITCH_CLIENT_SECRET`**: Your application's Client Secret from the Twitch Dev Console.
    *   **`TWITCH_CHANNEL_NAME`**: The *login name* (the part in the twitch.tv/ URL) of the channel you want to monitor (e.g., `shroud`, `criticalrole`). Case-insensitive but usually lowercase.
    *   **`DISCORD_WEBHOOK_URL`**: The full webhook URL you copied from Discord.
    *   **`CHECK_INTERVAL_SECONDS`**: How frequently (in seconds) the script queries the Twitch API. Lower values mean faster notifications but higher API usage. (Default: 30)
    *   **`CLIP_LOOKBACK_MINUTES`**: When checking, how many minutes into the past should the script look for clips created? This ensures clips made just before a check are caught. It's also used on startup to "prime" the list of known clips, preventing notifications for clips created just before the script started (within this window). (Default: 2)

## Running the Script

1.  Navigate to the directory containing `clip.py` and `config.py` in your terminal.
2.  Run the script using Python:
    ```bash
    python clip.py
    ```
3.  The script will start, log its actions to the console, and run continuously, checking for new clips at the specified interval.

    *   It will first get a Twitch token and the broadcaster ID.
    *   Then, it performs an initial scan for clips within the `CLIP_LOOKBACK_MINUTES` window to populate its list of already-seen clips.
    *   After that, it enters the main loop, checking periodically and sending Discord notifications for any *new* clips found.


## How it Works

1.  **Initialization:**
    *   Reads configuration from `config.py`.
    *   Obtains a Twitch API App Access Token using the provided Client ID and Secret.
    *   Fetches the numerical Broadcaster ID associated with the `TWITCH_CHANNEL_NAME`.
    *   Performs an initial query for clips created within the `CLIP_LOOKBACK_MINUTES` window and stores their IDs in `sent_clip_ids`. This prevents spamming old clips upon script restart.
2.  **Main Loop:**
    *   Waits for `CHECK_INTERVAL_SECONDS`.
    *   Ensures the Twitch Access Token is still valid (or refreshes it if a 401 error occurred previously).
    *   Queries the Twitch API's `/clips` endpoint for clips created by the target broadcaster within the last `CLIP_LOOKBACK_MINUTES`.
    *   Iterates through the fetched clips.
    *   For each clip, it checks if its ID is already in the `sent_clip_ids` set.
    *   If the clip ID is *not* found in the set:
        *   It sends a formatted notification message containing the clip's title and URL to the configured `DISCORD_WEBHOOK_URL`.
        *   It adds the clip's ID to the `sent_clip_ids` set to prevent future notifications for this clip.
    *   Logs actions (fetching clips, finding new clips, sending notifications, errors) to the console.
    *   Repeats the loop.

## License

This project is likely intended for personal use. If distributing, consider adding a license file (e.g., MIT License).
