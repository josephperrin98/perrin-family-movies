"""
Genre filter component.
Global filter that persists across pages.
"""

import streamlit as st
from typing import Optional
import database as db


def render(key: str = "genre_filter", show_country: bool = False) -> tuple[Optional[str], Optional[str]]:
    """
    Render genre (and optionally country) filter dropdowns.
    
    Args:
        key: Unique key for session state
        show_country: Whether to also show country filter
    
    Returns:
        (selected_genre, selected_country) - None means "All"
    """
    genre_key = f"{key}_genre"
    country_key = f"{key}_country"
    
    # Initialize session state
    if genre_key not in st.session_state:
        st.session_state[genre_key] = None
    if country_key not in st.session_state:
        st.session_state[country_key] = None
    
    # Get available options from database
    genres = ["All Genres"] + db.get_all_genres()
    
    if show_country:
        countries = ["All Countries"] + db.get_all_countries()
        col1, col2 = st.columns(2)
        
        with col1:
            selected_genre = st.selectbox(
                "Genre",
                genres,
                index=0 if not st.session_state[genre_key] else genres.index(st.session_state[genre_key]) if st.session_state[genre_key] in genres else 0,
                key=f"{key}_genre_select",
                label_visibility="collapsed"
            )
        
        with col2:
            selected_country = st.selectbox(
                "Country",
                countries,
                index=0 if not st.session_state[country_key] else countries.index(st.session_state[country_key]) if st.session_state[country_key] in countries else 0,
                key=f"{key}_country_select",
                label_visibility="collapsed"
            )
        
        # Update session state
        st.session_state[genre_key] = None if selected_genre == "All Genres" else selected_genre
        st.session_state[country_key] = None if selected_country == "All Countries" else selected_country
        
        return st.session_state[genre_key], st.session_state[country_key]
    
    else:
        selected_genre = st.selectbox(
            "Filter by Genre",
            genres,
            index=0 if not st.session_state[genre_key] else genres.index(st.session_state[genre_key]) if st.session_state[genre_key] in genres else 0,
            key=f"{key}_genre_select",
            label_visibility="collapsed"
        )
        
        st.session_state[genre_key] = None if selected_genre == "All Genres" else selected_genre
        
        return st.session_state[genre_key], None


def render_inline(key: str = "genre_filter") -> Optional[str]:
    """
    Render a compact inline genre filter.
    
    Returns:
        Selected genre or None for "All"
    """
    genre_key = f"{key}_genre"
    
    if genre_key not in st.session_state:
        st.session_state[genre_key] = None
    
    genres = ["All"] + db.get_all_genres()
    
    current_index = 0
    if st.session_state[genre_key] and st.session_state[genre_key] in genres:
        current_index = genres.index(st.session_state[genre_key])
    
    selected = st.selectbox(
        "Genre",
        genres,
        index=current_index,
        key=f"{key}_inline",
        label_visibility="collapsed"
    )
    
    st.session_state[genre_key] = None if selected == "All" else selected
    return st.session_state[genre_key]


def get_current_genre(key: str = "genre_filter") -> Optional[str]:
    """Get the currently selected genre without rendering."""
    return st.session_state.get(f"{key}_genre")


def get_current_country(key: str = "genre_filter") -> Optional[str]:
    """Get the currently selected country without rendering."""
    return st.session_state.get(f"{key}_country")


def clear_filters(key: str = "genre_filter"):
    """Clear all filters."""
    st.session_state[f"{key}_genre"] = None
    st.session_state[f"{key}_country"] = None


