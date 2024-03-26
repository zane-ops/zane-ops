import requests
from responses import _recorder

CADDY_PROXY_URL = "http://localhost:2019"


@_recorder.record(file_path="out.yaml")
def test_recorder():
    # Create caddy config
    # resp_get = requests.get("http://twitter.com/")
    # print(resp_get)
    # response = requests.get(
    #     f"{CADDY_PROXY_URL}/id/root",
    #     headers={"content-type": "application/json", "accept": "application/json"},
    # )
    # response = requests.get(
    #     f"{CADDY_PROXY_URL}/config/",
    #     headers={"content-type": "application/json", "accept": "application/json"},
    # )
    response = requests.get(
        f"{CADDY_PROXY_URL}/id/zane.local",
        headers={"content-type": "application/json", "accept": "application/json"},
    )
    # response = requests.post(
    #     f"{CADDY_PROXY_URL}/id/root/http/servers/zane/logs/logger_names/kiss-hub.local",
    #     data=json.dumps(""),
    #     headers={"content-type": "application/json", "accept": "application/json"},
    # )
    pass


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


if __name__ == "__main__":
    test_recorder()
    # print(strip_slash_if_exists("/bash"))
    # print(strip_slash_if_exists("bash/", strip_end=True))
    # print(strip_slash_if_exists("/bash/", strip_start=True, strip_end=True))
