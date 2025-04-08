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

def getNotionPages():
    """Fetch recently edited pages from Notion"""
    url = f"https://api.notion.com/v1/databases/{notionDatabaseId}/query"
    
    filterParams = {
        "filter": {
                    "timestamp": "last_edited_time",
                    "last_edited_time": {
                        "past_week": {}
                    }
                  }
        }
    
    response = requests.post(url, headers=notionHeaders, json=filterParams)
    return response.json().get("results", [])

def getAllNotionPages():
    """Fetch all pages from Notion"""
    url = f"https://api.notion.com/v1/databases/{notionDatabaseId}/query"
    
    response = requests.post(url, headers=notionHeaders)
    return response.json().get("allResults", [])

def syncToGoogleCalendar():
    """Sync Notion pages to Google Calendar events"""
    notionPages = getNotionPages()
    
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
        else:
            # Insert new event
            calendarService.events().insert(
                calendarId=calendarId, 
                body=event
            ).execute()

def deleteGoogleCalendarEvents():
    """Delete Google Calendar events that no longer have corresponding Notion pages"""
    notionPages = getAllNotionPages()
    notionPageIds = {page["id"] for page in notionPages}
    
    try:
        # Set time range (check events from past week to future)
        now = datetime.utcnow()
        timeMinimum = (now - timedelta(days=7)).isoformat() + 'Z'
        
        # Get all calendar events
        eventsResult = calendarService.events().list(
            calendarId=calendarId,
            timeMin=timeMinimum,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = eventsResult.get('items', [])
        
        for event in events:
            description = event.get('description', '')
            # Check if it's a Notion-related event
            if description and "Notion Page ID:" in description:
                eventPageId = description.split("Notion Page ID:")[1].strip()
                # Delete event if its Notion page is not in the recently edited list
                if eventPageId not in notionPageIds:
                    try:
                        calendarService.events().delete(
                            calendarId=calendarId,
                            eventId=event['id']
                        ).execute()
                    except Exception as error:
                        print(f"Failed to delete event: {str(error)}")
                        
    except Exception as error:
        print(f"Error processing calendar events: {str(error)}")

if __name__ == "__main__":
    try:
        # Delete unnecessary events, then sync new events
        deleteGoogleCalendarEvents()
        syncToGoogleCalendar()
    except Exception as error:
        print(f"Error executing program: {str(error)}")