from django.db import models
from zane_api.models import TimestampedModel
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization


class SSHKey(TimestampedModel):
    user = models.CharField(max_length=255, blank=False)
    public_key = models.TextField(blank=False)
    private_key = models.TextField(blank=False)
    name = models.CharField(max_length=255, blank=False, unique=True)

    @classmethod
    def create_key_pair(cls) -> tuple[str, str]:
        # Generate a new RSA key pair
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_key_str = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()

        public_key = private_key.public_key()
        public_key_str = public_key.public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH,
        ).decode()

        return (public_key_str, private_key_str)
