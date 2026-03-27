
import os
import requests
import logging

class AuthService:
    def __init__(self):
        self.license_file = "license.key"
        self.verify_url = "https://mytube-ashy-seven.vercel.app/api/verify"
        self._membership = "standard" # Default
        self._user_email = ""
        self._verified = False
        self.logger = logging.getLogger(__name__)

    def verify_license(self):
        if not os.path.exists(self.license_file):
            self.logger.warning("License file not found")
            return False

        try:
            with open(self.license_file, "r") as f:
                user_id = f.read().strip()

            if not user_id:
                return False

            response = requests.post(
                self.verify_url,
                json={"userId": user_id},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    self._membership = data.get("membership", "standard")
                    self._user_email = data.get("email", "")
                    self._verified = True
                    self.logger.info(f"License verified. Membership: {self._membership}")
                    return True
            
            self.logger.error(f"License verification failed: {response.text}")
            return False

        except Exception as e:
            self.logger.error(f"Error during license verification: {e}")
            return False

    def is_independent(self):
        return self._membership == "independent"

    def get_membership(self):
        return self._membership

    def get_user_email(self):
        return self._user_email

auth_service = AuthService()
