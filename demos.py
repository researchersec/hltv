import requests

# URL of the file to download
url = "https://www.hltv.org/download/demo/56507"
FLARE_SOLVERR_URL = "http://localhost:8191/v1"

post_body = {"cmd": "request.get", "url": url, "maxTimeout": 60000}

# Proxy configuration
proxies = {
    "http": FLARE_SOLVERR_URL,
    "https": FLARE_SOLVERR_URL
}

# Send the POST request with proxy configuration
response = requests.post(
    FLARE_SOLVERR_URL,
    headers={"Content-Type": "application/json"},
    json=post_body,
    proxies=proxies
)

# Check if the request was successful
if response.status_code == 200:
    # Assuming the response contains the file content, save it to a file
    filename = "downloaded_file.txt"  # You can specify any filename here
    with open(filename, "wb") as file:
        file.write(response.content)
    print("File downloaded successfully:", filename)
else:
    print("Failed to download the file. Status code:", response.status_code)
