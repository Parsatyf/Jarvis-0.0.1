import unittest

from config import Config
from logger import Logger
from tools import Tools


class DummyLogger:
    def info(self, *args, **kwargs):
        pass

    def warn(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class ToolsSafetyTests(unittest.TestCase):
    def test_run_command_rejects_shell_metacharacters(self):
        tools = Tools(Config(), DummyLogger())
        result = tools.run_command("echo hello && echo world")
        self.assertFalse(result.ok)
        self.assertIn("unsafe", (result.error or "").lower())


if __name__ == "__main__":
    unittest.main()
