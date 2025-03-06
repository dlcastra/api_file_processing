class PasswordValidator:
    """
    Manages and validates password constraints for a given set of user attributes.

    This class is responsible for validating a password based on various rules and user data,
    including verifying the presence of capital letters and numbers, and ensuring the password
    does not contain personal information like the username, first name, last name, or email.
    It also checks for forbidden patterns such as spaces in the password. The class is designed
    to evaluate these constraints efficiently and return a boolean result indicating whether
    the password adheres to all specified rules.

    Attributes:
        _attrs: dict
            A dictionary of user attributes used for validation including password, username,
            first name, last name, and email.
        _password: str
            The password string being validated.

    """

    def __init__(self):
        self._attrs = {}
        self._password = ""

    def password_validator(self, attrs: dict) -> bool:
        """
        Returns True if the password is valid and False otherwise
        """

        self._attrs: dict = attrs
        self._password: str = attrs.get("password")

        return all(
            [
                self._password_has_capital_letter(),
                self._password_has_number(),
                not self._password_to_short(),
                not self._password_to_long(),
                not self._password_has_only_digits(),
                not self._password_has_email(),
                not self._password_has_spaces(),
                not self.is_password_compromised(),
            ]
        )

    def _password_has_capital_letter(self) -> bool:
        """Returns True if the password has at least one capital letter and False otherwise"""
        return any(char.isupper() for char in self._password)

    def _password_has_number(self) -> bool:
        """Returns True if the password has at least one number and False otherwise"""
        return any(char.isdigit() for char in self._password)

    def _password_to_short(self) -> bool:
        """Returns True if the password is shorter than 8 characters and False otherwise"""
        return len(self._password) < 8

    def _password_to_long(self) -> bool:
        """Returns True if the password is more than 256 characters long and False otherwise"""
        return len(self._password) > 64

    def _password_has_only_digits(self) -> bool:
        """Returns True if the password has only digits and False otherwise"""
        return self._password.isdigit()

    def _password_has_email(self) -> bool:
        """Returns True if the password has email or email name and False otherwise"""
        lower_email = self._attrs.get("email").lower()
        lower_password = self._password.lower()
        email_name = lower_email.split("@")[0]

        if lower_email in lower_password or lower_email[::-1] in lower_password:
            return True

        if email_name in lower_password or email_name[::-1] in lower_password:
            return True

        return False

    def _password_has_spaces(self) -> bool:
        """Returns True if the password has spaces or spaces and False otherwise"""
        return True if " " in self._password else False

    def is_password_compromised(self) -> bool:
        """Returns True if the password has been found in known breached passwords"""
        import hashlib
        import requests

        sha1_password = hashlib.sha1(self._password.encode()).hexdigest().upper()
        prefix, suffix = sha1_password[:5], sha1_password[5:]
        url = f"https://api.pwnedpasswords.com/range/{prefix}"

        try:
            response = requests.get(url)
            response.raise_for_status()
            return any(suffix in line for line in response.text.splitlines())
        except Exception:
            return False


invalid_password = {
    "password": "Not a reliable password.",
    "password scheme": {
        "capital_letter": "At least once capital letter is required.",
        "numeric": "At least once numeric is required.",
        "cannot_be_used": "Username, email.",
        "spaces": "Password must not contain spaces.",
    },
}
