"""
Top 100 page - Family movie rankings with genre and country filters.
"""

import streamlit as st
import database as db
from components import genre_filter


def render():
    """Render the top 100 page."""
    st.header("🏆 Top 100 Perrin Movies")
    st.caption("The best movies according to our family!")
    
    with st.expander("ℹ️ How ratings are calculated"):
        st.write("""
        **Normalized ratings** account for different rating styles:
        - If you're a harsh critic (avg 5/10), your 7 counts as "very good"
        - If you're generous (avg 8.5/10), your 7 counts as "below your average"
        
        This way, everyone's opinion is weighted fairly regardless of their rating style.
        The "Raw avg" shows the simple average of all ratings.
        """)
    
    # Filter section
    render_filters()
    
    st.divider()
    
    # Get current filters
    selected_genre = genre_filter.get_current_genre("top100_filter")
    selected_country = genre_filter.get_current_country("top100_filter")
    
    # Get rankings
    rankings = db.get_family_top100(genre=selected_genre, country=selected_country, limit=100)
    
    if not rankings:
        if selected_genre or selected_country:
            st.info("No movies found with the selected filters. Try different filters!")
            if st.button("Clear Filters"):
                genre_filter.clear_filters("top100_filter")
                st.rerun()
        else:
            st.info("No movies have been rated yet. Be the first to add a review!")
            if st.button("➕ Add a Review", use_container_width=True):
                st.session_state.current_page = "add_review"
                st.rerun()
        return
    
    # Stats summary
    render_stats_summary(rankings)
    
    st.divider()
    
    # Display rankings
    st.subheader(f"🎬 {len(rankings)} Movies Ranked")
    
    for rank, movie in enumerate(rankings, 1):
        render_ranking_row(rank, movie)


def render_filters():
    """Render the filter section."""
    st.subheader("🔍 Filters")
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        # Genre filter
        genres = ["All Genres"] + db.get_all_genres()
        current_genre = genre_filter.get_current_genre("top100_filter")
        
        genre_index = 0
        if current_genre and current_genre in genres:
            genre_index = genres.index(current_genre)
        
        selected_genre = st.selectbox(
            "Genre",
            genres,
            index=genre_index,
            key="top100_genre_select"
        )
        
        # Update session state
        if selected_genre == "All Genres":
            st.session_state["top100_filter_genre"] = None
        else:
            st.session_state["top100_filter_genre"] = selected_genre
    
    with col2:
        # Country filter
        countries = ["All Countries"] + db.get_all_countries()
        current_country = genre_filter.get_current_country("top100_filter")
        
        country_index = 0
        if current_country and current_country in countries:
            country_index = countries.index(current_country)
        
        selected_country = st.selectbox(
            "Country",
            countries,
            index=country_index,
            key="top100_country_select"
        )
        
        # Update session state
        if selected_country == "All Countries":
            st.session_state["top100_filter_country"] = None
        else:
            st.session_state["top100_filter_country"] = selected_country
    
    with col3:
        st.write("")  # Spacing
        st.write("")
        if st.button("Clear All", use_container_width=True):
            st.session_state["top100_filter_genre"] = None
            st.session_state["top100_filter_country"] = None
            st.rerun()


def render_stats_summary(rankings: list):
    """Render summary statistics."""
    if not rankings:
        return
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Movies", len(rankings))
    
    with col2:
        # Average of all averages
        avg_of_avg = sum(m["avg_rating"] for m in rankings) / len(rankings)
        st.metric("Overall Average", f"{avg_of_avg:.1f}/10")
    
    with col3:
        # Movie with most ratings
        most_rated = max(rankings, key=lambda m: m["num_ratings"])
        st.metric("Most Reviewed", f"{most_rated['num_ratings']} ratings")
    
    with col4:
        # Top rated movie
        top_movie = rankings[0]
        st.metric("#1 Movie", f"{top_movie['avg_rating']}/10")


def render_ranking_row(rank: int, movie: dict):
    """Render a single ranking row."""
    # Medal for top 3
    if rank == 1:
        medal = "🥇"
    elif rank == 2:
        medal = "🥈"
    elif rank == 3:
        medal = "🥉"
    else:
        medal = f"#{rank}"
    
    with st.container():
        col1, col2, col3, col4, col5 = st.columns([0.5, 1, 3, 1.5, 1])
        
        with col1:
            st.markdown(f"### {medal}")
        
        with col2:
            poster = movie.get("poster_url", "")
            if poster and poster != "N/A":
                st.image(poster, width=70)
            else:
                st.markdown("### 🎬")
        
        with col3:
            title = movie.get("title", "Unknown")
            year = movie.get("year", "")
            director = movie.get("director", "")
            genre = movie.get("genre", "")
            country = movie.get("country", "")
            
            st.markdown(f"**{title}** ({year})")
            
            # Info line
            info_parts = []
            if director and director != "N/A":
                info_parts.append(f"🎬 {director}")
            if genre and genre != "N/A":
                # Show first 2 genres
                genres = [g.strip() for g in genre.split(",")][:2]
                info_parts.append(f"🎭 {', '.join(genres)}")
            
            if info_parts:
                st.caption(" · ".join(info_parts))
            
            # Country
            if country and country != "N/A":
                # Show first 2 countries
                countries = [c.strip() for c in country.split(",")][:2]
                st.caption(f"🌍 {', '.join(countries)}")
        
        with col4:
            avg_rating = movie.get("avg_rating", 0)  # Normalized
            raw_avg = movie.get("raw_avg_rating", avg_rating)  # Original
            num_ratings = movie.get("num_ratings", 0)
            imdb_rating = movie.get("imdb_rating", "N/A")
            
            # Normalized family rating (prominent)
            from components import format_stars
            stars = format_stars(avg_rating)
            st.markdown(f"{stars}")
            st.markdown(f"**{avg_rating}/10**")
            
            # Show raw average if different from normalized
            if abs(avg_rating - raw_avg) > 0.1:
                st.caption(f"Raw avg: {raw_avg}/10")
            
            st.caption(f"{num_ratings} rating{'s' if num_ratings != 1 else ''}")
            
            # IMDb comparison
            if imdb_rating and imdb_rating != "N/A":
                try:
                    imdb_float = float(imdb_rating)
                    diff = avg_rating - imdb_float
                    if diff > 0:
                        st.caption(f"IMDb: {imdb_rating} (+{diff:.1f})")
                    elif diff < 0:
                        st.caption(f"IMDb: {imdb_rating} ({diff:.1f})")
                    else:
                        st.caption(f"IMDb: {imdb_rating}")
                except ValueError:
                    st.caption(f"IMDb: {imdb_rating}")
        
        with col5:
            imdb_id = movie.get("imdb_id")
            if imdb_id:
                if st.button("View", key=f"top100_{imdb_id}_{rank}"):
                    st.session_state.current_page = "movie"
                    st.session_state.selected_imdb_id = imdb_id
                    st.rerun()
    
    st.divider()
