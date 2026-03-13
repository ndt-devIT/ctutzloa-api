import requests

url = "https://oauth.zaloapp.com/v4/oa/access_token"

data = {
    "app_id": "YOUR_APP_ID",
    "app_secret": "YOUR_SECRET",
    "grant_type": "authorization_code",
    "code": "AUTH_CODE",
    "code_verifier": "CODE_VERIFIER"
}

res = requests.post(url, data=data)

print(res.json())