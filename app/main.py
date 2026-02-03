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
CALENDARS_CONFIG = os.environ.get('CALENDARS')
TIMEZONE_STR = os.environ.get('TIMEZONE', 'Europe/Berlin')
DAYS_TO_SHOW = int(os.environ.get('DAYS_TO_SHOW', 5))
LATITUDE = os.environ.get('LATITUDE')
LONGITUDE = os.environ.get('LONGITUDE')
LANGUAGE = os.environ.get('LANGUAGE', os.environ.get('LANG', 'en')).split('.')[0]
THEME = os.environ.get('THEME', 'auto').lower()

# Simple in-memory cache
# Structure: {'timestamp': datetime, 'data': {...}}
CACHE = {}
CACHE_DURATION = 900  # 15 minutes in seconds

DEFAULT_PALETTE = [
    '#2962ff', # Blue
    '#d50000', # Red
    '#00c853', # Green
    '#ff6d00', # Orange
    '#aa00ff', # Purple
    '#00bfa5', # Teal
    '#c51162', # Pink
]

def get_timezone():
    return tz.gettz(TIMEZONE_STR)

def get_theme_mode():
    """
    Determines if the theme should be 'light' or 'dark'.
    Checks THEME env var first, then calculates based on sun position if 'auto'.
    Light mode: Sunrise + 45min < NOW < Sunset - 30min
    """
    if THEME in ['light', 'dark']:
        return THEME

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

def parse_calendars_config():
    """
    Parses CALENDARS env var or falls back to CALENDAR_NAME.
    Returns a dict: {'Calendar Name': 'ColorHex'}
    """
    logger.info(f"Parsing config. CALENDARS='{CALENDARS_CONFIG}', CALENDAR_NAME='{CALENDAR_NAME}'")
    targets = {}
    
    if CALENDARS_CONFIG:
        # Parse comma separated list
        parts = [x.strip() for x in CALENDARS_CONFIG.split(',') if x.strip()]
        logger.info(f"Found {len(parts)} config parts: {parts}")
        
        for i, part in enumerate(parts):
            if ':' in part:
                name, color = part.rsplit(':', 1)
                targets[name.strip()] = color.strip()
                logger.info(f"Parsed explicit color: {name.strip()} -> {color.strip()}")
            else:
                # Assign default color based on index
                color = DEFAULT_PALETTE[i % len(DEFAULT_PALETTE)]
                targets[part.strip()] = color
                logger.info(f"Assigned default color: {part.strip()} -> {color}")
                
    elif CALENDAR_NAME:
        # Fallback to single legacy calendar
        targets[CALENDAR_NAME] = DEFAULT_PALETTE[0]
        logger.info(f"Using legacy CALENDAR_NAME: {CALENDAR_NAME}")
        
    logger.info(f"Final calendar configuration: {targets}")
    return targets


