"""
OMDb API wrapper for Perrin Family Movie Ratings App.
Handles movie search, details fetching, and autocomplete.
"""

import streamlit as st
import requests
from typing import Optional

# OMDb API configuration
OMDB_URL = "https://www.omdbapi.com/"
TIMEOUT = 10


def get_api_key() -> str:
    """Get OMDb API key from Streamlit secrets."""
    try:
        return st.secrets["OMDB_API_KEY"]
    except Exception:
        # Fallback for local development
        import os
        key = os.environ.get("OMDB_API_KEY")
        if not key:
            raise ValueError("OMDB_API_KEY not found in st.secrets or environment")
        return key




class OMDbError(Exception):
    """Custom exception for OMDb API errors."""
    pass


def search_movies(query: str, year: Optional[str] = None, page: int = 1) -> dict:
    """
    Search for movies by title.
    
    Args:
        query: Search term (movie title)
        year: Optional year filter
        page: Page number for pagination (10 results per page)
    
    Returns:
        dict with keys: 'results' (list of movies), 'total_results' (int), 'error' (str or None)
    """
    if not query or not query.strip():
        return {"results": [], "total_results": 0, "error": None}
    
    params = {
        "apikey": get_api_key(),
        "s": query.strip(),
        "type": "movie",
        "page": page
    }
    
    if year:
        params["y"] = year
    
    try:
        response = requests.get(OMDB_URL, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        if data.get("Response") == "True":
            return {
                "results": data.get("Search", []),
                "total_results": int(data.get("totalResults", 0)),
                "error": None
            }
        else:
            error_msg = data.get("Error", "Unknown error")
            # "Movie not found" is not really an error, just no results
            if "not found" in error_msg.lower():
                return {"results": [], "total_results": 0, "error": None}
            return {"results": [], "total_results": 0, "error": error_msg}
            
    except requests.Timeout:
        return {"results": [], "total_results": 0, "error": "Request timed out"}
    except requests.RequestException as e:
        return {"results": [], "total_results": 0, "error": f"Connection error: {str(e)}"}


def get_movie_details(imdb_id: str) -> dict:
    """
    Get full movie details by IMDb ID.
    
    Args:
        imdb_id: IMDb ID (e.g., "tt1375666")
    
    Returns:
        dict with movie details or {"error": "message"}
    
    Available fields from OMDb:
        Title, Year, Rated, Released, Runtime, Genre, Director, Writer,
        Actors, Plot, Language, Country, Awards, Poster, Ratings,
        Metascore, imdbRating, imdbVotes, imdbID, Type, DVD, BoxOffice,
        Production, Website
    """
    if not imdb_id:
        return {"error": "Missing IMDb ID"}
    
    params = {
        "apikey": get_api_key(),
        "i": imdb_id,
        "plot": "full"  # Get full plot instead of short
    }
    
    try:
        response = requests.get(OMDB_URL, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        if data.get("Response") == "True":
            return data
        else:
            return {"error": data.get("Error", "Movie not found")}
            
    except requests.Timeout:
        return {"error": "Request timed out"}
    except requests.RequestException as e:
        return {"error": f"Connection error: {str(e)}"}


def autocomplete_search(query: str, max_results: int = 5) -> list[dict]:
    """
    Quick search for autocomplete dropdown.
    Returns a simplified list of movies for display.
    
    Args:
        query: Search term
        max_results: Maximum number of results to return
    
    Returns:
        List of dicts with keys: imdb_id, title, year, poster
    """
    if not query or len(query.strip()) < 2:
        return []
    
    result = search_movies(query)
    
    if result["error"] or not result["results"]:
        return []
    
    suggestions = []
    for movie in result["results"][:max_results]:
        suggestions.append({
            "imdb_id": movie.get("imdbID"),
            "title": movie.get("Title", "Unknown"),
            "year": movie.get("Year", ""),
            "poster": movie.get("Poster", "")
        })
    
    return suggestions


def format_movie_for_db(omdb_data: dict) -> dict:
    """
    Format OMDb response for database insertion.
    Normalizes field names to match our database schema.
    
    Args:
        omdb_data: Raw response from OMDb API
    
    Returns:
        dict ready for database.get_or_create_movie()
    """
    return {
        "imdbID": omdb_data.get("imdbID"),
        "Title": omdb_data.get("Title", "Unknown"),
        "Year": omdb_data.get("Year"),
        "Poster": omdb_data.get("Poster") if omdb_data.get("Poster") != "N/A" else None,
        "Director": omdb_data.get("Director") if omdb_data.get("Director") != "N/A" else None,
        "Genre": omdb_data.get("Genre") if omdb_data.get("Genre") != "N/A" else None,
        "Country": omdb_data.get("Country") if omdb_data.get("Country") != "N/A" else None,
        "Actors": omdb_data.get("Actors") if omdb_data.get("Actors") != "N/A" else None,
        "Plot": omdb_data.get("Plot") if omdb_data.get("Plot") != "N/A" else None,
        "imdbRating": omdb_data.get("imdbRating") if omdb_data.get("imdbRating") != "N/A" else None
    }


def is_valid_poster(poster_url: str) -> bool:
    """Check if poster URL is valid (not N/A or empty)."""
    return bool(poster_url) and poster_url != "N/A"

