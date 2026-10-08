"""
Movie card component for displaying movie info.
Reusable across different pages.
"""

import streamlit as st
from typing import Optional
import database as db
import omdb


def render(
    movie: dict,
    show_rating: bool = True,
    show_user_rating: Optional[float] = None,
    compact: bool = False,
    show_actions: bool = False,
    on_click: Optional[callable] = None
):
    """
    Render a movie card.
    
    Args:
        movie: Movie dict (from DB or OMDb)
        show_rating: Show IMDb rating
        show_user_rating: Show user's rating if provided
        compact: Use compact layout
        show_actions: Show action buttons
        on_click: Callback when card is clicked
    """
    # Normalize field names (DB uses lowercase, OMDb uses mixed case)
    title = movie.get("title") or movie.get("Title", "Unknown")
    year = movie.get("year") or movie.get("Year", "")
    poster = movie.get("poster_url") or movie.get("Poster", "")
    director = movie.get("director") or movie.get("Director", "")
    genre = movie.get("genre") or movie.get("Genre", "")
    imdb_rating = movie.get("imdb_rating") or movie.get("imdbRating", "")
    imdb_id = movie.get("imdb_id") or movie.get("imdbID", "")
    
    if compact:
        _render_compact(title, year, poster, imdb_rating, show_user_rating, imdb_id, on_click)
    else:
        _render_full(title, year, poster, director, genre, imdb_rating, show_user_rating, imdb_id, on_click)


def _render_compact(
    title: str,
    year: str,
    poster: str,
    imdb_rating: str,
    user_rating: Optional[float],
    imdb_id: str,
    on_click: Optional[callable]
):
    """Render compact card layout."""
    col1, col2, col3 = st.columns([1, 4, 1])
    
    with col1:
        if omdb.is_valid_poster(poster):
            st.image(poster, width=60)
        else:
            st.markdown("🎬")
    
    with col2:
        st.markdown(f"**{title}** ({year})")
        if imdb_rating:
            st.caption(f"⭐ {imdb_rating}")
    
    with col3:
        if user_rating is not None:
            st.metric("Your", f"{user_rating}", label_visibility="collapsed")
        if on_click:
            if st.button("View", key=f"view_{imdb_id}"):
                on_click(imdb_id)


def _render_full(
    title: str,
    year: str,
    poster: str,
    director: str,
    genre: str,
    imdb_rating: str,
    user_rating: Optional[float],
    imdb_id: str,
    on_click: Optional[callable]
):
    """Render full card layout."""
    col1, col2 = st.columns([1, 3])
    
    with col1:
        if omdb.is_valid_poster(poster):
            st.image(poster, width=120)
        else:
            st.markdown("### 🎬")
    
    with col2:
        st.markdown(f"### {title} ({year})")
        
        if director:
            st.write(f"**Director:** {director}")
        if genre:
            st.write(f"**Genre:** {genre}")
        
        rating_col1, rating_col2 = st.columns(2)
        with rating_col1:
            if imdb_rating:
                st.write(f"**IMDb:** ⭐ {imdb_rating}")
        with rating_col2:
            if user_rating is not None:
                st.write(f"**Your Rating:** ⭐ {user_rating}")
        
        if on_click:
            if st.button("View Details", key=f"view_{imdb_id}"):
                on_click(imdb_id)


def render_feed_item(
    user: dict,
    movie: dict,
    rating: dict,
    on_movie_click: Optional[callable] = None
):
    """
    Render a feed item showing a user's rating.
    
    Args:
        user: User dict with display_name, avatar_emoji
        movie: Movie dict
        rating: Rating dict with score, comment, created_at
    """
    # Normalize fields
    title = movie.get("title") or movie.get("Title", "Unknown")
    year = movie.get("year") or movie.get("Year", "")
    poster = movie.get("poster_url") or movie.get("Poster", "")
    imdb_id = movie.get("imdb_id") or movie.get("imdbID", "")
    
    avatar = user.get("avatar_emoji", "👤")
    display_name = user.get("display_name", "Unknown")
    score = rating.get("score", 0)
    comment = rating.get("comment", "")
    created_at = rating.get("created_at", "")
    
    with st.container():
        # Header: user info and timestamp
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"**{avatar} {display_name}** rated a movie")
        with col2:
            if created_at:
                st.caption(_format_time_ago(created_at))
        
        # Movie info
        col1, col2, col3 = st.columns([1, 4, 1])
        
        with col1:
            if omdb.is_valid_poster(poster):
                st.image(poster, width=80)
            else:
                st.markdown("🎬")
        
        with col2:
            if on_movie_click:
                if st.button(f"**{title}** ({year})", key=f"feed_{imdb_id}_{created_at}"):
                    on_movie_click(imdb_id)
            else:
                st.markdown(f"**{title}** ({year})")
            
            # Rating display
            from components import format_stars
            stars = format_stars(score)
            st.write(f"{stars} **{score}/10**")
            
            # Comment
            if comment:
                st.caption(f"💬 \"{comment}\"")
        
        with col3:
            pass  # Could add action buttons here
    
    st.divider()


def _format_time_ago(timestamp) -> str:
    """Format timestamp as 'time ago' string."""
    from datetime import datetime
    
    if isinstance(timestamp, str):
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            return timestamp
    else:
        dt = timestamp
    
    now = db.utc_now()  # timestamps are stored in UTC
    if dt.tzinfo:
        now = datetime.now(dt.tzinfo)
    
    diff = now - dt
    
    if diff.days > 30:
        return f"{diff.days // 30} months ago"
    elif diff.days > 0:
        return f"{diff.days} days ago"
    elif diff.seconds > 3600:
        return f"{diff.seconds // 3600} hours ago"
    elif diff.seconds > 60:
        return f"{diff.seconds // 60} mins ago"
    else:
        return "Just now"

