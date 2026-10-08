"""
Movie detail page - Full movie info and family ratings.
"""

import streamlit as st
import database as db
import omdb
import identity


def render(imdb_id: str = None):
    """Render the movie detail page."""
    if not imdb_id:
        st.warning("No movie selected.")
        if st.button("← Back to Browse"):
            st.session_state.current_page = "browse"
            st.rerun()
        return
    
    user = identity.get_current_user()
    
    # Try to get movie from database first
    movie = db.get_movie_by_imdb_id(imdb_id)
    
    # If not in database, fetch from OMDb
    if not movie:
        with st.spinner("Loading movie details..."):
            omdb_data = omdb.get_movie_details(imdb_id)
            
            if "error" in omdb_data:
                st.error(f"Error loading movie: {omdb_data['error']}")
                if st.button("← Back to Browse"):
                    st.session_state.current_page = "browse"
                    st.rerun()
                return
            
            # Save to database
            movie_data = omdb.format_movie_for_db(omdb_data)
            movie_id = db.get_or_create_movie(movie_data)
            movie = db.get_movie_by_id(movie_id)
            
            # Also store the full OMDb data for display
            movie.update({
                "actors": omdb_data.get("Actors"),
                "plot": omdb_data.get("Plot"),
                "runtime": omdb_data.get("Runtime"),
                "rated": omdb_data.get("Rated"),
            })
    
    # Back button
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("← Back"):
            st.session_state.current_page = "browse"
            st.rerun()
    
    st.divider()
    
    # Movie header
    render_movie_header(movie)
    
    st.divider()
    
    # Two columns: Your rating | Family ratings
    col1, col2 = st.columns([1, 1])
    
    with col1:
        render_your_rating(user, movie)
    
    with col2:
        render_family_ratings(movie, user["id"])


def render_movie_header(movie: dict):
    """Render the movie header with poster and details."""
    col1, col2 = st.columns([1, 2])
    
    with col1:
        poster = movie.get("poster_url") or movie.get("Poster", "")
        if poster and poster != "N/A":
            st.image(poster, width=250)
        else:
            st.markdown("# 🎬")
    
    with col2:
        title = movie.get("title") or movie.get("Title", "Unknown")
        year = movie.get("year") or movie.get("Year", "")
        
        st.markdown(f"# {title} ({year})")
        
        # Movie metadata
        director = movie.get("director") or movie.get("Director", "N/A")
        genre = movie.get("genre") or movie.get("Genre", "N/A")
        country = movie.get("country") or movie.get("Country", "N/A")
        actors = movie.get("actors") or movie.get("Actors", "N/A")
        imdb_rating = movie.get("imdb_rating") or movie.get("imdbRating", "N/A")
        runtime = movie.get("runtime") or movie.get("Runtime", "")
        rated = movie.get("rated") or movie.get("Rated", "")
        
        # Info grid
        info_col1, info_col2 = st.columns(2)
        
        with info_col1:
            st.write(f"**Director:** {director}")
            st.write(f"**Genre:** {genre}")
            st.write(f"**Country:** {country}")
        
        with info_col2:
            st.write(f"**IMDb Rating:** ⭐ {imdb_rating}")
            if runtime and runtime != "N/A":
                st.write(f"**Runtime:** {runtime}")
            if rated and rated != "N/A":
                st.write(f"**Rated:** {rated}")
        
        # Cast
        if actors and actors != "N/A":
            st.write(f"**Cast:** {actors}")
        
        # Plot
        plot = movie.get("plot") or movie.get("Plot", "")
        if plot and plot != "N/A":
            with st.expander("📖 Plot", expanded=False):
                st.write(plot)
        
        # Calculate family average
        movie_id = movie.get("id")
        if movie_id:
            ratings = db.get_movie_ratings(movie_id)
            if ratings:
                avg = sum(r["score"] for r in ratings) / len(ratings)
                st.markdown(f"### 👨‍👩‍👧‍👦 Family Rating: ⭐ {avg:.1f}/10")
                st.caption(f"Based on {len(ratings)} rating{'s' if len(ratings) > 1 else ''}")
            
            # Mom-compatible status
            mom_status = db.get_movie_mom_compatible_status(movie_id)
            if mom_status["status"] == "compatible":
                st.success(f"👸 Mom-compatible! ({mom_status['yes']} vote{'s' if mom_status['yes'] > 1 else ''})")
            elif mom_status["status"] == "not_compatible":
                st.error(f"⚠️ Not for Mom ({mom_status['no']} vote{'s' if mom_status['no'] > 1 else ''})")
            elif mom_status["status"] == "mixed":
                st.warning(f"🤔 Mixed opinions: {mom_status['yes']} yes, {mom_status['no']} no")


