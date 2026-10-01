import json
import os
from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse


PORT = 8000

DATA_FOLDER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data"
)


class MyHandler(SimpleHTTPRequestHandler):

    def do_GET(self):

        parsed_path = urlparse(self.path)

        # API endpoint
        if parsed_path.path == "/api/projects":

            try:
                # Find JSON files
                files = [
                    f for f in os.listdir(DATA_FOLDER)
                    if f.lower().endswith(".json")
                ]

                if not files:
                    self.send_error(
                        404,
                        "No JSON files found in data folder"
                    )
                    return

                # Find newest JSON file by modification time
                files.sort(
                    key=lambda f: os.path.getmtime(
                        os.path.join(DATA_FOLDER, f)
                    ),
                    reverse=True
                )

                latest_file = files[0]

                latest_path = os.path.join(
                    DATA_FOLDER,
                    latest_file
                )

                print(
                    f"Loading latest project file: "
                    f"{latest_file}"
                )

                # Read JSON
                with open(
                    latest_path,
                    "r",
                    encoding="utf-8"
                ) as f:
                    data = json.load(f)

                # Convert to JSON
                response = json.dumps(data).encode("utf-8")

                # Send response
                self.send_response(200)

                self.send_header(
                    "Content-Type",
                    "application/json; charset=utf-8"
                )

                self.send_header(
                    "Content-Length",
                    str(len(response))
                )

                self.send_header(
                    "Access-Control-Allow-Origin",
                    "*"
                )

                self.end_headers()

                self.wfile.write(response)

                return

            except Exception as e:

                print("ERROR:", e)

                self.send_error(
                    500,
                    str(e)
                )

                return

        # Normal website files
        return super().do_GET()


server = HTTPServer(
    ("0.0.0.0", PORT),
    MyHandler
)

print()
print("======================================")
print("PAIMANA server running")
print(f"http://localhost:{8000}")
print("======================================")
print()

server.serve_forever()