import os
import datetime
import logging
import caldav
from flask import Flask, render_template, abort
from dateutil import tz
from dateutil.parser import parse
from astral import LocationInfo
from astral.sun import sun
from babel import dates
import translations

app = Flask(__name__)

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = app.logger

# Configuration
ICLOUD_URL = os.environ.get('ICLOUD_URL', 'https://caldav.icloud.com/')
ICLOUD_USERNAME = os.environ.get('ICLOUD_USERNAME')
ICLOUD_PASSWORD = os.environ.get('ICLOUD_PASSWORD')
CALENDAR_NAME = os.environ.get('CALENDAR_NAME')
TIMEZONE_STR = os.environ.get('TIMEZONE', 'Europe/Berlin')
DAYS_TO_SHOW = int(os.environ.get('DAYS_TO_SHOW', 5))
LATITUDE = os.environ.get('LATITUDE')
LONGITUDE = os.environ.get('LONGITUDE')
LANGUAGE = os.environ.get('LANGUAGE', os.environ.get('LANG', 'en')).split('.')[0]

# Simple in-memory cache
# Structure: {'timestamp': datetime, 'data': {...}}
CACHE = {}
CACHE_DURATION = 900  # 15 minutes in seconds

def get_timezone():
    return tz.gettz(TIMEZONE_STR)

def get_theme_mode():
    """
    Determines if the theme should be 'light' or 'dark' based on sun position.
    Light mode: Sunrise + 45min < NOW < Sunset - 30min
    """
    if not LATITUDE or not LONGITUDE:
        return 'dark' # Default fallback
        
    try:
        local_tz = get_timezone()
        now = datetime.datetime.now(local_tz)
        
        # Setup location
        l = LocationInfo("Custom", "Region", TIMEZONE_STR, float(LATITUDE), float(LONGITUDE))
        
        # Calculate sun events
        s = sun(l.observer, date=now.date(), tzinfo=local_tz)
        sunrise = s['sunrise']
        sunset = s['sunset']
        
        # Define window
        light_start = sunrise + datetime.timedelta(minutes=45)
        light_end = sunset - datetime.timedelta(minutes=30)
        
        if light_start < now < light_end:
            return 'light'
        else:
            return 'dark'
            
    except Exception as e:
        logger.error(f"Error calculating theme: {e}")
        return 'dark'

def get_date_range():
    """Returns a list of datetime.date objects for the configured range (default 5 days)"""
    local_tz = get_timezone()
    now = datetime.datetime.now(local_tz)
    today = now.date()
    yesterday = today - datetime.timedelta(days=1)
    
    days = []
    for i in range(DAYS_TO_SHOW):
        days.append(yesterday + datetime.timedelta(days=i))
    return days

