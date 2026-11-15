import vedro

from vedro_step_tracer.reporting.html.values import html_value

_PAYLOAD = b"\x00\xff" * (1024 * 1024)
_MAX_HTML_LEN = 200_000


class BinaryMessage:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def __str__(self) -> str:
        return repr(self.data)


class Scenario(vedro.Scenario):
    subject = "reporting: a huge single-line binary object renders bounded html"

    def given_an_object_with_a_huge_single_line_str(self):
        self.value = BinaryMessage(_PAYLOAD)

    def when_it_is_rendered_as_html(self):
        self.html = html_value(self.value)

    def then_the_markup_should_be_bounded(self):
        assert len(self.html) < _MAX_HTML_LEN

    def and_it_should_report_the_original_size(self):
        assert "chars" in self.html
