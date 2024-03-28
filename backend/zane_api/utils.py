def strip_slash_if_exists(
    url: str,
    strip_end: bool = False,
    strip_start: bool = True,
):
    final_url = url
    if strip_start and url.startswith("/"):
        final_url = final_url[1:]
    if strip_end and url.endswith("/"):
        final_url = final_url[:-1]
    return final_url
