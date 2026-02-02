# Vibe Wall Calendar

A lightweight, self-hosted wall calendar specifically designed for older hardware (e.g., Android 4.4 tablets running Firefox 64). It fetches events from an Apple iCloud calendar and displays them in a 5-day view (Yesterday, Today, Tomorrow, +2 days).

## Features

*   **5-Day Rolling View**: Always shows Yesterday -> Day after Tomorrow.
*   **Lightweight**: Server-Side Rendered (SSR) HTML/CSS. No heavy JavaScript frameworks.
*   **Legacy Support**: Tested/Designed for Firefox 64 and 1280x800 resolution.
*   **Apple iCloud Integration**: Connects via CalDAV protocol using the `caldav` library.
*   **Timezone Aware**: Hardcoded to `Europe/Berlin` as requested.
*   **Dockerized**: Simple `docker-compose` setup.

## Architecture

*   **Backend**: Python 3.11 + Flask.
    *   Fetches data from iCloud using `caldav`.
    *   Parses and filters events for the relevant 5 days.
    *   Caches results for 15 minutes to reduce API calls.
*   **Frontend**: Jinja2 Templates + CSS.
    *   Auto-refreshes every 15 minutes via HTML Meta tag.
    *   Responsive-ish layout optimized for fixed 1280px width.

## Setup

### Prerequisites

*   Docker and Docker Compose installed.
*   Apple ID credentials:
    *   **CalDAV URL**: Usually `https://caldav.icloud.com/`
    *   **Username**: Your Apple ID email.
    *   **Password**: An **App-Specific Password** (Generate at appleid.apple.com).

### Installation

1.  Clone this repository.
2.  Create a `.env` file (or modify `docker-compose.yml` directly) with your credentials:
    ```bash
    ICLOUD_USERNAME=your_email@example.com
    ICLOUD_PASSWORD=your_app_specific_password
    CALENDAR_NAME=Home  # Optional: specific calendar name, otherwise defaults to primary
    TIMEZONE=Europe/Berlin
    ```
3.  Run the container:
    ```bash
    docker-compose up -d --build
    ```
4.  Open your browser to `http://<server-ip>:5000`.

## Configuration

Environment variables in `docker-compose.yml`:

*   `ICLOUD_USERNAME`: Apple ID email.
*   `ICLOUD_PASSWORD`: App-specific password.
*   `ICLOUD_URL`: Defaults to `https://caldav.icloud.com/`.
*   `TIMEZONE`: Defaults to `Europe/Berlin`.
*   `DAYS_TO_SHOW`: Number of days to display (default: 5).
*   `CALENDAR_NAME`: (Optional) The specific calendar to fetch. If omitted, attempts to fetch from all or the primary.
