download = """
\b
\b\bExamples:
  # Basic download by title
  nviu anilist download -t "Attack on Titan"
\b
  # Download specific episodes
  nviu anilist download -t "One Piece" --episode-range "1-10"
\b
  # Download single episode
  nviu anilist download -t "Death Note" --episode-range "1"
\b
  # Download multiple specific episodes
  nviu anilist download -t "Naruto" --episode-range "1,5,10"
\b
  # Download with quality preference
  nviu anilist download -t "Death Note" --quality 1080 --episode-range "1-5"
\b
  # Download with multiple filters
  nviu anilist download -g Action -T Isekai --score-greater 80 --status RELEASING
\b
  # Download with concurrent downloads
  nviu anilist download -t "Demon Slayer" --episode-range "1-5" --max-concurrent 3
\b
  # Force redownload existing episodes
  nviu anilist download -t "Your Name" --episode-range "1" --force-redownload
\b
  # Download from a specific season and year
  nviu anilist download --season WINTER --year 2024 -s POPULARITY_DESC
\b
  # Download with genre filtering
  nviu anilist download -g Action -g Adventure --score-greater 75
\b
  # Download only completed series
  nviu anilist download -g Fantasy --status FINISHED --score-greater 75
\b
  # Download movies only
  nviu anilist download -F MOVIE -s SCORE_DESC --quality best
"""


search = """
\b
\b\bExamples:
  # Basic search by title
  nviu anilist search -t "Attack on Titan"
\b
  # Search with multiple filters
  nviu anilist search -g Action -T Isekai --score-greater 75 --status RELEASING
\b
  # Get anime with the tag of isekai
  nviu anilist search -T isekai
\b
  # Get anime of 2024 and sort by popularity, finished or releasing, not in your list
  nviu anilist search -y 2024 -s POPULARITY_DESC --status RELEASING --status FINISHED --not-on-list
\b
  # Get anime of 2024 season WINTER
  nviu anilist search -y 2024 --season WINTER
\b
  # Get anime genre action and tag isekai,magic
  nviu anilist search -g Action -T Isekai -T Magic
\b
  # Get anime of 2024 thats finished airing
  nviu anilist search -y 2024 -S FINISHED
\b
  # Get the most favourite anime movies
  nviu anilist search -f MOVIE -s FAVOURITES_DESC
\b
  # Search with score and popularity filters
  nviu anilist search --score-greater 80 --popularity-greater 50000
\b
  # Search excluding certain genres and tags
  nviu anilist search --genres-not Ecchi --tags-not "Hentai"
\b
  # Search with date ranges (YYYYMMDD format)
  nviu anilist search --start-date-greater 20200101 --start-date-lesser 20241231
\b
  # Get only TV series, exclude certain statuses
  nviu anilist search -f TV --status-not CANCELLED --status-not HIATUS
\b
  # Paginated search with custom page size
  nviu anilist search -g Action --page 2 --per-page 25
\b
  # Search for manga specifically
  nviu anilist search --media-type MANGA -g Fantasy
\b
  # Complex search with multiple criteria
  nviu anilist search -t "demon" -g Action -g Supernatural --score-greater 70 --year 2020 -s SCORE_DESC
\b
  # Dump search results as JSON instead of interactive mode
  nviu anilist search -g Action --dump-json
"""


main = """
\b
\b\bExamples:
  # ---- search ----
\b
  # Basic search by title
  nviu anilist search -t "Attack on Titan"
\b
  # Search with multiple filters
  nviu anilist search -g Action -T Isekai --score-greater 75 --status RELEASING
\b
  # Get anime with the tag of isekai
  nviu anilist search -T isekai
\b
  # Get anime of 2024 and sort by popularity, finished or releasing, not in your list
  nviu anilist search -y 2024 -s POPULARITY_DESC --status RELEASING --status FINISHED --not-on-list
\b
  # Get anime of 2024 season WINTER
  nviu anilist search -y 2024 --season WINTER
\b
  # Get anime genre action and tag isekai,magic
  nviu anilist search -g Action -T Isekai -T Magic
\b
  # Get anime of 2024 thats finished airing
  nviu anilist search -y 2024 -S FINISHED
\b
  # Get the most favourite anime movies
  nviu anilist search -f MOVIE -s FAVOURITES_DESC
\b
  # Search with score and popularity filters
  nviu anilist search --score-greater 80 --popularity-greater 50000
\b
  # Search excluding certain genres and tags
  nviu anilist search --genres-not Ecchi --tags-not "Hentai"
\b
  # Search with date ranges (YYYYMMDD format)
  nviu anilist search --start-date-greater 20200101 --start-date-lesser 20241231
\b
  # Get only TV series, exclude certain statuses
  nviu anilist search -f TV --status-not CANCELLED --status-not HIATUS
\b
  # Paginated search with custom page size
  nviu anilist search -g Action --page 2 --per-page 25
\b
  # Search for manga specifically
  nviu anilist search --media-type MANGA -g Fantasy
\b
  # Complex search with multiple criteria
  nviu anilist search -t "demon" -g Action -g Supernatural --score-greater 70 --year 2020 -s SCORE_DESC
\b
  # Dump search results as JSON instead of interactive mode
  nviu anilist search -g Action --dump-json
\b
  # ---- login ----
\b
  # To sign in just run
  nviu anilist auth
\b
  # To check your login status
  nviu anilist auth --status
\b
  # To log out and erase credentials
  nviu anilist auth --logout
\b
  # ---- notifier ----
\b
  # basic form
  nviu anilist notifier
\b
  # with logging to stdout
  nviu --log anilist notifier
\b
  # with logging to a file. stored in the same place as your config
  nviu --log-file anilist notifier
"""
