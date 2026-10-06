"""
Family page - View all family members and their movie stats.
"""

import streamlit as st
import database as db
import identity


def render():
    """Render the family page."""
    st.header("👨‍👩‍👧‍👦 Perrin Family")
    st.caption("See what everyone's been watching!")
    
    # Get all family members
    users = db.get_all_users()
    current_user = identity.get_current_user()
    
    if not users:
        st.info("No family members found.")
        return
    
    # Display family members in a grid
    cols = st.columns(3)
    
    for i, user in enumerate(users):
        with cols[i % 3]:
            render_user_card(user, is_current_user=(user["id"] == current_user["id"]))


def render_user_card(user: dict, is_current_user: bool = False):
    """Render a card for a family member."""
    stats = db.get_user_stats(user["id"])
    
    with st.container():
        # User header
        st.markdown(f"### {user['avatar_emoji']} {user['display_name']}")
        if is_current_user:
            st.caption("(You)")
        
        # Stats
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Movies Rated", stats["total_rated"])
        with col2:
            st.metric("Avg Rating", f"{stats['avg_rating']}/10" if stats["avg_rating"] else "—")
        
        # Top genres
        if stats["top_genres"]:
            genres_str = ", ".join(stats["top_genres"][:2])
            st.caption(f"🎭 Loves: {genres_str}")
        
        # View profile button
        if st.button(
            "View Profile" if not is_current_user else "View Your Movies",
            key=f"view_user_{user['id']}",
            use_container_width=True
        ):
            if is_current_user:
                st.session_state.current_page = "your_movies"
                st.session_state.viewing_user_id = None
            else:
                st.session_state.current_page = "user_profile"
                st.session_state.viewing_user_id = user["id"]
            st.rerun()
        
        st.divider()

