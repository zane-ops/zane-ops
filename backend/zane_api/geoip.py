import geoip2.database
import functools
from django.conf import settings
import geoip2.errors
import maxminddb
import traceback


# We cache the geoip Reader as creating a Reader
# is an expensive operation, so we use the same object to query all ips
@functools.cache
def get_geoip_reader(path: str):
    geoip_reader = geoip2.database.Reader(path)
    print(f"[get_geoip_reader] {geoip_reader=}")
    return geoip_reader


def lookup_country_code(ip: str):
    iso_code: str | None = None

    if settings.MAXMIND_DB_PATH:
        try:
            reader = get_geoip_reader(settings.MAXMIND_DB_PATH)
        except (OSError, maxminddb.InvalidDatabaseError):
            # the DB is optional : missing, unreadable or invalid file (ex: `/dev/null`)
            # should never make the ingest fail
            traceback.print_exc()
        else:
            try:
                response = reader.country(ip)
            except geoip2.errors.AddressNotFoundError:
                traceback.print_exc()
            else:
                iso_code = response.country.iso_code

    print(f"[lookup_country_code] {iso_code=}")
    return iso_code
