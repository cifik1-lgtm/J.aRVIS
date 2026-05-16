import webbrowser
from urllib.parse import quote_plus


def weather_action(
    parameters: dict,
    player=None,
    session_memory=None,
) -> str:
    city     = parameters.get("city")
    when     = parameters.get("time", "today")  

    if not city or not isinstance(city, str) or not city.strip():
        msg = "Sir, the city is missing for the weather report."
        _log(msg, player)
        return msg

    city = city.strip()
    when = (when or "today").strip()

    search_query  = f"weather in {city} {when}"
    
    try:
        from .ghost_browser import GhostBrowser
        import asyncio
        
        async def _run_ghost():
            gb = GhostBrowser(player)
            # Launch HEADFUL (headless=False) so the user can see it
            await gb.start(headless=False)
            await gb.navigate(search_query)
            # We DON'T close it immediately so the user can look at the weather
            return gb

        # Start it in the background
        asyncio.run_coroutine_threadsafe(_run_ghost(), asyncio.get_event_loop())
    except Exception as e:
        msg = f"Sir, I couldn't launch the Ghost Browser for the weather report: {e}"
        _log(msg, player)
        return msg

    msg = f"Opening the weather for {city} in the Ghost Browser, sir."
    _log(msg, player)

    if session_memory:
        try:
            session_memory.set_last_search(query=search_query, response=msg)
        except Exception:
            pass

    return msg


def _log(message: str, player=None) -> None:
    print(f"[Weather] {message}")
    if player:
        try:
            player.write_log(f"JARVIS: {message}")
        except Exception:
            pass