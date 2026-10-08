"""
Your Movies page - User's personal watched list and stats.
Also used to view other family members' profiles.
"""

import streamlit as st
import database as db
import identity
from components import genre_filter


def render(user_id: int = None):
    """
    Render the your movies page.
    
    Args:
        user_id: If provided, show this user's movies (for viewing other profiles).
                 If None, show current user's movies.
    """
    current_user = identity.get_current_user()
    
    # Determine whose movies to show
    if user_id and user_id != current_user["id"]:
        # Viewing another user's profile
        target_user = db.get_user_by_id(user_id)
        if not target_user:
            st.error("User not found.")
            return
        is_own_profile = False
    else:
        # Viewing own profile
        target_user = current_user
        is_own_profile = True
    
    # Header
    if is_own_profile:
        st.header("📚 Your Movies")
    else:
        st.header(f"{target_user['avatar_emoji']} {target_user['display_name']}'s Movies")
        if st.button("← Back to Family"):
            st.session_state.current_page = "family"
            st.rerun()
    
    # Stats section
    render_stats(target_user)
    
    st.divider()
    
    # Tabs for Rated Movies and Watchlist
    if is_own_profile:
        tab1, tab2 = st.tabs(["🎬 Rated Movies", "📋 My Watchlist"])
        
        with tab1:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.subheader("🎬 Rated Movies")
            with col2:
                selected_genre = genre_filter.render_inline(key=f"your_movies_{target_user['id']}")
            render_movie_list(target_user, genre=selected_genre)
        
        with tab2:
            st.subheader("📋 My Watchlist")
            render_watchlist(target_user)
    else:
        # For other users, just show rated movies
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader("🎬 Rated Movies")
        with col2:
            selected_genre = genre_filter.render_inline(key=f"your_movies_{target_user['id']}")
        render_movie_list(target_user, genre=selected_genre)


def render_stats(user: dict):
    """Render user statistics."""
    stats = db.get_user_stats(user["id"])
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Movies Rated", stats["total_rated"])
    
    with col2:
        avg = stats["avg_rating"]
        st.metric("Average Rating", f"{avg}/10" if avg else "—")
    
    with col3:
        # Get highest rated movie
        ratings = db.get_user_ratings(user["id"])
        if ratings:
            highest = max(ratings, key=lambda r: r["score"])
            st.metric("Highest Rated", f"{highest['score']}/10")
        else:
            st.metric("Highest Rated", "—")
    
    with col4:
        # Favorite genres
        if stats["top_genres"]:
            st.metric("Favorite Genre", stats["top_genres"][0].split(",")[0].strip())
        else:
            st.metric("Favorite Genre", "—")


def render_movie_list(user: dict, genre: str = None):
    """Render the list of rated movies."""
    ratings = db.get_user_ratings(user["id"])
    
    if not ratings:
        st.info("No movies rated yet.")
        
        # Only show add button for own profile
        if user["id"] == identity.get_current_user()["id"]:
            if st.button("➕ Add Your First Review", use_container_width=True):
                st.session_state.current_page = "add_review"
                st.rerun()
        return
    
    # Filter by genre if specified
    if genre:
        # Need to get genre info for each movie
        filtered_ratings = []
        for rating in ratings:
            movie = db.get_movie_by_id(rating["movie_id"])
            if movie and movie.get("genre"):
                if genre.lower() in movie["genre"].lower():
                    rating["genre"] = movie["genre"]
                    filtered_ratings.append(rating)
        ratings = filtered_ratings
        
        if not ratings:
            st.info(f"No movies found with genre '{genre}'.")
            return
    
    # Sort options
    sort_col1, sort_col2 = st.columns([2, 2])
    with sort_col1:
        sort_by = st.selectbox(
            "Sort by",
            ["Recent", "Highest Rated", "Lowest Rated", "Title A-Z"],
            label_visibility="collapsed"
        )
    
    # Sort ratings
    if sort_by == "Recent":
        ratings.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    elif sort_by == "Highest Rated":
        ratings.sort(key=lambda r: r["score"], reverse=True)
    elif sort_by == "Lowest Rated":
        ratings.sort(key=lambda r: r["score"])
    elif sort_by == "Title A-Z":
        ratings.sort(key=lambda r: r.get("title", "").lower())
    
    st.caption(f"Showing {len(ratings)} movie{'s' if len(ratings) != 1 else ''}")
    
    # Display movies
    for rating in ratings:
        render_movie_row(rating)


