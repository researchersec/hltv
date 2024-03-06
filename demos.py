import requests
import json
import os
 
url_cookie = "https://hltv.org/results"
url_demo = "https://www.hltv.org/download/demo/56508"
api_url = "http://localhost:8191/v1"
headers = {"Content-Type": "application/json"}

filename = url_demo.split("/")[-1]+".rar"  # Extracting filename from URL

data = {
    "cmd": "request.get",
    "url": url_cookie,
    "maxTimeout": 60000
}
 
response = requests.post(api_url, headers=headers, json=data)

# retrieve the entire JSON response from FlareSolverr
response_data = json.loads(response.content)
 
# Extract the cookies from the FlareSolverr response
cookies = response_data["solution"]["cookies"]

# Clean the cookies
cookies = {cookie["name"]: cookie["value"] for cookie in cookies}
 
# Extract the user agent from the FlareSolverr response
user_agent = response_data["solution"]["userAgent"]

demo_file = requests.get(url_demo, cookies=cookies, headers={"User-Agent": user_agent}) 
with open(filename, "wb") as f:
    f.write(demo_file.content)
print(f"Demo downloaded successfully to {filename}")
