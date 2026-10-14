from getpass import getpass
from argon2 import PasswordHasher

hasher = PasswordHasher()
password = getpass("Password: ")
password_confirmation = getpass("Retype password: ")

if password != password_confirmation:
	raise SystemExit("Passwords do not match.")

print(hasher.hash(password))