def fetch_events():
    """
    Fetches events from CalDAV or returns cached data.
    Supports multiple calendars via CALENDARS config or legacy CALENDAR_NAME.
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
        
        target_config = parse_calendars_config()
        calendars_to_fetch = []

        if not target_config:
            # Fallback: No config provided, try to use first calendar
            if calendars:
                logger.info(f"No calendar config. Defaulting to first found: {calendars[0].name}")
                calendars_to_fetch.append((calendars[0], DEFAULT_PALETTE[0]))
        else:
            # Match available calendars to config
            # Optimization: Map available calendars by name for O(1) lookup
            available_map = {cal.name: cal for cal in calendars}
            
            for name, color in target_config.items():
                if name in available_map:
                    calendars_to_fetch.append((available_map[name], color))
                else:
                    logger.warning(f"Configured calendar '{name}' not found on server.")

        if not calendars_to_fetch:
            logger.error("No matching calendars found.")
            return {}

        # Initialize data containers
        data = {
            'timed': {},
            'all_day': []
        }
        
        # Search Range
        local_tz = get_timezone()
        dt_now = datetime.datetime.now(local_tz)
        
        # Start from the beginning of yesterday (matches get_date_range)
        today = dt_now.date()
        yesterday = today - datetime.timedelta(days=1)
        start_dt = datetime.datetime.combine(yesterday, datetime.time.min, tzinfo=local_tz)
        
        end_dt = dt_now + datetime.timedelta(days=DAYS_TO_SHOW)

        for target_calendar, color in calendars_to_fetch:
            logger.info(f"Fetching events from '{target_calendar.name}'...")
            results = target_calendar.date_search(start=start_dt, end=end_dt, expand=True)
            
            for event in results:
                # Parse the vObject
                # Handle single or multiple VEVENT components (expanded recurrence)
                vevents = getattr(event.instance, 'vevent_list', [])
                if not vevents and hasattr(event.instance, 'vevent'):
                    # Fallback if list not found but single item exists (safety net)
                    vevents = [event.instance.vevent]

                for ical_data in vevents:
                    summary = str(ical_data.summary.value)
                    
                    description = ""
                    if hasattr(ical_data, 'description'):
                        description = str(ical_data.description.value)

                    location = ""
                    if hasattr(ical_data, 'location'):
                        location = str(ical_data.location.value)
                    
                    dtstart = ical_data.dtstart.value
                    
                    if hasattr(ical_data, 'dtend'):
                        dtend = ical_data.dtend.value
                    else:
                        dtend = None

                    is_all_day = not isinstance(dtstart, datetime.datetime)
                    
                    if not is_all_day:
                        if dtstart.tzinfo is None:
                            dtstart = dtstart.replace(tzinfo=tz.UTC)
                        
                        dtstart_local = dtstart.astimezone(local_tz)
                        date_key = dtstart_local.date()
                        time_str = dtstart_local.strftime("%H:%M")
                        
                        if dtend:
                            if isinstance(dtend, datetime.datetime):
                                if dtend.tzinfo is None:
                                    dtend = dtend.replace(tzinfo=tz.UTC)
                                dtend_local = dtend.astimezone(local_tz)
                                end_time_str = dtend_local.strftime("%H:%M")
                            else:
                                 end_time_str = ""
                        else:
                            end_time_str = (dtstart_local + datetime.timedelta(hours=1)).strftime("%H:%M")

                        if date_key not in data['timed']:
                            data['timed'][date_key] = []
                            
                        data['timed'][date_key].append({
                            'summary': summary,
                            'description': description,
                            'location': location,
                            'time': time_str,
                            'end_time': end_time_str,
                            'is_all_day': False,
                            'sort_key': dtstart_local,
                            'color': color  # Inject Color
                        })

                    else:
                        if not dtend:
                            dtend = dtstart + datetime.timedelta(days=1)
                        elif dtend == dtstart:
                             dtend = dtstart + datetime.timedelta(days=1)
                        
                        data['all_day'].append({
                            'summary': summary,
                            'description': description,
                            'location': location,
                            'start': dtstart,
                            'end': dtend,
                            'is_all_day': True,
                            'color': color # Inject Color
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
        if 'data' in CACHE:
            return CACHE['data']
        return {}

@app.route('/')
def calendar():
    theme = get_theme_mode()
    days_to_show = get_date_range() 
    
    view_start = days_to_show[0]
    view_end = days_to_show[-1] + datetime.timedelta(days=1)
    
    fetched_data = fetch_events()
    timed_events = fetched_data.get('timed', {})
    raw_all_day = fetched_data.get('all_day', [])
    
    # Process All Day Events (Bin Packing)
    visible_all_day = []
    for ev in raw_all_day:
        if ev['start'] < view_end and ev['end'] > view_start:
            visible_all_day.append(ev)
            
    # Sort by start date, then duration (desc)
    visible_all_day.sort(key=lambda x: (x['start'], (x['start'] - x['end']).days))
    
    rows = [] 
    processed_all_day = []
    
    for ev in visible_all_day:
        # Calculate visual start/end (clamped to view)
        
        if ev['start'] < view_start:
            col_start = 1
            is_continuation_left = True
        else:
            col_start = (ev['start'] - view_start).days + 1
            is_continuation_left = False
            
        if ev['end'] > view_end:
            col_end = len(days_to_show) + 1
            is_continuation_right = True
        else:
            col_end = (ev['end'] - view_start).days + 1
            is_continuation_right = False
            
        col_span = col_end - col_start
        
        assigned_row = -1
        for i, row_end in enumerate(rows):
            if ev['start'] >= row_end:
                assigned_row = i
                rows[i] = ev['end']
                break
        
        if assigned_row == -1:
            rows.append(ev['end'])
            assigned_row = len(rows) - 1
            
        inclusive_end = ev['end'] - datetime.timedelta(days=1)
        
        start_str = dates.format_date(ev['start'], format='MMM d', locale=LANGUAGE)
        end_str = dates.format_date(inclusive_end, format='MMM d', locale=LANGUAGE)
        
        if ev['start'] == inclusive_end:
            date_range_str = start_str
        else:
            date_range_str = f"{start_str} - {end_str}"
            
        processed_all_day.append({
            'summary': ev['summary'],
            'description': ev['description'],
            'location': ev['location'],
            'col_start': col_start,
            'col_span': col_span,
            'row': assigned_row + 1,
            'is_left': is_continuation_left,
            'is_right': is_continuation_right,
            'time_str': translations.get_text(LANGUAGE, 'all_day'),
            'date_range': date_range_str,
            'color': ev['color'] # Pass color through
        })

    columns = []
    today = datetime.datetime.now(get_timezone()).date()
    
    no_events_text = translations.get_text(LANGUAGE, 'no_events')

    for day in days_to_show:
        is_today = (day == today)
        
        if is_today:
             day_name = translations.get_text(LANGUAGE, 'today')
        else:
             day_name = dates.format_date(day, format='EEEE', locale=LANGUAGE).upper()

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