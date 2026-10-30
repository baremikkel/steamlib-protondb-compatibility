# Steam × ProtonDB

A small Streamlit dashboard that checks the games in a Steam library against
ProtonDB. Use it to get an overview of how your games are reported to run on
Linux and Steam Deck with Proton.

## Features

- Load owned games from a Steam account and show each game's playtime.
- Look up ProtonDB tier, trending tier, and report count for each game.
- Filter by rating and minimum hours played, or search by game name.
- Browse games grouped by rating and view a summary chart.
- Download the currently filtered results as a CSV file.

Ratings are grouped as Platinum, Gold, Silver, Bronze, Borked, Pending, and
No data.

## Requirements

- Python 3.10 or later
- A Steam Web API key
- A Steam profile with **Game details** visibility set to **Public**

The app uses the Steam Web API to retrieve the owned-games list and ProtonDB's
public API to retrieve compatibility summaries. A SteamID64 can be entered
directly; custom profile names and profile URLs are also accepted.

## Setup

1. Clone this repository and change into the project directory.
2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

   On Windows, activate it with `.venv\Scripts\activate`.

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Get a Steam Web API key at <https://steamcommunity.com/dev/apikey>.
   You can enter it in the app's sidebar, or save it in a `.env` file:

   ```dotenv
   STEAM_API_KEY=your_steam_web_api_key
   ```

   `.env` is ignored by Git; do not commit your key.

5. Start the dashboard:

   ```bash
   streamlit run app.py
   ```

6. In the sidebar, enter your SteamID64, custom profile name, or profile URL,
   then select **Load library**.

## Notes

- Your Steam profile's **Game details** must be public for the Steam API to
  return your library.
- ProtonDB ratings are community-reported and may not reflect your own system
  or current game version.
- Steam library data is cached for one hour and ProtonDB summaries for six
  hours during the app session.
