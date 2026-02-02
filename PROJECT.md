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

#### Option 1: Docker (Recommended)
You can run the pre-built image directly from GitHub Container Registry.

1.  Create a `docker-compose.yml` file:
    ```yaml
    version: '3.8'
    services:
      wallcalendar:
        image: ghcr.io/sonntam/vibe-wallcalendar:latest
        container_name: vibe-wallcalendar
        restart: unless-stopped
        ports:
          - "5000:5000"
        env_file:
          - secrets.env
        environment:
          - ICLOUD_URL=https://caldav.icloud.com/
          - CALENDAR_NAME=Home
          - TIMEZONE=Europe/Berlin
          - DAYS_TO_SHOW=5
          - LANGUAGE=de
          - LATITUDE=52.5200
          - LONGITUDE=13.4050
    ```
2.  Create a `secrets.env` file with your credentials:
    ```bash
    ICLOUD_USERNAME=your_email@example.com
    ICLOUD_PASSWORD=your_app_specific_password
    ```
3.  Start the container:
    ```bash
    docker-compose up -d
    ```

#### Option 2: Build from Source
1.  Clone this repository.
2.  Create a `secrets.env` file (or modify `docker-compose.yml` directly) with your credentials.
3.  Run the container:
    ```bash
    docker-compose up -d --build
    ```
4.  Open your browser to `http://<server-ip>:5000`.

## Releasing (For Maintainers)

This project uses **Conventional Commits** to automate releases. When contributing, please format your commit messages as follows:

*   `feat: ...` for a new feature (triggers a MINOR version update).
*   `fix: ...` for a bug fix (triggers a PATCH version update).
*   `feat!: ...` or `fix!: ...` (exclamation mark) signals a **BREAKING CHANGE** and triggers a **MAJOR** version update.
*   `chore: ...` for maintenance tasks (no release).

**Workflow:**
1.  Push changes to `main`.
2.  A "Release PR" will be automatically created/updated by the `release-please` bot.
3.  Merge the Release PR to trigger a new release.
4.  This automatically builds and pushes the Docker image to `ghcr.io`.

## Configuration

Environment variables in `docker-compose.yml`:

*   `ICLOUD_USERNAME`: Apple ID email.
*   `ICLOUD_PASSWORD`: App-specific password.
*   `ICLOUD_URL`: Defaults to `https://caldav.icloud.com/`.
*   `TIMEZONE`: Defaults to `Europe/Berlin`.
*   `DAYS_TO_SHOW`: Number of days to display (default: 5).
*   `LATITUDE`: (Optional) Latitude for auto-theme switching (e.g., 52.5200).
*   `LONGITUDE`: (Optional) Longitude for auto-theme switching (e.g., 13.4050).
*   `LANGUAGE`: (Optional) Language code for UI strings and date formatting (default: `en`, options: `en`, `de`).
*   `CALENDAR_NAME`: (Optional) The specific calendar to fetch. If omitted, attempts to fetch from all or the primary.
