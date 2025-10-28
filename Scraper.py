from datetime import datetime
import requests
import MySQLdb
import xml.etree.ElementTree as ET

# Database connection settings
DB_HOST = "127.0.0.1"
DB_USER = "wurm"
DB_PASSWORD = "Wurming1!"
DB_NAME = "wurm"

# Connect to the database
db = MySQLdb.connect(host=DB_HOST, user=DB_USER, passwd=DB_PASSWORD, database=DB_NAME)
cursor = db.cursor()

# Dictionary mapping server names to their respective XML feed URLs
servers = {
    'Xanadu': 'http://xanadu.game.wurmonline.com/battles/server_feed.xml',
    'Release': 'http://release.game.wurmonline.com/battles/server_feed.xml',
    'Independence': 'https://independence.game.wurmonline.com/battles/server_feed.xml',
    'Deliverance': 'http://deliverance.game.wurmonline.com/battles/server_feed.xml',
    'Exodus': 'http://exodus.game.wurmonline.com/battles/server_feed.xml',
    'Celebration': 'https://celebration.wurmonline.com/battles/server_feed.xml',
    'Pristine': 'http://pristine.game.wurmonline.com/battles/server_feed.xml',
    'Chaos': 'http://chaos.game.wurmonline.com/battles/server_feed.xml',
    'Cadence': 'https://cadence.game.wurmonline.com/battles/server_feed.xml',
    'Harmony': 'https://harmony.game.wurmonline.com/battles/server_feed.xml',
    'Defiance': 'https://defiance.game.wurmonline.com/battles/server_feed.xml',
    'Melody': 'https://melody.game.wurmonline.com/battles/server_feed.xml'
}

# Process each server and its associated XML feed
for server, url in servers.items():
    print(f"\nChecking {server}")
    try:
        response = requests.get(url, verify=True)
        response.raise_for_status()  # Raises an error for bad responses (4xx, 5xx)
    except requests.RequestException as e:
        print(f"Failed to retrieve data for {server}: {e}")
        continue
    
    # Parse the XML response
    root = ET.fromstring(response.text)

    # Retrieve the latest stored event timestamp for this server
    cursor.execute(f"SELECT epoch FROM wurm_scrape WHERE server = %s ORDER BY epoch DESC LIMIT 1", (server,))
    result = cursor.fetchone()
    last_time = result[0] if result else 0  # Default to 0 if no previous record exists

    # Iterate through events in reverse order (oldest first)
    for event in reversed(root[1]):
        event_time = int(event.attrib['time'])
        event_text = event.attrib['text']
        # print(f"{server} - Event time: {event_time} > Last_time: {int(last_time)} = {event_time > int(last_time)}")
        if event_time > int(last_time):
            print(f"{server} - {event_text}")

            # Insert new event into 'wurm_scrape' table
            sql_wurm_scrape = """
                INSERT INTO wurm_scrape (`server`, `text`, `epoch`)
                VALUES (%s, %s, %s)
            """
            cursor.execute(sql_wurm_scrape, (server, event_text, event_time))

            # Insert new event into 'all_wurm' table
            sql_all_wurm = """
                INSERT INTO all_wurm (`server`, `created_at`, `text`)
                VALUES (%s, %s, %s)
            """
            created_at = datetime.fromtimestamp(event_time).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(sql_all_wurm, (server, created_at, event_text))

            # Process settlement (deed) events for Xanadu server
            if server == "Xanadu":
                try:
                    if " founded " in event_text:
                        village_name = event_text.replace('The settlement of ', '').split(' has just been founded by ')[0]
                        founder_name = event_text.split("founded by ")[1].split(".")[0]

                        # Check if the village already exists
                        sql_check_village = """
                            SELECT id FROM deeds
                            WHERE server = %s AND village_name = %s AND status = 0
                            ORDER BY created_at DESC LIMIT 1
                        """
                        cursor.execute(sql_check_village, (server, village_name))
                        existing_village = cursor.fetchone()

                        if not existing_village:
                            sql_insert_village = """
                                INSERT INTO deeds (server, village_name, created_at, created_by, status)
                                VALUES (%s, %s, %s, %s, FALSE)
                            """
                            cursor.execute(sql_insert_village, (server, village_name, created_at, founder_name))
                        else:
                            sql_disband_village = """
                                UPDATE deeds SET status = 2 WHERE id = %s
                            """
                            cursor.execute(sql_disband_village, (existing_village[0],))
                            cursor.execute(sql_insert_village, (server, village_name, created_at, founder_name))

                    elif " disbanded" in event_text:
                        village_name = event_text.replace('The settlement of ', '').split(' has just been ')[0]
                        disbanded_by = event_text.split("disbanded by ")[1].split(".")[0] if " disbanded by " in event_text else "Upkeep"

                        sql_check_village = """
                            SELECT id FROM deeds
                            WHERE server = %s AND village_name = %s AND status = FALSE
                            ORDER BY created_at DESC LIMIT 1
                        """
                        cursor.execute(sql_check_village, (server, village_name))
                        existing_village = cursor.fetchone()

                        if not existing_village:
                            sql_insert_disband = """
                                INSERT INTO deeds (server, village_name, status, disbanded_at)
                                VALUES (%s, %s, 3, %s)
                            """
                            cursor.execute(sql_insert_disband, (server, village_name, created_at))
                        else:
                            sql_update_disband = """
                                UPDATE deeds
                                SET status = TRUE, disbanded_at = %s, disbanded_by = %s
                                WHERE id = %s
                            """
                            cursor.execute(sql_update_disband, (created_at, disbanded_by, existing_village[0]))
                except Exception as e:
                    print(f"Error processing deed info for {server}: {e}")

            # Commit changes to the database
            db.commit()
            # print("Database updated successfully.")

# Close the database connection
cursor.close()
db.close()
print("Database connection closed.")
input()
