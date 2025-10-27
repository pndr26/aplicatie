import requests
import sys
import json
from datetime import datetime, timedelta

class PTIAPITester:
    def __init__(self, base_url="https://inspectro.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.client_token = None
        self.inspector_token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        
        # Test data
        self.test_client_email = f"client_test_{datetime.now().strftime('%H%M%S')}@test.com"
        self.test_inspector_email = f"inspector_test_{datetime.now().strftime('%H%M%S')}@test.com"
        self.test_password = "TestPass123!"
        self.inspector_creation_password = "Chiru_041217_"
        self.test_car_plate = "AB123CDE"
        self.test_inspection_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None, description=""):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        default_headers = {'Content-Type': 'application/json'}
        if headers:
            default_headers.update(headers)

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        if description:
            print(f"   Description: {description}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=default_headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=default_headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=default_headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=default_headers, timeout=10)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json() if response.text else {}
                except:
                    response_data = {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_detail = response.json().get('detail', 'No detail provided')
                    print(f"   Error: {error_detail}")
                except:
                    print(f"   Response: {response.text}")
                response_data = {}

            self.test_results.append({
                "name": name,
                "method": method,
                "endpoint": endpoint,
                "expected_status": expected_status,
                "actual_status": response.status_code,
                "success": success,
                "description": description
            })

            return success, response_data

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            self.test_results.append({
                "name": name,
                "method": method,
                "endpoint": endpoint,
                "expected_status": expected_status,
                "actual_status": "ERROR",
                "success": False,
                "error": str(e),
                "description": description
            })
            return False, {}

    def test_client_registration(self):
        """Test client registration"""
        success, response = self.run_test(
            "Client Registration",
            "POST",
            "auth/register",
            200,
            data={
                "name": "Test Client",
                "phone": "0712345678",
                "email": self.test_client_email,
                "password": self.test_password,
                "role": "client"
            },
            description="Register a new client account"
        )
        if success and 'access_token' in response:
            self.client_token = response['access_token']
            return True
        return False

    def test_inspector_registration_correct_password(self):
        """Test inspector registration with correct password"""
        success, response = self.run_test(
            "Inspector Registration (Correct Password)",
            "POST",
            "auth/register",
            200,
            data={
                "name": "Test Inspector",
                "phone": "0712345679",
                "email": self.test_inspector_email,
                "password": self.test_password,
                "role": "inspector",
                "inspector_id": "INS001",
                "inspector_creation_password": self.inspector_creation_password
            },
            description="Register inspector with correct creation password"
        )
        if success and 'access_token' in response:
            self.inspector_token = response['access_token']
            return True
        return False

    def test_inspector_registration_wrong_password(self):
        """Test inspector registration with wrong password"""
        success, response = self.run_test(
            "Inspector Registration (Wrong Password)",
            "POST",
            "auth/register",
            403,
            data={
                "name": "Test Inspector Wrong",
                "phone": "0712345680",
                "email": f"inspector_wrong_{datetime.now().strftime('%H%M%S')}@test.com",
                "password": self.test_password,
                "role": "inspector",
                "inspector_id": "INS002",
                "inspector_creation_password": "wrong_password"
            },
            description="Should fail with wrong inspector creation password"
        )
        return success

    def test_client_login(self):
        """Test client login"""
        success, response = self.run_test(
            "Client Login",
            "POST",
            "auth/login",
            200,
            data={
                "email": self.test_client_email,
                "password": self.test_password
            },
            description="Login with client credentials"
        )
        if success and 'access_token' in response:
            self.client_token = response['access_token']
            return True
        return False

    def test_inspector_login(self):
        """Test inspector login"""
        success, response = self.run_test(
            "Inspector Login",
            "POST",
            "auth/login",
            200,
            data={
                "email": self.test_inspector_email,
                "password": self.test_password
            },
            description="Login with inspector credentials"
        )
        if success and 'access_token' in response:
            self.inspector_token = response['access_token']
            return True
        return False

    def test_get_me_client(self):
        """Test get current user info for client"""
        if not self.client_token:
            print("❌ Skipping - No client token available")
            return False
            
        success, response = self.run_test(
            "Get Me (Client)",
            "GET",
            "auth/me",
            200,
            headers={'Authorization': f'Bearer {self.client_token}'},
            description="Get current client user information"
        )
        return success

    def test_get_me_inspector(self):
        """Test get current user info for inspector"""
        if not self.inspector_token:
            print("❌ Skipping - No inspector token available")
            return False
            
        success, response = self.run_test(
            "Get Me (Inspector)",
            "GET",
            "auth/me",
            200,
            headers={'Authorization': f'Bearer {self.inspector_token}'},
            description="Get current inspector user information"
        )
        return success

    def test_add_car(self):
        """Test adding a car to client account"""
        if not self.client_token:
            print("❌ Skipping - No client token available")
            return False
            
        success, response = self.run_test(
            "Add Car",
            "POST",
            "users/add-car",
            200,
            data={"license_plate": self.test_car_plate},
            headers={'Authorization': f'Bearer {self.client_token}'},
            description="Add a car to client account"
        )
        return success

    def test_add_duplicate_car(self):
        """Test adding duplicate car (should fail)"""
        if not self.client_token:
            print("❌ Skipping - No client token available")
            return False
            
        success, response = self.run_test(
            "Add Duplicate Car",
            "POST",
            "users/add-car",
            400,
            data={"license_plate": self.test_car_plate},
            headers={'Authorization': f'Bearer {self.client_token}'},
            description="Should fail when adding duplicate car"
        )
        return success

    def test_create_inspection(self):
        """Test creating an inspection"""
        if not self.inspector_token:
            print("❌ Skipping - No inspector token available")
            return False
            
        # Calculate dates
        today = datetime.now()
        expiry = today + timedelta(days=365)
        
        success, response = self.run_test(
            "Create Inspection",
            "POST",
            "inspections",
            200,
            data={
                "car_license_plate": self.test_car_plate,
                "owner_phone": "0712345678",
                "inspection_date": today.strftime("%d-%m-%Y"),
                "expiry_date": expiry.strftime("%d-%m-%Y"),
                "inspector_name": "Test Inspector",
                "inspector_phone": "0712345679",
                "car_kilometers": 50000
            },
            headers={'Authorization': f'Bearer {self.inspector_token}'},
            description="Create a new inspection"
        )
        if success and 'id' in response:
            self.test_inspection_id = response['id']
            return True
        return False

    def test_get_inspections_client(self):
        """Test getting inspections as client"""
        if not self.client_token:
            print("❌ Skipping - No client token available")
            return False
            
        success, response = self.run_test(
            "Get Inspections (Client)",
            "GET",
            "inspections",
            200,
            headers={'Authorization': f'Bearer {self.client_token}'},
            description="Get inspections for client (should only see own cars)"
        )
        return success

    def test_get_inspections_inspector(self):
        """Test getting inspections as inspector"""
        if not self.inspector_token:
            print("❌ Skipping - No inspector token available")
            return False
            
        success, response = self.run_test(
            "Get Inspections (Inspector)",
            "GET",
            "inspections",
            200,
            headers={'Authorization': f'Bearer {self.inspector_token}'},
            description="Get all inspections for inspector"
        )
        return success

    def test_search_inspections(self):
        """Test searching inspections by license plate"""
        if not self.inspector_token:
            print("❌ Skipping - No inspector token available")
            return False
            
        success, response = self.run_test(
            "Search Inspections",
            "GET",
            f"inspections/search/{self.test_car_plate}",
            200,
            headers={'Authorization': f'Bearer {self.inspector_token}'},
            description="Search inspections by license plate"
        )
        return success

    def test_update_inspection(self):
        """Test updating an inspection"""
        if not self.inspector_token or not self.test_inspection_id:
            print("❌ Skipping - No inspector token or inspection ID available")
            return False
            
        success, response = self.run_test(
            "Update Inspection",
            "PUT",
            f"inspections/{self.test_inspection_id}",
            200,
            data={"car_kilometers": 55000},
            headers={'Authorization': f'Bearer {self.inspector_token}'},
            description="Update inspection kilometers"
        )
        return success

    def test_get_expiring_inspections(self):
        """Test getting expiring inspections"""
        if not self.client_token:
            print("❌ Skipping - No client token available")
            return False
            
        success, response = self.run_test(
            "Get Expiring Inspections",
            "GET",
            "inspections/expiring/soon",
            200,
            headers={'Authorization': f'Bearer {self.client_token}'},
            description="Get inspections expiring within 30 days"
        )
        return success

    def test_remove_car(self):
        """Test removing a car from client account"""
        if not self.client_token:
            print("❌ Skipping - No client token available")
            return False
            
        success, response = self.run_test(
            "Remove Car",
            "DELETE",
            f"users/remove-car/{self.test_car_plate}",
            200,
            headers={'Authorization': f'Bearer {self.client_token}'},
            description="Remove car from client account"
        )
        return success

    def test_delete_inspection(self):
        """Test deleting an inspection"""
        if not self.inspector_token or not self.test_inspection_id:
            print("❌ Skipping - No inspector token or inspection ID available")
            return False
            
        success, response = self.run_test(
            "Delete Inspection",
            "DELETE",
            f"inspections/{self.test_inspection_id}",
            200,
            headers={'Authorization': f'Bearer {self.inspector_token}'},
            description="Delete inspection"
        )
        return success

def main():
    print("🚀 Starting PTI API Testing...")
    print(f"Backend URL: https://inspectro.preview.emergentagent.com")
    print("=" * 60)
    
    tester = PTIAPITester()
    
    # Authentication Tests
    print("\n📋 AUTHENTICATION TESTS")
    print("-" * 30)
    tester.test_client_registration()
    tester.test_inspector_registration_correct_password()
    tester.test_inspector_registration_wrong_password()
    tester.test_client_login()
    tester.test_inspector_login()
    tester.test_get_me_client()
    tester.test_get_me_inspector()
    
    # Car Management Tests
    print("\n🚗 CAR MANAGEMENT TESTS")
    print("-" * 30)
    tester.test_add_car()
    tester.test_add_duplicate_car()
    
    # Inspection Tests
    print("\n🔍 INSPECTION TESTS")
    print("-" * 30)
    tester.test_create_inspection()
    tester.test_get_inspections_client()
    tester.test_get_inspections_inspector()
    tester.test_search_inspections()
    tester.test_update_inspection()
    tester.test_get_expiring_inspections()
    
    # Cleanup Tests
    print("\n🧹 CLEANUP TESTS")
    print("-" * 30)
    tester.test_delete_inspection()
    tester.test_remove_car()
    
    # Print results
    print("\n" + "=" * 60)
    print(f"📊 FINAL RESULTS")
    print(f"Tests passed: {tester.tests_passed}/{tester.tests_run}")
    success_rate = (tester.tests_passed / tester.tests_run * 100) if tester.tests_run > 0 else 0
    print(f"Success rate: {success_rate:.1f}%")
    
    # Print failed tests
    failed_tests = [test for test in tester.test_results if not test['success']]
    if failed_tests:
        print(f"\n❌ FAILED TESTS ({len(failed_tests)}):")
        for test in failed_tests:
            print(f"   - {test['name']}: Expected {test['expected_status']}, got {test['actual_status']}")
    
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())