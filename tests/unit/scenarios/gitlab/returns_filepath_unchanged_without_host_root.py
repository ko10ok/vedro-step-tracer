import os

import vedro

from vedro_step_tracer.gitlab import to_host_path


class Scenario(vedro.Scenario):
    subject = "gitlab: without host_root (argument or env var), the path is returned unchanged"

    def given_the_env_var_is_not_set(self):
        self._prev_env = os.environ.pop("HOST_PROJECT_ROOT_DIRECTORY", None)

    def when_to_host_path_is_called_without_host_root(self):
        self.filepath = "/project/helpers/client.py"
        self.result = to_host_path(self.filepath, "/project", "app")

    def then_the_original_filepath_should_be_returned(self):
        assert self.result == self.filepath

    def and_the_env_var_should_be_restored(self):
        if self._prev_env is not None:
            os.environ["HOST_PROJECT_ROOT_DIRECTORY"] = self._prev_env
