from django.core.exceptions import ValidationError
from django.test import TestCase

from ..validators import validate_url_domain, validate_url_path


class DomainValidatorsTestCase(TestCase):
    def test_validate_url_domain_succesfull(self):
        try:
            validate_url_domain("zane.local")
        except ValidationError:
            self.fail("ValidationError raised unexpectedly!")

    def test_validate_url_domain_succesfull_for_subdomains(self):
        try:
            validate_url_domain("git.zane.local")
        except ValidationError:
            self.fail("ValidationError raised unexpectedly!")

    def test_validate_url_domain_without_http(self):
        with self.assertRaises(ValidationError):
            validate_url_domain("http://zane.local")

    def test_validate_url_domain_without_pathname(self):
        with self.assertRaises(ValidationError):
            validate_url_domain("zane.local/hello")

    def test_validate_url_domain_without_search_params(self):
        with self.assertRaises(ValidationError):
            validate_url_domain("zane.local?hello=world")

    def test_validate_url_domain_without_hashtag(self):
        with self.assertRaises(ValidationError):
            validate_url_domain("zane.local#hello=world")


class BasePathValidatorsTestCase(TestCase):
    def test_validate_base_path_succesfull(self):
        try:
            validate_url_path("/hello")
        except ValidationError:
            self.fail("ValidationError raised unexpectedly!")

    def test_validate_base_path_succesfull_for_multi_path(self):
        try:
            validate_url_path("/hello/world")
        except ValidationError:
            self.fail("ValidationError raised unexpectedly!")

    def test_validate_base_path_succesfull_for_slash(self):
        try:
            validate_url_path("/")
        except ValidationError:
            self.fail("ValidationError raised unexpectedly!")

    def test_validate_base_path_without_domain(self):
        with self.assertRaises(ValidationError):
            validate_url_path("google.com/")

    def test_validate_base_path_without_double_dots(self):
        with self.assertRaises(ValidationError):
            validate_url_path("../")

    def test_validate_base_path_with_dots(self):
        try:
            validate_url_path("/hello.world")
        except ValidationError:
            self.fail("ValidationError raised unexpectedly!")

    def test_validate_base_path_without_star(self):
        try:
            validate_url_path("/hello/*")
        except ValidationError:
            self.fail("ValidationError raised unexpectedly!")

    def test_validate_base_path_without_slash(self):
        with self.assertRaises(ValidationError):
            validate_url_path("hello/*")
