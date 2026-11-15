import vedro

from vedro_step_tracer.reporting.html.values import html_value

_PAYLOAD = bytes(range(256)) * 8192
_MAX_HTML_LEN = 200_000


class BinaryMessage:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def __str__(self) -> str:
        data = self.data
        return "\n".join(data[i:i + 16].hex() for i in range(0, len(data), 16))


class Scenario(vedro.Scenario):
    subject = "reporting: a huge multiline binary object renders bounded html"

    def given_an_object_with_a_huge_multiline_str(self):
        self.value = BinaryMessage(_PAYLOAD)

    def when_it_is_rendered_as_html(self):
        self.html = html_value(self.value)

    def then_the_markup_should_be_bounded(self):
        assert len(self.html) < _MAX_HTML_LEN

    def and_it_should_report_the_original_size(self):
        assert "chars" in self.html
