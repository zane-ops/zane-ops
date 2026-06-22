# Licensing-related constants for the EE package.
from datetime import timedelta

ZANEOPS_REMOTE_API_HOST = "https://api.zaneops.dev"

ZANEOPS_LICENSE_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEAuQke5cRU0kAh1la82bgq
Npba1vKvpNzOmMO33uOkKfUS1Y+pOH5ivpQvTYJ0B61c6JHfcJ1sCz5V2Fe5Fsoi
Mnn3Gcd4dYnyLTkS8/BtBpgD20IofRN0n65+NK2ItK9Oz/5sBeSmVW1sGPq/zFIl
6lmKyRgSnwGC09PpbEocwN9Op8z5tsA9uxuVDj3zNJUEhwzRwbn1FHlszlFdDLkR
ah3R23Dc6H1b3A7pDFkGRAnppPjKFZpQWSoZ8T6ubdYg9P220gj1nQkmHec29toU
/LdTfSlEPDSzVDOq/FH2qqkcqUplxoFQ0mYtxNbRcPcCJgVy/92fyfCa5yg6n8ab
2Jlq4cqnnVdTBvuPgEER+Pln31jL3fa8+pqenCwiJu+HU3D+SZTuLx77NqVWFWan
9lDFxC4vOGzKmKbxWnU1+p7vpbdXNhQCujGD83in2ZXRU8FUefyYLcDPw8XSEqlW
yOWcajE+OskUCAk3rSweiixaDsjxncp7+9PCFnfV9QImyLZ887m9B4CnpARq7EWO
7Kd2wflz/7rBv1lqWrtnlDCPjZgbNkpF4bHeTtAUdft6GXZhaO3a6ntu6fN/YZEY
W6HxRzFYargWaMjoljbeG0bXuf0htl6Kqp0vSHm01F42CuahoA0WR6NGuQitkebv
I7pRh9THeci07r3zs88WW4sCAwEAAQ==
-----END PUBLIC KEY-----
"""

# Recurring schedule that periodically re-validates the installed license
# against the remote API (`POST /v1/license/check`). The instance holds a single
# license (singleton), so the schedule id is a constant.
LICENSE_CHECK_SCHEDULE_ID = "license-check"
LICENSE_CHECK_INTERVAL = timedelta(hours=12)
