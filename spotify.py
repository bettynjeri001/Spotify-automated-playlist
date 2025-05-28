import os
import logging
import webbrowser
from typing import List, Optional

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from youtubesearchpython import VideosSearch
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# Constants
ENV_VARS = ["SPOTIPY_CLIENT_ID", "SPOTIPY_CLIENT_SECRET", "SPOTIPY_REDIRECT_URI"]
SPOTIFY_SCOPE = (
    "playlist-read-private playlist-read-collaborative user-top-read "
    "playlist-modify-public playlist-modify-private user-library-read"
)
CACHE_PATH = ".spotipy_cache"
MAX_SEARCH_RESULTS = 10


class SpotifyClient:
    def __init__(self):
        load_dotenv()
        self._validate_env()
        self.sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=os.getenv("SPOTIPY_CLIENT_ID"),
                client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
                redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
                scope=SPOTIFY_SCOPE,
                cache_path=CACHE_PATH,
                show_dialog=True,
            )
        )
        logger.info("Authenticated with Spotify")

    @staticmethod
    def _validate_env():
        missing = [var for var in ENV_VARS if not os.getenv(var)]
        if missing:
            raise EnvironmentError(f"Missing environment variables: {', '.join(missing)}")

    def get_user_id(self) -> str:
        return self.sp.current_user()["id"]

    def list_playlists(self, limit: int = 50) -> List[dict]:
        playlists = []
        results = self.sp.current_user_playlists(limit=limit)
        playlists.extend(results["items"])
        while results.get("next"):
            results = self.sp.next(results)
            playlists.extend(results["items"])
        logger.info(f"Loaded {len(playlists)} playlists")
        return playlists

    def get_playlist_tracks(self, playlist_id: str) -> List[dict]:
        tracks = []
        results = self.sp.playlist_tracks(playlist_id)
        tracks.extend(results["items"])
        while results.get("next"):
            results = self.sp.next(results)
            tracks.extend(results["items"])
        logger.info(f"Fetched {len(tracks)} tracks for playlist {playlist_id}")
        return tracks

    def search_tracks(self, query: str, limit: int = MAX_SEARCH_RESULTS) -> List[dict]:
        results = self.sp.search(q=query, type="track", limit=limit)
        return results.get("tracks", {}).get("items", [])

    def create_playlist(self, user_id: str, name: str, public: bool, description: str) -> dict:
        playlist = self.sp.user_playlist_create(
            user=user_id, name=name, public=public, description=description
        )
        logger.info(f"Created playlist '{name}' (id={playlist['id']})")
        return playlist

    def add_items(self, playlist_id: str, items: List[str]):
        for i in range(0, len(items), 100):
            batch = items[i : i + 100]
            self.sp.playlist_add_items(playlist_id, batch)
        logger.info(f"Added {len(items)} items to playlist {playlist_id}")


