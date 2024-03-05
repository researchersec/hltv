import requests

post_body = {
  "cmd": "request.get",
  "url":"https://www.petsathome.com/",
  "maxTimeout": 60000
}

response = requests.post('http://localhost:8191/v1', headers={'Content-Type': 'application/json'}, json=post_body)

print(response.json())
