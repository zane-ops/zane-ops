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


if __name__ == "__main__":
    test_recorder()