def render_movie_row(rating: dict):
    """Render a single movie row."""
    with st.container():
        col1, col2, col3, col4 = st.columns([1, 3, 1, 1])
        
        with col1:
            poster = rating.get("poster_url", "")
            if poster and poster != "N/A":
                st.image(poster, width=70)
            else:
                st.markdown("### 🎬")
        
        with col2:
            title = rating.get("title", "Unknown")
            year = rating.get("year", "")
            
            st.markdown(f"**{title}** ({year})")
            
            # Comment preview
            comment = rating.get("comment", "")
            if comment:
                # Truncate long comments
                preview = comment[:80] + "..." if len(comment) > 80 else comment
                st.caption(f"💬 \"{preview}\"")
            
            # Date
            created_at = rating.get("created_at", "")
            if created_at:
                st.caption(f"Rated: {format_date(created_at)}")
        
        with col3:
            score = rating.get("score", 0)
            from components import format_stars
            stars = format_stars(score)
            st.markdown(f"{stars}")
            st.markdown(f"**{score}/10**")
        
        with col4:
            imdb_id = rating.get("imdb_id")
            if imdb_id:
                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    if st.button("👁", key=f"view_{imdb_id}_{rating.get('created_at')}", help="View movie"):
                        st.session_state.current_page = "movie"
                        st.session_state.selected_imdb_id = imdb_id
                        st.rerun()
                with btn_col2:
                    if st.button("✏️", key=f"edit_{imdb_id}_{rating.get('created_at')}", help="Edit review"):
                        st.session_state.current_page = "movie"
                        st.session_state.selected_imdb_id = imdb_id
                        st.session_state.open_edit = True  # Flag to auto-open edit
                        st.rerun()
    
    st.divider()


def render_watchlist(user: dict):
    """Render the user's watchlist."""
    watchlist = db.get_user_watchlist(user["id"])
    
    if not watchlist:
        st.info("Your watchlist is empty. Add movies you want to watch!")
        st.caption("💡 Tip: Search for a movie in Browse and click '+ Watchlist'")
        return
    
    st.caption(f"{len(watchlist)} movie{'s' if len(watchlist) != 1 else ''} to watch")
    
    for movie in watchlist:
        render_watchlist_row(movie, user["id"])


def render_watchlist_row(movie: dict, user_id: int):
    """Render a single watchlist row."""
    with st.container():
        col1, col2, col3 = st.columns([1, 4, 1])
        
        with col1:
            poster = movie.get("poster_url", "")
            if poster and poster != "N/A":
                st.image(poster, width=70)
            else:
                st.markdown("### 🎬")
        
        with col2:
            title = movie.get("title", "Unknown")
            year = movie.get("year", "")
            director = movie.get("director", "")
            genre = movie.get("genre", "")
            
            st.markdown(f"**{title}** ({year})")
            if director:
                st.caption(f"🎬 {director}")
            if genre:
                st.caption(f"🎭 {genre}")
        
        with col3:
            # Action buttons
            if st.button("👁 View", key=f"wl_view_{movie['imdb_id']}", use_container_width=True):
                st.session_state.current_page = "movie"
                st.session_state.selected_imdb_id = movie["imdb_id"]
                st.rerun()
            
            if st.button("✅ Watched", key=f"wl_watched_{movie['imdb_id']}", use_container_width=True, help="Mark as watched & rate"):
                st.session_state.current_page = "movie"
                st.session_state.selected_imdb_id = movie["imdb_id"]
                st.session_state.open_edit = True
                st.rerun()
            
            if st.button("🗑️ Remove", key=f"wl_remove_{movie['imdb_id']}", use_container_width=True):
                db.remove_from_watchlist(user_id, movie["id"])
                st.rerun()
    
    st.divider()


def format_date(timestamp) -> str:
    """Format timestamp as readable date."""
    from datetime import datetime
    
    if isinstance(timestamp, str):
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00").replace(" ", "T"))
            return dt.strftime("%b %d, %Y")
        except ValueError:
            return timestamp
    return str(timestamp)
