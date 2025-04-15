import os
import requests
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2 import service_account
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure API keys and credentials
notionApiKey = os.getenv("NOTION_API_KEY")
notionDatabaseId = os.getenv("NOTION_DATABASE_ID")
serviceAccountFile = os.getenv("SERVICE_ACCOUNT_FILE")
calendarId = os.getenv("CALENDAR_ID")

# Headers for Notion API requests
notionHeaders = {
    "Authorization": f"Bearer {notionApiKey}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# Configure Google Calendar API
calendarScopes = ["https://www.googleapis.com/auth/calendar"]
credentials = service_account.Credentials.from_service_account_file(
    serviceAccountFile, scopes=calendarScopes
)
calendarService = build("calendar", "v3", credentials=credentials)

def getlastEditedNotionPages():
    """Fetch pages from Notion, limited to last edited time within the past month"""
    url = f"https://api.notion.com/v1/databases/{notionDatabaseId}/query"
    
    filterParams = {
        "filter": {
            "timestamp": "last_edited_time",
            "last_edited_time": {
                "past_week": {}
            }
        }
    }
    
    all_pages = []
    has_more = True
    next_cursor = None
    
    while has_more:
        # Prepare request parameters
        params = filterParams.copy()
        if next_cursor:
            params["start_cursor"] = next_cursor
        
        # Send request
        response = requests.post(url, headers=notionHeaders, json=params)
        data = response.json()
        
        # Add results to list
        all_pages.extend(data.get("results", []))
        
        # Check if there are more pages
        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")
    
    print(f"Retrieved a total of {len(all_pages)} pages from Notion")
    return all_pages

def getAllNotionPages():
    """Fetch all pages from Notion database"""
    url = f"https://api.notion.com/v1/databases/{notionDatabaseId}/query"
    
    all_pages = []
    has_more = True
    next_cursor = None
    
    while has_more:
        # Prepare request parameters
        params = {}
        if next_cursor:
            params["start_cursor"] = next_cursor
        
        # Send request
        response = requests.post(url, headers=notionHeaders, json=params)
        data = response.json()
        
        # Add results to list
        all_pages.extend(data.get("results", []))
        
        # Check if there are more pages
        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")
    
    print(f"Retrieved a total of {len(all_pages)} pages from Notion")
    return all_pages

def syncToGoogleCalendar():
    """Sync Notion pages to Google Calendar events"""
    notionPages = getlastEditedNotionPages()
    
    print(f"Starting to sync {len(notionPages)} Notion pages to Google Calendar")
    
    for page in notionPages:
        properties = page["properties"]
        
        # Get task title
        title = properties["Task"]["title"][0]["text"]["content"] if properties["Task"]["title"] else "No Title"
        
        # Get timeline information
        timeline = properties.get("Timeline", {}).get("date", {})
        startString = timeline.get("start")
        endString = timeline.get("end")

        if not startString:
            continue  # Skip if no start time exists

        isDateTime = "T" in startString

        # Prepare event data
        event = {
            "summary": title,
            "description": f"Notion Page ID: {page['id']}"
        }

        if isDateTime:
            # Handle date-time events
            eventStart = datetime.fromisoformat(startString)
            eventEnd = datetime.fromisoformat(endString) if endString else eventStart + timedelta(hours=1)

            event["start"] = {
                "dateTime": eventStart.isoformat(),
                "timeZone": "Asia/Taipei"
            }
            event["end"] = {
                "dateTime": eventEnd.isoformat(),
                "timeZone": "Asia/Taipei"
            }
        else:
            # Handle all-day events
            startDate = datetime.fromisoformat(startString).date()
            
            # Set end date according to requirements
            if not endString:
                endDate = startDate + timedelta(days=1)
            else:
                originalEndDate = datetime.fromisoformat(endString).date()
                endDate = (startDate + timedelta(days=1) if originalEndDate == startDate 
                          else originalEndDate + timedelta(days=1))
            
            event["start"] = {"date": startDate.isoformat()}
            event["end"] = {"date": endDate.isoformat()}

        # Check for existing events
        existingEvents = calendarService.events().list(
            calendarId=calendarId, q=page["id"]
        ).execute().get("items", [])

        if existingEvents:
            existingEvent = existingEvents[0]
            needUpdate = False

            # Check if title changed
            if existingEvent.get("summary") != title:
                needUpdate = True

            # Check if time changed
            if isDateTime:
                existingStart = existingEvent.get("start", {}).get("dateTime")
                existingEnd = existingEvent.get("end", {}).get("dateTime")
                
                if existingStart:
                    existingStartTime = datetime.fromisoformat(existingStart.replace('Z', '+00:00'))
                    notionStartTime = eventStart.astimezone()
                    if existingStartTime != notionStartTime:
                        needUpdate = True
                        
                if existingEnd:
                    existingEndTime = datetime.fromisoformat(existingEnd.replace('Z', '+00:00'))
                    notionEndTime = eventEnd.astimezone()
                    if existingEndTime != notionEndTime:
                        needUpdate = True
            else:
                existingStartDate = existingEvent.get("start", {}).get("date")
                existingEndDate = existingEvent.get("end", {}).get("date")
                
                if existingStartDate != event["start"]["date"] or existingEndDate != event["end"]["date"]:
                    needUpdate = True

            # Update event if needed
            if needUpdate:
                calendarService.events().update(
                    calendarId=calendarId, 
                    eventId=existingEvent["id"], 
                    body=event
                ).execute()
                print(f"✅ Successfully updated event: {title}")
            else:
                print(f"Event does not need update: {title}")
        else:
            # Insert new event
            print(f"Adding new Google Calendar event: {title}")
            calendarService.events().insert(
                calendarId=calendarId, 
                body=event
            ).execute()
            print(f"✅ Successfully added event: {title}")

def deleteGoogleCalendarEvents():
    """Delete Google Calendar events that no longer have corresponding Notion pages"""
    notionPages = getAllNotionPages()  # Use getAllNotionPages to get all pages
    notionPageIds = {page["id"] for page in notionPages}
    
    print(f"Retrieved {len(notionPageIds)} page IDs from Notion")
    
    try:
        # Set time range (check events from past 1 month to future)
        now = datetime.utcnow()
        timeMinimum = (now - timedelta(days=30)).isoformat() + 'Z'
        
        # Get all calendar events
        events = []
        page_token = None
        
        while True:
            eventsResult = calendarService.events().list(
                calendarId=calendarId,
                timeMin=timeMinimum,
                singleEvents=True,
                orderBy='startTime',
                pageToken=page_token
            ).execute()
            
            events.extend(eventsResult.get('items', []))
            page_token = eventsResult.get('nextPageToken')
            
            if not page_token:
                break
        
        print(f"Retrieved {len(events)} events from Google Calendar")
        
        for event in events:
            description = event.get('description', '')
            # Check if it's a Notion-related event
            if description and "Notion Page ID:" in description:
                eventPageId = description.split("Notion Page ID:")[1].strip()
                print(f"Checking event: {event.get('summary', 'Unnamed Event')}, Notion Page ID: {eventPageId}")
                
                # Delete event if its Notion page is not in the list of all pages
                if eventPageId not in notionPageIds:
                    print(f"No corresponding Notion page found, preparing to delete event")
                    try:
                        calendarService.events().delete(
                            calendarId=calendarId,
                            eventId=event['id']
                        ).execute()
                        print(f"✅ Successfully deleted event: {event.get('summary', 'Unnamed Event')}")
                    except Exception as error:
                        print(f"❌ Failed to delete event: {str(error)}")
                else:
                    print(f"Found corresponding Notion page, keeping event")
                        
    except Exception as error:
        print(f"Error processing calendar events: {str(error)}")

if __name__ == "__main__":
    try:
        print("Starting Notion to Google Calendar sync process...")
        # Delete unnecessary events, then sync new events
        print("💡 Step 1: Delete Google Calendar events that no longer have corresponding Notion pages")
        deleteGoogleCalendarEvents()
        print("💡 Step 2: Sync Notion pages to Google Calendar events")
        syncToGoogleCalendar()
        print("✨ Sync process completed!")
    except Exception as error:
        print(f"⚠️ Error executing program: {str(error)}")