import base64
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

MOBILE = Path(__file__).resolve().parents[1] / "Mobile-Agent-v3.5/mobile_use"
sys.path.insert(0, str(MOBILE))
from run_gui_owl_1_5_for_mobile import parse_action, rescale_coordinates
from utils import AdbTools, build_messages, image_to_base64


class PhoneRuntimeTests(unittest.TestCase):
    def test_messages_can_encode_file_uri_with_spaces_and_unicode(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "手机 screenshot.png"
            Image.new("RGB", (1080, 2280)).save(path)
            messages = build_messages(str(path), "Read the screen", [], "gui-owl")
            reference = messages[-1]["content"][-1]["image"]
            result = image_to_base64(reference)
            encoded = result.split(",", 1)[1]
            with Image.open(BytesIO(base64.b64decode(encoded))) as image:
                self.assertEqual(image.size, (1092, 2268))

    def test_device_coordinates_do_not_use_resized_model_dimensions(self):
        action = rescale_coordinates({"coordinate": [500, 500],
                                      "coordinate2": [1000, 1000]}, 1080, 2280)
        self.assertEqual(action["coordinate"], [540, 1140])
        self.assertEqual(action["coordinate2"], [1079, 2279])
        with self.assertRaises(ValueError):
            rescale_coordinates({"coordinate": [-1, 500]}, 1080, 2280)

    def test_tool_call_accepts_compact_and_multiline_json(self):
        action = {"name": "mobile_use", "arguments": {"action": "type", "text": "中文 }}"}}
        for indent in [None, 2]:
            output = "Action: type\n<tool_call>" + json.dumps(action, indent=indent) + "</tool_call>"
            self.assertEqual(parse_action(output), action)
        with self.assertRaises(ValueError):
            parse_action('<tool_call>{"arguments": []}</tool_call>')

    def test_screenshot_rejects_failed_adb_output(self):
        with tempfile.TemporaryDirectory() as folder:
            target = str(Path(folder) / "screen.png")
            result = subprocess.CompletedProcess(["adb"], 0, stdout=b"device error", stderr=b"")
            with patch("utils.subprocess.run", return_value=result):
                self.assertFalse(AdbTools("adb").get_screenshot(target, retry_times=1))
            self.assertFalse(Path(target).exists())

    def test_unicode_text_input_restores_previous_keyboard_state(self):
        class Phone(AdbTools):
            def __init__(self):
                super().__init__("adb", "test-device")
                self.calls = []

            def _run(self, args):
                self.calls.append(args)
                result = ""
                if args[-1] == "default_input_method":
                    result = "original.keyboard/.IME\n"
                elif args[-1] == "enabled_input_methods":
                    result = "original.keyboard/.IME:other.keyboard/.IME\n"
                return subprocess.CompletedProcess(args, 0, stdout=result, stderr="")

        phone = Phone()
        text = '中文 "quoted" $(this-must-stay-literal)'
        with patch("utils.time.sleep"):
            phone.type(text)
        broadcast = next(args for args in phone.calls if "ADB_INPUT_B64" in args)
        self.assertEqual(base64.b64decode(broadcast[-1]).decode(), text)
        self.assertEqual(phone.calls[-2], ["shell", "ime", "set", "original.keyboard/.IME"])
        self.assertEqual(phone.calls[-1], ["shell", "ime", "disable", "com.android.adbkeyboard/.AdbIME"])


if __name__ == "__main__":
    unittest.main()
