import os
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from youtubesearchpython import VideosSearch
import webbrowser

# Load environment variables
load_dotenv()

class SpotifyPlaylistManagerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Spotify Playlist Manager 🎧")
        self.root.configure(bg="white")
        self.playlists = []
        self.selected_tracks = []
        self.search_results_tracks = []

        # Load credentials
        self.client_id = os.getenv("SPOTIPY_CLIENT_ID")
        self.client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
        self.redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI")

        if not all([self.client_id, self.client_secret, self.redirect_uri]):
            messagebox.showerror("Error", "Missing Spotify API credentials in .env")
            self.root.destroy()
            return

        # Authenticate Spotify
        self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope="playlist-read-private playlist-read-collaborative user-top-read playlist-modify-public playlist-modify-private user-library-read",
            cache_path=".spotipy_cache",
            show_dialog=True
        ))

        self.build_gui()
        self.load_user_playlists()

    def build_gui(self):
        tk.Label(self.root, text="Spotify Playlist Manager", font=("Arial", 18, "bold"), fg="purple", bg="white").pack(pady=10)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        self.browse_tab = ttk.Frame(self.notebook)
        self.create_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.browse_tab, text="Browse Playlists")
        self.notebook.add(self.create_tab, text="Create Playlist")

        self.build_browse_tab()
        self.build_create_tab()

        self.status_box = scrolledtext.ScrolledText(self.root, width=60, height=5, bg="white", fg="purple", font=("Courier", 10))
        self.status_box.pack(padx=10, pady=10, fill=tk.BOTH)

    def build_browse_tab(self):
        playlist_frame = tk.Frame(self.browse_tab, bg="white")
        playlist_frame.pack(pady=5, fill=tk.X)

        tk.Label(playlist_frame, text="Select Playlist:", bg="white", fg="purple", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(0, 10))

        self.playlist_var = tk.StringVar()
        self.playlist_dropdown = ttk.Combobox(playlist_frame, textvariable=self.playlist_var, width=40, state="readonly")
        self.playlist_dropdown.pack(side=tk.LEFT)
        self.playlist_dropdown.bind("<<ComboboxSelected>>", self.on_playlist_select)

        fetch_btn = tk.Button(self.browse_tab, text="Fetch Playlist Details", command=self.fetch_playlist_details, bg="purple", fg="white", font=("Arial", 12, "bold"))
        fetch_btn.pack(pady=5)

        self.track_list = scrolledtext.ScrolledText(self.browse_tab, width=60, height=25, bg="white", fg="purple", font=("Courier", 10))
        self.track_list.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    def build_create_tab(self):
        tk.Label(self.create_tab, text="Playlist Name:", bg="white", fg="purple", font=("Arial", 10, "bold")).pack(pady=(10, 0))
        self.new_playlist_name = tk.Entry(self.create_tab, width=50, bg="white", fg="purple", insertbackground="purple")
        self.new_playlist_name.pack(pady=5)

        tk.Label(self.create_tab, text="Description (optional):", bg="white", fg="purple", font=("Arial", 10, "bold")).pack(pady=(10, 0))
        self.new_playlist_desc = tk.Entry(self.create_tab, width=50, bg="white", fg="purple", insertbackground="purple")
        self.new_playlist_desc.pack(pady=5)

        self.public_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self.create_tab, text="Public Playlist", variable=self.public_var, bg="white", fg="purple", selectcolor="black").pack(pady=5)

        search_frame = tk.Frame(self.create_tab, bg="white")
        search_frame.pack(pady=10)

        tk.Label(search_frame, text="Search Tracks:", bg="white", fg="purple", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        self.search_entry = tk.Entry(search_frame, width=30, bg="white", fg="purple", insertbackground="purple")
        self.search_entry.pack(side=tk.LEFT)

        search_btn = tk.Button(search_frame, text="Search", command=self.search_tracks, bg="purple", fg="white", font=("Arial", 10))
        search_btn.pack(side=tk.LEFT, padx=5)

        self.search_results = tk.Listbox(self.create_tab, width=60, height=10, bg="white", fg="purple", selectbackground="purple", selectforeground="white")
        self.search_results.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)
        self.search_results.bind("<Double-Button-1>", self.add_track_to_selection)
        self.search_results.bind("<Button-3>", self.play_track_on_youtube)  # Right-click to play

        selected_frame = tk.Frame(self.create_tab, bg="white")
        selected_frame.pack(pady=5, fill=tk.X)

        tk.Label(selected_frame, text="Selected Tracks:", bg="white", fg="purple", font=("Arial", 10, "bold")).pack(side=tk.LEFT)

        remove_btn = tk.Button(selected_frame, text="Remove Selected", command=self.remove_selected_track, bg="purple", fg="white", font=("Arial", 10))
        remove_btn.pack(side=tk.RIGHT, padx=5)

        self.selected_tracks_list = tk.Listbox(self.create_tab, width=60, height=5, bg="white", fg="purple", selectbackground="purple", selectforeground="white")
        self.selected_tracks_list.pack(pady=5, padx=10, fill=tk.BOTH)

        create_btn = tk.Button(self.create_tab, text="Create Playlist", command=self.create_new_playlist, bg="purple", fg="white", font=("Arial", 12, "bold"))
        create_btn.pack(pady=10)

    def log(self, message):
        self.status_box.insert(tk.END, f"{message}\n")
        self.status_box.see(tk.END)
        self.root.update_idletasks()

    def play_track_on_youtube(self, event):
        widget = event.widget
        index = widget.curselection()
        if not index:
            return
        selected_text = widget.get(index[0])
        query = f"{selected_text} audio"
        try:
            videos_search = VideosSearch(query, limit=1)
            result = videos_search.result()
            if result["result"]:
                video_url = result["result"][0]["link"]
                webbrowser.open(video_url)
                self.log(f"▶️ Playing on YouTube: {selected_text}")
            else:
                self.log(f"❌ No YouTube result for: {selected_text}")
        except Exception as e:
            self.log(f"❌ Error playing on YouTube: {str(e)}")

    def load_user_playlists(self):
        self.log("🔍 Loading your playlists...")
        try:
            playlists = self.sp.current_user_playlists(limit=50)
            self.playlists = playlists['items']
            while playlists['next']:
                playlists = self.sp.next(playlists)
                self.playlists.extend(playlists['items'])
            playlist_names = [p['name'] for p in self.playlists]
            self.playlist_dropdown['values'] = playlist_names
            self.log(f"✅ Found {len(self.playlists)} playlists")
        except Exception as e:
            self.log(f"❌ Error loading playlists: {str(e)}")

    def on_playlist_select(self, event=None):
        selected_name = self.playlist_var.get()
        selected_playlist = next((p for p in self.playlists if p['name'] == selected_name), None)
        if selected_playlist:
            self.log(f"ℹ️ Selected playlist: {selected_playlist['name']}")

    def fetch_playlist_details(self):
        selected_name = self.playlist_var.get()
        if not selected_name:
            self.log("❌ Please select a playlist")
            return
        selected_playlist = next((p for p in self.playlists if p['name'] == selected_name), None)
        if not selected_playlist:
            self.log("❌ Playlist not found")
            return

        self.track_list.delete(1.0, tk.END)
        try:
            results = self.sp.playlist_tracks(selected_playlist['id'])
            tracks = results['items']
            while results['next']:
                results = self.sp.next(results)
                tracks.extend(results['items'])

            self.track_list.insert(tk.END, f"Playlist: {selected_playlist['name']}\n")
            self.track_list.insert(tk.END, f"Description: {selected_playlist.get('description', 'No description')}\n")
            self.track_list.insert(tk.END, f"Total Tracks: {selected_playlist['tracks']['total']}\n\n")
            self.track_list.insert(tk.END, "Track List:\n")

            for i, item in enumerate(tracks, 1):
                track = item['track']
                if track:
                    artists = ", ".join(artist['name'] for artist in track['artists'])
                    self.track_list.insert(tk.END, f"{i}. {track['name']} - {artists}\n")

            self.log(f"✅ Fetched {len(tracks)} tracks")
        except Exception as e:
            self.log(f"❌ Error fetching playlist: {str(e)}")

    def search_tracks(self):
        query = self.search_entry.get().strip()
        if not query:
            self.log("❌ Please enter a search term")
            return

        self.search_results.delete(0, tk.END)
        self.search_results_tracks = []
        try:
            results = self.sp.search(q=query, type='track', limit=10)
            tracks = results['tracks']['items']
            for track in tracks:
                artists = ", ".join(artist['name'] for artist in track['artists'])
                self.search_results.insert(tk.END, f"{track['name']} - {artists}")
                self.search_results_tracks.append(track['uri'])
            self.log(f"✅ Found {len(tracks)} tracks")
        except Exception as e:
            self.log(f"❌ Error searching: {str(e)}")

    def add_track_to_selection(self, event):
        index = self.search_results.curselection()
        if not index:
            return
        idx = index[0]
        track_info = self.search_results.get(idx)
        track_uri = self.search_results_tracks[idx]
        if track_uri in self.selected_tracks:
            self.log(f"ℹ️ Track already added: {track_info}")
            return
        self.selected_tracks.append(track_uri)
        self.selected_tracks_list.insert(tk.END, track_info)
        self.log(f"➕ Added: {track_info}")

    def remove_selected_track(self):
        selection = self.selected_tracks_list.curselection()
        if not selection:
            return
        index = selection[0]
        removed_track = self.selected_tracks_list.get(index)
        self.selected_tracks.pop(index)
        self.selected_tracks_list.delete(index)
        self.log(f"➖ Removed: {removed_track}")

    def create_new_playlist(self):
        name = self.new_playlist_name.get().strip()
        if not name:
            self.log("❌ Playlist name is required")
            return
        if not self.selected_tracks:
            self.log("❌ Add tracks before creating")
            return

        description = self.new_playlist_desc.get().strip()
        public = self.public_var.get()
        self.log(f"📝 Creating playlist: {name}")

        try:
            user_id = self.sp.current_user()['id']
            playlist = self.sp.user_playlist_create(
                user=user_id,
                name=name,
                public=public,
                description=description
            )
            for i in range(0, len(self.selected_tracks), 100):
                self.sp.playlist_add_items(playlist['id'], self.selected_tracks[i:i+100])

            self.log(f"✅ Created: {name} with {len(self.selected_tracks)} tracks")
            self.log(f"🔗 URL: {playlist['external_urls']['spotify']}")
            self.load_user_playlists()
            self.reset_create_form()
        except Exception as e:
            self.log(f"❌ Error: {str(e)}")

    def reset_create_form(self):
        self.new_playlist_name.delete(0, tk.END)
        self.new_playlist_desc.delete(0, tk.END)
        self.search_entry.delete(0, tk.END)
        self.search_results.delete(0, tk.END)
        self.selected_tracks_list.delete(0, tk.END)
        self.search_results_tracks = []
        self.selected_tracks = []
        self.public_var.set(True)

if __name__ == "__main__":
    root = tk.Tk()
    app = SpotifyPlaylistManagerGUI(root)
    root.mainloop()
