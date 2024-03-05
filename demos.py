import os
import requests

FLARE_SOLVERR_URL = "http://localhost:8191/v1"

def download_demo(url, output_dir="."):

    filename = url.split("/")[-1]  # Extracting filename from URL
    filepath = os.path.join(output_dir, filename)

    # Create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Check if file already exists
    if os.path.exists(filepath):
        print(f"Demo file '{filename}' already exists. Skipping download.")
        return filepath

    try:
        print(f"Downloading demo from {url}...")
        post_body = {"cmd": "request.get", "url": url, "maxTimeout": 60000}
        response = requests.post(
            FLARE_SOLVERR_URL,
            headers={"Content-Type": "application/json"},
            json=post_body,
            allow_redirects=False,  # Disable automatic redirection
        )
        response.raise_for_status()  # Raise an exception for non-200 status codes

        # Print out the entire response content for inspection
        print("Response Headers:")
        print(response.headers)

        # Raise an error since we couldn't extract the final download URL
        raise ValueError("Failed to extract final download URL from headers")

    except requests.exceptions.RequestException as e:
        print(f"Failed to download demo: {e}")
        return None

if __name__ == "__main__":
    # Example usage
    demo_url = "https://hltv.org/download/demo/85546"
    download_demo(demo_url, output_dir="demos")