class SpotifyPlaylistManagerGUI(tk.Tk):
    def __init__(self, spotify_client: SpotifyClient):
        super().__init__()
        self.spotify = spotify_client
        self.title("Spotify Playlist Manager 🎧")
        self.configure(bg="#f5f5f5")

        self.playlists: List[dict] = []
        self.selected_track_uris: List[str] = []
        self.search_results: List[dict] = []

        self._build_widgets()
        self._load_playlists()

    def _build_widgets(self):
        header = ttk.Label(
            self, text="Spotify Playlist Manager", font=("Helvetica", 18, "bold")
        )
        header.pack(pady=10)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._build_browse_tab()
        self._build_create_tab()

        self.status_box = scrolledtext.ScrolledText(
            self, height=5, state="disabled", font=("Courier", 10)
        )
        self.status_box.pack(fill=tk.BOTH, padx=10, pady=(0, 10))

    def _build_browse_tab(self):
        browse = ttk.Frame(self.notebook)
        self.notebook.add(browse, text="Browse Playlists")

        control_frame = ttk.Frame(browse)
        control_frame.pack(fill=tk.X, pady=5)

        ttk.Label(control_frame, text="Select Playlist:").pack(side=tk.LEFT, padx=(0, 5))
        self.playlist_var = tk.StringVar()
        self.playlist_combo = ttk.Combobox(
            control_frame, textvariable=self.playlist_var, state="readonly", width=40
        )
        self.playlist_combo.pack(side=tk.LEFT)
        ttk.Button(
            control_frame,
            text="Fetch",
            command=self._on_fetch_playlist
        ).pack(side=tk.LEFT, padx=5)

        self.track_display = scrolledtext.ScrolledText(
            browse, state="disabled", font=("Courier", 10)
        )
        self.track_display.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def _build_create_tab(self):
        create = ttk.Frame(self.notebook)
        self.notebook.add(create, text="Create Playlist")

        form_frame = ttk.Frame(create)
        form_frame.pack(pady=10)

        ttk.Label(form_frame, text="Name:").grid(row=0, column=0, sticky=tk.W)
        self.name_entry = ttk.Entry(form_frame, width=50)
        self.name_entry.grid(row=0, column=1, padx=5)

        ttk.Label(form_frame, text="Description:").grid(row=1, column=0, sticky=tk.W)
        self.desc_entry = ttk.Entry(form_frame, width=50)
        self.desc_entry.grid(row=1, column=1, padx=5)

        self.public_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            form_frame, text="Public", variable=self.public_var
        ).grid(row=2, columnspan=2, pady=5)

        ttk.Separator(create, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        search_frame = ttk.Frame(create)
        search_frame.pack(pady=5)

        ttk.Label(search_frame, text="Search Tracks:").pack(side=tk.LEFT)
        self.search_entry = ttk.Entry(search_frame, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(
            search_frame,
            text="Search",
            command=self._on_search_tracks
        ).pack(side=tk.LEFT)

        self.results_list = tk.Listbox(create, height=8)
        self.results_list.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.results_list.bind('<Double-1>', self._add_track)
        self.results_list.bind('<Button-3>', self._play_on_youtube)

        selected_frame = ttk.Frame(create)
        selected_frame.pack(fill=tk.X, padx=10)
        ttk.Label(selected_frame, text="Selected Tracks:").pack(side=tk.LEFT)
        ttk.Button(
            selected_frame,
            text="Remove",
            command=self._remove_track
        ).pack(side=tk.RIGHT)

        self.selected_list = tk.Listbox(create, height=4)
        self.selected_list.pack(fill=tk.BOTH, expand=True, pady=5, padx=10)

        ttk.Button(
            create,
            text="Create Playlist",
            command=self._on_create_playlist,
            style="Accent.TButton"
        ).pack(pady=10)

    def _load_playlists(self):
        try:
            self.playlists = self.spotify.list_playlists()
            names = [pl['name'] for pl in self.playlists]
            self.playlist_combo['values'] = names
            self._log(f"Loaded {len(names)} playlists.")
        except Exception as e:
            messagebox.showerror("Error", str(e))
            logger.exception("Failed to load playlists")

    def _on_fetch_playlist(self):
        name = self.playlist_var.get()
        pl = next((p for p in self.playlists if p['name'] == name), None)
        if not pl:
            self._log("No playlist selected.")
            return

        tracks = self.spotify.get_playlist_tracks(pl['id'])
        self.track_display.configure(state="normal")
        self.track_display.delete("1.0", tk.END)
        self.track_display.insert(tk.END, f"Playlist: {name}\nTotal tracks: {len(tracks)}\n\n")
        for idx, item in enumerate(tracks, 1):
            track = item.get('track')
            if track:
                artists = ", ".join(a['name'] for a in track['artists'])
                self.track_display.insert(tk.END, f"{idx}. {track['name']} - {artists}\n")
        self.track_display.configure(state="disabled")
        self._log(f"Fetched {len(tracks)} tracks.")

    def _on_search_tracks(self):
        query = self.search_entry.get().strip()
        if not query:
            self._log("Enter search term.")
            return
        self.results_list.delete(0, tk.END)
        self.search_results = self.spotify.search_tracks(query)
        for track in self.search_results:
            name = f"{track['name']} - {', '.join(a['name'] for a in track['artists'])}"
            self.results_list.insert(tk.END, name)
        self._log(f"Found {len(self.search_results)} tracks.")

    def _add_track(self, event):
        idx = self.results_list.curselection()
        if not idx:
            return
        track = self.search_results[idx[0]]
        uri = track['uri']
        if uri in self.selected_track_uris:
            self._log("Track already added.")
            return
        self.selected_track_uris.append(uri)
        display = f"{track['name']} - {', '.join(a['name'] for a in track['artists'])}"
        self.selected_list.insert(tk.END, display)
        self._log(f"Added: {display}")

    def _remove_track(self):
        idx = self.selected_list.curselection()
        if not idx:
            return
        self.selected_track_uris.pop(idx[0])
        removed = self.selected_list.get(idx)
        self.selected_list.delete(idx)
        self._log(f"Removed: {removed}")

    def _play_on_youtube(self, event):
        idx = self.results_list.curselection()
        if not idx:
            return
        text = self.results_list.get(idx)
        try:
            result = VideosSearch(f"{text} audio", limit=1).result().get('result', [])
            if result:
                url = result[0]['link']
                webbrowser.open(url)
        except Exception:
            pass

    def _on_create_playlist(self):
        name = self.name_entry.get().strip()
        if not name or not self.selected_track_uris:
            self._log("Name and tracks required.")
            return
        desc = self.desc_entry.get().strip()
        public = self.public_var.get()
        user_id = self.spotify.get_user_id()
        try:
            playlist = self.spotify.create_playlist(user_id, name, public, desc)
            self.spotify.add_items(playlist['id'], self.selected_track_uris)
            self._log(f"Playlist '{name}' created with {len(self.selected_track_uris)} tracks.")
            self._load_playlists()
            self._reset_form()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            logger.exception("Failed to create playlist")

    def _reset_form(self):
        for widget in [self.name_entry, self.desc_entry, self.search_entry]:
            widget.delete(0, tk.END)
        self.results_list.delete(0, tk.END)
        self.selected_list.delete(0, tk.END)
        self.selected_track_uris.clear()
        self.public_var.set(True)

    def _log(self, message: str):
        self.status_box.configure(state="normal")
        self.status_box.insert(tk.END, f"{message}\n")
        self.status_box.see(tk.END)
        self.status_box.configure(state="disabled")


if __name__ == "__main__":
    try:
        spotify_client = SpotifyClient()
    except EnvironmentError as e:
        messagebox.showerror("Configuration Error", str(e))
        exit(1)

    app = SpotifyPlaylistManagerGUI(spotify_client)
    app.mainloop().env
