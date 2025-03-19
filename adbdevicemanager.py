from ppadb.client import Client as AdbClient
import os
from PIL import Image as PILImage

class AdbDeviceManager:
    def __init__(self, device_name: str) -> None:
        self.device = AdbClient().device(device_name)

    def get_packages(self) -> str:
        command = "pm list packages"
        packages = self.device.shell(command).strip().split("\n")
        result = [package[8:] for package in packages]
        output = "\n".join(result)
        return output

    def get_package_action_intents(self, package_name: str) -> list[str]:
        command = f"dumpsys package {package_name}"
        output = self.device.shell(command)

        resolver_table_start = output.find("Activity Resolver Table:")
        if resolver_table_start == -1:
            return []
        resolver_section = output[resolver_table_start:]

        non_data_start = resolver_section.find("\n  Non-Data Actions:")
        if non_data_start == -1:
            return []

        section_end = resolver_section[non_data_start:].find("\n\n")
        if section_end == -1:
            non_data_section = resolver_section[non_data_start:]
        else:
            non_data_section = resolver_section[
                non_data_start : non_data_start + section_end
            ]

        actions = []
        for line in non_data_section.split("\n"):
            line = line.strip()
            if line.startswith("android.") or line.startswith("com."):
                actions.append(line)

        return actions

    def execute_adb_command(self, command: str) -> str:
        """Executes an ADB command and returns the output."""
        if command.startswith("adb shell "):
            command = command[10:]
        elif command.startswith("adb "):
            command = command[4:]
        result = self.device.shell(command)
        return result

    def take_screenshot(self) -> None:
        self.device.shell("screencap -p /sdcard/screenshot.png")
        self.device.pull("/sdcard/screenshot.png", "screenshot.png")
        self.device.shell("rm /sdcard/screenshot.png")

        # compressing the ss to avoid "maximum call stack exceeded" error on claude desktop
        with PILImage.open("screenshot.png") as img:
            width, height = img.size
            new_width = int(width * 0.3)
            new_height = int(height * 0.3)
            resized_img = img.resize(
                (new_width, new_height), PILImage.Resampling.LANCZOS
            )

            resized_img.save(
                "compressed_screenshot.png", "PNG", quality=85, optimize=True
            )

    def get_uilayout(self) -> str:
        self.device.shell("uiautomator dump")
        self.device.pull("/sdcard/window_dump.xml", "window_dump.xml")
        self.device.shell("rm /sdcard/window_dump.xml")

        import xml.etree.ElementTree as ET
        import re

        def calculate_center(bounds_str):
            matches = re.findall(r"\[(\d+),(\d+)\]", bounds_str)
            if len(matches) == 2:
                x1, y1 = map(int, matches[0])
                x2, y2 = map(int, matches[1])
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                return center_x, center_y
            return None

        tree = ET.parse("window_dump.xml")
        root = tree.getroot()

        clickable_elements = []
        for element in root.findall(".//node[@clickable='true']"):
            text = element.get("text", "")
            content_desc = element.get("content-desc", "")
            bounds = element.get("bounds", "")

            # Only include elements that have either text or content description
            if text or content_desc:
                center = calculate_center(bounds)
                element_info = "Clickable element:"
                if text:
                    element_info += f"\n  Text: {text}"
                if content_desc:
                    element_info += f"\n  Description: {content_desc}"
                element_info += f"\n  Bounds: {bounds}"
                if center:
                    element_info += f"\n  Center: ({center[0]}, {center[1]})"
                clickable_elements.append(element_info)

        if not clickable_elements:
            return "No clickable elements found with text or description"
        else:
            result = "\n\n".join(clickable_elements)
            return result
