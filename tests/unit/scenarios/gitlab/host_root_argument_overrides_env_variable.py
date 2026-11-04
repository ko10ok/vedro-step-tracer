import os

import vedro

from vedro_step_tracer.gitlab import to_host_path


class Scenario(vedro.Scenario):
    subject = "gitlab: an explicit host_root argument overrides the HOST_PROJECT_ROOT_DIRECTORY env var"

    def given_the_env_var_is_set_to_a_different_value(self):
        self._prev_env = os.environ.get("HOST_PROJECT_ROOT_DIRECTORY")
        os.environ["HOST_PROJECT_ROOT_DIRECTORY"] = "/from-env"

    def when_to_host_path_is_called_with_an_explicit_host_root(self):
        self.result = to_host_path(
            "/project/helpers/client.py", "/project", "app",
            host_root="/from-config",
        )

    def then_the_explicit_value_should_win(self):
        assert self.result == os.path.join("/from-config", "app", "helpers/client.py")

    def and_the_env_var_should_be_restored(self):
        if self._prev_env is None:
            os.environ.pop("HOST_PROJECT_ROOT_DIRECTORY", None)
        else:
            os.environ["HOST_PROJECT_ROOT_DIRECTORY"] = self._prev_env