def render_your_rating(user: dict, movie: dict):
    """Render the current user's rating section."""
    st.subheader("📝 Your Rating")
    
    movie_id = movie.get("id")
    if not movie_id:
        st.info("Rate this movie to add it to your collection!")
        return
    
    # Get existing rating
    existing_rating = db.get_user_rating(user["id"], movie_id)
    
    if existing_rating:
        # Check if we just saved a rating
        if st.session_state.pop("rating_saved", False):
            st.success("✅ Rating updated successfully!")
        
        st.info(f"You rated this movie **{existing_rating['score']}/10**")
        if existing_rating.get("comment"):
            st.caption(f"💬 \"{existing_rating['comment']}\"")
        st.caption(f"Rated on: {format_date(existing_rating['created_at'])}")
        
        # Check if we should auto-open edit (coming from Your Movies edit button)
        auto_open = st.session_state.pop("open_edit", False)
        
        # Option to update
        with st.expander("✏️ Update your rating", expanded=auto_open):
            render_rating_form(user, movie, existing_rating)
    else:
        st.info("You haven't rated this movie yet.")
        
        # Watchlist button
        if movie_id:
            in_watchlist = db.is_in_watchlist(user["id"], movie_id)
            if in_watchlist:
                if st.button("✅ In Watchlist", use_container_width=True, disabled=True):
                    pass
                if st.button("🗑️ Remove from Watchlist", use_container_width=True):
                    db.remove_from_watchlist(user["id"], movie_id)
                    st.rerun()
            else:
                if st.button("📋 Add to Watchlist", use_container_width=True, type="secondary"):
                    db.add_to_watchlist(user["id"], movie_id)
                    st.success("Added to your watchlist!")
                    st.rerun()
        
        render_rating_form(user, movie)


def render_rating_form(user: dict, movie: dict, existing_rating: dict = None):
    """Render the rating form."""
    movie_id = movie.get("id")
    imdb_id = movie.get("imdb_id")
    
    with st.form(f"rating_form_{imdb_id}"):
        default_score = existing_rating["score"] if existing_rating else 7.0
        score = st.slider(
            "Rating",
            min_value=1.0,
            max_value=10.0,
            value=float(default_score),
            step=0.1
        )
        
        default_comment = existing_rating["comment"] if existing_rating else ""
        comment = st.text_area(
            "Comment (optional)",
            value=default_comment or "",
            placeholder="Share your thoughts...",
            max_chars=500
        )
        
        # Mom compatible option
        default_mom_compat = existing_rating.get("mom_compatible") if existing_rating else None
        mom_options = ["Don't know", "👸 Yes, Mom-friendly", "⚠️ No, not for Mom"]
        default_idx = 0
        if default_mom_compat is True:
            default_idx = 1
        elif default_mom_compat is False:
            default_idx = 2
        
        mom_choice = st.radio("Mom-compatible?", mom_options, index=default_idx, horizontal=True)
        
        if mom_choice == mom_options[1]:
            mom_compatible = True
        elif mom_choice == mom_options[2]:
            mom_compatible = False
        else:
            mom_compatible = None
        
        submitted = st.form_submit_button(
            "Update Rating" if existing_rating else "Submit Rating",
            use_container_width=True,
            type="primary"
        )
        
    # Handle form submission outside the form context
    if submitted:
        try:
            # Ensure movie is in database
            current_movie_id = movie_id
            if not current_movie_id:
                imdb_data = omdb.get_movie_details(imdb_id)
                if "error" not in imdb_data:
                    movie_data = omdb.format_movie_for_db(imdb_data)
                    current_movie_id = db.get_or_create_movie(movie_data)
            
            if current_movie_id:
                db.add_rating(user["id"], current_movie_id, score, comment, mom_compatible)
                db.set_watch_status(user["id"], current_movie_id, "watched")
                st.session_state.rating_saved = True
                st.rerun()
            else:
                st.error("Error: Could not find movie in database")
        except Exception as e:
            st.error(f"Error saving rating: {str(e)}")


def render_family_ratings(movie: dict, current_user_id: int):
    """Render all family members' ratings for this movie."""
    st.subheader("👨‍👩‍👧‍👦 Family Ratings")
    
    movie_id = movie.get("id")
    if not movie_id:
        st.info("No ratings yet.")
        return
    
    ratings = db.get_movie_ratings(movie_id)
    
    if not ratings:
        st.info("No one has rated this movie yet. Be the first!")
        return
    
    # Sort: current user first, then by score descending
    ratings.sort(key=lambda r: (r["user_id"] != current_user_id, -r["score"]))
    
    for rating in ratings:
        render_rating_card(rating, is_current_user=(rating["user_id"] == current_user_id))


def render_rating_card(rating: dict, is_current_user: bool = False):
    """Render a single rating card."""
    avatar = rating.get("avatar_emoji", "👤")
    display_name = rating.get("display_name", "Unknown")
    score = rating.get("score", 0)
    comment = rating.get("comment", "")
    created_at = rating.get("created_at", "")
    
    with st.container():
        col1, col2, col3 = st.columns([1, 3, 1])
        
        with col1:
            st.markdown(f"### {avatar}")
        
        with col2:
            name_suffix = " (You)" if is_current_user else ""
            st.markdown(f"**{display_name}**{name_suffix}")
            
            # Star display
            from components import format_stars
            stars = format_stars(score)
            st.write(f"{stars} **{score}/10**")
            
            if comment:
                st.caption(f"💬 \"{comment}\"")
        
        with col3:
            if created_at:
                st.caption(format_date(created_at))
    
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
