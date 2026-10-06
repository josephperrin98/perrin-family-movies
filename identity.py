"""
Identity module for Perrin Family Movie Ratings App.
Simple user picker with optional family PIN gate.
"""

import hmac
import streamlit as st
from typing import Optional
import database as db

# Seeded into an empty database when no family_members secret is configured
DEMO_MEMBERS = [
    {"username": "alice", "display_name": "Alice", "avatar_emoji": "🎬"},
    {"username": "bob", "display_name": "Bob", "avatar_emoji": "🍿"},
    {"username": "chloe", "display_name": "Chloé", "avatar_emoji": "🎨"},
]


def init_session():
    """Initialize session state for identity."""
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "display_name" not in st.session_state:
        st.session_state.display_name = None
    if "avatar_emoji" not in st.session_state:
        st.session_state.avatar_emoji = None
    if "family_verified" not in st.session_state:
        st.session_state.family_verified = False


def get_family_pin() -> Optional[str]:
    """Get the family PIN from Streamlit secrets; None disables the gate."""
    try:
        return st.secrets.get("family_pin")
    except Exception:
        return None


def is_pin_required() -> bool:
    """Check if PIN gate is enabled."""
    return get_family_pin() is not None


def is_pin_verified() -> bool:
    """Check if family PIN has been verified."""
    if not is_pin_required():
        return True
    return st.session_state.get("family_verified", False)


def pin_matches(entered_pin: str, correct_pin: Optional[str]) -> bool:
    """Compare PINs in constant time (bytes, so non-ASCII PINs work)."""
    if not correct_pin:
        return False
    return hmac.compare_digest(entered_pin.encode("utf-8"), correct_pin.encode("utf-8"))


def verify_pin(entered_pin: str) -> bool:
    """Verify the entered PIN."""
    correct_pin = get_family_pin()
    if pin_matches(entered_pin, correct_pin):
        st.session_state.family_verified = True
        return True
    return False


def is_user_selected() -> bool:
    """Check if a user has been selected."""
    return st.session_state.get("user_id") is not None


def get_current_user() -> Optional[dict]:
    """Get the currently selected user."""
    if not is_user_selected():
        return None
    
    return {
        "id": st.session_state.user_id,
        "display_name": st.session_state.display_name,
        "avatar_emoji": st.session_state.avatar_emoji
    }


def select_user(user_id: int, display_name: str, avatar_emoji: str):
    """Set the current user."""
    st.session_state.user_id = user_id
    st.session_state.display_name = display_name
    st.session_state.avatar_emoji = avatar_emoji


def clear_user():
    """Clear the current user (switch user)."""
    st.session_state.user_id = None
    st.session_state.display_name = None
    st.session_state.avatar_emoji = None


def require_identity() -> bool:
    """
    Require user to be identified.
    Shows PIN gate (if enabled) then user picker.
    Returns True if user is identified, False otherwise.
    """
    init_session()
    
    # Step 1: PIN gate (if enabled)
    if is_pin_required() and not is_pin_verified():
        render_pin_gate()
        return False
    
    # Step 2: User picker
    if not is_user_selected():
        render_user_picker()
        return False
    
    return True


def render_pin_gate():
    """Render the family PIN entry gate."""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("logo.jpeg", use_container_width=True)
    st.subheader("🔐 Family Access")
    
    st.write("Enter the family PIN to continue:")
    
    with st.form("pin_form"):
        pin = st.text_input("PIN", type="password", placeholder="Enter PIN...")
        submitted = st.form_submit_button("Enter", use_container_width=True)
        
        if submitted:
            if verify_pin(pin):
                st.success("Welcome to Perrin Movies!")
                st.rerun()
            else:
                st.error("Incorrect PIN. Try again!")


def render_user_picker():
    """Render the user selection page."""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("logo.jpeg", use_container_width=True)
    st.subheader("👋 Who's watching?")
    
    # Ensure users exist
    seed_users_if_empty()
    
    # Get all users
    users = db.get_all_users()
    
    if not users:
        st.error("No users found. Please contact the admin.")
        return
    
    # Create user selection
    st.write("Select your name to continue:")
    
    # Display users as clickable cards
    cols = st.columns(3)
    
    for i, user in enumerate(users):
        with cols[i % 3]:
            if st.button(
                f"{user['avatar_emoji']} {user['display_name']}",
                key=f"select_user_{user['id']}",
                use_container_width=True
            ):
                select_user(user["id"], user["display_name"], user["avatar_emoji"])
                st.rerun()
    
    st.divider()
    st.caption("👨‍👩‍👧‍👦 This is a private family app.")


def members_to_seed(configured) -> list[dict]:
    """Return the configured family members, or the demo members if none."""
    if not configured:
        return DEMO_MEMBERS
    return [
        {
            "username": m["username"],
            "display_name": m["display_name"],
            "avatar_emoji": m.get("avatar_emoji", "👤"),
        }
        for m in configured
    ]


def seed_users_if_empty():
    """Create the family members from secrets if the users table is empty."""
    if db.get_all_users():
        return

    try:
        configured = st.secrets.get("family_members")
    except Exception:
        configured = None

    for user in members_to_seed(configured):
        db.create_user_simple(
            username=user["username"],
            display_name=user["display_name"],
            avatar_emoji=user["avatar_emoji"]
        )

