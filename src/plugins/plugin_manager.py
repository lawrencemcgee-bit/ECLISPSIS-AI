"""
PluginManager: discovers, loads, validates, and executes user-installed plugins.
Milestone 7 Step 13: plugin system foundation.
"""

import os
import json
import importlib.util

class PluginManager:
    def __init__(self):
        self.plugin_dir = os.path.join(os.getcwd(), "plugins")
        self.plugins = {}
        self._ensure_dirs()
        self.discover_plugins()

    def _ensure_dirs(self):
        if not os.path.exists(self.plugin_dir):
            os.makedirs(self.plugin_dir)

    def discover_plugins(self):
        for folder in os.listdir(self.plugin_dir):
            path = os.path.join(self.plugin_dir, folder)
            manifest_path = os.path.join(path, "plugin.json")
            main_path = os.path.join(path, "main.py")

            if not os.path.isdir(path):
                continue
            if not os.path.exists(manifest_path):
                continue
            if not os.path.exists(main_path):
                continue

            try:
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)

                spec = importlib.util.spec_from_file_location(
                    manifest["id"], main_path
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                plugin_class = getattr(module, manifest["entry"], None)
                if plugin_class is None:
                    continue

                instance = plugin_class()
                self.plugins[manifest["id"]] = {
                    "manifest": manifest,
                    "instance": instance,
                    "enabled": manifest.get("enabled", True)
                }

            except Exception as exc:
                print(f"Plugin load failed: {folder}: {exc}")

    def execute(self, plugin_id, payload):
        plugin = self.plugins.get(plugin_id)
        if not plugin:
            return {"error": "Plugin not found"}

        if not plugin["enabled"]:
            return {"error": "Plugin disabled"}

        try:
            return plugin["instance"].run(payload)
        except Exception as exc:
            return {"error": str(exc)}

    def list_plugins(self):
        return [
            {
                "id": p["manifest"]["id"],
                "name": p["manifest"]["name"],
                "enabled": p["enabled"]
            }
            for p in self.plugins.values()
        ]

    def set_enabled(self, plugin_id, value):
        if plugin_id in self.plugins:
            self.plugins[plugin_id]["enabled"] = value
