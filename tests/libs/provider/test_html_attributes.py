from viu_media.libs.provider.scraping.html_parser import extract_attributes


def test_attributes_preserve_full_data_names_and_legacy_aliases() -> None:
    attributes = extract_attributes(
        """<a data-id="123" data-server-name="ZokoAnime"
        title="JoJo's &amp; Friends" href='/watch/jojo-123?ep=1&amp;lang=sub'>Title</a>"""
    )
    assert attributes["data-id"] == attributes["id"] == "123"
    assert attributes["data-server-name"] == attributes["name"] == "ZokoAnime"
    assert attributes["title"] == "JoJo's & Friends"
    assert attributes["href"] == "/watch/jojo-123?ep=1&lang=sub"


def test_unquoted_attributes_and_empty_fragments_remain_supported() -> None:
    assert extract_attributes("<button data-src=https://video.example/720>")["src"] == (
        "https://video.example/720"
    )
    assert extract_attributes("") == {}
