"""
Food Donation Management System - Functional Backend Prototype
==============================================================

Core workflow:
1. Register donors and volunteers.
2. Donors create food donations.
3. Volunteers view available donations and claim one.
4. Donation status progresses: Available -> Claimed -> Picked Up -> Delivered.
5. User and donation records persist in a JSON file.

Run:
    python food_donation_management.py

Storage:
    food_donation_data.json is created beside this script.

This is a backend-focused prototype. It uses only Python's standard library.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


# ------------------------------ EXCEPTIONS ------------------------------

class DonationSystemError(Exception):
    """Base exception for expected application errors."""


class ValidationError(DonationSystemError):
    """Raised when supplied information is invalid."""


class NotFoundError(DonationSystemError):
    """Raised when a user or donation does not exist."""


class InvalidStatusError(DonationSystemError):
    """Raised when a donation cannot make the requested status change."""


class PersistenceError(DonationSystemError):
    """Raised when stored data cannot be read or written."""


# ------------------------------ USER CLASSES ----------------------------

class User:
    """Base class for all system users."""

    VALID_ROLES = {"Donor", "Volunteer", "Requester"}

    def __init__(self, user_id: str, name: str, phone: str, location: str, role: str):
        self.user_id = self._text(user_id, "User ID").upper()
        self.name = self._text(name, "Name")
        self.phone = self._text(phone, "Contact number")
        self.location = self._text(location, "Location")
        if role not in self.VALID_ROLES:
            raise ValidationError("Invalid user role.")
        self.role = role

    @staticmethod
    def _text(value, field: str) -> str:
        value = str(value).strip()
        if not value:
            raise ValidationError(f"{field} cannot be empty.")
        return value

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "phone": self.phone,
            "location": self.location,
            "role": self.role,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        role = data.get("role")
        user_classes = {
            "Donor": Donor,
            "Volunteer": Volunteer,
            "Requester": Requester,
        }
        if role not in user_classes:
            raise ValidationError(f"Unknown user role: {role}")
        return user_classes[role](
            data["user_id"], data["name"], data["phone"], data["location"]
        )


class Donor(User):
    def __init__(self, user_id: str, name: str, phone: str, location: str):
        super().__init__(user_id, name, phone, location, "Donor")


class Volunteer(User):
    def __init__(self, user_id: str, name: str, phone: str, location: str):
        super().__init__(user_id, name, phone, location, "Volunteer")


class Requester(User):
    """Reserved for future recipient/requester functionality."""

    def __init__(self, user_id: str, name: str, phone: str, location: str):
        super().__init__(user_id, name, phone, location, "Requester")


# ------------------------------ DONATION MODEL --------------------------

class Donation:
    """Represents a food donation and its workflow state."""

    STATUSES = ("Available", "Claimed", "Picked Up", "Delivered")

    def __init__(
        self,
        donation_id: str,
        food_name: str,
        quantity: str,
        location: str,
        available_until: str,
        donor_id: str,
        contact: str,
        status: str = "Available",
        volunteer_id: Optional[str] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ):
        self.donation_id = self._required(donation_id, "Donation ID").upper()
        self.food_name = self._required(food_name, "Food name")
        self.quantity = self._required(quantity, "Quantity")
        self.location = self._required(location, "Location")
        self.available_until = self._required(available_until, "Available-until time")
        self.donor_id = self._required(donor_id, "Donor ID").upper()
        self.contact = self._required(contact, "Contact information")

        if status not in self.STATUSES:
            raise ValidationError(f"Invalid donation status: {status}")
        self.status = status
        self.volunteer_id = volunteer_id.upper() if volunteer_id else None
        self.created_at = created_at or self._now()
        self.updated_at = updated_at or self.created_at

        if status != "Available" and not self.volunteer_id:
            raise ValidationError("A claimed or completed donation must have a volunteer.")

    @staticmethod
    def _required(value, field: str) -> str:
        value = str(value).strip()
        if not value:
            raise ValidationError(f"{field} cannot be empty.")
        return value

    @staticmethod
    def _now() -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def change_status(self, new_status: str, volunteer_id: Optional[str] = None) -> None:
        """Enforce one-step forward status transitions."""
        if new_status not in self.STATUSES:
            raise InvalidStatusError(f"Unknown status: {new_status}")

        current_index = self.STATUSES.index(self.status)
        if current_index >= len(self.STATUSES) - 1:
            raise InvalidStatusError("This donation has already been delivered.")

        expected_status = self.STATUSES[current_index + 1]
        if new_status != expected_status:
            raise InvalidStatusError(
                f"Cannot change status from {self.status} to {new_status}. "
                f"Next status must be {expected_status}."
            )

        if new_status == "Claimed":
            if not volunteer_id:
                raise ValidationError("A volunteer ID is required to claim a donation.")
            self.volunteer_id = volunteer_id.upper()
        elif volunteer_id and volunteer_id.upper() != self.volunteer_id:
            raise InvalidStatusError("Only the volunteer who claimed this donation can update it.")

        self.status = new_status
        self.updated_at = self._now()

    def to_dict(self) -> dict:
        return {
            "donation_id": self.donation_id,
            "food_name": self.food_name,
            "quantity": self.quantity,
            "location": self.location,
            "available_until": self.available_until,
            "donor_id": self.donor_id,
            "contact": self.contact,
            "status": self.status,
            "volunteer_id": self.volunteer_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Donation":
        return cls(**data)


# ------------------------------ JSON STORAGE ----------------------------

class FileManager:
    """Loads and saves users and donations as JSON."""

    def __init__(self, filename: str = "food_donation_data.json"):
        self.path = Path(filename)

    def save(self, users: Dict[str, User], donations: Dict[str, Donation]) -> None:
        payload = {
            "users": [user.to_dict() for user in users.values()],
            "donations": [donation.to_dict() for donation in donations.values()],
        }
        try:
            self.path.write_text(json.dumps(payload, indent=4), encoding="utf-8")
        except OSError as error:
            raise PersistenceError(f"Unable to save data: {error}") from error

    def load(self) -> tuple:
        if not self.path.exists():
            return {}, {}

        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValidationError("Data file must contain a JSON object.")

            users_list = payload.get("users", [])
            donations_list = payload.get("donations", [])
            if not isinstance(users_list, list) or not isinstance(donations_list, list):
                raise ValidationError("Users and donations must be JSON lists.")

            users: Dict[str, User] = {}
            donations: Dict[str, Donation] = {}

            for item in users_list:
                user = User.from_dict(item)
                if user.user_id in users:
                    raise ValidationError(f"Duplicate user ID in file: {user.user_id}")
                users[user.user_id] = user

            for item in donations_list:
                donation = Donation.from_dict(item)
                if donation.donation_id in donations:
                    raise ValidationError(
                        f"Duplicate donation ID in file: {donation.donation_id}"
                    )
                donations[donation.donation_id] = donation

            return users, donations

        except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
            raise PersistenceError(f"Unable to load data: {error}") from error


# ------------------------------ BUSINESS LOGIC --------------------------

class DonationManager:
    """Coordinates users, donations, validation, and workflow operations."""

    def __init__(self, file_manager: FileManager):
        self.file_manager = file_manager
        self.users: Dict[str, User] = {}
        self.donations: Dict[str, Donation] = {}
        self._next_donation_number = 1

    def register_user(self, user: User) -> None:
        if user.user_id in self.users:
            raise ValidationError(f"User ID {user.user_id} already exists.")
        self.users[user.user_id] = user
        self.save()

    def get_user(self, user_id: str, required_role: Optional[str] = None) -> User:
        key = str(user_id).strip().upper()
        user = self.users.get(key)
        if user is None:
            raise NotFoundError(f"User {key} was not found.")
        if required_role and user.role != required_role:
            raise ValidationError(f"User {key} must have the role {required_role}.")
        return user

    def create_donation(
        self,
        donor_id: str,
        food_name: str,
        quantity: str,
        location: str,
        available_until: str,
        contact: str,
    ) -> Donation:
        donor = self.get_user(donor_id, "Donor")
        donation_id = self._generate_donation_id()
        donation = Donation(
            donation_id=donation_id,
            food_name=food_name,
            quantity=quantity,
            location=location,
            available_until=available_until,
            donor_id=donor.user_id,
            contact=contact,
        )
        self.donations[donation_id] = donation
        self.save()
        return donation

    def _generate_donation_id(self) -> str:
        while True:
            candidate = f"DON{self._next_donation_number:03d}"
            self._next_donation_number += 1
            if candidate not in self.donations:
                return candidate

    def available_donations(self) -> list:
        return sorted(
            (d for d in self.donations.values() if d.status == "Available"),
            key=lambda donation: donation.created_at,
        )

    def get_donation(self, donation_id: str) -> Donation:
        key = str(donation_id).strip().upper()
        donation = self.donations.get(key)
        if donation is None:
            raise NotFoundError(f"Donation {key} was not found.")
        return donation

    def claim_donation(self, donation_id: str, volunteer_id: str) -> Donation:
        volunteer = self.get_user(volunteer_id, "Volunteer")
        donation = self.get_donation(donation_id)
        donation.change_status("Claimed", volunteer.user_id)
        self.save()
        return donation

    def update_donation_status(self, donation_id: str, volunteer_id: str, new_status: str) -> Donation:
        volunteer = self.get_user(volunteer_id, "Volunteer")
        donation = self.get_donation(donation_id)

        if donation.volunteer_id != volunteer.user_id:
            raise ValidationError("Only the volunteer assigned to this donation can update it.")

        donation.change_status(new_status, volunteer.user_id)
        self.save()
        return donation

    def donations_for_user(self, user_id: str) -> list:
        user = self.get_user(user_id)
        if user.role == "Donor":
            return [d for d in self.donations.values() if d.donor_id == user.user_id]
        if user.role == "Volunteer":
            return [d for d in self.donations.values() if d.volunteer_id == user.user_id]
        return []

    def save(self) -> None:
        self.file_manager.save(self.users, self.donations)

    def load(self) -> None:
        self.users, self.donations = self.file_manager.load()
        numbers = []
        for donation_id in self.donations:
            if donation_id.startswith("DON") and donation_id[3:].isdigit():
                numbers.append(int(donation_id[3:]))
        self._next_donation_number = max(numbers, default=0) + 1


# ------------------------------ CONSOLE PROTOTYPE -----------------------

class FoodDonationApp:
    """Simple console interface for exercising the backend workflow."""

    def __init__(self):
        self.manager = DonationManager(FileManager())

    @staticmethod
    def _input(prompt: str) -> str:
        value = input(prompt).strip()
        if not value:
            raise ValidationError("Input cannot be empty.")
        return value

    def register_user(self) -> None:
        print("\nRegister User")
        print("1. Donor\n2. Volunteer\n3. Requester")
        role_choice = self._input("Choose role: ")
        roles = {"1": Donor, "2": Volunteer, "3": Requester}
        user_class = roles.get(role_choice)
        if user_class is None:
            raise ValidationError("Choose 1, 2, or 3.")

        user = user_class(
            self._input("User ID (e.g. DON101 or VOL102): "),
            self._input("Name: "),
            self._input("Contact number: "),
            self._input("Location: "),
        )
        self.manager.register_user(user)
        print(f"{user.role} registered successfully. User ID: {user.user_id}")

    def create_donation(self) -> None:
        print("\nCreate Donation")
        donation = self.manager.create_donation(
            donor_id=self._input("Donor ID: "),
            food_name=self._input("Food name: "),
            quantity=self._input("Quantity (e.g. 20 Meals): "),
            location=self._input("Pickup location: "),
            available_until=self._input("Available until (e.g. 8:00 PM): "),
            contact=self._input("Contact information: "),
        )
        print("\nDonation Created Successfully.")
        print(f"Donation ID: {donation.donation_id}")
        print(f"Status: {donation.status}")

    @staticmethod
    def print_donation(donation: Donation) -> None:
        print(
            f"\n{donation.donation_id}\n"
            f"Food           : {donation.food_name}\n"
            f"Quantity       : {donation.quantity}\n"
            f"Location       : {donation.location}\n"
            f"Available Until: {donation.available_until}\n"
            f"Status         : {donation.status}\n"
            f"Donor ID       : {donation.donor_id}\n"
            f"Volunteer      : {donation.volunteer_id or 'Not assigned'}"
        )

    def view_available(self) -> None:
        donations = self.manager.available_donations()
        print("\nAvailable Donations\n-------------------")
        if not donations:
            print("No available donations at the moment.")
            return
        for donation in donations:
            self.print_donation(donation)

    def claim_donation(self) -> None:
        donation = self.manager.claim_donation(
            self._input("Donation ID: "),
            self._input("Volunteer ID: "),
        )
        print(f"\nDonation {donation.donation_id}")
        print(f"Status: {donation.status}")
        print(f"Volunteer: {donation.volunteer_id}")

    def advance_status(self) -> None:
        print("Next status options: Picked Up, Delivered")
        donation = self.manager.update_donation_status(
            self._input("Donation ID: "),
            self._input("Volunteer ID: "),
            self._input("New status: "),
        )
        print(f"Donation {donation.donation_id} status updated to {donation.status}.")

    def view_user_donations(self) -> None:
        user_id = self._input("User ID: ")
        donations = self.manager.donations_for_user(user_id)
        if not donations:
            print("No donations found for this user.")
            return
        for donation in donations:
            self.print_donation(donation)

    def run(self) -> None:
        try:
            self.manager.load()
            print(
                f"Loaded {len(self.manager.users)} user(s) and "
                f"{len(self.manager.donations)} donation(s)."
            )
        except DonationSystemError as error:
            print(f"Warning: {error}")
            print("The application will continue with empty in-memory records.")

        actions = {
            "1": self.register_user,
            "2": self.create_donation,
            "3": self.view_available,
            "4": self.claim_donation,
            "5": self.advance_status,
            "6": self.view_user_donations,
            "7": lambda: (self.manager.save(), print("Data saved successfully.")),
        }

        while True:
            print(
                "\n====== FOOD DONATION MANAGEMENT SYSTEM ======\n"
                "1. Register user (Donor / Volunteer / Requester)\n"
                "2. Create food donation (Donor)\n"
                "3. View available donations\n"
                "4. Claim donation (Volunteer)\n"
                "5. Update status (Picked Up / Delivered)\n"
                "6. View donations by user\n"
                "7. Save records\n"
                "8. Exit"
            )
            choice = input("Enter choice (1-8): ").strip()

            if choice == "8":
                try:
                    self.manager.save()
                    print("Records saved. Goodbye!")
                except DonationSystemError as error:
                    print(f"Could not save records: {error}")
                break

            action = actions.get(choice)
            if action is None:
                print("Invalid menu choice. Enter a number from 1 to 8.")
                continue

            try:
                action()
            except DonationSystemError as error:
                print(f"Operation failed: {error}")
            except (EOFError, KeyboardInterrupt):
                print("\nOperation cancelled.")
                break
            except Exception as error:
                # Final safety net for unexpected errors; details remain visible for debugging.
                print(f"Unexpected error: {type(error).__name__}: {error}")


if __name__ == "__main__":
    try:
        FoodDonationApp().run()
    except KeyboardInterrupt:
        print("\nApplication stopped.")
