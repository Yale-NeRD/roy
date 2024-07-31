from hatchling.builders.hooks.plugin.interface import BuildHookInterface
import subprocess

class CythonBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        # You can perform any initial setup here if needed
        pass

    def finalize(self, version, build_data, artifact_data):
        # This method runs after the build is complete
        subprocess.check_call(["make"], cwd="src/roy_on_ray")

# The script entry point
if __name__ == "__main__":
    hook = CythonBuildHook()
    hook.finalize(None, None, None)
