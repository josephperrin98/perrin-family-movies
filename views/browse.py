"""
Browse page - Landing page with search, genre filter, and activity feed.
"""

import streamlit as st
import database as db
import omdb
from components import search_bar


def render():
    """Render the browse page."""
    st.header("🏠 Browse")
    
    # Search bar section
    st.subheader("🔍 Find a Movie")
    search_bar.render(
        key="browse_search",
        placeholder="Search for any movie...",
        on_select=handle_movie_select
    )
    
    st.divider()
    
    # Feed section header
    st.subheader("📰 Latest from the Family")
    
    # Get users and genres for filters
    users = db.get_all_users()
    genres = db.get_all_genres()
    
    # Build filter options as lists (for index-based selection)
    user_keys = ["all"] + [str(u["id"]) for u in users]
    user_labels = ["👥 Everyone"] + [f"{u['avatar_emoji']} {u['display_name']}" for u in users]
    
    genre_keys = ["all"] + list(genres)
    genre_labels = ["🎭 All Genres"] + list(genres)
    
    # Get current filter indices (default to 0 = "all")
    current_user_idx = 0
    current_genre_idx = 0
    
    # Filters row
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        user_idx = st.selectbox(
            "Filter by person",
            options=range(len(user_keys)),
            format_func=lambda i: user_labels[i],
            index=current_user_idx,
            key="feed_user_select",
            label_visibility="collapsed"
        )
        selected_user_key = user_keys[user_idx]
    
    with col2:
        genre_idx = st.selectbox(
            "Filter by genre",
            options=range(len(genre_keys)),
            format_func=lambda i: genre_labels[i],
            index=current_genre_idx,
            key="feed_genre_select",
            label_visibility="collapsed"
        )
        selected_genre_key = genre_keys[genre_idx]
    
    with col3:
        # Reset just navigates back to browse (clears widget state)
        if st.button("🔄 Reset", use_container_width=True):
            # Clear the widget keys and rerun
            if "feed_user_select" in st.session_state:
                del st.session_state.feed_user_select
            if "feed_genre_select" in st.session_state:
                del st.session_state.feed_genre_select
            st.rerun()
    
    # Show active filters
    active_filters = []
    if selected_user_key != "all":
        active_filters.append(f"Person: {user_labels[user_idx]}")
    if selected_genre_key != "all":
        active_filters.append(f"Genre: {selected_genre_key}")
    
    if active_filters:
        st.info(f"🔍 Filtering by: {' · '.join(active_filters)}")
    
    # Convert filter keys to actual values
    user_id_filter = int(selected_user_key) if selected_user_key != "all" else None
    genre_filter = selected_genre_key if selected_genre_key != "all" else None
    
    # Display the feed
    render_feed(user_id=user_id_filter, genre=genre_filter)


def handle_movie_select(movie_details: dict):
    """Handle when a movie is selected from search results."""
    imdb_id = movie_details.get("imdbID")
    if imdb_id:
        # Store movie in database
        db.get_or_create_movie(omdb.format_movie_for_db(movie_details))
        
        # Navigate to movie page
        st.session_state.current_page = "movie"
        st.session_state.selected_imdb_id = imdb_id
        st.rerun()


def render_feed(user_id: int = None, genre: str = None, limit: int = 50):
    """
    Render the activity feed showing latest watched movies.
    
    Args:
        user_id: Optional user filter (show only this user's ratings)
        genre: Optional genre filter
        limit: Maximum number of items to fetch
    """
    # Get latest watched movies
    feed_items = db.get_latest_watched(limit=limit)
    
    if not feed_items:
        st.warning("🎬 No movies rated yet! Be the first to add a review.")
        
        if st.button("➕ Add Your First Review", use_container_width=True):
            st.session_state.current_page = "add_review"
            st.rerun()
        return
    
    # Apply user filter
    if user_id is not None:
        feed_items = [item for item in feed_items if item.get("user_id") == user_id]
    
    # Apply genre filter
    if genre is not None:
        feed_items = [
            item for item in feed_items 
            if item.get("genre") and genre.lower() in item.get("genre", "").lower()
        ]
    
    # Check if any items remain after filtering
    if not feed_items:
        st.warning("No movies match the selected filters. Try different filters!")
        return
    
    # Show count
    st.caption(f"Showing {len(feed_items)} rating{'s' if len(feed_items) != 1 else ''}")
    
    # Render feed items
    for item in feed_items:
        render_feed_item(item)


