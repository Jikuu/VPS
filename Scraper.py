import json
import time
import requests
import MySQLdb
import xml.etree.ElementTree as ET
from datetime import datetime

# === Discord webhook config ===
#WEBHOOK_URL = "https://discord.com/api/webhooks/XXXXXX/XXXXXXXX"  # Replace with your real webhook URL
WEBHOOK_URL = "https://discord.com/api/webhooks/1400993852994879548/12aIplK569bSRMod_q-4i3j1U60nRgPIlM7ZZdeKyVnZBY9laLYaRJdUCK_6EqtEuzqA" # Replace this with your real webhook URL

def send_discord_alert(message: str) -> None:
    """Send an alert to a Discord channel via webhook."""
    try:
        requests.post(WEBHOOK_URL, json={"content": message})
    except Exception as e:
        print("⚠️ Failed to send Discord alert:", e)


# === Wurm servers and URLs ===
SERVER_URLS = {
    "Xanadu": "https://xanadu.game.wurmonline.com/battles/server_feed.xml",
    "Release": "https://release.game.wurmonline.com/battles/server_feed.xml",
    "Independence": "https://independence.game.wurmonline.com/battles/server_feed.xml",
    "Deliverance": "https://deliverance.game.wurmonline.com/battles/server_feed.xml",
    "Exodus": "https://exodus.game.wurmonline.com/battles/server_feed.xml",
    "Celebration": "https://celebration.wurmonline.com/battles/server_feed.xml",
    "Pristine": "https://pristine.game.wurmonline.com/battles/server_feed.xml",
    "Chaos": "https://chaos.game.wurmonline.com/battles/server_feed.xml",
    "Cadence": "https://cadence.game.wurmonline.com/battles/server_feed.xml",
    "Harmony": "https://harmony.game.wurmonline.com/battles/server_feed.xml",
    "Defiance": "https://defiance.game.wurmonline.com/battles/server_feed.xml",
    "Melody": "https://melody.game.wurmonline.com/battles/server_feed.xml",
}


def get_database_connection():
    """Establish and return a MySQL database connection."""
    return MySQLdb.connect(
        host="localhost",
        user="wurm",
        passwd="Wurming1!",
        database="wurm",
        auth_plugin="mysql_native_password"
    )

def fetch_server_feed(server: str, url: str) -> ET.Element | None:
    """Fetch XML feed for a given server with retry & backoff.
       After 5 failures, sends a Discord alert."""
    retries = 5
    backoff = 1  # seconds

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, verify=True, timeout=10)
            response.raise_for_status()
            return ET.fromstring(response.text)
        except requests.RequestException as e:
            print(f"❌ Attempt {attempt}/{retries} failed for {server}: {e}")
            if attempt == retries:
                send_discord_alert(f"VPS ⚠️ Failed to fetch {server} feed after {retries} attempts: {e}")
                return None
            time.sleep(backoff)
            backoff *= 2  # exponential backoff


def process_server_feed(server: str, xml_root: ET.Element, cursor, db) -> None:
    """Process a Wurm server XML feed and insert updates into the database."""

    # Fetch last recorded epoch
    cursor.execute(
        "SELECT epoch FROM wurm_scrape WHERE server = %s ORDER BY epoch DESC LIMIT 1",
        (server,)
    )
    result = cursor.fetchone()
    last_time = result[0] if result else 0

    # Process new entries (in chronological order)
    for entry in reversed(xml_root[1]):
        entry_time = int(entry.attrib["time"])
        entry_text = entry.attrib["text"]

        if entry_time <= last_time:
            continue

        print(f"{entry_time} - {server} - {entry_text}")

        # Insert into wurm_scrape
        cursor.execute(
            "INSERT INTO wurm_scrape (server, text, epoch) VALUES (%s, %s, %s)",
            (server, entry_text, entry_time),
        )

        # Insert into all_wurm
        created_at = datetime.fromtimestamp(entry_time).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO all_wurm (server, created_at, text) VALUES (%s, %s, %s)",
            (server, created_at, entry_text),
        )

        # Process deed info (only for Xanadu)
        # if server == "Xanadu":
            #handle_deeds(server, entry_text, entry_time, cursor)

        db.commit()


def handle_deeds(server: str, text: str, epoch: int, cursor) -> None:
    """Process deed creation/disbanding events for Xanadu."""
    created_at = datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M:%S")

    try:
        if " founded " in text:
            village_name = text.replace("The settlement of ", "").split(" has just been founded by ")[0]
            founder = text.split("founded by ")[1].split(".")[0]

            cursor.execute(
                "SELECT id FROM deeds WHERE server=%s AND village_name=%s AND status=0 ORDER BY created_at DESC LIMIT 1",
                (server, village_name)
            )
            existing = cursor.fetchone()

            if not existing:
                cursor.execute(
                    "INSERT INTO deeds (server, village_name, created_at, created_by, status) VALUES (%s, %s, %s, %s, FALSE)",
                    (server, village_name, created_at, founder),
                )
            else:
                cursor.execute("UPDATE deeds SET status=2 WHERE id=%s", (existing[0],))
                cursor.execute(
                    "INSERT INTO deeds (server, village_name, created_at, created_by, status) VALUES (%s, %s, %s, %s, FALSE)",
                    (server, village_name, created_at, founder),
                )

        elif " disbanded" in text:
            village_name = text.replace("The settlement of ", "").split(" has just been ")[0]
            disbanded_by = text.split("disbanded by ")[1].split(".")[0] if " disbanded by " in text else "Upkeep"

            cursor.execute(
                "SELECT id FROM deeds WHERE status=FALSE AND server=%s AND village_name=%s ORDER BY created_at DESC LIMIT 1",
                (server, village_name),
            )
            existing = cursor.fetchone()

            if not existing:
                cursor.execute(
                    "INSERT INTO deeds (server, village_name, status, disbanded_at) VALUES (%s, %s, 3, %s)",
                    (server, village_name, created_at),
                )
            else:
                cursor.execute(
                    "UPDATE deeds SET status=TRUE, disbanded_at=%s, disbanded_by=%s WHERE id=%s",
                    (created_at, disbanded_by, existing[0]),
                )
    except Exception as e:
        print("⚠️ Failed to process deed info:", e)


def main():
    db = get_database_connection()
    cursor = db.cursor()

    for server, url in SERVER_URLS.items():
        print(f"Checking {server} @ {url}")
        xml_root = fetch_server_feed(server, url)
        if xml_root is not None:
            process_server_feed(server, xml_root, cursor, db)

    cursor.close()
    db.close()


if __name__ == "__main__":
    main()
