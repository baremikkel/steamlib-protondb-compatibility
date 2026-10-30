import html, json, os, re, requests
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="Steam × ProtonDB", page_icon="🎮", layout="wide")

TIER_ORDER = ["platinum", "gold", "silver", "bronze", "borked", "pending", "no data"]
TIER_EMOJI = {
    "platinum": "🏆", "gold": "🥇", "silver": "🥈", "bronze": "🥉",
    "borked": "💥", "pending": "⏳", "no data": "❓",
}
HEADERS = {"User-Agent": "steam-protondb-checker/1.0"}


# ---------- Steam ----------
def extract_identifier(text: str) -> str:
    """Accept a 17-digit SteamID64, a vanity name, or a full profile URL."""
    text = text.strip().rstrip("/")
    m = re.search(r"steamcommunity\.com/(?:id|profiles)/([^/?#]+)", text) #Stops before URL parameteres
    return m.group(1) if m else text


def resolve_vanity_keyless(name: str) -> str | None:
    """Resolve a custom-URL name to a SteamID64 by reading the public profile."""
    for url, params, pattern in [
        (f"https://steamcommunity.com/id/{name}", {}, r'"steamid":"(\d{17})"'),
    ]:
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=15)
            m = re.search(pattern, r.text)
            if m:
                return m.group(1)
        except requests.RequestException:
            continue
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def resolve_steam_id(identifier: str, api_key: str) -> str | None:
    if re.fullmatch(r"\d{17}", identifier):
        return identifier
    if api_key:
        try:
            r = requests.get(
                "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/",
                params={"key": api_key, "vanityurl": identifier},
                headers=HEADERS, timeout=15,
            )
            r.raise_for_status()
            resp = r.json().get("response", {})
            if resp.get("success") == 1:
                return resp.get("steamid")
        except (requests.RequestException, ValueError):
            pass
    return resolve_vanity_keyless(identifier)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_library_api(steam_id: str, api_key: str) -> list[dict]:
    r = requests.get(
        "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/",
        params={"key": api_key, "steamid": steam_id,
                "include_appinfo": 1, "include_played_free_games": 1},
        headers=HEADERS, timeout=30,
    )
    r.raise_for_status()
    games = r.json().get("response", {}).get("games", [])
    return [
        {"appid": g["appid"], "name": g.get("name", f"App {g['appid']}"),
         "hours": round(g.get("playtime_forever", 0) / 60, 1)}
        for g in games
    ]

# ---------- ProtonDB ----------
@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fetch_protondb(appid: int) -> dict:
    try:
        r = requests.get(
            f"https://www.protondb.com/api/v1/reports/summaries/{appid}.json",
            headers=HEADERS, timeout=10,
        )
        if r.status_code == 200:
            d = r.json()
            return {"tier": d.get("tier", "pending"),
                    "trending": d.get("trendingTier"),
                    "reports": d.get("total", 0)}
    except requests.RequestException:
        pass
    return {"tier": "no data", "trending": None, "reports": 0}

def build_dataframe(games: list[dict]) -> pd.DataFrame:
    progress = st.progress(0.0, text="Checking ProtonDB…")
    results = []
    with ThreadPoolExecutor(max_workers=16) as pool:
        for i, res in enumerate(pool.map(lambda g: fetch_protondb(g["appid"]), games), 1):
            results.append(res)
            if i % 10 == 0 or i == len(games):
                progress.progress(i / len(games), text=f"Checking ProtonDB… {i}/{len(games)}")
    progress.empty()

    df = pd.DataFrame(games)
    df = pd.concat([df, pd.DataFrame(results)], axis=1)
    df["tier"] = pd.Categorical(df["tier"], categories=TIER_ORDER, ordered=True)
    df["rating"] = df["tier"].astype(str).map(lambda t: f"{TIER_EMOJI.get(t, '')} {t.title()}")
    df["protondb"] = df["appid"].map(lambda a: f"https://www.protondb.com/app/{a}")
    df["image"] = df["appid"].map(
        lambda a: f"https://cdn.cloudflare.steamstatic.com/steam/apps/{a}/header.jpg")
    return df.sort_values(["tier", "name"]).reset_index(drop=True)

# ---------- UI ----------
st.title(" Steam × ProtonDB")
st.caption("See which games in your Steam library run on Linux / Steam Deck via ProtonDB.")

