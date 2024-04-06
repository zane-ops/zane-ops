# from responses import _recorder
import json
from io import BytesIO

import pycurl
import requests


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


def fetch_config_and_etag(url):
    """Fetch configuration and ETag using pycurl."""
    buffer = BytesIO()
    etag = [None]  # Mutable object to capture the ETag

    def header_function(header_line):
        """Callback for processing headers, captures ETag."""
        try:
            header_line = header_line.decode("iso-8859-1")
            if ":" in header_line:
                name, value = header_line.split(":", 1)
                if name.strip().lower() == "etag":
                    etag[0] = value.strip()
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

    body = buffer.getvalue().decode("utf-8")
    return etag[0], body


def apply_config_change(url, data, etag, retry_count=3):
    """Attempt to apply configuration change using the requests library."""
    for attempt in range(retry_count):
        headers = {"If-Match": etag, "Content-Type": "application/json"}
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 412:
            print(f"Collision detected, retrying... (Attempt {attempt + 1})")
            etag, _ = fetch_config_and_etag(url)  # Fetch new ETag and config
            if not etag:
                print("Failed to retrieve new ETag. Aborting.")
                return
        elif response.ok:
            print("Change applied successfully.")
            return
        else:
            print(f"Failed to apply changes. Status code: {response.status_code}")
            return
    print("Failed to apply changes after several attempts.")


if __name__ == "__main__":
    # fetch_config("apps")
    etag, body = fetch_config_and_etag(
        "localhost:2020/config/apps/http/servers/zane/routes"
    )
    print(f"Etag={etag}")
    print(f"Body={json.dumps(json.loads(body), indent=2)}")
    pass
