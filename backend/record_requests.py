# from responses import _recorder
from io import BytesIO

import pycurl


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
# def sort_paths(paths: list[str]):
#     """
#     This function implement the same ordering as caddy to pass to the caddy proxy API
#     reference: https://caddyserver.com/docs/caddyfile/directives#sorting-algorithm
#     This code is adapated from caddy source code : https://github.com/caddyserver/caddy/blob/ddb1d2c2b11b860f1e91b43d830d283d1e1363b2/caddyconfig/httpcaddyfile/directives.go#L495-L513
#     """
#
#     def path_specificity(path: str):
#         # Removing trailing '*' for comparison and determining the "real" length
#         normalized_path = path.rstrip("*")
#         path_length = len(normalized_path)
#
#         # Using a tuple for comparison: first by the normalized length (longest first),
#         # then by whether the original path ends with '*' (no wildcard is more specific),
#         # and finally by the original path length in case of identical paths except for the wildcard
#         return -path_length, path.endswith("*"), -len(path)
#
#     # Sort the paths based on the specified criteria
#     sorted_paths = sorted(paths, key=path_specificity)
#     return sorted_paths
#
#
# if __name__ == "__main__":
#     # Example paths
#     paths = ["/foo", "/foo*", "/foobar", "/foo/*"]
#     paths = ["/*", "/api/*"]
#
#     sorted_paths = sort_paths(paths)
#     print(sorted_paths)
#     assert sorted_paths == ["/foobar", "/foo/*", "/foo", "/foo*"]
# class ConfigAPI:
#     def __init__(self):
#         self.config = {}
#
#     def _resolve_path(self, path):
#         """Resolve path to dict and key."""
#         parts = path.split("/")
#         return (
#             eval(f"self.config" + "".join([f'["{part}"]' for part in parts[:-1]])),
#             parts[-1],
#         )
#
#     def get(self, path):
#         """GET /id/[path] - Exports the config at the named path"""
#         try:
#             parent, key = self._resolve_path(path)
#             return parent[key]
#         except KeyError:
#             return None
#
#     def post(self, path, value):
#         """POST /id/[path] - Sets or replaces object; appends to array"""
#         parent, key = self._resolve_path(path)
#         if key in parent:
#             if isinstance(parent[key], list):
#                 parent[key].append(value)
#             else:
#                 parent[key] = value
#         else:
#             parent[key] = value
#
#     def put(self, path, value):
#         """PUT /id/[path] - Creates new object; inserts into array"""
#         parent, key = self._resolve_path(path)
#         if isinstance(parent.get(key, None), list):
#             parent[key].insert(0, value)  # Example: inserts at the beginning
#         else:
#             parent[key] = value
#
#     def patch(self, path, value):
#         """PATCH /id/[path] - Replaces an existing object or array element"""
#         self.post(path, value)  # For simplicity, PATCH behaves like POST here
#
#     def delete(self, path):
#         """DELETE /id/[path] - Deletes the value at the named path"""
#         parent, key = self._resolve_path(path)
#         if key in parent:
#             del parent[key]
#
#
# if __name__ == "__main__":
#     # Example usage
#     api = ConfigAPI()
#
#     # Adding and retrieving a configuration
#     api.post(
#         "zane.local",
#         {
#             "@id": "zane.local",
#             "handle": [{"handler": "subroute", "routes": []}],
#             "match": [{"host": "zane.local"}],
#             "terminal": True,
#         },
#     )
#
#     api.post(
#         "zane.local/handle/0/routes",
#         {
#             "@id": "zane.local-api",
#             "handle": [
#                 {
#                     "handler": "subroute",
#                     "routes": [
#                         {
#                             "handle": [
#                                 {
#                                     "handler": "reverse_proxy",
#                                     "upstreams": [
#                                         {"dial": "host.docker.internal:8000"}
#                                     ],
#                                 }
#                             ]
#                         }
#                     ],
#                 }
#             ],
#             "match": [{"path": ["/api/*"]}],
#         },
#     )
#
#     print(api.get("zane.local"))
#     print(api.get("zane.local-api"))
# def fetch_config_with_trailer(scope):
#     conn = http.client.HTTPConnection("localhost", 2019)
#     conn.request("GET", f"/config/{scope}")
#     response = conn.getresponse()
#
#     # Read the body to ensure all data is received, including trailers.
#     body = response.read()
#
#     # Attempt to access the trailer headers. This part is highly dependent on server support and client behavior.
#     etag = response.get_trailer("ETag")
#     return etag, body


def fetch_etag(url: str):
    buffer = BytesIO()
    etag: str | None = None  # Mutable object to capture the ETag

    def header_function(header_line: bytes):
        """Callback for processing headers, captures ETag."""
        nonlocal etag
        try:
            header_line = header_line.decode("iso-8859-1")
            if ":" in header_line:
                name, value = header_line.split(":", 1)
                if name.strip().lower() == "etag":
                    etag = value.strip()
        except ValueError:
            pass  # Ignore headers that don't split as expected

    c = pycurl.Curl()
    c.setopt(c.URL, url)
    c.setopt(c.WRITEDATA, buffer)
    c.setopt(c.HEADERFUNCTION, header_function)
    try:
        c.perform()
    finally:
        c.close()

    return etag


def apply_config_changes(
    url: str, request_function: Callable[[str, dict], Response], retry_count=3
):
    for attempt in range(retry_count):
        etag = fetch_etag(url)

        if not etag:
            raise Exception("Failed to retrieve new ETag. ")

        headers = {"If-Match": etag, "Content-Type": "application/json"}
        response = request_function(
            url,
            headers,
        )
        if response.status_code == 412:
            print(f"Collision detected, retrying... (Attempt {attempt + 1})")
            continue
        return response
    raise Exception("Failed to apply changes after several attempts.")


if __name__ == "__main__":
    # fetch_config("apps")
    etag, body = fetch_etag(
        "localhost:2019/config/apps/http/servers/zane/routes"
    )
    print(f"Etag={etag}")
    # print(f"Body={json.dumps(json.loads(body), indent=2)}")
    pass
