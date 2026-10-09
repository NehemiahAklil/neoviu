download = """
\b
\b\bExamples:
  # Download all available episodes
  # multiple titles can be specified with -t option
  nviu download -t <anime-title> -t <anime-title>
  # -- or --
  nviu download -t <anime-title> -t <anime-title> -r ':'
\b
  # download latest episode for the two anime titles
  # the number can be any no of latest episodes but a minus sign
  # must be present
  nviu download -t <anime-title> -t <anime-title> -r '-1'
\b
  # latest 5
  nviu download -t <anime-title> -t <anime-title> -r '-5'
\b
  # Download specific episode range
  # be sure to observe the range Syntax
  nviu download -t <anime-title> -r '<episodes-start>:<episodes-end>:<step>'
\b
  nviu download -t <anime-title> -r '<episodes-start>:<episodes-end>'
\b
  nviu download -t <anime-title> -r '<episodes-start>:'
\b
  nviu download -t <anime-title> -r ':<episodes-end>'
\b
  # download specific episode
  # remember python indexing starts at 0
  nviu download -t <anime-title> -r '<episode-1>:<episode>'
\b
  # merge subtitles with ffmpeg to mkv format; hianime tends to give subs as separate files
  # and dont prompt for anything
  # eg existing file in destination instead remove
  # and clean
  # ie remove original files (sub file and vid file)
  # only keep merged files
  nviu download -t <anime-title> --merge --clean --no-prompt
\b
  # EOF is used since -t always expects a title
  # you can supply anime titles from file or -t at the same time
  # from stdin
  echo -e "<anime-title>\\n<anime-title>\\n<anime-title>" | nviu download -t "EOF" -r <range> -f -
\b
  # from file
  nviu download -t "EOF" -r <range> -f <file-path>
"""
search = """
\b
\b\bExamples:
  # basic form where you will still be prompted for the episode number
  # multiple titles can be specified with the -t option
  nviu search -t <anime-title> -t <anime-title>
\b
  # binge all episodes with this command
  nviu search -t <anime-title> -r ':'
\b
  # watch latest episode
  nviu search -t <anime-title> -r '-1'
\b
  # binge a specific episode range with this command
  # be sure to observe the range Syntax
  nviu search -t <anime-title> -r '<start>:<stop>'
\b
  nviu search -t <anime-title> -r '<start>:<stop>:<step>'
\b
  nviu search -t <anime-title> -r '<start>:'
\b
  nviu search -t <anime-title> -r ':<end>'
"""
