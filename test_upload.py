import requests

# First, login
login_url = 'http://127.0.0.1:5000/login'
upload_url = 'http://127.0.0.1:5000/upload'

session = requests.Session()

# Login with default admin
data = {'username': 'admin', 'password': 'admin'}
response = session.post(login_url, data=data)
print("Login response:", response.status_code)

# Now upload the file
files = {'file': open('sample_harvest.csv', 'rb')}
response = session.post(upload_url, files=files)
print("Upload response:", response.status_code)
print("Response text:", response.text)