from getpass import getpass
from argon2 import PasswordHasher

hasher = PasswordHasher()
print(hasher.hash(getpass("Password: ")))