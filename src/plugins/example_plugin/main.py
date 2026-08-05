class ExamplePlugin:
    def run(self, payload):
        return {
            "plugin": "example_plugin",
            "input": payload,
            "output": f"Processed: {payload}"
        }