with st.sidebar:
    st.header("Your Steam account")
    user_input = st.text_input(
        "Steam username, SteamID64, or profile URL",
        help="Steam username only works for custom URLs, enabled in profile settings.",
    )
    api_key = os.environ.get("STEAM_API_KEY", "")
    api_key = st.text_input(
         "Steam Web API key (optional)", type="password",
         help="Get one free at steamcommunity.com/dev/apikey. Without it the app "
              "falls back to the public XML list, which is less reliable.",
    )

    if not api_key:
        api_key = os.environ.get("STEAM_API_KEY", "")

    go = st.button("Load library", type="primary", width='stretch')
    st.info("Your Steam profile's **Game details** must be set to **Public**.")

if go and user_input:
    try:
        identifier = extract_identifier(user_input)
        with st.spinner("Fetching Steam library…"):
            steam_id = resolve_steam_id(identifier, api_key)
            if not steam_id:
                raise ValueError(
                    f"Couldn't find a Steam profile with the custom URL name '{identifier}'. "
                    "Use the name from steamcommunity.com/id/<name> (not your login or "
                    "display name), or paste your profile URL or SteamID64."
                )
            if api_key and steam_id:
                games = fetch_library_api(steam_id, api_key)
            else:
                st.warning("API key limit reached, try again later or get your own on https://steamcommunity.com/dev/apikey")
        st.session_state["df"] = build_dataframe(games)
        st.session_state["user"] = identifier
    except Exception as e:
        st.error(f"Couldn't load library: {e}")

df = st.session_state.get("df")
if df is None:
    st.write("👈 Enter your Steam username in the sidebar to get started.")
    st.stop()

# Filters
c1, c2, c3 = st.columns([2, 3, 2])
tiers = c1.multiselect("Rating", TIER_ORDER, default=[t for t in TIER_ORDER])
query = c2.text_input("Search games")
min_hours = c3.number_input("Min hours played", min_value=0.0, value=0.0, step=1.0)

view = df[df["tier"].astype(str).isin(tiers) & (df["hours"] >= min_hours)]
if query:
    view = view[view["name"].str.contains(query, case=False, na=False)]

# Summary metrics
counts = df["tier"].astype(str).value_counts()
playable = counts.reindex(["platinum", "gold", "silver"]).fillna(0).sum()
m = st.columns(4)
m[0].metric("Games", len(df))
m[1].metric("Playable (Silver+)", f"{int(playable)}", f"{playable / len(df):.0%}")
m[2].metric("Borked", int(counts.get("borked", 0)))
m[3].metric("No ProtonDB data", int(counts.get("no data", 0)))

tab_table, tab_groups, tab_chart = st.tabs(["📋 Table", "🗂️ By rating", "📊 Overview"])

with tab_table:
    st.dataframe(
        view[["image", "name", "rating", "trending", "reports", "hours", "protondb"]],
        width='stretch', hide_index=True, height=600,
        column_config={
            "image": st.column_config.ImageColumn("", width="small"),
            "name": "Game",
            "rating": "ProtonDB",
            "trending": "Trending",
            "reports": st.column_config.NumberColumn("Reports"),
            "hours": st.column_config.NumberColumn("Hours played", format="%.1f"),
            "protondb": st.column_config.LinkColumn("Link", display_text="Open"),
        },
    )
    st.download_button("Download CSV",
                       view.drop(columns=["image"]).to_csv(index=False),
                       file_name="steam_protondb.csv", mime="text/csv")

with tab_groups:
    for tier in TIER_ORDER:
        group = view[view["tier"].astype(str) == tier]
        if group.empty:
            continue
        with st.expander(f"{TIER_EMOJI[tier]} {tier.title()} ({len(group)})",
                         expanded=tier in ("platinum", "borked")):
            for _, row in group.iterrows():
                st.markdown(
                    f"- [{row['name']}]({row['protondb']}) — {row['hours']} h"
                )

with tab_chart:
    chart_df = counts.reindex(TIER_ORDER).fillna(0).astype(int).rename("games").to_frame()
    st.bar_chart(chart_df)
    st.subheader("Most played games with issues")
    problems = df[df["tier"].astype(str).isin(["bronze", "borked"])].nlargest(10, "hours")
    st.dataframe(problems[["name", "rating", "hours"]], hide_index=True,
                 width='stretch')
