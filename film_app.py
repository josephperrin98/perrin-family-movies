"""
Perrin Family Movie Ratings App
Main entry point with navigation and user picker.
"""

import streamlit as st

# Page configuration - must be first Streamlit command
st.set_page_config(
    page_title="Perrin Family Movies",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

import identity
import database as db

# Initialize database
try:
    db.init_db()
except Exception as e:
    st.error(f"⚠️ Database connection failed: {e}")
    st.info("Make sure DATABASE_URL is set in Streamlit secrets or environment.")
    st.stop()


def render_navigation():
    """Render the top navigation bar."""
    user = identity.get_current_user()
    
    # Create navigation columns
    nav_cols = st.columns([2, 1.2, 1.2, 1.2, 1.2, 1.2, 2])
    
    with nav_cols[0]:
        st.image("logo.jpeg", width=150)
    
    with nav_cols[1]:
        if st.button("🏠 Browse", use_container_width=True, 
                     type="primary" if st.session_state.get("current_page") == "browse" else "secondary"):
            st.session_state.current_page = "browse"
            st.rerun()
    
    with nav_cols[2]:
        if st.button("🏆 Top 100", use_container_width=True,
                     type="primary" if st.session_state.get("current_page") == "top100" else "secondary"):
            st.session_state.current_page = "top100"
            st.rerun()
    
    with nav_cols[3]:
        if st.button("👨‍👩‍👧‍👦 Family", use_container_width=True,
                     type="primary" if st.session_state.get("current_page") == "family" else "secondary"):
            st.session_state.current_page = "family"
            st.rerun()
    
    with nav_cols[4]:
        if st.button("📚 Your Movies", use_container_width=True,
                     type="primary" if st.session_state.get("current_page") == "your_movies" else "secondary"):
            st.session_state.current_page = "your_movies"
            st.session_state.viewing_user_id = None  # Reset to view own movies
            st.rerun()
    
    with nav_cols[5]:
        if st.button("➕ Add Review", use_container_width=True,
                     type="primary" if st.session_state.get("current_page") == "add_review" else "secondary"):
            st.session_state.current_page = "add_review"
            st.rerun()
    
    with nav_cols[6]:
        if user:
            subcol1, subcol2 = st.columns([3, 1])
            with subcol1:
                st.markdown(f"**{user['avatar_emoji']} {user['display_name']}**")
            with subcol2:
                if st.button("🔄", help="Switch user"):
                    identity.clear_user()
                    st.rerun()
    
    st.divider()


def render_page():
    """Render the current page based on session state."""
    current_page = st.session_state.get("current_page", "browse")
    
    if current_page == "browse":
        from views import browse
        browse.render()
    elif current_page == "top100":
        from views import top100
        top100.render()
    elif current_page == "family":
        from views import family
        family.render()
    elif current_page == "your_movies":
        from views import your_movies
        your_movies.render()
    elif current_page == "add_review":
        from views import add_review
        add_review.render()
    elif current_page == "movie":
        from views import movie
        movie.render(st.session_state.get("selected_imdb_id"))
    elif current_page == "user_profile":
        from views import your_movies
        your_movies.render(user_id=st.session_state.get("viewing_user_id"))
    else:
        from views import browse
        browse.render()


def main():
    """Main application entry point."""
    # Initialize session state
    if "current_page" not in st.session_state:
        st.session_state.current_page = "browse"
    
    # Require user to be identified (PIN gate + user picker)
    if not identity.require_identity():
        return
    
    # Render navigation and current page
    render_navigation()
    render_page()


if __name__ == "__main__":
    main()
