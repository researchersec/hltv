import requests
import json
import os
import patoolib

url_cookie = "https://hltv.org/results"
url_demo = "https://www.hltv.org/download/demo/56508"
api_url = "http://localhost:8191/v1"
headers = {"Content-Type": "application/json"}

filename = url_demo.split("/")[-1]  # Extracting filename from URL

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

# Save the demo file
with open(filename, "wb") as f:
    f.write(demo_file.content)
print(f"Demo downloaded successfully to {filename}")

# Remove the directory if it already exists
if os.path.exists(extracted_directory):
    shutil.rmtree(extracted_directory)

# Create a directory for extraction
os.makedirs(extracted_directory)

# Extract the contents of the RAR file into the directory
patoolib.extract_archive(filename, outdir=extracted_directory)

print(f"File extracted successfully to {extracted_directory}")

# Compress the extracted directory into a 7z archive
compressed_filename = extracted_directory + ".7z"
patoolib.create_archive(compressed_filename, extracted_directory)

print(f"Directory compressed successfully to {compressed_filename}")

# Optionally, you can remove the original RAR file and extracted directory
os.remove(filename)
print(f"Original file {filename} removed.")
os.rmdir(extracted_directory)
print(f"Extracted directory {extracted_directory} removed.")