def render_feed_item(item: dict):
    """Render a single feed item."""
    with st.container():
        # Header row: User info
        header_col1, header_col2 = st.columns([4, 1])
        
        with header_col1:
            avatar = item.get("avatar_emoji", "👤")
            display_name = item.get("display_name", "Unknown")
            st.markdown(f"**{avatar} {display_name}** rated a movie")
        
        with header_col2:
            created_at = item.get("created_at", "")
            if created_at:
                st.caption(format_time_ago(created_at))
        
        # Movie info row
        col1, col2, col3 = st.columns([1, 4, 1])
        
        with col1:
            poster = item.get("poster_url", "")
            if poster and poster != "N/A":
                st.image(poster, width=80)
            else:
                st.markdown("### 🎬")
        
        with col2:
            title = item.get("title", "Unknown")
            year = item.get("year", "")
            score = item.get("score", 0)
            comment = item.get("comment", "")
            
            st.markdown(f"**{title}** ({year})")
            
            # Star rating display
            from components import format_stars
            stars = format_stars(score)
            st.markdown(f"{stars} **{score}/10**")
            
            # Comment
            if comment:
                st.caption(f"💬 \"{comment}\"")
        
        with col3:
            imdb_id = item.get("imdb_id")
            movie_id = item.get("movie_id")
            if imdb_id:
                if st.button("View details", key=f"feed_view_{imdb_id}_{item.get('user_id')}_{item.get('created_at')}", use_container_width=True):
                    st.session_state.current_page = "movie"
                    st.session_state.selected_imdb_id = imdb_id
                    st.rerun()
                
                # Add to watchlist button (only if user hasn't rated this movie)
                import identity
                current_user = identity.get_current_user()
                if current_user and movie_id:
                    user_rating = db.get_user_rating(current_user["id"], movie_id)
                    if not user_rating:
                        in_watchlist = db.is_in_watchlist(current_user["id"], movie_id)
                        if in_watchlist:
                            st.button("✓ In Watchlist", key=f"feed_wl_{imdb_id}_{item.get('created_at')}", use_container_width=True, disabled=True)
                        else:
                            if st.button("+ Watchlist", key=f"feed_wl_{imdb_id}_{item.get('created_at')}", use_container_width=True):
                                db.add_to_watchlist(current_user["id"], movie_id)
                                st.toast("Added to watchlist!")
                                st.rerun()
    
    st.divider()


def format_time_ago(timestamp) -> str:
    """Format timestamp as 'time ago' string."""
    from datetime import datetime
    
    if not timestamp:
        return ""
    
    if isinstance(timestamp, str):
        try:
            # Handle SQLite timestamp format (YYYY-MM-DD HH:MM:SS.ffffff)
            # Replace space with T for ISO format parsing
            ts = timestamp.replace(" ", "T")
            # Remove timezone info if present, treat as local time
            if "+" in ts:
                ts = ts.split("+")[0]
            if "Z" in ts:
                ts = ts.replace("Z", "")
            dt = datetime.fromisoformat(ts)
        except ValueError:
            return ""
    else:
        dt = timestamp
    
    now = db.utc_now()  # timestamps are stored in UTC
    
    # Calculate difference
    diff = now - dt
    total_seconds = diff.total_seconds()
    
    # Handle negative differences (future timestamps, shouldn't happen)
    if total_seconds < 0:
        return "Just now"
    
    # Calculate time ago
    minutes = int(total_seconds // 60)
    hours = int(total_seconds // 3600)
    days = int(total_seconds // 86400)
    
    if days > 30:
        months = days // 30
        return f"{months} month{'s' if months > 1 else ''} ago"
    elif days > 0:
        return f"{days} day{'s' if days > 1 else ''} ago"
    elif hours > 0:
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif minutes > 0:
        return f"{minutes} min{'s' if minutes > 1 else ''} ago"
    else:
        return "Just now"
