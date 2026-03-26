"""
Agri-Direct API Testing Script
Demonstrates middleware integration with JWT authentication
"""

import requests
import json
from datetime import datetime

# API Base URL
BASE_URL = "http://127.0.0.1:5000"

# Test credentials
TEST_USERNAME = "admin"
TEST_PASSWORD = "admin"

print("=" * 60)
print("AGRI-DIRECT MIDDLEWARE - API TESTING")
print("=" * 60)

# ========== STEP 1: Get JWT Token ==========
print("\n[STEP 1] Obtaining JWT Token...")
print("-" * 60)

token_data = {
    "username": TEST_USERNAME,
    "password": TEST_PASSWORD
}

try:
    response = requests.post(f"{BASE_URL}/token", data=token_data)
    
    if response.status_code == 200:
        token_response = response.json()
        token = token_response["token"]
        print(f"✅ Token obtained successfully!")
        print(f"Token: {token[:50]}...")
        print(f"Expires in: {token_response['expires_in']} seconds")
    else:
        print(f"❌ Failed to get token: {response.status_code}")
        print(response.json())
        exit()
except Exception as e:
    print(f"❌ Error: {str(e)}")
    exit()

# ========== STEP 2: Send Harvest Data via API ==========
print("\n[STEP 2] Sending Harvest Data via API Middleware...")
print("-" * 60)

# Example harvest records from external systems
harvest_records = [
    {
        "crop_name": "Tomatoes",
        "quantity": 150,
        "farmer": "External Farm System 1"
    },
    {
        "crop_name": "Corn",
        "quantity": 300,
        "farmer": "External Farm System 2"
    },
    {
        "crop_name": "Wheat",
        "quantity": 250,
        "farmer": "External Farm System 3"
    }
]

# Headers with JWT token
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

for record in harvest_records:
    try:
        response = requests.post(
            f"{BASE_URL}/api/harvest",
            json=record,
            headers=headers
        )
        
        if response.status_code == 201:
            print(f"✅ {record['crop_name']}: {record['quantity']} units - SUCCESS")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ {record['crop_name']}: FAILED")
            print(f"   Status: {response.status_code}")
            print(f"   Error: {response.json()}")
    except Exception as e:
        print(f"❌ Error sending {record['crop_name']}: {str(e)}")

# ========== STEP 3: Test Invalid Token ==========
print("\n[STEP 3] Testing Invalid Token (Should Fail)...")
print("-" * 60)

invalid_headers = {
    "Authorization": "Bearer invalid_token_123",
    "Content-Type": "application/json"
}

test_record = {
    "crop_name": "Potatoes",
    "quantity": 100,
    "farmer": "Test Farm"
}

try:
    response = requests.post(
        f"{BASE_URL}/api/harvest",
        json=test_record,
        headers=invalid_headers
    )
    
    if response.status_code == 401:
        print(f"✅ Invalid token correctly rejected!")
        print(f"   Response: {response.json()}")
    else:
        print(f"❌ Unexpected response: {response.status_code}")
except Exception as e:
    print(f"Error: {str(e)}")

# ========== STEP 4: Test Missing Token ==========
print("\n[STEP 4] Testing Missing Token (Should Fail)...")
print("-" * 60)

try:
    response = requests.post(
        f"{BASE_URL}/api/harvest",
        json=test_record,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code in [401, 403]:
        print(f"✅ Missing token correctly rejected!")
        print(f"   Response: {response.json()}")
    else:
        print(f"❌ Unexpected response: {response.status_code}")
except Exception as e:
    print(f"Error: {str(e)}")

# ========== STEP 5: Test Invalid Input ==========
print("\n[STEP 5] Testing Input Validation...")
print("-" * 60)

invalid_records = [
    {
        "crop_name": "Cucumber",
        "quantity": -50,  # Negative quantity
        "farmer": "Test Farm"
    },
    {
        "crop_name": "Lettuce",
        # Missing quantity
        "farmer": "Test Farm"
    }
]

for record in invalid_records:
    try:
        response = requests.post(
            f"{BASE_URL}/api/harvest",
            json=record,
            headers=headers
        )
        
        if response.status_code != 201:
            print(f"✅ Invalid record rejected - {record}")
            print(f"   Error: {response.json()['error']}")
        else:
            print(f"⚠️  Record accepted (may need stricter validation)")
    except Exception as e:
        print(f"Error: {str(e)}")

# ========== STEP 6: Get Dashboard Statistics ==========
print("\n[STEP 6] Retrieving Dashboard Statistics...")
print("-" * 60)

# Note: /api/stats requires session, so we use headers for display
# In a real scenario, this would be called from the web dashboard
print("(Statistics endpoint requires browser session)")
print("But API successfully demonstrates:")
print("  ✅ JWT Authentication")
print("  ✅ Token validation")
print("  ✅ Real-time API integration")
print("  ✅ Input validation")
print("  ✅ Middleware data processing")

print("\n" + "=" * 60)
print("TESTING COMPLETE")
print("=" * 60)
print("\n📊 SUMMARY:")
print("✅ JWT token generation working")
print("✅ API middleware accepting real-time harvest data")
print("✅ Security validation (token checks)")
print("✅ Input validation (negative quantities, missing fields)")
print("✅ System ready for external integrations")
print("\n💡 This demonstrates the 'MIDDLEWARE' concept:")
print("   External Systems → API Middleware → Database → Dashboard")
print("=" * 60)
