"""
Search bar component with live autocomplete suggestions.
Reusable across Browse and Add Review pages.
"""

import streamlit as st
from typing import Callable, Optional
import omdb


def render(
    key: str = "search",
    placeholder: str = "Search for a movie...",
    on_select: Optional[Callable[[dict], None]] = None,
    show_search_button: bool = False,
    max_suggestions: int = 6,
):
    """
    Render a search bar with live autocomplete suggestions.

    Suggestions appear as compact rows below the input as the user types
    (triggered on Enter or when the field loses focus).

    Args:
        key: Unique key for session state
        placeholder: Placeholder text for input
        on_select: Callback when a movie is selected (receives full OMDb detail dict)
        show_search_button: Show an explicit search button next to the input
        max_suggestions: Maximum suggestions to display
    """
    search_key = f"{key}_query"
    results_key = f"{key}_results"

    if search_key not in st.session_state:
        st.session_state[search_key] = ""
    if results_key not in st.session_state:
        st.session_state[results_key] = []

    # --- Input row ---
    if show_search_button:
        col_input, col_btn = st.columns([5, 1])
        with col_input:
            query = st.text_input(
                "Search",
                value=st.session_state[search_key],
                placeholder=placeholder,
                label_visibility="collapsed",
                key=f"{key}_input",
            )
        with col_btn:
            search_clicked = st.button("🔍", key=f"{key}_btn", use_container_width=True)
    else:
        query = st.text_input(
            "Search",
            value=st.session_state[search_key],
            placeholder=placeholder,
            label_visibility="collapsed",
            key=f"{key}_input",
        )
        search_clicked = False

    # --- Trigger search when query changes ---
    query_changed = query and query != st.session_state[search_key] and len(query) >= 2
    if search_clicked or query_changed:
        st.session_state[search_key] = query
        if query.strip():
            with st.spinner("Searching..."):
                result = omdb.search_movies(query)
                if result["error"]:
                    st.error(f"Search error: {result['error']}")
                    st.session_state[results_key] = []
                else:
                    st.session_state[results_key] = result["results"]
        else:
            st.session_state[results_key] = []

    # --- Display compact suggestions ---
    results = st.session_state[results_key]
    if results:
        _render_suggestions(results[:max_suggestions], key, on_select)


def _render_suggestions(
    results: list[dict],
    key: str,
    on_select: Optional[Callable[[dict], None]] = None,
):
    """Render search results as compact, clickable suggestion rows."""
    for i, movie in enumerate(results):
        imdb_id = movie.get("imdbID", "")
        title = movie.get("Title", "Unknown")
        year = movie.get("Year", "")
        poster = movie.get("Poster", "")

        col_poster, col_info, col_action = st.columns([0.6, 5, 1.2])

        with col_poster:
            if omdb.is_valid_poster(poster):
                st.image(poster, width=40)
            else:
                st.markdown("🎬")

        with col_info:
            st.markdown(f"**{title}** ({year})")

        with col_action:
            if st.button("Select", key=f"{key}_sel_{imdb_id}_{i}", use_container_width=True):
                if on_select:
                    with st.spinner("Loading..."):
                        details = omdb.get_movie_details(imdb_id)
                        if "error" not in details:
                            on_select(details)
                        else:
                            st.error(f"Error: {details['error']}")
                else:
                    st.session_state.selected_movie = movie
                    st.session_state.selected_imdb_id = imdb_id


def clear_search(key: str = "search"):
    """Clear search state."""
    search_key = f"{key}_query"
    results_key = f"{key}_results"
    if search_key in st.session_state:
        st.session_state[search_key] = ""
    if results_key in st.session_state:
        st.session_state[results_key] = []
