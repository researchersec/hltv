import requests

# URL of the FlareSolverr API endpoint
url = "http://172.17.0.3:8191/v1"

# Headers for the POST request
headers = {"Content-Type": "application/json"}

# Data to be sent in the POST request
data = {
    "cmd": "request.get",       # Command to indicate that you want to perform a GET request
    "url": "http://www.google.com/",  # URL you want to request
    "maxTimeout": 60000         # Maximum timeout in milliseconds (optional)
}

# Send the POST request to the FlareSolverr API endpoint
response = requests.post(url, headers=headers, json=data)

# Print the response
print(response.text)
