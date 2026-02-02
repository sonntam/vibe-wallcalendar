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
        
        data = {
            'timed': {},
            'all_day': []
        }
        
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
                dtend = None

            # Normalize to local timezone for display
            is_all_day = not isinstance(dtstart, datetime.datetime)
            
            if not is_all_day:
                # Ensure timezone awareness
                if dtstart.tzinfo is None:
                    dtstart = dtstart.replace(tzinfo=tz.UTC)
                
                dtstart_local = dtstart.astimezone(local_tz)
                date_key = dtstart_local.date()
                time_str = dtstart_local.strftime("%H:%M")
                
                # Handle End Time formatting
                if dtend:
                    if isinstance(dtend, datetime.datetime):
                        if dtend.tzinfo is None:
                            dtend = dtend.replace(tzinfo=tz.UTC)
                        dtend_local = dtend.astimezone(local_tz)
                        end_time_str = dtend_local.strftime("%H:%M")
                    else:
                         end_time_str = ""
                else:
                    # Assume 1 hour
                    end_time_str = (dtstart_local + datetime.timedelta(hours=1)).strftime("%H:%M")

                # Store timed event
                if date_key not in data['timed']:
                    data['timed'][date_key] = []
                    
                data['timed'][date_key].append({
                    'summary': summary,
                    'description': description,
                    'location': location,
                    'time': time_str,
                    'end_time': end_time_str,
                    'is_all_day': False,
                    'sort_key': dtstart_local
                })

            else:
                # All Day Event
                if not dtend:
                    dtend = dtstart + datetime.timedelta(days=1)
                elif dtend == dtstart:
                     # Some clients might set start=end for single day, though spec says exclusive
                     dtend = dtstart + datetime.timedelta(days=1)
                
                data['all_day'].append({
                    'summary': summary,
                    'description': description,
                    'location': location,
                    'start': dtstart,
                    'end': dtend,
                    'is_all_day': True
                })

        # Sort timed events within days
        for day in data['timed']:
            data['timed'][day].sort(key=lambda x: x['sort_key'])

        # Update Cache
        CACHE['timestamp'] = now
        CACHE['data'] = data
        return data

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
    
    # Range for all-day calculation
    view_start = days_to_show[0]
    view_end = days_to_show[-1] + datetime.timedelta(days=1) # Exclusive
    
    fetched_data = fetch_events()
    timed_events = fetched_data.get('timed', {})
    raw_all_day = fetched_data.get('all_day', [])
    
    # Process All Day Events (Bin Packing)
    # Filter overlapping events
    visible_all_day = []
    for ev in raw_all_day:
        # Check overlap: start < view_end AND end > view_start
        if ev['start'] < view_end and ev['end'] > view_start:
            visible_all_day.append(ev)
            
    # Sort by start date, then duration (desc)
    visible_all_day.sort(key=lambda x: (x['start'], (x['start'] - x['end']).days))
    
    # Assign Rows
    # rows is a list of lists: [[end_date_of_last_event_in_row, ...], ...]
    # We store the end date of the last event in that row.
    rows = [] 
    
    processed_all_day = []
    
    for ev in visible_all_day:
        # Calculate visual start/end (clamped to view)
        
        # Grid Column Start (1-based)
        # If starts before view, start at 1
        if ev['start'] < view_start:
            col_start = 1
            is_continuation_left = True
        else:
            col_start = (ev['start'] - view_start).days + 1
            is_continuation_left = False
            
        # Grid Column End (Exclusive)
        if ev['end'] > view_end:
            # Spans beyond view
            col_end = len(days_to_show) + 1 # +1 because grid lines are 1-based, 6 lines for 5 cols
            is_continuation_right = True
        else:
            col_end = (ev['end'] - view_start).days + 1
            is_continuation_right = False
            
        col_span = col_end - col_start
        
        # Find a row
        assigned_row = -1
        for i, row_end in enumerate(rows):
            # Check if this row is free after row_end
            # We need strictly greater because if prev ends at today 00:00, next can start today 00:00
            # Wait, ev['start'] must be >= row_end
            if ev['start'] >= row_end:
                assigned_row = i
                rows[i] = ev['end']
                break
        
        if assigned_row == -1:
            # Create new row
            rows.append(ev['end'])
            assigned_row = len(rows) - 1
            
        # Add to list with layout info
        processed_all_day.append({
            'summary': ev['summary'],
            'description': ev['description'],
            'location': ev['location'],
            'col_start': col_start,
            'col_span': col_span,
            'row': assigned_row + 1, # CSS Grid rows are 1-based
            'is_left': is_continuation_left,
            'is_right': is_continuation_right,
            'time_str': translations.get_text(LANGUAGE, 'all_day')
        })

    # Structure data for template
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
        
        day_events = timed_events.get(day, [])
        
        columns.append({
            'is_today': is_today,
            'day_name': day_name,
            'date_str': date_str,
            'events': day_events
        })
        
    return render_template('calendar.html', columns=columns, all_day_events=processed_all_day, theme=theme, no_events_text=no_events_text)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
