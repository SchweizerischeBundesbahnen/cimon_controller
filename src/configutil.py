# Copyright (C) Schweizerische Bundesbahnen SBB, 2016
# Python 3.4
__author__ = 'florianseidl'

import os
import pyaes
import base64
from argparse import ArgumentParser

# Shared utilities for configuration
# uses pyaes of encryption/decryption https://github.com/ricmoo/pyaes

def find_config_file_path(filename, optional=False):
    """search cimon.yaml in home dir cimon directory"""
    if os.path.isfile(filename):
        return filename
    home = os.path.expanduser("~")
    for dir in (os.path.join(home, "cimon"), home, os.getcwd()):
        file = os.path.join(dir, filename)
        if os.path.isfile(file):
            return file
    if not optional:
        raise Exception("No file %s found user home, current or application directory" % filename)

def decrypt(encrypted, key):
    if encrypted:
        if not key:
            raise Exception("No key given to decrypt password")
        aes = pyaes.AESModeOfOperationCTR(key)
        return (aes.decrypt(base64.b64decode(encrypted))).decode("utf-8")

def encrypt(plaintext, key):
    if plaintext:
        if not key:
            raise Exception("No key given to encrypt password")
        aes = pyaes.AESModeOfOperationCTR(key)
        return (base64.b64encode(aes.encrypt(plaintext))).decode("utf-8")

def generateKey():
    return os.urandom(32)

def generateKeyfile(keyfile):
    if os.path.exists(keyfile):
        raise FileExistsError(keyfile)
    with open (keyfile, "wb") as k:
        k.write(generateKey())

def printEncryptedOrDecrypted(keyfile, encrypted, plaintext):
    with open(keyfile, "rb") as k:
        if encrypted:
            print(decrypt(encrypted, k.read()))
        else:
            print(encrypt(plaintext, k.read()))

if  __name__ =='__main__':
    parser = ArgumentParser(description="Encrypt or decyrpt passwords")
    parser.add_argument("-k",  "--key", help="The password key file with its path")
    parser.add_argument("-e",  "--encrypt", help="Encrypt the given string")
    parser.add_argument("-d",  "--decrypt", help="Decrypt the given string")
    parser.add_argument("-g",  "--generate", action="store_true", help="Generate the key file")

    args = parser.parse_args()
    if not args.encrypt and args.decrypt and args.generate:
        print("One of the Options encrypt or decrypt are required")
        parser.print_help()
    else:
        keyfile = args.key or find_config_file_path("key.bin")
        if args.generate:
            generateKeyfile(keyfile)
        else:
            printEncryptedOrDecrypted(keyfile, args.decrypt, args.encrypt)

