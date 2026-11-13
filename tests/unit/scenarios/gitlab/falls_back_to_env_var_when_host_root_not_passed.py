import os

import vedro

from vedro_step_tracer.gitlab import to_host_path


class Scenario(vedro.Scenario):
    subject = "gitlab: without an explicit host_root argument, the env var is used as a fallback"

    def given_the_env_var_is_set(self):
        self._prev_env = os.environ.get("HOST_PROJECT_ROOT_DIRECTORY")
        os.environ["HOST_PROJECT_ROOT_DIRECTORY"] = "/from-env"

    def when_to_host_path_is_called_without_host_root(self):
        self.result = to_host_path("/project/helpers/client.py", "/project", "app")

    def then_the_env_var_value_should_be_used(self):
        assert self.result == os.path.join("/from-env", "app", "helpers/client.py")

    def and_the_env_var_should_be_restored(self):
        if self._prev_env is None:
            os.environ.pop("HOST_PROJECT_ROOT_DIRECTORY", None)
        else:
            os.environ["HOST_PROJECT_ROOT_DIRECTORY"] = self._prev_env
