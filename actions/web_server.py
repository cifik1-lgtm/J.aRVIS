from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

class HelloHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html><head><title>Hello</title></head>")
        self.wfile.write(b"<body><p>Hello World</p></body></html>")
        print("Served 'Hello World'")

def run_server(port=8000):
    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, HelloHandler)
    print(f"Starting web server on port {port}...")
    httpd.serve_forever()

if __name__ == "__main__":
    # Running in a thread so shell_runner can complete, but the process stays active
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    import time
    while True:
        time.sleep(10)
