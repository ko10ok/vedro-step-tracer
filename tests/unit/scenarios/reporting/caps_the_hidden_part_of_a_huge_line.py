import vedro

from vedro_step_tracer.reporting.shorten import shorten_line

_MAX_RETAINED_LEN = 100_000


class Scenario(vedro.Scenario):
    subject = "reporting: a huge line keeps only a bounded hidden part"

    def given_a_two_megabyte_line(self):
        self.text = "x" * (2 * 1024 * 1024)

    def when_it_is_shortened(self):
        self.chunk = shorten_line(self.text, 1000)

    def then_the_retained_text_should_be_bounded(self):
        assert self.chunk.total < _MAX_RETAINED_LEN

    def and_the_visible_head_and_tail_should_still_be_present(self):
        assert self.chunk.head
        assert self.chunk.tail
