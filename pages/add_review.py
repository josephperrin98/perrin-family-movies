"""
Add Review page - Search, select, and rate a movie.
Supports both OMDb search and manual entry for niche/unlisted films.
"""

import re
import streamlit as st
import database as db
import omdb
import identity
from components import search_bar


def render():
    """Render the add review page."""
    st.header("➕ Add a Movie Review")
    
    user = identity.get_current_user()
    if not user:
        st.error("Please log in to add a review.")
        return
    
    # Initialize session state for this page
    if "add_review_step" not in st.session_state:
        st.session_state.add_review_step = "search"  # search, review, manual, done
    if "add_review_movie" not in st.session_state:
        st.session_state.add_review_movie = None
    
    # Show current step
    step = st.session_state.add_review_step
    
    if step == "search":
        render_search_step()
    elif step == "review":
        render_review_step(user)
    elif step == "manual":
        render_manual_step(user)
    elif step == "done":
        render_done_step()
    else:
        st.session_state.add_review_step = "search"
        st.rerun()


def render_search_step():
    """Step 1: Search for a movie."""
    st.subheader("🔍 Step 1: Find Your Movie")
    st.caption("Search for the movie you want to review")
    
    # Search bar with custom callback
    search_bar.render(
        key="add_review_search",
        placeholder="Enter movie title...",
        on_select=handle_movie_select
    )
    
    # Show "add manually" option when a search has been performed
    search_key = "add_review_search_query"
    has_searched = st.session_state.get(search_key, "").strip() != ""
    has_results = len(st.session_state.get("add_review_search_results", [])) > 0
    
    if has_searched:
        st.divider()
        if not has_results:
            st.info("No movies found on OMDb for this search.")
        if st.button("🎬 Can't find your movie? Add it manually", use_container_width=True):
            st.session_state.add_review_step = "manual"
            st.rerun()


def handle_movie_select(movie_details: dict):
    """Handle when a movie is selected."""
    if "error" in movie_details:
        st.error(f"Error: {movie_details['error']}")
        return
    
    # Store the movie and move to review step
    st.session_state.add_review_movie = movie_details
    st.session_state.add_review_step = "review"
    
    # Clear search results
    search_bar.clear_search("add_review_search")
    st.rerun()


def render_review_step(user: dict):
    """Step 2: Rate and review the movie."""
    movie = st.session_state.add_review_movie
    
    if not movie:
        st.session_state.add_review_step = "search"
        st.rerun()
        return
    
    st.subheader("📝 Step 2: Write Your Review")
    
    # Back button
    if st.button("← Back to Search"):
        st.session_state.add_review_step = "search"
        st.session_state.add_review_movie = None
        st.rerun()
    
    st.divider()
    
    # Movie details
    col1, col2 = st.columns([1, 3])
    
    with col1:
        poster = movie.get("Poster", "")
        if poster and poster != "N/A":
            st.image(poster, width=150)
        else:
            st.markdown("### 🎬")
    
    with col2:
        title = movie.get("Title", "Unknown")
        year = movie.get("Year", "")
        director = movie.get("Director", "N/A")
        genre = movie.get("Genre", "N/A")
        actors = movie.get("Actors", "N/A")
        plot = movie.get("Plot", "")
        imdb_rating = movie.get("imdbRating", "N/A")
        country = movie.get("Country", "N/A")
        
        st.markdown(f"### {title} ({year})")
        st.write(f"**Director:** {director}")
        st.write(f"**Genre:** {genre}")
        st.write(f"**Country:** {country}")
        st.write(f"**Cast:** {actors}")
        st.write(f"**IMDb Rating:** ⭐ {imdb_rating}")
        
        if plot and plot != "N/A":
            with st.expander("📖 Plot"):
                st.write(plot)
    
    st.divider()
    
    # Check if user already rated this movie
    imdb_id = movie.get("imdbID")
    existing_movie = db.get_movie_by_imdb_id(imdb_id)
    existing_rating = None
    
    if existing_movie:
        existing_rating = db.get_user_rating(user["id"], existing_movie["id"])
    
    if existing_rating:
        st.warning(f"You already rated this movie {existing_rating['score']}/10. Submitting will update your review.")
    
    # Rating form
    st.subheader("Your Review")
    
    with st.form("review_form"):
        # Rating slider
        default_score = existing_rating["score"] if existing_rating else 7.0
        score = st.slider(
            "Your Rating",
            min_value=1.0,
            max_value=10.0,
            value=float(default_score),
            step=0.1,
            help="Rate from 1 (worst) to 10 (best)"
        )
        
        # Comment
        default_comment = existing_rating["comment"] if existing_rating else ""
        comment = st.text_area(
            "Your Comment (optional)",
            value=default_comment,
            placeholder="What did you think about this movie?",
            max_chars=500
        )
        
        # Mom compatible checkbox
        st.divider()
        default_mom_compat = existing_rating.get("mom_compatible") if existing_rating else None
        
        mom_compatible_options = ["Don't know / Skip", "👸 Yes, Mom-friendly!", "⚠️ No, too violent/intense"]
        default_index = 0
        if default_mom_compat is True:
            default_index = 1
        elif default_mom_compat is False:
            default_index = 2
        
        mom_compatible_choice = st.radio(
            "Is this movie Mom-compatible? (no violence/intense scenes)",
            mom_compatible_options,
            index=default_index,
            horizontal=True
        )
        
        # Convert choice to bool
        if mom_compatible_choice == mom_compatible_options[1]:
            mom_compatible = True
        elif mom_compatible_choice == mom_compatible_options[2]:
            mom_compatible = False
        else:
            mom_compatible = None
        
        # Submit buttons
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("✅ Submit Review", use_container_width=True, type="primary")
        with col2:
            cancelled = st.form_submit_button("❌ Cancel", use_container_width=True)
        
        if submitted:
            save_review(user, movie, score, comment, mom_compatible)
        
        if cancelled:
            st.session_state.add_review_step = "search"
            st.session_state.add_review_movie = None
            st.rerun()


