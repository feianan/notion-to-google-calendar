# Notion to Google Calendar  

This tool allows you to locally create, update, or delete Google Calendar events based on a specified Notion database.  

## How to Use It  

1. Clone the project using Git.  
2. Modify your `.env.example` file:  
   1. Obtain your Notion API key and database ID.  
   2. Acquire your Google Calendar ID.  
   3. Rename the `.env.example` file to `.env`.  
3. Download your Google Calendar key JSON file and name it `google_calendar_key.json`.  

### Get Google Calendar Events  

Run the following command to check if you can successfully retrieve Google Calendar events: 

```
(projectRoot) python3 getGoogleCalendar.py
```
This command retrieves Google Calendar events from the past seven days to the next seven days.  

### Export Notion Pages to Google Calendar Events  

Execute this command to export your Notion pages as Google Calendar events:  

```
(projectRoot) python3 notionToGoogleCalendar.py
```

## Configurations  

1. The tool creates all-day events if the Notion page includes only a date.  
2. It generates multi-day events if the Notion page specifies both a start date and an end date.  
3. It creates one-hour events if the Notion page indicates a specific time.  