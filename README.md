================================================================
                       YT DOWNLOADER  —  SETUP
----------------------------------------------------------------
1.  REQUIREMENTS
----------------------------------------------------------------

You need three things installed before the app will run:

  (a) PYTHON 3.9 or newer
      Download:  https://www.python.org/downloads/
      During install, TICK the box "Add Python to PATH".

  (b) FFMPEG (also gives you ffprobe)
      Download:  https://www.gyan.dev/ffmpeg/builds/
                 (grab "ffmpeg-release-essentials.zip")
      Extract anywhere, then add the "bin" folder to your
      Windows PATH so the app can find ffmpeg.exe.

      Quick PATH check — open Command Prompt and type:
          ffmpeg -version
      If you see a version string, you are good.

  (c) PYTHON PACKAGES — open Command Prompt and run:
          pip install yt-dlp customtkinter tkinterdnd2 plyer

      plyer is optional — it enables desktop toast notifications
      when a download finishes.  The app works fine without it.

----------------------------------------------------------------
2.  OPTIONAL FONT
----------------------------------------------------------------

The header uses the "Old London" font.  If it is not installed
the app still runs — Windows just falls back to a default font.
To install it:

      Download from any free font site (search "Old London
      font Dieter Steffmann"), unzip, right-click the .ttf,
      then "Install".

----------------------------------------------------------------
3.  RUNNING THE APP
----------------------------------------------------------------

Option A  —  Double-click  run.bat

Option B  —  From a Command Prompt:
                python yt_downloader_ui.py

----------------------------------------------------------------
4.  USING THE APP
----------------------------------------------------------------

  1.  Paste a YouTube URL into the URL box, OR drag-and-drop a
      URL from your browser onto the window.
  2.  Pick a format:
          MP4              -  video file (choose quality: Best/1080p/720p/480p/360p)
          MP3 (audio only) -  choose 128 / 192 / 320 kbps; optionally embed thumbnail
          WAV (lossless)   -  uncompressed PCM WAV
  3.  Pick a Save folder (remembered between launches).
  4.  Click Download.  A progress bar and live stats appear.
      Click "✕ Cancel" at any time to abort.

  5.  History tab keeps a log of every file you downloaded.
      Each entry has:
          📂 Show  — opens the containing folder
          ▶ Open   — opens the file directly
          ✕        — removes the entry from history

  6.  "⟳ Update yt-dlp" button in the top-right keeps the
      downloader current whenever YouTube breaks things.

  7.  When the app gains focus and the URL box is empty, it
      automatically detects a YouTube URL on the clipboard.

  8.  A desktop notification appears when a download finishes
      (requires plyer — see step 1c).

----------------------------------------------------------------
5.  TROUBLESHOOTING
----------------------------------------------------------------

  *  "Missing: yt-dlp, ffmpeg" appears in red
        - re-run the pip install command
        - confirm ffmpeg is on PATH ( ffmpeg -version )

  *  Drag-and-drop does nothing
        - tkinterdnd2 was not installed; see step 1c

  *  Old London header looks like normal text
        - the font is not installed; see step 2

  *  Header floppy / tab icons render as boxes
        - your Windows lacks the Segoe UI Emoji font; that
          font ships with Windows 10/11 by default

  *  Settings / history are stored in your home folder:
        %USERPROFILE%\.yt_downloader_settings.json
        %USERPROFILE%\.yt_downloader_history.json
      Delete those files to reset to defaults.

================================================================
