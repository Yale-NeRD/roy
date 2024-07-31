from hatchling.builders.hooks.plugin.interface import BuildHookInterface
import subprocess
import os
import shutil

class CythonBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        subprocess.check_call(["make"], cwd="src/roy_on_ray")
        pass

    def finalize(self, version, build_data, artifact_data):
        # This method runs after the build is complete
        pass

# The script entry point
if __name__ == "__main__":
    hook = CythonBuildHook()
    hook.initialize(None, None)
    hook.finalize(None, None, None)