def _make_manual_imdb_id(title, year):
    """Generate a deterministic placeholder IMDb ID for manually added movies."""
    key = f"{title}_{year}".lower()
    slug = re.sub(r"[^a-z0-9]+", "_", key).strip("_")[:60]
    return f"manual_{slug}"


def render_manual_step(user: dict):
    """Manual movie entry + review in one form."""
    st.subheader("🎬 Add a Movie Manually")

    if st.button("← Back to Search"):
        st.session_state.add_review_step = "search"
        st.rerun()

    st.divider()

    with st.form("manual_movie_form"):
        st.markdown("**Movie Details**")
        title = st.text_input("Movie Title *", placeholder="e.g. Chien de la Casse")
        col_dir, col_year = st.columns(2)
        with col_dir:
            director = st.text_input("Director *", placeholder="e.g. Jean-Baptiste Durand")
        with col_year:
            year = st.text_input("Year *", placeholder="e.g. 2022")
        actors = st.text_input("Main Actors (2-3 names)", placeholder="e.g. Anthony Bajon, Raphaël Quenard")
        col_genre, col_country = st.columns(2)
        with col_genre:
            genre = st.text_input("Genre", placeholder="e.g. Comédie Dramatique")
        with col_country:
            country = st.text_input("Country", placeholder="e.g. France")
        plot = st.text_area("Short Description (optional)", placeholder="A brief plot summary...", max_chars=500)

        st.divider()
        st.markdown("**Your Review**")

        score = st.slider("Your Rating", min_value=1.0, max_value=10.0, value=7.0, step=0.1)
        comment = st.text_area("Your Comment (optional)", placeholder="What did you think?", max_chars=500)

        st.divider()
        mom_options = ["Don't know / Skip", "👸 Yes, Mom-friendly!", "⚠️ No, too violent/intense"]
        mom_choice = st.radio("Is this movie Mom-compatible?", mom_options, index=0, horizontal=True)
        if mom_choice == mom_options[1]:
            mom_compatible = True
        elif mom_choice == mom_options[2]:
            mom_compatible = False
        else:
            mom_compatible = None

        col_sub, col_cancel = st.columns(2)
        with col_sub:
            submitted = st.form_submit_button("✅ Submit", use_container_width=True, type="primary")
        with col_cancel:
            cancelled = st.form_submit_button("❌ Cancel", use_container_width=True)

        if submitted:
            if not title.strip() or not director.strip() or not year.strip():
                st.error("Please fill in at least the title, director, and year.")
            else:
                manual_movie = {
                    "imdbID": _make_manual_imdb_id(title.strip(), year.strip()),
                    "Title": title.strip(),
                    "Year": year.strip(),
                    "Director": director.strip(),
                    "Actors": actors.strip() or "N/A",
                    "Genre": genre.strip() or "N/A",
                    "Country": country.strip() or "N/A",
                    "Plot": plot.strip() or "N/A",
                    "Poster": "N/A",
                    "imdbRating": "N/A",
                }
                save_review(user, manual_movie, score, comment, mom_compatible)

        if cancelled:
            st.session_state.add_review_step = "search"
            st.session_state.add_review_movie = None
            st.rerun()


def save_review(user: dict, movie: dict, score: float, comment: str, mom_compatible: bool = None):
    """Save the review to the database."""
    try:
        # Format movie data for database
        movie_data = omdb.format_movie_for_db(movie)
        
        # Get or create movie in database
        movie_id = db.get_or_create_movie(movie_data)
        
        # Add the rating
        db.add_rating(user["id"], movie_id, score, comment, mom_compatible)
        
        # Set watch status to "watched"
        db.set_watch_status(user["id"], movie_id, "watched")
        
        # Store success info and move to done step
        st.session_state.add_review_success = {
            "title": movie.get("Title", "Unknown"),
            "score": score
        }
        st.session_state.add_review_step = "done"
        st.rerun()
        
    except Exception as e:
        st.error(f"Error saving review: {str(e)}")


def render_done_step():
    """Step 3: Success message."""
    success_info = st.session_state.get("add_review_success", {})
    title = success_info.get("title", "the movie")
    score = success_info.get("score", 0)
    
    st.success("🎉 Review submitted!")
    st.markdown(f"### You rated **{title}** {score}/10")
    
    st.balloons()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("➕ Add Another Review", use_container_width=True):
            reset_add_review()
            st.rerun()
    
    with col2:
        if st.button("🏠 Go to Browse", use_container_width=True):
            reset_add_review()
            st.session_state.current_page = "browse"
            st.rerun()
    
    with col3:
        if st.button("📚 View Your Movies", use_container_width=True):
            reset_add_review()
            st.session_state.current_page = "your_movies"
            st.rerun()


def reset_add_review():
    """Reset the add review page state."""
    st.session_state.add_review_step = "search"
    st.session_state.add_review_movie = None
    st.session_state.add_review_success = None
    search_bar.clear_search("add_review_search")