def fetch_events():
    """
    Fetches events from CalDAV or returns cached data.
    """
    global CACHE
    now = datetime.datetime.now()
    
    # Check cache
    if 'timestamp' in CACHE:
        age = (now - CACHE['timestamp']).total_seconds()
        if age < CACHE_DURATION:
            logger.info(f"Serving from cache ({int(age)}s old)")
            return CACHE['data']

    if not ICLOUD_USERNAME or not ICLOUD_PASSWORD:
        logger.warning("No credentials provided. Returning empty list.")
        return {}

    try:
        logger.info("Connecting to CalDAV...")
        client = caldav.DAVClient(
            url=ICLOUD_URL,
            username=ICLOUD_USERNAME,
            password=ICLOUD_PASSWORD
        )
        principal = client.principal()
        calendars = principal.calendars()
        
        target_calendar = None
        if CALENDAR_NAME:
            for cal in calendars:
                # Some servers return display name, others might require property lookup
                # caldav library tries to handle this.
                if cal.name == CALENDAR_NAME:
                    target_calendar = cal
                    break
        
        if not target_calendar and calendars:
            target_calendar = calendars[0] # Fallback to first found
            
        if not target_calendar:
            logger.error("No calendar found.")
            return {}

        logger.info(f"Fetching events from '{target_calendar.name}'...")
        
        # Define search range for query
        # We need yesterday start to +DAYS_TO_SHOW days end (to be safe)
        local_tz = get_timezone()
        dt_now = datetime.datetime.now(local_tz)
        start_dt = dt_now - datetime.timedelta(days=1)
        end_dt = dt_now + datetime.timedelta(days=DAYS_TO_SHOW)
        
        # date_search expects datetime objects
        results = target_calendar.date_search(start=start_dt, end=end_dt, expand=True)
        
        events_by_date = {}
        
        for event in results:
            # Parse the vObject
            # caldav 1.0+ returns a defined object, we access instance.vevent
            ical_data = event.instance.vevent
            
            summary = str(ical_data.summary.value)
            
            # Extract Description (optional)
            description = ""
            if hasattr(ical_data, 'description'):
                description = str(ical_data.description.value)

            # Extract Location (optional)
            location = ""
            if hasattr(ical_data, 'location'):
                location = str(ical_data.location.value)
            
            # Handle Start Time
            dtstart = ical_data.dtstart.value
            
            # Handle End Time (optional in spec, but usually present)
            if hasattr(ical_data, 'dtend'):
                dtend = ical_data.dtend.value
            else:
                # If no end, assume 1 hour duration or all day depending on type
                if isinstance(dtstart, datetime.datetime):
                    dtend = dtstart + datetime.timedelta(hours=1)
                else:
                    dtend = dtstart # Single day event
            
            # Normalize to local timezone for display
            # If it's a date object (all day), keep it as date
            # If it's datetime, convert to local
            
            is_all_day = not isinstance(dtstart, datetime.datetime)
            
            if not is_all_day:
                # Ensure timezone awareness
                if dtstart.tzinfo is None:
                    # Naive, assume local? Or UTC? 
                    # Usually ical is UTC if ends in Z. 
                    dtstart = dtstart.replace(tzinfo=tz.UTC)
                
                dtstart_local = dtstart.astimezone(local_tz)
                date_key = dtstart_local.date()
                time_str = dtstart_local.strftime("%H:%M")
                
                # Handle End Time formatting
                if dtend:
                    if dtend.tzinfo is None:
                        dtend = dtend.replace(tzinfo=tz.UTC)
                    dtend_local = dtend.astimezone(local_tz)
                    end_time_str = dtend_local.strftime("%H:%M")
                else:
                    end_time_str = ""

            else:
                date_key = dtstart
                time_str = translations.get_text(LANGUAGE, 'all_day')
                end_time_str = ""

            # Store
            if date_key not in events_by_date:
                events_by_date[date_key] = []
                
            events_by_date[date_key].append({
                'summary': summary,
                'description': description,
                'location': location,
                'time': time_str,
                'end_time': end_time_str,
                'is_all_day': is_all_day,
                'sort_key': dtstart if not is_all_day else datetime.datetime.combine(dtstart, datetime.time.min).replace(tzinfo=local_tz)
            })

        # Sort events within days
        for day in events_by_date:
            events_by_date[day].sort(key=lambda x: x['sort_key'])

        # Update Cache
        CACHE['timestamp'] = now
        CACHE['data'] = events_by_date
        return events_by_date

    except Exception as e:
        logger.error(f"Error fetching calendar: {e}")
        # Return stale cache if available, else empty
        if 'data' in CACHE:
            return CACHE['data']
        return {}

@app.route('/')
def calendar():
    theme = get_theme_mode()
    days_to_show = get_date_range() # List of 5 date objects
    events_by_date = fetch_events()
    
    # Structure data for template
    # list of dicts: {'date_obj': date, 'day_name': 'Mon', 'day_str': '02.02', 'events': []}
    
    columns = []
    today = datetime.datetime.now(get_timezone()).date()
    
    no_events_text = translations.get_text(LANGUAGE, 'no_events')

    for day in days_to_show:
        is_today = (day == today)
        
        # Determine day name (e.g. "Monday" or "HEUTE")
        if is_today:
             day_name = translations.get_text(LANGUAGE, 'today')
        else:
             # Babel formatting: 'EEEE' = full weekday name
             day_name = dates.format_date(day, format='EEEE', locale=LANGUAGE).upper()

        # Format date: "Feb 02" or localized "2. Feb."
        # Babel 'MMM d' handles locale specific order
        date_str = dates.format_date(day, format='MMM d', locale=LANGUAGE)
        
        day_events = events_by_date.get(day, [])
        
        columns.append({
            'is_today': is_today,
            'day_name': day_name,
            'date_str': date_str,
            'events': day_events
        })
        
    return render_template('calendar.html', columns=columns, theme=theme, no_events_text=no_events_text)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
