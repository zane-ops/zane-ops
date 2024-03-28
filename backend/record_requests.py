# from responses import _recorder

# CADDY_PROXY_URL = "http://localhost:2019"
#
#
# # @_recorder.record(file_path="out.yaml")
# def test_recorder():
#     # Create caddy config
#     # resp_get = requests.get("http://twitter.com/")
#     # print(resp_get)
#     # response = requests.get(
#     #     f"{CADDY_PROXY_URL}/id/root",
#     #     headers={"content-type": "application/json", "accept": "application/json"},
#     # )
#     # response = requests.get(
#     #     f"{CADDY_PROXY_URL}/config/",
#     #     headers={"content-type": "application/json", "accept": "application/json"},
#     # )
#     response = requests.get(
#         f"{CADDY_PROXY_URL}/id/zane.local",
#         headers={"content-type": "application/json", "accept": "application/json"},
#     )
#     # response = requests.post(
#     #     f"{CADDY_PROXY_URL}/id/root/http/servers/zane/logs/logger_names/kiss-hub.local",
#     #     data=json.dumps(""),
#     #     headers={"content-type": "application/json", "accept": "application/json"},
#     # )
#     pass


def sort_paths(paths: list[str]):
    """
    This function implement the same ordering as caddy to pass to the caddy proxy API
    reference: https://caddyserver.com/docs/caddyfile/directives#sorting-algorithm
    This code is adapated from caddy source code : https://github.com/caddyserver/caddy/blob/ddb1d2c2b11b860f1e91b43d830d283d1e1363b2/caddyconfig/httpcaddyfile/directives.go#L495-L513
    """

    def path_specificity(path: str):
        # Removing trailing '*' for comparison and determining the "real" length
        normalized_path = path.rstrip("*")
        path_length = len(normalized_path)

        # Using a tuple for comparison: first by the normalized length (longest first),
        # then by whether the original path ends with '*' (no wildcard is more specific),
        # and finally by the original path length in case of identical paths except for the wildcard
        return -path_length, path.endswith("*"), -len(path)

    # Sort the paths based on the specified criteria
    sorted_paths = sorted(paths, key=path_specificity)
    return sorted_paths


if __name__ == "__main__":
    # Example paths
    paths = ["/foo", "/foo*", "/foobar", "/foo/*"]
    paths = ["/*", "/api/*"]

    sorted_paths = sort_paths(paths)
    print(sorted_paths)
    assert sorted_paths == ["/foobar", "/foo/*", "/foo", "/foo*"]
